"""
core_api/tests.py — Test suite for Project Puente backend.

Tests cover:
  - TranslateRequestSerializer validation (max 250 chars, mode choices)
  - WikiVozView API endpoint (search + full list)
  - HealthCheckView response shape
  - TranslationLog model creation
  - SUPPORTED_LANGUAGES scope (strict 5 + auto)
  - FLORES_MAP completeness
"""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from unittest.mock import patch

from .models import CulturalTerm, TranslationLog
from .serializers import TextToSpeechRequestSerializer, TranslateRequestSerializer
from .views import FLORES_MAP, SUPPORTED_LANGUAGES


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


class SupportedLanguagesTests(TestCase):
    """Ensure SUPPORTED_LANGUAGES is strictly scoped to 5 + auto."""

    def test_only_six_entries(self):
        expected = {'auto', 'en', 'tl', 'cbk', 'hil', 'ceb'}
        self.assertEqual(set(SUPPORTED_LANGUAGES.keys()), expected)

    def test_no_chinese_arabic_etc(self):
        for code in ['zh', 'ar', 'ja', 'ko', 'ru', 'es', 'fr', 'de']:
            self.assertNotIn(code, SUPPORTED_LANGUAGES)


class FloresMapTests(TestCase):
    """Validate FLORES code mapping completeness."""

    def test_all_languages_mapped(self):
        for code in SUPPORTED_LANGUAGES:
            self.assertIn(code, FLORES_MAP, f'{code} missing from FLORES_MAP')

    def test_hiligaynon_native_support(self):
        self.assertEqual(FLORES_MAP['hil'], 'hil_Latn')

    def test_chavacano_correct(self):
        self.assertEqual(FLORES_MAP['cbk'], 'cbk_Latn')


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
        self.assertIn('cbk', langs)
        self.assertNotIn('zh', langs)

    def test_health_reports_tts_fields(self):
        resp = self.client_api.get('/api/health/')
        self.assertIn('tts_available', resp.data)
        self.assertIn('tts_engine', resp.data)


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
