"""
core_api/tests.py — Test suite for Project Puente backend.

Tests cover:
  - TranslateRequestSerializer validation (max 250 chars, mode choices)
  - WikiVozView API endpoint (search + full list)
  - HealthCheckView response shape
  - TranslationLog model creation
    - SUPPORTED_LANGUAGES scope (includes Spanish control variable)
  - FLORES_MAP completeness
"""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from unittest.mock import patch

from .apps import CoreApiConfig
from .languages import FLORES_MAP, SUPPORTED_LANGUAGES
from .models import CulturalTerm, TranslationLog
from .serializers import (
    BackTranslationRequestSerializer,
    TextToSpeechRequestSerializer,
    TranslateRequestSerializer,
)
from .views import nllb_translate


class TranslateSerializerTests(TestCase):
    """Validate input constraints on the translation serializer."""

    def test_valid_payload(self):
        data = {
            'text': 'Buenos días',
            'source_lang': 'cbk',
            'target_lang': 'en',
            'mode': 'formal',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_text_max_length_250(self):
        data = {
            'text': 'x' * 251,
            'source_lang': 'en',
            'target_lang': 'cbk',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('text', s.errors)

    def test_text_at_limit(self):
        data = {
            'text': 'x' * 250,
            'source_lang': 'en',
            'target_lang': 'cbk',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_mode_default_formal(self):
        data = {
            'text': 'hello',
            'source_lang': 'en',
            'target_lang': 'cbk',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['mode'], 'formal')

    def test_invalid_mode_rejected(self):
        data = {
            'text': 'hello',
            'source_lang': 'en',
            'target_lang': 'cbk',
            'mode': 'slang',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('mode', s.errors)

    def test_empty_text_rejected(self):
        data = {
            'text': '',
            'source_lang': 'en',
            'target_lang': 'cbk',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_target_auto_rejected(self):
        data = {
            'text': 'hello',
            'source_lang': 'en',
            'target_lang': 'auto',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('target_lang', s.errors)

    def test_spanish_translation_pair_valid(self):
        data = {
            'text': 'Buenos días',
            'source_lang': 'es',
            'target_lang': 'hil',
        }
        s = TranslateRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)


class TextToSpeechSerializerTests(TestCase):
    """Validate Edge TTS request payloads."""

    def test_valid_payload(self):
        s = TextToSpeechRequestSerializer(data={
            'text': 'Buenas dias',
            'lang_code': 'cbk',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_lang_rejected(self):
        s = TextToSpeechRequestSerializer(data={
            'text': 'Hello',
            'lang_code': 'zh',
        })
        self.assertFalse(s.is_valid())
        self.assertIn('lang_code', s.errors)

    def test_spanish_lang_accepted(self):
        s = TextToSpeechRequestSerializer(data={
            'text': 'Buenos días',
            'lang_code': 'es',
        })
        self.assertTrue(s.is_valid(), s.errors)


class BackTranslationSerializerTests(TestCase):
    """Validate BTVL serializer payloads."""

    def test_valid_payload(self):
        s = BackTranslationRequestSerializer(data={
            'text': 'Ta ama yo contigo',
            'source_lang': 'cbk',
            'target_lang': 'en',
        })
        self.assertTrue(s.is_valid(), s.errors)

    def test_invalid_source_lang_rejected(self):
        s = BackTranslationRequestSerializer(data={
            'text': 'Hello',
            'source_lang': 'zh',
            'target_lang': 'en',
        })
        self.assertFalse(s.is_valid())
        self.assertIn('source_lang', s.errors)

    def test_target_lang_must_be_en(self):
        s = BackTranslationRequestSerializer(data={
            'text': 'Hello',
            'source_lang': 'cbk',
            'target_lang': 'cbk',
        })
        self.assertFalse(s.is_valid())
        self.assertIn('target_lang', s.errors)


class SupportedLanguagesTests(TestCase):
    """Ensure SUPPORTED_LANGUAGES includes thesis control-variable Spanish."""

    def test_expected_language_scope(self):
        expected = {'auto', 'en', 'es', 'tl', 'cbk', 'hil', 'ceb'}
        self.assertEqual(set(SUPPORTED_LANGUAGES.keys()), expected)

    def test_no_unapproved_languages(self):
        for code in ['zh', 'ar', 'ja', 'ko', 'ru', 'fr', 'de', 'it', 'pt']:
            self.assertNotIn(code, SUPPORTED_LANGUAGES)


class FloresMapTests(TestCase):
    """Validate FLORES code mapping completeness."""

    def test_all_languages_mapped(self):
        for code in SUPPORTED_LANGUAGES:
            self.assertIn(code, FLORES_MAP, f'{code} missing from FLORES_MAP')

    def test_hiligaynon_native_support(self):
        self.assertEqual(FLORES_MAP['hil'], 'hil_Latn')

    def test_spanish_mapping(self):
        self.assertEqual(FLORES_MAP['es'], 'spa_Latn')

    def test_chavacano_correct(self):
        self.assertEqual(FLORES_MAP['cbk'], 'cbk_Latn')


class NllbPivotLogicTests(TestCase):
    """Validate English-pivot behavior for non-English language pairs."""

    class _DummyTokenizer:
        def encode(self, text):
            return list(range(max(1, len((text or '').split()))))

    class _DummyModel:
        def set_adapter(self, adapter_name):
            return None

    @patch('core_api.views._infer_once')
    def test_spanish_to_hiligaynon_uses_english_pivot(self, mock_infer):
        mock_infer.side_effect = ['intermediate english', 'final hiligaynon']

        with patch.object(CoreApiConfig, 'nllb_tokenizer', self._DummyTokenizer()):
            with patch.object(CoreApiConfig, 'nllb_model', self._DummyModel()):
                with patch.object(CoreApiConfig, 'lora_adapters', {}):
                    result, _, _, _, pivot_used, _ = nllb_translate(
                        text='Buenos días',
                        src_code='es',
                        tgt_code='hil',
                        mode='formal',
                    )

        self.assertEqual(result, 'final hiligaynon')
        self.assertTrue(pivot_used)
        self.assertEqual(mock_infer.call_count, 2)

        first_call = mock_infer.call_args_list[0].args
        second_call = mock_infer.call_args_list[1].args

        self.assertEqual(first_call[3], 'spa_Latn')
        self.assertEqual(first_call[4], 'eng_Latn')
        self.assertEqual(second_call[3], 'eng_Latn')
        self.assertEqual(second_call[4], 'hil_Latn')


class CulturalTermModelTests(TestCase):
    """Test CulturalTerm model operations."""

    def setUp(self):
        CulturalTerm.objects.create(
            term='Satti',
            definition='A popular Zamboanga spicy stew.',
            language='Chavacano',
            category='food',
        )

    def test_case_insensitive_lookup(self):
        match = CulturalTerm.objects.filter(term__iexact='satti').first()
        self.assertIsNotNone(match)
        self.assertEqual(match.term, 'Satti')

    def test_icontains_search(self):
        results = CulturalTerm.objects.filter(term__icontains='sat')
        self.assertEqual(results.count(), 1)


class TranslationLogTests(TestCase):
    """Test TranslationLog model creation and querying."""

    def test_create_success_log(self):
        log = TranslationLog.objects.create(
            source_lang='en',
            target_lang='cbk',
            mode='formal',
            input_text='Good morning',
            input_chars=12,
            input_tokens=3,
            output_text='Buenos días',
            output_tokens=4,
            model_name='nllb-200-distilled-600M',
            pivot_used=False,
            latency_ms=1234.5,
            status='success',
        )
        self.assertEqual(log.status, 'success')
        self.assertFalse(log.pivot_used)

    def test_create_error_log(self):
        log = TranslationLog.objects.create(
            source_lang='ceb',
            target_lang='cbk',
            mode='street',
            input_text='test',
            input_chars=4,
            latency_ms=50.0,
            status='error',
            error_message='Model not loaded',
            model_name='none',
        )
        self.assertEqual(log.status, 'error')
        self.assertTrue(log.error_message)


class WikiVozViewTests(TestCase):
    """Test Wiki-Voz API endpoints."""

    def setUp(self):
        self.client_api = APIClient()
        CulturalTerm.objects.create(
            term='Vinta',
            definition='Traditional outrigger boat.',
            language='Zamboanga',
            category='culture',
        )

    def test_search_returns_results(self):
        resp = self.client_api.get('/api/wiki/', {'q': 'vinta'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['term'], 'Vinta')

    def test_empty_query_returns_all(self):
        resp = self.client_api.get('/api/wiki/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data['results']), 1)

    def test_no_match_returns_empty(self):
        resp = self.client_api.get('/api/wiki/', {'q': 'nonexistent'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results']), 0)


class HealthCheckViewTests(TestCase):
    """Test health check endpoint response."""

    def setUp(self):
        self.client_api = APIClient()

    def test_health_returns_ok(self):
        resp = self.client_api.get('/api/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ok')
        self.assertIn('engine', resp.data)
        self.assertIn('nllb_loaded', resp.data)
        self.assertIn('supported_languages', resp.data)

    def test_health_has_language_list(self):
        resp = self.client_api.get('/api/health/')
        langs = resp.data['supported_languages']
        self.assertIn('en', langs)
        self.assertIn('es', langs)
        self.assertIn('cbk', langs)
        self.assertNotIn('zh', langs)

    def test_health_reports_tts_fields(self):
        resp = self.client_api.get('/api/health/')
        self.assertIn('tts_available', resp.data)
        self.assertIn('tts_engine', resp.data)
        self.assertIn('api_key_required', resp.data)


class TextToSpeechViewTests(TestCase):
    """Test the edge-tts synthesis endpoint."""

    def setUp(self):
        self.client_api = APIClient()

    @patch('core_api.views._synthesize_speech_bytes')
    def test_tts_returns_audio(self, mock_synthesize):
        mock_synthesize.return_value = (b'fake-audio', 'en-US-EmmaMultilingualNeural')

        resp = self.client_api.post('/api/tts/', {
            'text': 'Hello from PUENTE',
            'lang_code': 'en',
        }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'audio/mpeg')
        self.assertEqual(resp['X-TTS-Voice'], 'en-US-EmmaMultilingualNeural')
        self.assertEqual(resp.content, b'fake-audio')

    def test_tts_invalid_payload_returns_400(self):
        resp = self.client_api.post('/api/tts/', {
            'text': 'Hello from PUENTE',
            'lang_code': 'zh',
        }, format='json')

        self.assertEqual(resp.status_code, 400)


class TranslateViewValidationTests(TestCase):
    """Test TranslateView input validation (without triggering ML)."""

    def setUp(self):
        self.client_api = APIClient()

    def test_missing_text_returns_400(self):
        resp = self.client_api.post('/api/translate/', {
            'source_lang': 'en',
            'target_lang': 'cbk',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_unsupported_language_returns_400(self):
        resp = self.client_api.post('/api/translate/', {
            'text': 'hello',
            'source_lang': 'zh',
            'target_lang': 'cbk',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_text_over_250_returns_400(self):
        resp = self.client_api.post('/api/translate/', {
            'text': 'x' * 251,
            'source_lang': 'en',
            'target_lang': 'cbk',
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class TranslationMemoryCacheTests(TestCase):
    """Validate normalized Translation Memory cache routing in TranslateView."""

    def setUp(self):
        self.client_api = APIClient()

    def test_cache_hit_bypasses_model_inference(self):
        TranslationLog.objects.create(
            source_lang='cbk',
            target_lang='en',
            mode='formal',
            input_text='Siyempre',
            input_chars=8,
            input_tokens=1,
            output_text='Of course',
            output_tokens=2,
            model_name='nllb-200-distilled-600M',
            pivot_used=False,
            latency_ms=1000.0,
            status='success',
        )

        with patch.object(CoreApiConfig, 'model_loaded', False):
            with patch('core_api.views.nllb_translate') as mock_translate:
                resp = self.client_api.post('/api/translate/', {
                    'text': '  siyempre  ',
                    'source_lang': 'cbk',
                    'target_lang': 'en',
                    'mode': 'street',
                }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['translated_text'], 'Of course')
        self.assertTrue(resp.data['is_cached'])
        self.assertEqual(resp.data['model'], 'tm-cache')
        mock_translate.assert_not_called()

    @patch('core_api.views.nllb_translate')
    def test_cache_miss_runs_inference(self, mock_translate):
        mock_translate.return_value = (
            'Syempre', 101.0, 2, 1, False, 'nllb-200-distilled-600M+lora-cbk-formal',
        )

        with patch.object(CoreApiConfig, 'model_loaded', True):
            resp = self.client_api.post('/api/translate/', {
                'text': 'Siyempre mabulig ko',
                'source_lang': 'cbk',
                'target_lang': 'en',
                'mode': 'formal',
            }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['is_cached'])
        self.assertEqual(resp.data['translated_text'], 'Syempre')
        mock_translate.assert_called_once()


class WikiVozPhraseInterceptorTests(TestCase):
    """Validate greedy longest-phrase interception for cultural term matching."""

    def setUp(self):
        self.client_api = APIClient()
        CulturalTerm.objects.create(
            term='siyempre',
            definition='Single-word term',
            language='cbk',
            category='expression',
        )
        CulturalTerm.objects.create(
            term='siyempre mabulig',
            definition='Longest phrase term',
            language='cbk',
            category='expression',
        )

    @patch('core_api.views.nllb_translate')
    def test_interceptor_picks_longest_phrase(self, mock_translate):
        mock_translate.return_value = (
            'Of course, I can help',
            133.2,
            5,
            5,
            False,
            'nllb-200-distilled-600M+lora-cbk-formal',
        )

        with patch.object(CoreApiConfig, 'model_loaded', True):
            resp = self.client_api.post('/api/translate/', {
                'text': 'Siyempre, mabulig ko con ustedes.',
                'source_lang': 'cbk',
                'target_lang': 'en',
                'mode': 'formal',
            }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertIn('wiki_voz', resp.data)
        self.assertEqual(resp.data['wiki_voz']['term'], 'siyempre mabulig')


class ApiKeyProtectionTests(TestCase):
    """Validate optional X-API-Key protection on mutating endpoints."""

    def setUp(self):
        self.client_api = APIClient()

    @override_settings(PUENTE_API_KEY='unit-test-key')
    def test_translate_requires_api_key_when_configured(self):
        resp = self.client_api.post('/api/translate/', {
            'text': 'hello',
            'source_lang': 'en',
            'target_lang': 'en',
        }, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertIn('error', resp.data)

    @override_settings(PUENTE_API_KEY='unit-test-key')
    def test_translate_accepts_valid_api_key(self):
        resp = self.client_api.post(
            '/api/translate/',
            {
                'text': 'hello',
                'source_lang': 'en',
                'target_lang': 'en',
            },
            format='json',
            HTTP_X_API_KEY='unit-test-key',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data.get('model'), 'passthrough')

    @override_settings(PUENTE_API_KEY='unit-test-key')
    def test_btvl_requires_api_key_when_configured(self):
        with patch.object(CoreApiConfig, 'model_loaded', False):
            resp = self.client_api.post('/api/btvl/', {
                'text': 'Ta ama yo contigo',
                'source_lang': 'cbk',
                'target_lang': 'en',
            }, format='json')

        self.assertEqual(resp.status_code, 401)
        self.assertIn('error', resp.data)

    @override_settings(PUENTE_API_KEY='unit-test-key')
    def test_tts_requires_api_key_when_configured(self):
        resp = self.client_api.post('/api/tts/', {
            'text': 'Hello from PUENTE',
            'lang_code': 'en',
        }, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertIn('error', resp.data)


class BackTranslationViewTests(TestCase):
    """Test BTVL endpoint behavior."""

    def setUp(self):
        self.client_api = APIClient()

    def test_btvl_missing_model_returns_503(self):
        with patch.object(CoreApiConfig, 'model_loaded', False):
            resp = self.client_api.post('/api/btvl/', {
                'text': 'Ta ama yo contigo',
                'source_lang': 'cbk',
                'target_lang': 'en',
            }, format='json')

        self.assertEqual(resp.status_code, 503)
        self.assertIn('error', resp.data)

    @patch('core_api.views.nllb_translate')
    def test_btvl_success(self, mock_translate):
        mock_translate.return_value = (
            'I love you', 842.7, 6, 4, False, 'nllb-200-distilled-600M+lora-cbk-formal',
        )

        with patch.object(CoreApiConfig, 'model_loaded', True):
            resp = self.client_api.post('/api/btvl/', {
                'text': 'Ta ama yo contigo',
                'source_lang': 'cbk',
                'target_lang': 'en',
            }, format='json')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['verified_text'], 'I love you')
        self.assertEqual(resp.data['source_lang'], 'cbk')
        self.assertEqual(resp.data['target_lang'], 'en')
        self.assertIn('latency_ms', resp.data)
        self.assertIn('tokens_in', resp.data)
        self.assertIn('tokens_out', resp.data)
        self.assertIn('pivot_used', resp.data)
        self.assertIn('model', resp.data)

    def test_btvl_invalid_payload_returns_400(self):
        resp = self.client_api.post('/api/btvl/', {
            'text': 'Ta ama yo contigo',
            'source_lang': 'zh',
            'target_lang': 'en',
        }, format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('errors', resp.data)
