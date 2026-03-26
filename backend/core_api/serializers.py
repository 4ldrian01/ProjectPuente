"""
core_api/serializers.py — DRF Serializers for Project Puente.
"""

from rest_framework import serializers
from .models import CulturalTerm


class TranslateRequestSerializer(serializers.Serializer):
    """Validates incoming translation requests.

    Max 250 characters to prevent OOM on 8GB RAM with NLLB-200 inference.
    """
    text = serializers.CharField(max_length=250, required=True)
    source_lang = serializers.ChoiceField(
        choices=['auto', 'en', 'tl', 'cbk', 'hil', 'ceb'],
        required=True,
    )
    target_lang = serializers.ChoiceField(
        choices=['en', 'tl', 'cbk', 'hil', 'ceb'],
        required=True,
    )
    mode = serializers.ChoiceField(
        choices=['formal', 'street'],
        default='formal',
        required=False,
    )


class TextToSpeechRequestSerializer(serializers.Serializer):
    """Validates Edge TTS synthesis requests."""

    text = serializers.CharField(max_length=1000, required=True, trim_whitespace=True)
    lang_code = serializers.ChoiceField(
        choices=['auto', 'en', 'tl', 'cbk', 'hil', 'ceb'],
        default='en',
        required=False,
    )
    voice = serializers.CharField(max_length=100, required=False, allow_blank=True)


class CulturalTermSerializer(serializers.ModelSerializer):
    """Serializes CulturalTerm model for Wiki-Voz responses."""

    class Meta:
        model = CulturalTerm
        fields = ['id', 'term', 'definition', 'image_url', 'language', 'category', 'created_at']
        read_only_fields = ['id', 'created_at']
