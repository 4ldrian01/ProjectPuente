"""
core_api/serializers.py — DRF Serializers for Project Puente.
"""

from rest_framework import serializers
from .languages import SOURCE_LANGUAGE_CODES, TARGET_LANGUAGE_CODES
from .models import CulturalTerm, TranslationLog


# BTVL is used for semantic verification checks in the thesis workflow.
# Keep this narrow and explicit to avoid unsupported reverse-target tests.
BTVL_TARGET_LANGUAGE_CODES = ('en', 'es', 'tl')


def _normalize_text_input(value):
    return ' '.join(str(value or '').split()).strip()


class TranslateRequestSerializer(serializers.Serializer):
    """Validates incoming translation requests.

    Max 250 characters to prevent OOM on 8GB RAM with NLLB-200 inference.
    """
    text = serializers.CharField(max_length=250, required=True)
    source_lang = serializers.ChoiceField(
        choices=SOURCE_LANGUAGE_CODES,
        required=True,
    )
    target_lang = serializers.ChoiceField(
        choices=TARGET_LANGUAGE_CODES,
        required=True,
    )
    mode = serializers.ChoiceField(
        choices=['formal', 'street'],
        default='formal',
        required=False,
    )

    def validate_text(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Text is required and cannot be empty.')
        if len(normalized) > 250:
            raise serializers.ValidationError('Text exceeds 250-character limit.')
        return normalized


class BackTranslationRequestSerializer(serializers.Serializer):
    """Validates BTVL requests for en/es/tl reverse verification targets."""

    text = serializers.CharField(max_length=250, required=True)
    source_lang = serializers.ChoiceField(
        choices=TARGET_LANGUAGE_CODES,
        required=True,
    )
    target_lang = serializers.ChoiceField(
        choices=BTVL_TARGET_LANGUAGE_CODES,
        default='en',
        required=False,
    )

    def validate_text(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Text is required and cannot be empty.')
        if len(normalized) > 250:
            raise serializers.ValidationError('Text exceeds 250-character limit.')
        return normalized


class TextToSpeechRequestSerializer(serializers.Serializer):
    """Validates Edge TTS synthesis requests."""

    text = serializers.CharField(max_length=1000, required=True, trim_whitespace=True)
    lang_code = serializers.ChoiceField(
        choices=SOURCE_LANGUAGE_CODES,
        default='en',
        required=False,
    )
    voice = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_text(self, value):
        normalized = _normalize_text_input(value)
        if not normalized:
            raise serializers.ValidationError('Text is required and cannot be empty.')
        return normalized


class CulturalTermSerializer(serializers.ModelSerializer):
    """Serializes CulturalTerm model for Wiki-Voz responses."""

    class Meta:
        model = CulturalTerm
        fields = ['id', 'term', 'definition', 'image_url', 'language', 'category', 'created_at']
        read_only_fields = ['id', 'created_at']


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
