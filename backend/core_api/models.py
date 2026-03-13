"""
core_api/models.py — Database models for Project Puente.

CulturalTerm: Wiki-Voz cultural terms and definitions.
TranslationLog: ISO 25010 metrics log for every translation request.
"""

from django.db import models


class CulturalTerm(models.Model):
    """Wiki-Voz: Cultural terms and definitions from Zamboanga."""

    term = models.CharField(
        max_length=200,
        unique=True,
        db_index=True,
        help_text='The cultural term or phrase (case-insensitive lookup).',
    )
    definition = models.TextField(
        help_text='Cultural definition and context for this term.',
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text='Optional image URL illustrating the term.',
    )
    language = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Language of origin (e.g. Chavacano, Tausug).',
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Category (food, culture, expression, etc.).',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['term']
        verbose_name = 'Cultural Term'
        verbose_name_plural = 'Cultural Terms'

    def __str__(self):
        return self.term


class TranslationLog(models.Model):
    """
    ISO 25010 metrics log for every translation request.

    Captures latency, token counts, pivot usage, and error states
    to generate Chapter 4 (Results) data for the capstone defense.
    """

    # Request metadata
    source_lang = models.CharField(max_length=10)
    target_lang = models.CharField(max_length=10)
    mode = models.CharField(
        max_length=10,
        choices=[('formal', 'Formal'), ('street', 'Street')],
    )
    input_text = models.TextField()
    input_chars = models.PositiveIntegerField()
    input_tokens = models.PositiveIntegerField(default=0)

    # Response metadata
    output_text = models.TextField(blank=True, default='')
    output_tokens = models.PositiveIntegerField(default=0)
    model_name = models.CharField(max_length=100)
    pivot_used = models.BooleanField(default=False)

    # ISO 25010: Performance Efficiency
    latency_ms = models.FloatField(
        help_text='Total inference time in milliseconds.',
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('error', 'Error'),
            ('timeout', 'Timeout'),
        ],
    )
    error_message = models.TextField(blank=True, default='')

    # ISO 25010: Functional Suitability (Wiki-Voz interception)
    wiki_voz_triggered = models.BooleanField(default=False)
    wiki_voz_term = models.CharField(max_length=200, blank=True, default='')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Translation Log'
        verbose_name_plural = 'Translation Logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['source_lang', 'target_lang']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'[{self.status}] {self.source_lang}→{self.target_lang} {self.latency_ms:.0f}ms'

