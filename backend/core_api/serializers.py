"""
core_api/serializers.py — DRF Serializers for Project Puente.
"""

from rest_framework import serializers
from .languages import SOURCE_LANGUAGE_CODES, TARGET_LANGUAGE_CODES
from .models import CulturalTerm, TranslationLog


WIKI_ALLOWED_LANGUAGES = (
    'Chavacano',
    'Cebuano/Bisaya',
    'Hiligaynon',
    'Spanish',
)

WIKI_ALLOWED_CATEGORIES = (
    'Idioms',
    'False Cognates',
    'Honorifics',
    'Expressions',
)

WIKI_CATEGORY_ALIASES = {
    'idiom': 'Idioms',
    'idioms': 'Idioms',
    'false cognate': 'False Cognates',
    'false cognates': 'False Cognates',
    'honorific': 'Honorifics',
    'honorifics': 'Honorifics',
    'expression': 'Expressions',
    'expressions': 'Expressions',
    'culture': 'Expressions',
}

WIKI_LANGUAGE_ALIASES = {
    'cbk': 'Chavacano',
    'chavacano': 'Chavacano',
    'chavacano (zamboanga)': 'Chavacano',
    'zamboanga': 'Chavacano',
    'ceb': 'Cebuano/Bisaya',
    'cebuano': 'Cebuano/Bisaya',
    'bisaya': 'Cebuano/Bisaya',
    'cebuano/bisaya': 'Cebuano/Bisaya',
    'hil': 'Hiligaynon',
    'hiligaynon': 'Hiligaynon',
    'ilonggo': 'Hiligaynon',
    'es': 'Spanish',
    'spanish': 'Spanish',
}


# BTVL is used for semantic verification checks in the thesis workflow.
# Keep this narrow and explicit to avoid unsupported reverse-target tests.
BTVL_TARGET_LANGUAGE_CODES = ('en', 'es', 'tl')

FLORES_TO_APP_CODE = {
    'eng_latn': 'en',
    'spa_latn': 'es',
    'tgl_latn': 'tl',
    'cbk_latn': 'cbk',
    'ceb_latn': 'ceb',
    'hil_latn': 'hil',
}


def _normalize_text_input(value):
    return ' '.join(str(value or '').split()).strip()


def _normalize_language_code(value, allowed_codes):
    raw = str(value or '').strip()
    normalized = raw.casefold()
    normalized = FLORES_TO_APP_CODE.get(normalized, normalized)
    if normalized not in allowed_codes:
        raise serializers.ValidationError(f'"{raw}" is not a valid choice.')
    return normalized


class TranslateRequestSerializer(serializers.Serializer):
    """Validates incoming translation requests.

    Max 250 characters to prevent OOM on 8GB RAM with NLLB-200 inference.
    """
    text = serializers.CharField(max_length=250, required=True)
    source_lang = serializers.CharField(required=True)
    target_lang = serializers.CharField(required=True)
    mode = serializers.ChoiceField(
        choices=['formal', 'street'],
        default='formal',
        required=False,
    )
    use_cache = serializers.BooleanField(default=True, required=False)

    def validate_text(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Text is required and cannot be empty.')
        if len(normalized) > 250:
            raise serializers.ValidationError('Text exceeds 250-character limit.')
        return normalized

    def validate_source_lang(self, value):
        return _normalize_language_code(value, SOURCE_LANGUAGE_CODES)

    def validate_target_lang(self, value):
        return _normalize_language_code(value, TARGET_LANGUAGE_CODES)


class BackTranslationRequestSerializer(serializers.Serializer):
    """Validates BTVL requests for en/es/tl reverse verification targets."""

    text = serializers.CharField(max_length=250, required=True)
    source_lang = serializers.CharField(required=True)
    target_lang = serializers.CharField(default='en', required=False)

    def validate_text(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Text is required and cannot be empty.')
        if len(normalized) > 250:
            raise serializers.ValidationError('Text exceeds 250-character limit.')
        return normalized

    def validate_source_lang(self, value):
        return _normalize_language_code(value, TARGET_LANGUAGE_CODES)

    def validate_target_lang(self, value):
        return _normalize_language_code(value, BTVL_TARGET_LANGUAGE_CODES)


class TextToSpeechRequestSerializer(serializers.Serializer):
    """Validates Edge TTS synthesis requests."""

    text = serializers.CharField(max_length=1000, required=True, trim_whitespace=True)
    lang_code = serializers.CharField(default='en', required=False)
    voice = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_text(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Text is required and cannot be empty.')
        return normalized

    def validate_lang_code(self, value):
        return _normalize_language_code(value, SOURCE_LANGUAGE_CODES)


class CulturalTermSerializer(serializers.ModelSerializer):
    """Serializes CulturalTerm model for Wiki-Voz responses."""

    trigger_words = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        allow_empty=False,
    )

    class Meta:
        model = CulturalTerm
        fields = [
            'id',
            'term',
            'definition',
            'trigger_words',
            'image_url',
            'language',
            'category',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_term(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Term is required.')
        return normalized

    def validate_definition(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Definition is required.')
        return normalized

    def validate_category(self, value):
        normalized = _normalize_text_input(value)
        canonical = WIKI_CATEGORY_ALIASES.get(normalized.casefold(), normalized)
        if canonical not in WIKI_ALLOWED_CATEGORIES:
            raise serializers.ValidationError(
                f'Category must be one of: {", ".join(WIKI_ALLOWED_CATEGORIES)}.'
            )
        return canonical

    def validate_language(self, value):
        normalized = _normalize_text_input(value)
        canonical = WIKI_LANGUAGE_ALIASES.get(normalized.casefold(), normalized)
        if canonical not in WIKI_ALLOWED_LANGUAGES:
            raise serializers.ValidationError(
                f'Language must be one of: {", ".join(WIKI_ALLOWED_LANGUAGES)}.'
            )
        return canonical

    def validate_trigger_words(self, value):
        cleaned = []
        seen = set()
        for item in value or []:
            normalized = _normalize_text_input(item)
            if not normalized:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)

        if not cleaned:
            raise serializers.ValidationError('At least one trigger word is required.')

        return cleaned

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if 'trigger_words' not in attrs:
            fallback_term = attrs.get('term')
            if fallback_term:
                attrs['trigger_words'] = [fallback_term.casefold()]
        return attrs


class TranslationLogListSerializer(serializers.ModelSerializer):
    """Serializes TranslationLog rows for observer/activity dashboards."""

    class Meta:
        model = TranslationLog
        fields = [
            'id',
            'created_at',
            'source_lang',
            'target_lang',
            'mode',
            'status',
            'latency_ms',
            'input_chars',
            'input_tokens',
            'output_tokens',
            'pivot_used',
            'route_confidence',
            'model_name',
            'wiki_voz_triggered',
            'wiki_voz_term',
            'error_message',
            'input_text',
            'output_text',
        ]
