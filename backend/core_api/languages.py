"""
Canonical language configuration for Project Puente.

This module centralizes supported language scope, FLORES mappings, and reusable
choices so backend models/serializers/views stay contract-synchronized.
"""

SUPPORTED_LANGUAGES = {
    'auto': 'Auto-Detect',
    'en': 'English',
    'es': 'Spanish',
    'tl': 'Tagalog',
    'cbk': 'Chavacano (Zamboanga)',
    'hil': 'Hiligaynon',
    'ceb': 'Cebuano/Bisaya',
}

# Include auto for source-side requests only.
SOURCE_LANGUAGE_CODES = tuple(SUPPORTED_LANGUAGES.keys())
TARGET_LANGUAGE_CODES = tuple(code for code in SOURCE_LANGUAGE_CODES if code != 'auto')

LANGUAGE_CHOICES = [(code, SUPPORTED_LANGUAGES[code]) for code in SOURCE_LANGUAGE_CODES]
TARGET_LANGUAGE_CHOICES = [(code, SUPPORTED_LANGUAGES[code]) for code in TARGET_LANGUAGE_CODES]

FLORES_MAP = {
    'en': 'eng_Latn',
    'es': 'spa_Latn',
    'tl': 'tgl_Latn',
    'cbk': 'cbk_Latn',
    'ceb': 'ceb_Latn',
    'hil': 'hil_Latn',
    'auto': 'eng_Latn',
}

PIVOT_LANG = 'eng_Latn'
