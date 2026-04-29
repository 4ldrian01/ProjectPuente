"""
core_api/views.py — Translation & Wiki-Voz API for Project Puente.

Primary engine: NLLB-200-distilled-600M (8-bit quantized, Singleton loaded
via apps.py) with LoRA adapters for formal/street Chavacano.

Features:
    - Direct many-to-many routing with confidence-gated proximate pivot fallback
    - Translation Memory (TM) cache before inference
    - Greedy Wiki-Voz multi-word phrase interception
  - ISO 25010 TranslationLog for every request
  - Formal/Street sociolinguistic mode switching
    - Pure Spanish (es) control-variable support for thesis baselines
"""

import gc
import logging
import re
import secrets
import time
import unicodedata
from datetime import datetime, timezone
import threading

from django.conf import settings
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .apps import CoreApiConfig
from .languages import (
    DIRECT_INFERENCE_CONFIDENCE_THRESHOLD,
    FLORES_MAP,
    SUPPORTED_LANGUAGES,
    select_proximate_pivot,
)
from .models import CulturalTerm, TranslationLog
from .serializers import (
    BackTranslationRequestSerializer,
    CulturalTermSerializer,
    TranslationLogListSerializer,
    TextToSpeechRequestSerializer,
    TranslateRequestSerializer,
    WIKI_ALLOWED_CATEGORIES,
    WIKI_ALLOWED_LANGUAGES,
    WIKI_CATEGORY_ALIASES,
    WIKI_LANGUAGE_ALIASES,
)

logger = logging.getLogger(__name__)

EDGE_TTS_DEFAULT_VOICES = {
    'en': 'en-US-EmmaMultilingualNeural',
    'es': 'es-ES-AlvaroNeural',
    'tl': 'fil-PH-BlessicaNeural',
    'cbk': 'es-ES-ElviraNeural',
    'hil': 'fil-PH-BlessicaNeural',
    'ceb': 'fil-PH-AngeloNeural',
}

INTERCEPTOR_LANGUAGE_ALIASES = {
    'en': ('en', 'english'),
    'es': ('es', 'spanish', 'español', 'espanol'),
    'tl': ('tl', 'tagalog', 'filipino'),
    'cbk': ('cbk', 'chavacano', 'chavacano (zamboanga)', 'zamboanga'),
    'hil': ('hil', 'hiligaynon', 'ilonggo'),
    'ceb': ('ceb', 'cebuano', 'bisaya', 'cebuano/bisaya'),
}

EN_TO_CBK_IDENTITY_GUARD_FALLBACKS = {
    'hello': 'hola',
    'hi': 'hola',
    'hey': 'hola',
    'good morning': 'buenas dias',
    'good afternoon': 'buenas tardes',
    'good evening': 'buenas noches',
}

# Lightweight phrase-level fallback for ultra-common, short greetings.
# This keeps UX responsive on low-RAM/CPU systems when full inference is costly.
EN_TO_CBK_QUICK_TRANSLATIONS = {
    'hello': 'hola',
    'hi': 'hola',
    'hey': 'hola',
    'good morning': 'buenas dias',
    'good afternoon': 'buenas tardes',
    'good evening': 'buenas noches',
    'good night': 'buenas noches',
    'thank you': 'gracias',
}

REGISTER_TOKENS = {
    'formal': '[FORMAL]',
    'street': '[STREET]',
}

GAP_CATEGORY_MAP = {
    'idiom': 'Idiomatic',
    'idioms': 'Idiomatic',
    'honorific': 'Politeness',
    'honorifics': 'Politeness',
    'politeness': 'Politeness',
    'false cognate': 'Cultural',
    'false cognates': 'Cultural',
    'expression': 'Cultural',
    'expressions': 'Cultural',
    'culture': 'Cultural',
    'cultural': 'Cultural',
}

MAX_WIKI_MATCHES = 80

GPU_LOCK = threading.Lock()

def _flatten_serializer_errors(errors):
    if not errors:
        return ''

    parts = []
    for value in errors.values():
        if isinstance(value, (list, tuple)):
            parts.extend([str(entry).strip() for entry in value if str(entry).strip()])
        else:
            item = str(value).strip()
            if item:
                parts.append(item)
    return ' '.join(parts).strip()


def _build_error_response(
    *,
    code,
    message,
    http_status,
    details=None,
    retryable=False,
):
    payload = {
        'error': message,
        'error_code': code,
        'retryable': bool(retryable),
    }
    if details:
        payload['details'] = details
    return Response(payload, status=http_status)


def is_strict_offline_mode():
    """Return True when strict offline simulation mode is enabled."""
    return bool(getattr(settings, 'STRICT_OFFLINE_MODE', False))


def is_edge_tts_available():
    """Return True when the optional edge-tts dependency is importable."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        return False
    return True


def is_api_key_required():
    """Return True when write-endpoint API key protection is enabled."""
    return bool((getattr(settings, 'PUENTE_API_KEY', '') or '').strip())


def _has_valid_api_key(request):
    """Validate X-API-Key header against configured backend API key."""
    configured_key = (getattr(settings, 'PUENTE_API_KEY', '') or '').strip()
    if not configured_key:
        return True

    provided_key = (request.headers.get('X-API-Key') or '').strip()
    if not provided_key:
        return False

    return secrets.compare_digest(provided_key, configured_key)


def _require_api_key_or_401(request):
    """Return 401 response when API key is required and invalid/missing."""
    if _has_valid_api_key(request):
        return None

    return _build_error_response(
        code='auth.api_key_invalid',
        message=(
            'Unauthorized: missing or invalid API key. '
            'Provide X-API-Key header.'
        ),
        http_status=status.HTTP_401_UNAUTHORIZED,
        retryable=False,
    )


def _estimate_token_count(text):
    """Fast fallback token estimate for pass-through or non-NLLB paths."""
    return len((text or '').split())


def _normalize_text_for_cache_lookup(text):
    """Normalize text for Translation Memory lookup (strip + lowercase)."""
    normalized = unicodedata.normalize('NFKC', text or '')
    return normalized.strip().casefold()


def _normalize_text_for_phrase_scan(text):
    """Normalize text for robust phrase scanning (lowercase + punctuation folding)."""
    normalized = unicodedata.normalize('NFKC', text or '')
    normalized = normalized.casefold()
    normalized = re.sub(r'[^\w]+', ' ', normalized, flags=re.UNICODE)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized


def _find_translation_memory_hit(text, source_lang, target_lang):
    """Find latest successful translation by normalized input + language pair."""
    normalized_input = _normalize_text_for_cache_lookup(text)
    if not normalized_input:
        return None

    return (
        TranslationLog.objects
        .filter(
            status='success',
            source_lang=source_lang,
            target_lang=target_lang,
        )
        .exclude(output_text='')
        .annotate(normalized_input=Lower(Trim('input_text')))
        .filter(normalized_input=normalized_input)
        .order_by('-created_at')
        .first()
    )


def _should_skip_cached_identity_output(input_text, output_text, source_lang, target_lang):
    """Bypass TM cache when cross-language cached output is unchanged from input."""
    if source_lang == target_lang:
        return False
    if source_lang != 'auto' and FLORES_MAP.get(source_lang) == FLORES_MAP.get(target_lang):
        return False
    return _is_identity_translation(input_text, output_text)


def _get_cultural_term_candidates(source_lang, target_lang):
    """Fetch language-scoped CulturalTerm candidates for phrase interception."""
    scan_lang = source_lang if source_lang != 'auto' else target_lang
    scan_lang = (scan_lang or '').strip().casefold()

    allowed_category_filter = Q()
    for category in WIKI_ALLOWED_CATEGORIES:
        allowed_category_filter |= Q(category__iexact=category)

    base_qs = CulturalTerm.objects.filter(allowed_category_filter).only(
        'id', 'term', 'definition', 'image_url', 'language', 'category',
    )

    if scan_lang in {'', 'auto'}:
        return list(base_qs)

    aliases = INTERCEPTOR_LANGUAGE_ALIASES.get(scan_lang, (scan_lang,))
    language_filter = Q()
    for alias in aliases:
        language_filter |= Q(language__iexact=alias)

    scoped_terms = list(base_qs.filter(language_filter))
    return scoped_terms


def _find_wiki_voz_phrase_match(text, source_lang, target_lang):
    """
    Greedy n-gram style interception:
    - normalize input phrase
    - sort candidate terms by descending normalized length
    - match longest phrase contained in input
    """
    normalized_haystack = _normalize_text_for_phrase_scan(text)
    if not normalized_haystack:
        return None

    haystack = f' {normalized_haystack} '
    candidates = _get_cultural_term_candidates(source_lang, target_lang)

    normalized_terms = []
    for entry in candidates:
        normalized_term = _normalize_text_for_phrase_scan(entry.term)
        if normalized_term:
            normalized_terms.append((len(normalized_term), normalized_term, entry))

    normalized_terms.sort(key=lambda item: (-item[0], item[1]))

    for _, normalized_term, entry in normalized_terms:
        if f' {normalized_term} ' in haystack:
            return entry

    return None


def _inject_register_token(text, mode, should_tag):
    """Inject [FORMAL]/[STREET] control token when Wiki-Voz terms are detected."""
    if not should_tag:
        return text

    token = REGISTER_TOKENS.get(str(mode or '').casefold(), REGISTER_TOKENS['formal'])
    if token in text:
        return text
    return f'{token} {text}'


def _strip_register_tokens(text):
    """Remove control tokens from model output before returning to clients."""
    if not text:
        return text

    cleaned = re.sub(r'\[(?:STREET|FORMAL)\]', '', str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _build_trigger_pattern(trigger):
    normalized = ' '.join(str(trigger or '').split()).strip()
    if not normalized:
        return ''

    escaped = re.escape(normalized)
    escaped = escaped.replace(r'\ ', r'\s+')
    if normalized[:1].isalnum():
        escaped = r'\b' + escaped
    if normalized[-1:].isalnum():
        escaped = escaped + r'\b'
    return escaped


def _collect_wiki_matches(text, candidates, source_label):
    """Collect all Wiki-Voz term matches with positions for UI highlighting. (OPTIMIZED)"""
    if not text:
        return []

    matches = []
    seen = set()
    total_hits = 0
    text_lower = text.casefold() # Pre-lower for fast scanning

    for entry in candidates:
        triggers = entry.trigger_words or []
        if not triggers:
            triggers = [entry.term]

        for trigger in triggers:
            # FAST PRE-CHECK: Only run regex if the word is actually in the string
            if str(trigger).casefold() not in text_lower:
                continue 

            pattern = _build_trigger_pattern(trigger)
            if not pattern:
                continue

            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                key = (entry.id, match.start(), match.end(), source_label)
                if key in seen:
                    continue
                seen.add(key)
                matches.append({
                    'entry': entry,
                    'index_start': match.start(),
                    'index_end': match.end(),
                    'source': source_label,
                    'matched_trigger': str(trigger),
                })
                total_hits += 1
                if total_hits >= MAX_WIKI_MATCHES:
                    return matches

    return matches


def _serialize_wiki_matches(matches):
    """Convert internal Wiki-Voz matches into API-safe metadata payloads."""
    payload = []
    for match in matches:
        entry = match.get('entry')
        if not entry:
            continue
        raw_category = str(getattr(entry, 'category', '') or '').strip()
        gap_category = GAP_CATEGORY_MAP.get(raw_category.casefold(), 'Cultural')
        payload.append({
            'id': entry.id,
            'term': entry.term,
            'definition': entry.definition,
            'image_url': entry.image_url,
            'language': entry.language,
            'category': entry.category,
            'gap_category': gap_category,
            'index_start': match.get('index_start', 0),
            'index_end': match.get('index_end', 0),
            'source': match.get('source', ''),
            'matched_trigger': match.get('matched_trigger', ''),
        })
    return payload


def _select_primary_wiki_match(matches):
    """Pick the strongest Wiki-Voz match for backwards-compatible responses."""
    if not matches:
        return None

    return sorted(
        matches,
        key=lambda item: (
            -(item['index_end'] - item['index_start']),
            item['index_start'],
        ),
    )[0]


def _build_wiki_metadata(input_matches, output_text, candidates):
    """Combine input/output Wiki-Voz matches into a single metadata payload."""
    output_matches = []
    if output_text:
        output_matches = _collect_wiki_matches(output_text, candidates, 'output')
    return _serialize_wiki_matches(input_matches + output_matches)


def _build_gap_analysis_data(metadata):
    """Aggregate Wiki-Voz gap data for the Gap Analysis Terminal."""
    category_counts = {
        'Cultural': 0,
        'Idiomatic': 0,
        'Politeness': 0,
    }
    source_counts = {
        'input': 0,
        'output': 0,
    }
    unique_terms = set()

    for entry in metadata or []:
        gap_category = entry.get('gap_category') or 'Cultural'
        if gap_category not in category_counts:
            gap_category = 'Cultural'
        category_counts[gap_category] += 1

        source_label = entry.get('source')
        if source_label in source_counts:
            source_counts[source_label] += 1

        term = entry.get('term')
        if term:
            unique_terms.add(str(term).casefold())

    total_hits = sum(category_counts.values())
    unique_count = len(unique_terms)
    severity = min(100, 20 + total_hits * 10 + unique_count * 4)

    return {
        'total_hits': total_hits,
        'unique_terms': unique_count,
        'by_category': category_counts,
        'by_source': source_counts,
        'severity_score': severity,
        'has_gaps': total_hits > 0,
    }


def _build_btvl_data(*, translation, target_lang, tokens_in, tokens_out, route_strategy, route_confidence, pivot_used, pivot_language):
    """Construct btvl payload scaffold for front-end card rendering."""
    return {
        'status': 'not_run',
        'available': CoreApiConfig.model_loaded,
        'recommended_target': 'en',
        'recommended_payload': {
            'text': translation,
            'source_lang': target_lang,
            'target_lang': 'en',
        },
        'telemetry': {
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
        },
        'linguistics': {
            'route_strategy': route_strategy,
            'route_confidence': route_confidence,
            'pivot_used': pivot_used,
            'pivot_language': pivot_language or '',
        },
    }


def _clear_inference_memory():
    """Free CUDA cache after heavy inference or adapter swaps."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect() # Clears zombie memory in RTX cards
    except ImportError:
        pass
    # REMOVED gc.collect() to prevent severe CPU latency spikes


def _ensure_lora_adapter(mode, src_code, tgt_code):
    """
    Loads the requested LoRA adapter for ALL translation directions.
    Enforces bidirectional use of the thesis weights.
    """
    base_model = CoreApiConfig.nllb_base_model or CoreApiConfig.nllb_model
    if base_model is None:
        raise RuntimeError('Base NLLB model is not loaded.')

    adapter_path = CoreApiConfig.adapter_paths.get(mode)
    
    # If no adapter is found, safely fallback to the base model
    if not adapter_path:
        if hasattr(CoreApiConfig.nllb_model, 'disable_adapter'):
            CoreApiConfig.nllb_model.disable_adapter()
        elif hasattr(base_model, 'disable_adapter'):
            base_model.disable_adapter()
        return CoreApiConfig.nllb_model or base_model, ''

    # If the adapter is already loaded, ensure it is ENABLED for this request
    current_path = CoreApiConfig.adapter_paths.get(CoreApiConfig.active_adapter_mode)
    if CoreApiConfig.nllb_model is not None and current_path == adapter_path:
        if hasattr(CoreApiConfig.nllb_model, 'enable_adapter'):
            CoreApiConfig.nllb_model.enable_adapter()
        return CoreApiConfig.nllb_model, adapter_path.name

    # Perform the VRAM-Safe Hot Swap
    _clear_inference_memory()
    try:
        from peft import PeftModel
    except ImportError:
        return base_model, ''

    CoreApiConfig.nllb_model = None
    peft_model = PeftModel.from_pretrained(
        base_model,
        str(adapter_path),
        adapter_name=mode,
        is_trainable=False,
        local_files_only=True,
    )
    peft_model.eval()

    CoreApiConfig.nllb_model = peft_model
    CoreApiConfig.active_adapter_mode = mode

    _clear_inference_memory()
    return peft_model, adapter_path.name


def _bytes_to_gb(value):
    return round(float(value) / (1024 ** 3), 4)


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


# ---------------------------------------------------------------------------
# NLLB-200 Local Inference (Primary Engine)
# ---------------------------------------------------------------------------
def _estimate_generation_confidence(step_scores):
    """Estimate confidence from per-step logits returned by generate()."""
    if not step_scores:
        return None

    import torch

    confidences = []
    for score_tensor in step_scores:
        if score_tensor is None or score_tensor.numel() == 0:
            continue
        step_probs = torch.nn.functional.softmax(score_tensor[0], dim=-1)
        confidences.append(float(torch.max(step_probs).item()))

    if not confidences:
        return None

    return round(sum(confidences) / len(confidences), 4)


def _normalize_accuracy_confidence(value):
    """Normalize confidence value into a 0-1 float for client display."""
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if numeric > 1.0:
        if numeric <= 100.0:
            numeric = numeric / 100.0
        else:
            numeric = 1.0

    if numeric < 0.0:
        numeric = 0.0

    return round(numeric, 4)


def _extract_pivot_lang_from_model_name(model_name):
    """Extract pivot language code from model label suffix, if available."""
    raw_name = str(model_name or '').casefold()
    match = re.search(r'\+pivot-([a-z]{2,3})\b', raw_name)
    if not match:
        return ''
    return match.group(1)


def _should_fallback_to_proximate_pivot(direct_confidence, pivot_code):
    if not pivot_code:
        return False
    if direct_confidence is None:
        return False
    return direct_confidence < DIRECT_INFERENCE_CONFIDENCE_THRESHOLD


def _is_identity_translation(input_text, output_text):
    """Return True when cross-lingual output is effectively unchanged."""
    normalized_in = _normalize_text_for_cache_lookup(input_text)
    normalized_out = _normalize_text_for_cache_lookup(output_text)
    return bool(normalized_in) and normalized_in == normalized_out


def _apply_identity_guard_rule_fallback(input_text, output_text, src_code, tgt_code):
    """Fallback for known en->cbk greetings when model output is unchanged."""
    if str(src_code or '').casefold() != 'en' or str(tgt_code or '').casefold() != 'cbk':
        return output_text, ''

    if not _is_identity_translation(input_text, output_text):
        return output_text, ''

    normalized_key = _normalize_text_for_phrase_scan(input_text)
    mapped = EN_TO_CBK_IDENTITY_GUARD_FALLBACKS.get(normalized_key)
    if not mapped:
        return output_text, ''

    stripped = str(input_text or '').rstrip()
    punctuation_match = re.search(r'([?!.,;:]+)$', stripped)
    punctuation = punctuation_match.group(1) if punctuation_match else ''

    fallback_text = mapped
    if punctuation and not fallback_text.endswith(punctuation):
        fallback_text = f'{fallback_text}{punctuation}'

    if stripped[:1].isupper() and fallback_text:
        fallback_text = fallback_text[:1].upper() + fallback_text[1:]

    return fallback_text, 'rule-fallback-en-cbk'


def _quick_rule_translate_if_available(input_text, source_lang, target_lang):
    """Return a fast phrase-level fallback translation when available."""
    src = str(source_lang or '').casefold()
    tgt = str(target_lang or '').casefold()
    if src != 'en' or tgt != 'cbk':
        return None, ''

    normalized_key = _normalize_text_for_phrase_scan(input_text)
    mapped = EN_TO_CBK_QUICK_TRANSLATIONS.get(normalized_key)
    if not mapped:
        return None, ''

    stripped = str(input_text or '').rstrip()
    punctuation_match = re.search(r'([?!.,;:]+)$', stripped)
    punctuation = punctuation_match.group(1) if punctuation_match else ''

    translated = mapped
    if punctuation and not translated.endswith(punctuation):
        translated = f'{translated}{punctuation}'

    if stripped[:1].isupper() and translated:
        translated = translated[:1].upper() + translated[1:]

    return translated, 'rule-fast-en-cbk'


def _infer_once(model, tokenizer, text, src_flores, tgt_flores, *, with_confidence=False):
    """Single NLLB-200 inference pass using Ultra-Lean Edge constraints."""
    import torch

    tokenizer.src_lang = src_flores
    inputs = tokenizer(
        text, return_tensors='pt', truncation=True, max_length=256, 
    )

    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # 🚀 THE ACTUAL FIX: Only use convert_tokens_to_ids. 
    # Do NOT use lang_code_to_id anywhere in this file.
    target_token_id = tokenizer.convert_tokens_to_ids(tgt_flores)

    generation_kwargs = {
        'forced_bos_token_id': target_token_id,
        'max_new_tokens': 256,   
        'max_length': None,      # 🚀 THE FIX: Silences the Hugging Face warning!
        'num_beams': 1,          
        'do_sample': False,      
        'repetition_penalty': 1.2,
        'no_repeat_ngram_size': 3,
        'length_penalty': 1.0,
    }
    
    if with_confidence:
        generation_kwargs.update({
            'output_scores': True,
            'return_dict_in_generate': True,
        })

    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            **generation_kwargs,
        )

    if with_confidence:
        translated_ids = generated.sequences
        translated_text = tokenizer.batch_decode(translated_ids, skip_special_tokens=True)[0]
        confidence = _estimate_generation_confidence(getattr(generated, 'scores', None))
        return translated_text, confidence

    return tokenizer.batch_decode(generated, skip_special_tokens=True)[0]

def nllb_translate(text, src_code, tgt_code, mode='formal'):
    """
        Translate using Singleton NLLB-200 + LoRA (direct-first routing).

        Returns:
            (
                translated_text,
                latency_ms,
                tokens_in,
                tokens_out,
                pivot_used,
                pivot_language,
                route_strategy,
                route_confidence,
                model_name,
            )
    """
    if not CoreApiConfig.model_loaded or CoreApiConfig.nllb_model is None or CoreApiConfig.nllb_tokenizer is None:
        if not CoreApiConfig.ensure_model_loaded():
            raise RuntimeError(
                'Local NLLB model could not be loaded safely. '
                'Keep other apps closed, ensure CUDA + bitsandbytes are available, '
                'and retry.'
            )

    tokenizer = CoreApiConfig.nllb_tokenizer
    model, adapter_name = _ensure_lora_adapter(str(mode or '').casefold(), src_code, tgt_code)
    raw_text = _strip_register_tokens(text)

    src_flores = FLORES_MAP.get(src_code, 'eng_Latn')
    tgt_flores = FLORES_MAP.get(tgt_code, 'cbk_Latn')

    adapter_label = f'+{adapter_name}' if adapter_name else ''
    model_base = f'nllb-200-distilled-600M{adapter_label}'

    # Short-circuit: same source and target language
    if src_flores == tgt_flores:adapter_label = f'+{adapter_name}' if adapter_name else ''
    model_base = f'nllb-200-distilled-600M{adapter_label}'

    # 🚀 THE FIX: Ensures Spanish to Chavacano actually runs through the AI
    # Short-circuit: same source and target language
    if src_code == tgt_code:
        tokens = len(tokenizer.encode(raw_text))
        return raw_text, 0.0, tokens, tokens, False, '', 'passthrough', 1.0, model_base
        
      

    # Ultra-fast guardrail for short en->cbk greeting phrases to keep
    # low-RAM systems responsive even before full model decode.
    fast_rule_result, fast_rule_strategy = _apply_identity_guard_rule_fallback(
        input_text=raw_text,
        output_text=raw_text,
        src_code=src_code,
        tgt_code=tgt_code,
    )
    if fast_rule_strategy:
        tokens_in = len(tokenizer.encode(text))
        tokens_out = len(tokenizer.encode(fast_rule_result))
        return (
            fast_rule_result,
            0.0,
            tokens_in,
            tokens_out,
            False,
            '',
            f'fast-{fast_rule_strategy}',
            None,
            f'{model_base}+rule-en-cbk-fast',
        )

    start = time.perf_counter()
    pivot_used = False
    pivot_language = ''
    route_strategy = 'direct'

    # Tokenize input once for token count logging
    input_ids = tokenizer.encode(text)
    tokens_in = len(input_ids)

    proximate_pivot = select_proximate_pivot(src_code, tgt_code)
    model_device = next(model.parameters()).device
    use_confidence_scores = getattr(model_device, 'type', '').lower() != 'cpu'

    if use_confidence_scores:
        result, direct_confidence = _infer_once(
            model,
            tokenizer,
            text,
            src_flores,
            tgt_flores,
            with_confidence=True,
        )
    else:
        result = _infer_once(
            model,
            tokenizer,
            text,
            src_flores,
            tgt_flores,
            with_confidence=False,
        )
        direct_confidence = None

    result = _strip_register_tokens(result)

    should_use_pivot = _should_fallback_to_proximate_pivot(direct_confidence, proximate_pivot)
    if (
        not should_use_pivot
        and src_flores != tgt_flores
        and proximate_pivot
        and _is_identity_translation(raw_text, result)
    ):
        should_use_pivot = True

    if should_use_pivot:
        pivot_flores = FLORES_MAP.get(proximate_pivot)
        if pivot_flores:
            pivot_used = True
            pivot_language = proximate_pivot
            route_strategy = 'proximate-pivot'
            if _is_identity_translation(text, result):
                route_strategy = 'identity-guard-pivot'
            mid_text = _infer_once(model, tokenizer, text, src_flores, pivot_flores)
            result = _infer_once(model, tokenizer, mid_text, pivot_flores, tgt_flores)

    result = _strip_register_tokens(result)

    result, rule_strategy = _apply_identity_guard_rule_fallback(
        input_text=raw_text,
        output_text=result,
        src_code=src_code,
        tgt_code=tgt_code,
    )
    if rule_strategy:
        route_strategy = f'{route_strategy}+{rule_strategy}'

    elapsed_ms = (time.perf_counter() - start) * 1000
    tokens_out = len(tokenizer.encode(result))
    route_label = f'+pivot-{pivot_language}' if pivot_language else ''
    rule_label = '+rule-en-cbk' if rule_strategy else ''
    model_name = f'{model_base}{route_label}{rule_label}'

    _clear_inference_memory()

    return (
        result,
        elapsed_ms,
        tokens_in,
        tokens_out,
        pivot_used,
        pivot_language,
        route_strategy,
        direct_confidence,
        model_name,
    )


@api_view(['GET'])
def telemetry_view(request):
    """GET /api/telemetry/ — real RAM and GPU VRAM metrics for edge-hardware validation."""
    try:
        import psutil
    except ImportError:
        return _build_error_response(
            code='dependency.psutil_missing',
            message='psutil is not installed. Install with: pip install psutil',
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
            retryable=False,
        )

    ram = psutil.virtual_memory()
    ram_payload = {
        'used_bytes': int(ram.used),
        'total_bytes': int(ram.total),
        'used_gb': _bytes_to_gb(ram.used),
        'total_gb': _bytes_to_gb(ram.total),
        'percent': round(float(ram.percent), 2),
    }

    gpu_payload = {
        'available': False,
        'name': '',
        'used_bytes': 0,
        'reserved_bytes': 0,
        'total_bytes': 0,
        'used_gb': 0.0,
        'reserved_gb': 0.0,
        'total_gb': 0.0,
        'percent': 0.0,
        'reason': 'cuda-unavailable',
        'torch_version': '',
        'torch_cuda_version': '',
    }

    try:
        import torch

        gpu_payload['torch_version'] = str(getattr(torch, '__version__', ''))
        gpu_payload['torch_cuda_version'] = str(getattr(torch.version, 'cuda', '') or '')

        if torch.cuda.is_available():
            device_index = torch.cuda.current_device()
            device_props = torch.cuda.get_device_properties(device_index)

            used_bytes = int(torch.cuda.memory_allocated(device_index))
            reserved_bytes = int(torch.cuda.memory_reserved(device_index))
            total_bytes = int(device_props.total_memory)
            usage_percent = round((used_bytes / total_bytes) * 100, 2) if total_bytes else 0.0

            gpu_payload = {
                'available': True,
                'name': str(device_props.name),
                'used_bytes': used_bytes,
                'reserved_bytes': reserved_bytes,
                'total_bytes': total_bytes,
                'used_gb': _bytes_to_gb(used_bytes),
                'reserved_gb': _bytes_to_gb(reserved_bytes),
                'total_gb': _bytes_to_gb(total_bytes),
                'percent': usage_percent,
                'reason': '',
                'torch_version': gpu_payload['torch_version'],
                'torch_cuda_version': gpu_payload['torch_cuda_version'],
            }
        else:
            if gpu_payload['torch_cuda_version']:
                gpu_payload['reason'] = f"cuda-not-detected (torch-cuda={gpu_payload['torch_cuda_version']})"
            else:
                gpu_payload['reason'] = 'torch-cpu-build'
    except ImportError:
        # Fallback path for machines where torch is unavailable but NV driver
        # metrics are still queryable via GPUtil.
        try:
            import importlib

            gputil_module = importlib.import_module('GPUtil')
            gpus = gputil_module.getGPUs()
            if gpus:
                gpu = gpus[0]
                used_bytes = int(float(gpu.memoryUsed) * 1024 * 1024)
                total_bytes = int(float(gpu.memoryTotal) * 1024 * 1024)
                usage_percent = round((used_bytes / total_bytes) * 100, 2) if total_bytes else 0.0

                gpu_payload = {
                    'available': True,
                    'name': str(gpu.name),
                    'used_bytes': used_bytes,
                    'reserved_bytes': 0,
                    'total_bytes': total_bytes,
                    'used_gb': _bytes_to_gb(used_bytes),
                    'reserved_gb': 0.0,
                    'total_gb': _bytes_to_gb(total_bytes),
                    'percent': usage_percent,
                    'reason': '',
                }
            else:
                gpu_payload['reason'] = 'gputil-no-gpu-detected'
        except ImportError:
            gpu_payload['reason'] = 'torch-and-gputil-unavailable'
        except Exception as exc:
            gpu_payload['reason'] = f'gputil-telemetry-error: {exc}'
    except Exception as exc:
        gpu_payload['reason'] = f'gpu-telemetry-error: {exc}'

    return Response(
        {
            'status': 'ok',
            'timestamp_utc': datetime.now(timezone.utc).isoformat(),
            'ram': ram_payload,
            'gpu': gpu_payload,
        }
    )


# ═══════════════════════════════════════════════════════════════
# API Root View
# ═══════════════════════════════════════════════════════════════
class APIRootView(APIView):
    """GET / — Root route with backend status and endpoint listing."""

    def get(self, request):
        return Response({
            'project': 'Project Puente Backend',
            'status': 'online',
            'engine': (
                CoreApiConfig.engine_name
                if CoreApiConfig.model_loaded
                else 'offline-model-missing'
            ),
            'endpoints': {
                'admin': '/admin/',
                'translate': '/api/translate/',
                'btvl': '/api/btvl/',
                'logs': '/api/logs/?limit=50',
                'telemetry': '/api/telemetry/',
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
        auth_error = _require_api_key_or_401(request)
        if auth_error:
            return auth_error

        # 1. Validate -------------------------------------------------------
        serializer = TranslateRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return _build_error_response(
                code='validation.translate.invalid_payload',
                message='Translation request validation failed.',
                http_status=status.HTTP_400_BAD_REQUEST,
                details={
                    'errors': serializer.errors,
                    'summary': _flatten_serializer_errors(serializer.errors),
                },
                retryable=False,
            )

        text = serializer.validated_data['text']
        source_lang = serializer.validated_data['source_lang']
        target_lang = serializer.validated_data['target_lang']
        mode = serializer.validated_data.get('mode', 'formal')
        use_cache = serializer.validated_data.get('use_cache', True)
        request_started = time.perf_counter()

        # 2. Wiki-Voz interception (multi-term scan + register tagging) ------
        wiki_candidates = _get_cultural_term_candidates(
            source_lang=source_lang,
            target_lang=target_lang,
        )
        input_matches = _collect_wiki_matches(text, wiki_candidates, 'input')
        primary_match = _select_primary_wiki_match(input_matches)
        primary_entry = primary_match['entry'] if primary_match else None
        wiki_data = CulturalTermSerializer(primary_entry).data if primary_entry else None
        has_wiki_match = bool(input_matches)

        tagged_text = _inject_register_token(text, mode, has_wiki_match)
        if has_wiki_match:
            use_cache = False

        # 2.5 Lightweight fast-path for common greeting phrases -----------
        quick_translation, quick_route = _quick_rule_translate_if_available(
            input_text=text,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        if quick_translation is not None and not has_wiki_match:
            wiki_metadata = _build_wiki_metadata(input_matches, quick_translation, wiki_candidates)
            gap_analysis_data = _build_gap_analysis_data(wiki_metadata)
            quick_tokens_in = _estimate_token_count(text)
            quick_tokens_out = _estimate_token_count(quick_translation)
            quick_latency_ms = (time.perf_counter() - request_started) * 1000

            TranslationLog.objects.create(
                source_lang=source_lang,
                target_lang=target_lang,
                mode=mode,
                input_text=text,
                input_chars=len(text),
                input_tokens=quick_tokens_in,
                output_text=quick_translation,
                output_tokens=quick_tokens_out,
                model_name='rule-fast-en-cbk',
                pivot_used=False,
                route_confidence=1.0,
                latency_ms=quick_latency_ms,
                status='success',
                wiki_voz_triggered=has_wiki_match,
                wiki_voz_term=primary_entry.term if primary_entry else '',
            )

            payload = {
                'translated_text': quick_translation,
                'translation': quick_translation,
                'source_lang': source_lang,
                'target_lang': target_lang,
                'mode': mode,
                'model': 'rule-fast-en-cbk',
                'latency_ms': round(quick_latency_ms, 1),
                'tokens_in': quick_tokens_in,
                'tokens_out': quick_tokens_out,
                'pivot_used': False,
                'pivot_language': None,
                'route_strategy': quick_route,
                'route_confidence': 1.0,
                'accuracy_confidence': _normalize_accuracy_confidence(1.0),
                'is_cached': False,
                'metadata': wiki_metadata,
                'gap_analysis_data': gap_analysis_data,
                'btvl_data': _build_btvl_data(
                    translation=quick_translation,
                    target_lang=target_lang,
                    tokens_in=quick_tokens_in,
                    tokens_out=quick_tokens_out,
                    route_strategy=quick_route,
                    route_confidence=1.0,
                    pivot_used=False,
                    pivot_language='',
                ),
            }
            if wiki_data:
                payload['wiki_voz'] = wiki_data
            return Response(payload)

        # 3. Translation Memory (TM) cache lookup ---------------------------
        cached_log = None
        if use_cache:
            cached_log = _find_translation_memory_hit(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
            )

        if cached_log:
            if _should_skip_cached_identity_output(
                input_text=text,
                output_text=cached_log.output_text,
                source_lang=source_lang,
                target_lang=target_lang,
            ):
                cached_log = None
            else:
                translated_text = _strip_register_tokens(cached_log.output_text)
                tokens_in = cached_log.input_tokens or _estimate_token_count(text)
                tokens_out = cached_log.output_tokens or _estimate_token_count(translated_text)
                cached_pivot_language = _extract_pivot_lang_from_model_name(cached_log.model_name)
                cached_route_strategy = 'proximate-pivot' if cached_log.pivot_used else 'direct'
                cached_route_confidence = cached_log.route_confidence
                cache_latency_ms = (time.perf_counter() - request_started) * 1000
                wiki_metadata = _build_wiki_metadata(input_matches, translated_text, wiki_candidates)
                gap_analysis_data = _build_gap_analysis_data(wiki_metadata)

                TranslationLog.objects.create(
                    source_lang=source_lang,
                    target_lang=target_lang,
                    mode=mode,
                    input_text=text,
                    input_chars=len(text),
                    input_tokens=tokens_in,
                    output_text=translated_text,
                    output_tokens=tokens_out,
                    model_name='tm-cache',
                    pivot_used=cached_log.pivot_used,
                    route_confidence=cached_route_confidence,
                    latency_ms=cache_latency_ms,
                    status='success',
                    wiki_voz_triggered=has_wiki_match,
                    wiki_voz_term=primary_entry.term if primary_entry else '',
                )

                payload = {
                    'translated_text': translated_text,
                    'translation': translated_text,
                    'source_lang': source_lang,
                    'target_lang': target_lang,
                    'mode': mode,
                    'model': 'tm-cache',
                    'latency_ms': round(cache_latency_ms, 1),
                    'tokens_in': tokens_in,
                    'tokens_out': tokens_out,
                    'pivot_used': cached_log.pivot_used,
                    'pivot_language': cached_pivot_language or None,
                    'route_strategy': cached_route_strategy,
                    'route_confidence': cached_route_confidence,
                    'accuracy_confidence': _normalize_accuracy_confidence(cached_route_confidence),
                    'is_cached': True,
                    'metadata': wiki_metadata,
                    'gap_analysis_data': gap_analysis_data,
                    'btvl_data': _build_btvl_data(
                        translation=translated_text,
                        target_lang=target_lang,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        route_strategy=cached_route_strategy,
                        route_confidence=cached_route_confidence,
                        pivot_used=cached_log.pivot_used,
                        pivot_language=cached_pivot_language,
                    ),
                }
                if wiki_data:
                    payload['wiki_voz'] = wiki_data
                return Response(payload)

        # 4. Short-circuit: same source and target language -----------------
        if source_lang == target_lang or (
            source_lang != 'auto'
            and FLORES_MAP.get(source_lang) == FLORES_MAP.get(target_lang)
        ):
            passthrough_tokens = _estimate_token_count(text)
            wiki_metadata = _build_wiki_metadata(input_matches, text, wiki_candidates)
            gap_analysis_data = _build_gap_analysis_data(wiki_metadata)
            log_entry = TranslationLog(
                source_lang=source_lang, target_lang=target_lang,
                mode=mode, input_text=text, input_chars=len(text),
                input_tokens=passthrough_tokens,
                output_text=text, latency_ms=0.0, status='success',
                output_tokens=passthrough_tokens,
                model_name='passthrough', pivot_used=False,
                route_confidence=1.0,
                wiki_voz_triggered=has_wiki_match,
                wiki_voz_term=primary_entry.term if primary_entry else '',
            )
            log_entry.save()
            payload = {
                'translated_text': text,
                'translation': text,
                'source_lang': source_lang,
                'target_lang': target_lang, 'mode': mode,
                'model': 'passthrough', 'latency_ms': 0.0,
                'tokens_in': passthrough_tokens,
                'tokens_out': passthrough_tokens,
                'pivot_used': False,
                'pivot_language': None,
                'route_strategy': 'passthrough',
                'route_confidence': 1.0,
                'accuracy_confidence': _normalize_accuracy_confidence(1.0),
                'is_cached': False,
                'metadata': wiki_metadata,
                'gap_analysis_data': gap_analysis_data,
                'btvl_data': _build_btvl_data(
                    translation=text,
                    target_lang=target_lang,
                    tokens_in=passthrough_tokens,
                    tokens_out=passthrough_tokens,
                    route_strategy='passthrough',
                    route_confidence=1.0,
                    pivot_used=False,
                    pivot_language='',
                ),
            }
            if wiki_data:
                payload['wiki_voz'] = wiki_data
            return Response(payload)

        # 5. Ultra-fast low-RAM rule fallback ------------------------------
        # This keeps basic greeting translation available even when the full
        # model is not loaded on 8GB devices.
        fast_translated_text, fast_route_strategy = _apply_identity_guard_rule_fallback(
            input_text=text,
            output_text=text,
            src_code=source_lang,
            tgt_code=target_lang,
        )
        if fast_route_strategy and not has_wiki_match:
            wiki_metadata = _build_wiki_metadata(input_matches, fast_translated_text, wiki_candidates)
            gap_analysis_data = _build_gap_analysis_data(wiki_metadata)
            fallback_tokens_in = _estimate_token_count(text)
            fallback_tokens_out = _estimate_token_count(fast_translated_text)
            fallback_latency_ms = (time.perf_counter() - request_started) * 1000

            TranslationLog.objects.create(
                source_lang=source_lang,
                target_lang=target_lang,
                mode=mode,
                input_text=text,
                input_chars=len(text),
                input_tokens=fallback_tokens_in,
                output_text=fast_translated_text,
                output_tokens=fallback_tokens_out,
                model_name='rule-based-fallback',
                pivot_used=False,
                route_confidence=1.0,
                latency_ms=fallback_latency_ms,
                status='success',
                wiki_voz_triggered=has_wiki_match,
                wiki_voz_term=primary_entry.term if primary_entry else '',
            )

            payload = {
                'translated_text': fast_translated_text,
                'translation': fast_translated_text,
                'source_lang': source_lang,
                'target_lang': target_lang,
                'mode': mode,
                'model': 'rule-based-fallback',
                'latency_ms': round(fallback_latency_ms, 1),
                'tokens_in': fallback_tokens_in,
                'tokens_out': fallback_tokens_out,
                'pivot_used': False,
                'pivot_language': None,
                'route_strategy': f'fast-{fast_route_strategy}',
                'route_confidence': 1.0,
                'accuracy_confidence': _normalize_accuracy_confidence(1.0),
                'is_cached': False,
                'metadata': wiki_metadata,
                'gap_analysis_data': gap_analysis_data,
                'btvl_data': _build_btvl_data(
                    translation=fast_translated_text,
                    target_lang=target_lang,
                    tokens_in=fallback_tokens_in,
                    tokens_out=fallback_tokens_out,
                    route_strategy=f'fast-{fast_route_strategy}',
                    route_confidence=1.0,
                    pivot_used=False,
                    pivot_language='',
                ),
            }
            if wiki_data:
                payload['wiki_voz'] = wiki_data
            return Response(payload)

        # 6. Prepare logging entry ------------------------------------------
        start_time = time.perf_counter()
        log_entry = TranslationLog(
            source_lang=source_lang,
            target_lang=target_lang,
            mode=mode,
            input_text=text,
            input_chars=len(text),
        )

        # 7. Translate — strict local edge inference (no outbound API calls) --
        if not CoreApiConfig.model_loaded and not CoreApiConfig.ensure_model_loaded():
            err_msg = (
                'Local NLLB model is unavailable or could not be loaded safely. '
                'Ensure CUDA + bitsandbytes are available and keep free RAM available.'
            )
            log_entry.latency_ms = (time.perf_counter() - start_time) * 1000
            log_entry.status = 'error'
            log_entry.error_message = err_msg
            log_entry.model_name = 'offline-model-missing'
            log_entry.save()
            return _build_error_response(
                code='model.local.unavailable',
                message=err_msg,
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=True,
            )

        try:
            (
                translated_text,
                latency_ms,
                tokens_in,
                tokens_out,
                pivot_used,
                pivot_language,
                route_strategy,
                route_confidence,
                model_used,
            ) = (
                nllb_translate(
                    text=tagged_text,
                    src_code=source_lang,
                    tgt_code=target_lang,
                    mode=mode,
                )
            )

            translated_text = _strip_register_tokens(translated_text)

            log_entry.output_text = translated_text
            log_entry.input_tokens = tokens_in
            log_entry.output_tokens = tokens_out
            log_entry.latency_ms = latency_ms
            log_entry.pivot_used = pivot_used
            log_entry.route_confidence = route_confidence
            log_entry.model_name = model_used
            log_entry.status = 'success'
        except Exception as e:
            err_msg = f'Local translation failed: {e}'
            logger.exception(err_msg)
            log_entry.latency_ms = (time.perf_counter() - start_time) * 1000
            log_entry.status = 'error'
            log_entry.error_message = err_msg
            log_entry.model_name = CoreApiConfig.engine_name or 'nllb-200-distilled-600M'
            log_entry.save()

            return _build_error_response(
                code='translation.local.failed',
                message=err_msg,
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                retryable=True,
            )

        # 8. Save log entry -------------------------------------------------
        log_entry.wiki_voz_triggered = has_wiki_match
        log_entry.wiki_voz_term = primary_entry.term if primary_entry else ''
        log_entry.save()

        wiki_metadata = _build_wiki_metadata(input_matches, translated_text, wiki_candidates)
        gap_analysis_data = _build_gap_analysis_data(wiki_metadata)

        # 9. Response -------------------------------------------------------
        payload = {
            'translated_text': translated_text,
            'translation': translated_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'mode': mode,
            'model': model_used,
            'latency_ms': round(log_entry.latency_ms, 1),
            'tokens_in': log_entry.input_tokens,
            'tokens_out': log_entry.output_tokens,
            'pivot_used': log_entry.pivot_used,
            'pivot_language': pivot_language or None,
            'route_strategy': route_strategy,
            'route_confidence': log_entry.route_confidence,
            'accuracy_confidence': _normalize_accuracy_confidence(log_entry.route_confidence),
            'is_cached': False,
            'metadata': wiki_metadata,
            'gap_analysis_data': gap_analysis_data,
            'btvl_data': _build_btvl_data(
                translation=translated_text,
                target_lang=target_lang,
                tokens_in=log_entry.input_tokens,
                tokens_out=log_entry.output_tokens,
                route_strategy=route_strategy,
                route_confidence=log_entry.route_confidence,
                pivot_used=log_entry.pivot_used,
                pivot_language=pivot_language,
            ),
        }
        if wiki_data:
            payload['wiki_voz'] = wiki_data

        return Response(payload)


# ═══════════════════════════════════════════════════════════════
# Back-Translation Verification Loop (BTVL)
# ═══════════════════════════════════════════════════════════════
class BackTranslationVerifyView(APIView):
    """
    POST /api/btvl/
    Body: { "text": "...", "source_lang": "cbk", "target_lang": "en" }

    Translates text into a verification target language for semantic checks.
    """

    def post(self, request):
        auth_error = _require_api_key_or_401(request)
        if auth_error:
            return auth_error

        serializer = BackTranslationRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return _build_error_response(
                code='validation.btvl.invalid_payload',
                message='Back-translation payload validation failed.',
                http_status=status.HTTP_400_BAD_REQUEST,
                details={
                    'errors': serializer.errors,
                    'summary': _flatten_serializer_errors(serializer.errors),
                },
                retryable=False,
            )

        text = serializer.validated_data['text']
        source_lang = serializer.validated_data['source_lang']
        target_lang = serializer.validated_data.get('target_lang', 'en')

        if not CoreApiConfig.model_loaded:
            return _build_error_response(
                code='model.local.unavailable',
                message=(
                    'Local NLLB model is unavailable. '
                    'Install it in ml_models/nllb-200-distilled-600M and restart backend.'
                ),
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=True,
            )

        try:
            (
                verified_text,
                latency_ms,
                tokens_in,
                tokens_out,
                pivot_used,
                pivot_language,
                route_strategy,
                route_confidence,
                model_used,
            ) = (
                nllb_translate(
                    text=text,
                    src_code=source_lang,
                    tgt_code=target_lang,
                    mode='formal',
                )
            )
        except Exception as e:
            logger.exception('Back-translation verification failed')
            return _build_error_response(
                code='translation.btvl.failed',
                message=f'Back-translation failed: {e}',
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                retryable=True,
            )

        return Response({
            'verified_text': verified_text,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'model': model_used,
            'latency_ms': round(latency_ms, 1),
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'pivot_used': pivot_used,
            'pivot_language': pivot_language or None,
            'route_strategy': route_strategy,
            'route_confidence': route_confidence,
            'accuracy_confidence': _normalize_accuracy_confidence(route_confidence),
        })


# ═══════════════════════════════════════════════════════════════
# Wiki-Voz CRUD ViewSet
# ═══════════════════════════════════════════════════════════════
class WikiVozViewSet(viewsets.ModelViewSet):
    """
    Wiki-Voz CRUD bridge.

    Supported methods:
      - GET    /api/wiki/
      - POST   /api/wiki/
      - DELETE /api/wiki/?id=<pk>  (and /api/wiki/<pk>/ for compatibility)
    """

    serializer_class = CulturalTermSerializer
    queryset = CulturalTerm.objects.all().order_by('term')
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    @staticmethod
    def _build_allowed_scope_filter():
        language_filter = Q()
        for language in WIKI_ALLOWED_LANGUAGES:
            language_filter |= Q(language__iexact=language)

        category_filter = Q()
        for category in WIKI_ALLOWED_CATEGORIES:
            category_filter |= Q(category__iexact=category)

        return language_filter & category_filter

    def get_queryset(self):
        queryset = CulturalTerm.objects.filter(
            self._build_allowed_scope_filter(),
        ).order_by('term')

        query = (self.request.query_params.get('q') or '').strip()
        language = (self.request.query_params.get('language') or '').strip()
        category = (self.request.query_params.get('category') or '').strip()

        if query:
            queryset = queryset.filter(
                Q(term__icontains=query) | Q(definition__icontains=query),
            )

        if language:
            normalized_language = WIKI_LANGUAGE_ALIASES.get(language.casefold(), language)
            if normalized_language in WIKI_ALLOWED_LANGUAGES:
                queryset = queryset.filter(language__iexact=normalized_language)

        if category:
            normalized_category = WIKI_CATEGORY_ALIASES.get(category.casefold(), category)
            if normalized_category in WIKI_ALLOWED_CATEGORIES:
                queryset = queryset.filter(category__iexact=normalized_category)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': len(serializer.data),
            'results': serializer.data,
        })

    def create(self, request, *args, **kwargs):
        auth_error = _require_api_key_or_401(request)
        if auth_error:
            return auth_error
        raw_id = request.data.get('id')
        existing_by_id = None

        if raw_id not in (None, ''):
            try:
                lookup_id = int(str(raw_id).strip())
            except (TypeError, ValueError):
                return _build_error_response(
                    code='validation.wiki.id_invalid',
                    message='id must be an integer when provided.',
                    http_status=status.HTTP_400_BAD_REQUEST,
                    retryable=False,
                )

            existing_by_id = CulturalTerm.objects.filter(pk=lookup_id).first()
            if not existing_by_id:
                return _build_error_response(
                    code='wiki.not_found',
                    message='Cannot update: wiki entry id does not exist.',
                    http_status=status.HTTP_404_NOT_FOUND,
                    retryable=False,
                )

            serializer = self.get_serializer(existing_by_id, data=request.data)
        else:
            serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)

        if existing_by_id is not None:
            obj, was_created = CulturalTerm.objects.update_or_create(
                pk=existing_by_id.pk,
                defaults=validated,
            )
        else:
            lookup_term = validated.get('term')
            lookup_language = validated.get('language')
            obj, was_created = CulturalTerm.objects.update_or_create(
                term=lookup_term,
                language=lookup_language,
                defaults=validated,
            )

        response_payload = self.get_serializer(obj).data
        return Response(
            response_payload,
            status=status.HTTP_201_CREATED if was_created else status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        auth_error = _require_api_key_or_401(request)
        if auth_error:
            return auth_error

        lookup_id = kwargs.get('pk') or request.query_params.get('id')
        if not lookup_id:
            return _build_error_response(
                code='validation.wiki.delete_id_required',
                message='DELETE /api/wiki/ requires an id query parameter, e.g. /api/wiki/?id=12',
                http_status=status.HTTP_400_BAD_REQUEST,
                retryable=False,
            )

        try:
            normalized_pk = int(str(lookup_id).strip())
        except (TypeError, ValueError):
            return _build_error_response(
                code='validation.wiki.delete_id_invalid',
                message='Wiki entry id must be an integer.',
                http_status=status.HTTP_400_BAD_REQUEST,
                retryable=False,
            )

        instance = CulturalTerm.objects.filter(pk=normalized_pk).first()
        if not instance:
            return _build_error_response(
                code='wiki.not_found',
                message='Wiki entry not found.',
                http_status=status.HTTP_404_NOT_FOUND,
                retryable=False,
            )

        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════════
# Translation Activity Log View
# ═══════════════════════════════════════════════════════════════
class TranslationLogListView(APIView):
    """
    GET /api/logs/?limit=50&status=success&source_lang=cbk&target_lang=en&q=term

    Returns recent TranslationLog records for observer dashboards.
    """

    def get(self, request):
        raw_limit = (request.query_params.get('limit') or '50').strip()
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = 50
        limit = max(1, min(limit, 200))

        status_filter = (request.query_params.get('status') or '').strip().casefold()
        source_lang = (request.query_params.get('source_lang') or '').strip().casefold()
        target_lang = (request.query_params.get('target_lang') or '').strip().casefold()
        query = (request.query_params.get('q') or '').strip()

        queryset = TranslationLog.objects.all().order_by('-created_at')

        if status_filter in {'success', 'error', 'timeout'}:
            queryset = queryset.filter(status=status_filter)

        if source_lang in SUPPORTED_LANGUAGES:
            queryset = queryset.filter(source_lang=source_lang)

        valid_target_langs = {code for code in SUPPORTED_LANGUAGES if code != 'auto'}
        if target_lang in valid_target_langs:
            queryset = queryset.filter(target_lang=target_lang)

        if query:
            queryset = queryset.filter(
                Q(input_text__icontains=query)
                | Q(output_text__icontains=query)
                | Q(error_message__icontains=query)
                | Q(wiki_voz_term__icontains=query)
            )

        total = queryset.count()
        rows = queryset[:limit]
        serializer = TranslationLogListSerializer(rows, many=True)

        results = []
        for row_obj, row_data in zip(rows, serializer.data):
            pivot_language = _extract_pivot_lang_from_model_name(row_obj.model_name)
            route_strategy = 'proximate-pivot' if row_obj.pivot_used else 'direct'
            if row_obj.model_name == 'tm-cache':
                route_strategy = 'tm-cache'
            elif row_obj.model_name == 'passthrough':
                route_strategy = 'passthrough'

            result_row = dict(row_data)
            result_row['pivot_language'] = pivot_language or None
            result_row['route_strategy'] = route_strategy
            results.append(result_row)

        return Response(
            {
                'count': total,
                'limit': limit,
                'results': results,
                'filters': {
                    'status': status_filter,
                    'source_lang': source_lang,
                    'target_lang': target_lang,
                    'q': query,
                },
            }
        )


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
        auth_error = _require_api_key_or_401(request)
        if auth_error:
            return auth_error

        if is_strict_offline_mode():
            return _build_error_response(
                code='tts.strict_offline.disabled',
                message=(
                    'Text-to-speech is disabled in strict offline mode '
                    'because edge-tts requires internet access.'
                ),
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                retryable=False,
            )

        serializer = TextToSpeechRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return _build_error_response(
                code='validation.tts.invalid_payload',
                message='Text-to-speech payload validation failed.',
                http_status=status.HTTP_400_BAD_REQUEST,
                details={
                    'errors': serializer.errors,
                    'summary': _flatten_serializer_errors(serializer.errors),
                },
                retryable=False,
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
            return _build_error_response(
                code='tts.validation.failed',
                message=message,
                http_status=status_code,
                retryable=False,
            )
        except Exception:
            logger.exception('Text-to-speech generation failed')
            return _build_error_response(
                code='tts.generation.failed',
                message=(
                    'Text-to-speech failed. edge-tts may need internet access '
                    'or a valid voice name.'
                ),
                http_status=status.HTTP_502_BAD_GATEWAY,
                retryable=True,
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
        strict_offline = is_strict_offline_mode()
        tts_available = is_edge_tts_available() and not strict_offline
        api_key_required = is_api_key_required()

        return Response({
            'status': 'ok',
            'engine': (
                CoreApiConfig.engine_name
                if nllb_loaded
                else 'offline-model-missing'
            ),
            'nllb_loaded': nllb_loaded,
            'lora_adapters': lora_modes,
            'api_key_required': api_key_required,
            'api_key_header': 'X-API-Key' if api_key_required else '',
            'api_key_configured': api_key_required,
            'tts_available': tts_available,
            'tts_engine': 'edge-tts' if tts_available else 'unavailable',
            'strict_offline_mode': strict_offline,
            'cloud_fallback_allowed': False,
            'inference_mode': 'offline-local-only',
            'supported_languages': list(SUPPORTED_LANGUAGES.keys()),
        })
