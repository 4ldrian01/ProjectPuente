"""Ingest lexicon pillar data into CulturalTerm.

Architectural note:
- Lexicon rows (word, POS, definition) are retrieval assets for inference/UI.
- They should not be merged into seq2seq training tensors because they are not
  aligned source-target sentence pairs and can distort supervised loss.

Usage examples:
  python manage.py ingest_lexicon
  python manage.py ingest_lexicon --input ../datasets/processed/001_chavacano/chavacano_lexicon_nllb.json
  python manage.py ingest_lexicon --dry-run --skip-existing
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core_api.models import CulturalTerm

LANGUAGE_NORMALIZATION = {
    'cbk_Latn': 'Chavacano',
    'eng_Latn': 'English',
    'spa_Latn': 'Spanish',
    'tgl_Latn': 'Tagalog',
    'ceb_Latn': 'Cebuano',
    'hil_Latn': 'Hiligaynon',
}

WHITESPACE_RE = re.compile(r'\s+')


def normalize_text(value: object) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = WHITESPACE_RE.sub(' ', text)
    return text.strip()


def normalize_language(value: str) -> str:
    text = normalize_text(value)
    if not text:
        return 'Chavacano'
    return LANGUAGE_NORMALIZATION.get(text, text)


def load_entries(path: Path) -> List[Dict[str, object]]:
    payload = json.loads(path.read_text(encoding='utf-8'))

    if isinstance(payload, dict):
        entries = payload.get('entries', [])
        if isinstance(entries, list):
            return [item for item in entries if isinstance(item, dict)]
        raise ValueError('Expected object payload with list field "entries".')

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    raise ValueError('Expected JSON list or object with list field "entries".')


def map_lexicon_entry(entry: Dict[str, object]) -> Optional[Dict[str, str]]:
    term = normalize_text(entry.get('word') or entry.get('term') or entry.get('lemma'))
    definition = normalize_text(
        entry.get('definition')
        or entry.get('english')
        or entry.get('gloss')
        or entry.get('meaning')
    )

    if not term or not definition:
        return None

    pos = normalize_text(entry.get('pos') or entry.get('type'))
    category = normalize_text(entry.get('category')) or (f'lexicon:{pos}' if pos else 'lexicon')

    language = normalize_language(str(entry.get('language') or 'cbk_Latn'))
    image_url = normalize_text(entry.get('image_url'))

    return {
        'term': term,
        'definition': definition,
        'language': language,
        'category': category,
        'image_url': image_url,
    }


class Command(BaseCommand):
    help = 'Ingest structured lexicon JSON files into CulturalTerm for runtime intercepts.'

    def add_arguments(self, parser):
        project_root = Path(__file__).resolve().parents[4]
        default_inputs = [
            project_root / 'datasets' / 'processed' / '001_chavacano' / 'chavacano_lexicon_nllb.json',
            project_root / 'datasets' / 'processed' / '01_chavacano' / 'chavacano_lexicon.json',
        ]

        parser.add_argument(
            '--input',
            action='append',
            default=[str(path) for path in default_inputs],
            help='Lexicon JSON file path. Can be repeated.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and validate, but do not write to the database.',
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Do not update existing terms (case-insensitive match).',
        )

    def handle(self, *args, **options):
        input_paths = [Path(raw).expanduser().resolve() for raw in options['input']]
        dry_run = bool(options['dry_run'])
        skip_existing = bool(options['skip_existing'])

        for path in input_paths:
            if not path.is_file():
                raise CommandError(f'Input file not found: {path}')

        created = 0
        updated = 0
        skipped = 0
        invalid = 0

        @transaction.atomic
        def _run() -> None:
            nonlocal created, updated, skipped, invalid

            for path in input_paths:
                entries = load_entries(path)
                self.stdout.write(f'INGEST_FILE:{path} ENTRIES:{len(entries)}')

                for entry in entries:
                    mapped = map_lexicon_entry(entry)
                    if mapped is None:
                        invalid += 1
                        continue

                    existing = CulturalTerm.objects.filter(term__iexact=mapped['term']).first()

                    if existing:
                        if skip_existing:
                            skipped += 1
                            continue

                        changed = False
                        for field in ('definition', 'language', 'category', 'image_url'):
                            new_value = mapped[field]
                            if getattr(existing, field) != new_value:
                                setattr(existing, field, new_value)
                                changed = True

                        if changed:
                            if not dry_run:
                                existing.save(update_fields=['definition', 'language', 'category', 'image_url', 'updated_at'])
                            updated += 1
                        else:
                            skipped += 1
                        continue

                    if not dry_run:
                        CulturalTerm.objects.create(**mapped)
                    created += 1

            if dry_run:
                # Roll back dry-run writes, even if no writes were attempted.
                transaction.set_rollback(True)

        _run()

        self.stdout.write('INGEST_LEXICON_DONE')
        self.stdout.write(f'DRY_RUN:{dry_run}')
        self.stdout.write(f'SKIP_EXISTING:{skip_existing}')
        self.stdout.write(f'CREATED:{created}')
        self.stdout.write(f'UPDATED:{updated}')
        self.stdout.write(f'SKIPPED:{skipped}')
        self.stdout.write(f'INVALID:{invalid}')
