from django.contrib import admin
from .models import CulturalTerm, TranslationLog


@admin.register(CulturalTerm)
class CulturalTermAdmin(admin.ModelAdmin):
    list_display = ('term', 'language', 'category', 'definition', 'created_at')
    search_fields = ('term', 'definition')
    list_filter = ('language', 'category', 'created_at')
    ordering = ('term',)


@admin.register(TranslationLog)
class TranslationLogAdmin(admin.ModelAdmin):
    """ISO 25010 metrics dashboard in Django Admin."""
    list_display = (
        'created_at', 'source_lang', 'target_lang', 'mode',
        'latency_ms', 'status', 'pivot_used', 'wiki_voz_triggered',
    )
    list_filter = (
        'status', 'mode', 'source_lang', 'target_lang',
        'pivot_used', 'wiki_voz_triggered',
    )
    search_fields = ('input_text', 'output_text', 'error_message')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

