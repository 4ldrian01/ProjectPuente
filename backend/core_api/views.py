"""
core_api/views.py — Translation & Wiki-Voz API for Project Puente.

Primary engine: NLLB-200-distilled-600M (8-bit quantized, Singleton loaded
via apps.py) with LoRA adapters for formal/street Chavacano.
Fallback engine: Google Gemini Cloud API (only when NLLB model is unavailable).

Features:
  - English Pivot routing for non-English language pairs
  - Wiki-Voz cultural term interception
  - ISO 25010 TranslationLog for every request
  - Formal/Street sociolinguistic mode switching
"""

import logging
import time

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .apps import CoreApiConfig
from .models import CulturalTerm, TranslationLog
from .serializers import (
    CulturalTermSerializer,
    TextToSpeechRequestSerializer,
    TranslateRequestSerializer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NLLB-200 FLORES language code mapping (strict 5-language scope)
# ---------------------------------------------------------------------------
FLORES_MAP = {
    'en':   'eng_Latn',
    'tl':   'tgl_Latn',
    'cbk':  'cbk_Latn',
    'ceb':  'ceb_Latn',
    'hil':  'hil_Latn',    # Hiligaynon (native NLLB-200 support)
    'auto': 'eng_Latn',    # Auto-detect fallback to English
}

PIVOT_LANG = 'eng_Latn'

# Supported languages — STRICTLY 5 languages only
SUPPORTED_LANGUAGES = {
    'auto': 'Auto-Detect',
    'en':   'English',
    'tl':   'Tagalog',
    'cbk':  'Chavacano (Zamboanga)',
    'hil':  'Hiligaynon',
    'ceb':  'Cebuano/Bisaya',
}

TARGET_LANGUAGES = {
    code: label for code, label in SUPPORTED_LANGUAGES.items() if code != 'auto'
}

# ---------------------------------------------------------------------------
# Gemini fallback (only when NLLB model is not loaded)
# ---------------------------------------------------------------------------
GEMINI_MODEL_CANDIDATES = (
    'gemini-2.0-flash',
    'gemini-1.5-flash-latest',
    'gemini-1.5-flash-8b',
    'gemini-1.5-flash',
)

SYSTEM_FORMAL = (
    "You are an expert multilingual translator specializing in Zamboanga languages "
    "and Philippine dialects. Translate the following text using the HIGH variety — "
    "formal, respectful, and grammatically precise. Preserve cultural nuance. "
    "Return ONLY the translated text, no explanations."
)

SYSTEM_STREET = (
    "You are an expert multilingual translator specializing in Zamboanga languages "
    "and Philippine dialects. Translate the following text using the LOW variety — "
    "casual street slang, colloquial, and natural everyday speech. "
    "Return ONLY the translated text, no explanations."
)

EDGE_TTS_DEFAULT_VOICES = {
    'en': 'en-US-EmmaMultilingualNeural',
    'tl': 'fil-PH-BlessicaNeural',
    'cbk': 'es-ES-ElviraNeural',
    'hil': 'fil-PH-BlessicaNeural',
    'ceb': 'fil-PH-AngeloNeural',
}


def is_edge_tts_available():
    """Return True when the optional edge-tts dependency is importable."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    return True


def _estimate_token_count(text):
    """Fast fallback token estimate for pass-through or non-NLLB paths."""
    return len((text or '').split())


def _get_edge_tts_voice(lang_code, voice_override=None):
    """Resolve the voice used for TTS, with env overrides per language."""
    if voice_override:
        return voice_override.strip()

    normalized_code = 'en' if lang_code == 'auto' else lang_code
    configured_voice = getattr(
        settings,
        f'EDGE_TTS_VOICE_{normalized_code.upper()}',
        '',
    ).strip()
    if configured_voice:
        return configured_voice

    return EDGE_TTS_DEFAULT_VOICES.get(normalized_code, EDGE_TTS_DEFAULT_VOICES['en'])


def _synthesize_speech_bytes(text, lang_code, voice_override=None):
    """Generate MP3 bytes with edge-tts for the requested language."""
    cleaned_text = (text or '').strip()
    if not cleaned_text:
        raise ValueError('Text-to-speech requires non-empty text.')

    try:
        import edge_tts
    except ImportError as exc:
        raise ValueError(
            'edge-tts is not installed. Run pip install -r backend/requirements.txt.'
        ) from exc

    selected_voice = _get_edge_tts_voice(lang_code, voice_override=voice_override)
    communicate = edge_tts.Communicate(
        text=cleaned_text,
        voice=selected_voice,
        rate=getattr(settings, 'EDGE_TTS_RATE', '+0%'),
        volume=getattr(settings, 'EDGE_TTS_VOLUME', '+0%'),
        pitch=getattr(settings, 'EDGE_TTS_PITCH', '+0Hz'),
    )

    audio_bytes = bytearray()
    for chunk in communicate.stream_sync():
        if chunk.get('type') == 'audio' and chunk.get('data'):
            audio_bytes.extend(chunk['data'])

    if not audio_bytes:
        raise RuntimeError('edge-tts returned no audio data.')

    return bytes(audio_bytes), selected_voice


def _get_gemini_client():
    """Configure and return Gemini client instance (fallback only)."""
    try:
        from google import genai
    except ImportError:
        raise ValueError(
            'google-genai is not installed and NLLB-200 model is unavailable. '
            'Install ML dependencies or google-genai.'
        )
    api_key = getattr(settings, 'GOOGLE_API_KEY', '')
    if not api_key or api_key == 'YOUR_GEMINI_API_KEY_HERE':
        raise ValueError(
            'GOOGLE_API_KEY is not configured and NLLB-200 model is unavailable. '
            'Set it in backend/.env or install the NLLB model.'
        )
    return genai.Client(api_key=api_key)


def _generate_translation_gemini(client, user_prompt, system_prompt):
    """Generate translation with fallback across Gemini model aliases."""
    from google import genai as _genai

    last_error = None
    for model_name in GEMINI_MODEL_CANDIDATES:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=_genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.3,
                ),
            )
            translated_text = (response.text or '').strip().strip('"').strip("'")
            if translated_text:
                return translated_text, model_name
        except Exception as exc:
            last_error = exc
            error_text = str(exc).lower()
            if 'not_found' in error_text or 'not found' in error_text:
                continue
            raise
    raise RuntimeError(
        f'No available Gemini model alias succeeded. Last error: {last_error}'
    )


# ---------------------------------------------------------------------------
# NLLB-200 Local Inference (Primary Engine)
# ---------------------------------------------------------------------------
def _infer_once(model, tokenizer, text, src_flores, tgt_flores):
    """Single NLLB-200 inference pass (no gradient computation)."""
    import torch

    tokenizer.src_lang = src_flores
    inputs = tokenizer(
        text, return_tensors='pt', truncation=True, max_length=128,
    )

    # Move inputs to same device as model (CPU or CUDA)
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        translated_ids = model.generate(
            **inputs,
            forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt_flores),
            max_new_tokens=128,
            num_beams=4,
        )
    return tokenizer.batch_decode(translated_ids, skip_special_tokens=True)[0]


def nllb_translate(text, src_code, tgt_code, mode='formal'):
    """
    Translate using Singleton NLLB-200 + LoRA (English-pivot if needed).

    Returns: (translated_text, latency_ms, tokens_in, tokens_out, pivot_used, model_name)
    """
    tokenizer = CoreApiConfig.nllb_tokenizer
    model = CoreApiConfig.nllb_model

    # Activate LoRA adapter if available (dynamic switching, no merge)
    adapter_name = CoreApiConfig.lora_adapters.get(mode)
    if adapter_name and hasattr(model, 'set_adapter'):
        model.set_adapter(adapter_name)

    src_flores = FLORES_MAP.get(src_code, 'eng_Latn')
    tgt_flores = FLORES_MAP.get(tgt_code, 'cbk_Latn')

    adapter_label = f'+lora-cbk-{mode}' if adapter_name else ''
    model_name = f'nllb-200-distilled-600M{adapter_label}'

    # Short-circuit: same source and target language
    if src_flores == tgt_flores:
        tokens = len(tokenizer.encode(text))
        return text, 0.0, tokens, tokens, False, model_name

    start = time.perf_counter()
    pivot_used = False

    # Tokenize input once for token count logging
    input_ids = tokenizer.encode(text)
    tokens_in = len(input_ids)

    if src_flores != PIVOT_LANG and tgt_flores != PIVOT_LANG:
        # Two-hop pivot via English
        pivot_used = True
        mid_text = _infer_once(model, tokenizer, text, src_flores, PIVOT_LANG)
        result = _infer_once(model, tokenizer, mid_text, PIVOT_LANG, tgt_flores)
    else:
        result = _infer_once(model, tokenizer, text, src_flores, tgt_flores)

    elapsed_ms = (time.perf_counter() - start) * 1000
    tokens_out = len(tokenizer.encode(result))

    return result, elapsed_ms, tokens_in, tokens_out, pivot_used, model_name


# ═══════════════════════════════════════════════════════════════
# API Root View
# ═══════════════════════════════════════════════════════════════
class APIRootView(APIView):
    """GET / — Root route with backend status and endpoint listing."""

    def get(self, request):
        return Response({
            'project': 'Project Puente Backend',
            'status': 'online',
            'engine': 'nllb-200' if CoreApiConfig.model_loaded else 'gemini-fallback',
            'endpoints': {
                'admin': '/admin/',
                'translate': '/api/translate/',
                'tts': '/api/tts/',
                'wiki_voz': '/api/wiki/?q=<term>',
                'health': '/api/health/',
            },
        })


# ═══════════════════════════════════════════════════════════════
# Translate View
# ═══════════════════════════════════════════════════════════════
class TranslateView(APIView):
    """
    POST /api/translate/
    Body: { "text": "...", "source_lang": "en", "target_lang": "cbk", "mode": "formal" }
    """

    def post(self, request):
        # 1. Validate -------------------------------------------------------
        serializer = TranslateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        text = serializer.validated_data['text']
        source_lang = serializer.validated_data['source_lang']
        target_lang = serializer.validated_data['target_lang']
        mode = serializer.validated_data.get('mode', 'formal')

        # 2. Wiki-Voz interception ------------------------------------------
        wiki_match = CulturalTerm.objects.filter(term__iexact=text.strip()).first()
        wiki_data = None
        if wiki_match:
            wiki_data = CulturalTermSerializer(wiki_match).data

        # 2b. Short-circuit: same source and target language -----------------
        if source_lang == target_lang or (
            source_lang != 'auto'
            and FLORES_MAP.get(source_lang) == FLORES_MAP.get(target_lang)
        ):
            passthrough_tokens = _estimate_token_count(text)
            log_entry = TranslationLog(
                source_lang=source_lang, target_lang=target_lang,
                mode=mode, input_text=text, input_chars=len(text),
                input_tokens=passthrough_tokens,
                output_text=text, latency_ms=0.0, status='success',
                output_tokens=passthrough_tokens,
                model_name='passthrough', pivot_used=False,
                wiki_voz_triggered=wiki_match is not None,
                wiki_voz_term=wiki_match.term if wiki_match else '',
            )
            log_entry.save()
            payload = {
                'translated_text': text, 'source_lang': source_lang,
                'target_lang': target_lang, 'mode': mode,
                'model': 'passthrough', 'latency_ms': 0.0,
                'tokens_in': passthrough_tokens,
                'tokens_out': passthrough_tokens,
                'pivot_used': False,
            }
            if wiki_data:
                payload['wiki_voz'] = wiki_data
            return Response(payload)

        # 3. Prepare logging entry ------------------------------------------
        start_time = time.perf_counter()
        log_entry = TranslationLog(
            source_lang=source_lang,
            target_lang=target_lang,
            mode=mode,
            input_text=text,
            input_chars=len(text),
        )

        # 4. Translate — NLLB-200 primary, Gemini fallback ------------------
        try:
            if CoreApiConfig.model_loaded:
                # ── PRIMARY: Local NLLB-200 + LoRA ──
                translated_text, latency_ms, tokens_in, tokens_out, pivot_used, model_used = (
                    nllb_translate(text, source_lang, target_lang, mode)
                )
                log_entry.output_text = translated_text
                log_entry.input_tokens = tokens_in
                log_entry.output_tokens = tokens_out
                log_entry.latency_ms = latency_ms
                log_entry.pivot_used = pivot_used
                log_entry.model_name = model_used
                log_entry.status = 'success'

            else:
                # ── FALLBACK: Gemini Cloud API ──
                system_prompt = SYSTEM_FORMAL if mode == 'formal' else SYSTEM_STREET
                is_auto = source_lang == 'auto'
                src_label = 'the auto-detected source language' if is_auto else SUPPORTED_LANGUAGES[source_lang]
                tgt_label = TARGET_LANGUAGES[target_lang]

                user_prompt = f'Translate from {src_label} to {tgt_label}:\n\n"{text}"'
                if wiki_match:
                    user_prompt += (
                        f'\n\nCultural context (Wiki-Voz): '
                        f'The term "{wiki_match.term}" means: {wiki_match.definition}'
                    )

                client = _get_gemini_client()
                translated_text, model_used = _generate_translation_gemini(
                    client=client,
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                )
                log_entry.output_text = translated_text
                log_entry.latency_ms = (time.perf_counter() - start_time) * 1000
                log_entry.pivot_used = False
                log_entry.model_name = model_used
                log_entry.status = 'success'

        except ValueError as e:
            log_entry.latency_ms = (time.perf_counter() - start_time) * 1000
            log_entry.status = 'error'
            log_entry.error_message = str(e)
            log_entry.model_name = 'none'
            log_entry.save()
            return Response(
                {'error': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            logger.exception('Translation failed')
            log_entry.latency_ms = (time.perf_counter() - start_time) * 1000
            log_entry.status = 'error'
            log_entry.error_message = str(e)
            log_entry.model_name = getattr(log_entry, 'model_name', 'unknown') or 'unknown'
            log_entry.save()

            error_text = str(e).lower()
            response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            friendly_message = f'Translation failed: {e}'

            if 'resource_exhausted' in error_text or 'quota' in error_text:
                response_status = status.HTTP_429_TOO_MANY_REQUESTS
                friendly_message = 'API quota exceeded. Try again later.'
            elif 'permission_denied' in error_text or 'api key not valid' in error_text:
                response_status = status.HTTP_403_FORBIDDEN
                friendly_message = 'API key was rejected. Verify configuration.'

            return Response({'error': friendly_message}, status=response_status)

        # 5. Save log entry -------------------------------------------------
        log_entry.wiki_voz_triggered = wiki_match is not None
        log_entry.wiki_voz_term = wiki_match.term if wiki_match else ''
        log_entry.save()

        # 6. Response -------------------------------------------------------
        payload = {
            'translated_text': translated_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'mode': mode,
            'model': model_used,
            'latency_ms': round(log_entry.latency_ms, 1),
            'tokens_in': log_entry.input_tokens,
            'tokens_out': log_entry.output_tokens,
            'pivot_used': log_entry.pivot_used,
        }
        if wiki_data:
            payload['wiki_voz'] = wiki_data

        return Response(payload)


# ═══════════════════════════════════════════════════════════════
# Wiki-Voz Search View
# ═══════════════════════════════════════════════════════════════
class WikiVozView(APIView):
    """
    GET /api/wiki/?q=<term>
    Returns matching CulturalTerm entries from PostgreSQL.
    Without query, returns all entries (for frontend term-map loading).
    """

    def get(self, request):
        query = request.query_params.get('q', '').strip()
        if query:
            terms = CulturalTerm.objects.filter(term__icontains=query).order_by('term')[:20]
        else:
            # Return ALL terms so frontend can build dynamic CULTURAL_TERMS_MAP
            terms = CulturalTerm.objects.order_by('term')[:100]
        serializer = CulturalTermSerializer(terms, many=True)
        return Response({'results': serializer.data})


# ═══════════════════════════════════════════════════════════════
# Text-to-Speech View
# ═══════════════════════════════════════════════════════════════
class TextToSpeechView(APIView):
    """
    POST /api/tts/
    Body: { "text": "...", "lang_code": "en", "voice": "optional-edge-voice" }

    Uses the unofficial edge-tts library to generate MP3 audio.
    Note: edge-tts relies on Microsoft's cloud voices, so outbound internet
    access is required when synthesizing speech.
    """

    def post(self, request):
        serializer = TextToSpeechRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        text = serializer.validated_data['text']
        lang_code = serializer.validated_data.get('lang_code', 'en')
        voice_override = serializer.validated_data.get('voice') or None

        try:
            audio_bytes, selected_voice = _synthesize_speech_bytes(
                text=text,
                lang_code=lang_code,
                voice_override=voice_override,
            )
        except ValueError as exc:
            message = str(exc)
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            if 'requires non-empty' in message.lower():
                status_code = status.HTTP_400_BAD_REQUEST
            return Response({'error': message}, status=status_code)
        except Exception:
            logger.exception('Text-to-speech generation failed')
            return Response(
                {
                    'error': (
                        'Text-to-speech failed. edge-tts may need internet access '
                        'or a valid voice name.'
                    ),
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        response = HttpResponse(audio_bytes, content_type='audio/mpeg')
        response['Content-Disposition'] = 'inline; filename="puente-tts.mp3"'
        response['Cache-Control'] = 'no-store'
        response['X-TTS-Voice'] = selected_voice
        return response


# ═══════════════════════════════════════════════════════════════
# Health Check View
# ═══════════════════════════════════════════════════════════════
class HealthCheckView(APIView):
    """GET /api/health/ — System status check for frontend health polling."""

    def get(self, request):
        nllb_loaded = CoreApiConfig.model_loaded
        lora_modes = list(CoreApiConfig.lora_adapters.keys())

        # Fallback: check if Gemini is configured
        api_key = getattr(settings, 'GOOGLE_API_KEY', '')
        gemini_configured = bool(api_key and api_key != 'YOUR_GEMINI_API_KEY_HERE')
        tts_available = is_edge_tts_available()

        return Response({
            'status': 'ok',
            'engine': 'nllb-200-distilled-600M' if nllb_loaded else 'gemini-fallback',
            'nllb_loaded': nllb_loaded,
            'lora_adapters': lora_modes,
            'api_key_configured': gemini_configured or nllb_loaded,
            'tts_available': tts_available,
            'tts_engine': 'edge-tts' if tts_available else 'unavailable',
            'supported_languages': list(SUPPORTED_LANGUAGES.keys()),
        })
