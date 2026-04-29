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
    # 🚀 THE FIX: Tricks NLLB into generating Chavacano via Spanish weights
    'cbk': 'spa_Latn', 
    'ceb': 'ceb_Latn',
    'hil': 'hil_Latn',
    'auto': 'eng_Latn',
}

# Direct inference is always attempted first. If confidence is critically low,
# a proximate pivot can be used for selected pairs.
DIRECT_INFERENCE_CONFIDENCE_THRESHOLD = 0.28

# Local language scope for Austronesian proximate pivot routing.
LOCAL_LANGUAGE_CODES = frozenset({'tl', 'cbk', 'ceb', 'hil'})


def _normalize_lang_code(code):
    return str(code or '').strip().casefold()


def is_local_language(code):
    return _normalize_lang_code(code) in LOCAL_LANGUAGE_CODES


def is_local_to_local_pair(source_lang, target_lang):
    src = _normalize_lang_code(source_lang)
    tgt = _normalize_lang_code(target_lang)
    return src in LOCAL_LANGUAGE_CODES and tgt in LOCAL_LANGUAGE_CODES and src != tgt


def select_proximate_pivot(source_lang, target_lang):
    """
    Proximate-pivot routing matrix (English is never selected as pivot):

    - cbk-involved pairs prefer Spanish pivot (`es`) when usable
    - local<->local pairs prefer Tagalog (`tl`)
    - if Tagalog is already part of the pair, use Cebuano (`ceb`)
    """
    src = _normalize_lang_code(source_lang)
    tgt = _normalize_lang_code(target_lang)

    if not src or not tgt or src == tgt:
        return ''

    candidate = ''

    if 'cbk' in {src, tgt}:
        candidate = 'es'
    elif is_local_to_local_pair(src, tgt):
        candidate = 'ceb' if 'tl' in {src, tgt} else 'tl'

    # Candidate must be a supported non-English intermediate that is
    # different from source/target.
    if candidate in {'', 'en', src, tgt}:
        return ''

    return candidate
