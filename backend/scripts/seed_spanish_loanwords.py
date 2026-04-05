"""Seed Spanish-derived Chavacano loanwords into CulturalTerm.

Usage:
  python backend/scripts/seed_spanish_loanwords.py
  python backend/scripts/seed_spanish_loanwords.py --dry-run
  python backend/scripts/seed_spanish_loanwords.py --skip-existing

Default CSV:
  datasets/raw/02_Chavacano/spanish_loanwords_mapping.csv
"""

import argparse
import csv
import os
import sys

# Ensure backend folder is importable so Django settings can be loaded.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django

django.setup()

from django.db import transaction

from core_api.models import CulturalTerm


DEFAULT_CSV_PATH = os.path.join(
    PROJECT_ROOT,
    'datasets',
    'raw',
    '02_Chavacano',
    'spanish_loanwords_mapping.csv',
)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Seed spanish_loanwords_mapping.csv into CulturalTerm.',
    )
    parser.add_argument(
        '--csv',
        type=str,
        default=DEFAULT_CSV_PATH,
        help='Path to spanish_loanwords_mapping.csv',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview inserts/updates without writing to DB.',
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Do not update existing terms (matched case-insensitively).',
    )
    return parser.parse_args()


def normalize_row(row):
    term = (row.get('term') or '').strip()
    spanish_origin = (row.get('spanish_origin') or '').strip()
    english_gloss = (row.get('english_gloss') or '').strip()
    definition = (row.get('definition') or '').strip()
    language = (row.get('language') or '').strip() or 'Chavacano'
    category = (row.get('category') or '').strip() or 'loanword'
    image_url = (row.get('image_url') or '').strip()

    if not term:
        return None

    if not definition:
        details = []
        if english_gloss:
            details.append(f'English gloss: {english_gloss}.')
        if spanish_origin:
            details.append(f'Spanish origin: {spanish_origin}.')
        definition = ' '.join(details) if details else 'Spanish-derived Chavacano loanword.'

    return {
        'term': term,
        'definition': definition,
        'language': language,
        'category': category,
        'image_url': image_url,
    }


def process_rows(rows, dry_run=False, skip_existing=False):
    created = 0
    updated = 0
    skipped = 0
    invalid = 0

    for row in rows:
        normalized = normalize_row(row)
        if not normalized:
            invalid += 1
            continue

        existing = CulturalTerm.objects.filter(term__iexact=normalized['term']).first()

        if existing:
            if skip_existing:
                skipped += 1
                continue

            changed = False
            for field in ('definition', 'language', 'category', 'image_url'):
                new_value = normalized[field]
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
            CulturalTerm.objects.create(**normalized)
        created += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'invalid': invalid,
    }


def load_csv_rows(csv_path):
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f'CSV file not found: {csv_path}')

    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or 'term' not in reader.fieldnames:
            raise ValueError('CSV must include at least the "term" column.')
        return list(reader)


def main():
    args = parse_args()
    csv_path = os.path.abspath(args.csv)

    print('SEED_SPANISH_LOANWORDS_START')
    print(f'CSV_PATH:{csv_path}')
    print(f'DRY_RUN:{args.dry_run}')
    print(f'SKIP_EXISTING:{args.skip_existing}')

    rows = load_csv_rows(csv_path)
    print(f'CSV_ROWS:{len(rows)}')

    if args.dry_run:
        summary = process_rows(rows, dry_run=True, skip_existing=args.skip_existing)
    else:
        with transaction.atomic():
            summary = process_rows(rows, dry_run=False, skip_existing=args.skip_existing)

    print('SEED_SPANISH_LOANWORDS_DONE')
    print(f"CREATED:{summary['created']}")
    print(f"UPDATED:{summary['updated']}")
    print(f"SKIPPED:{summary['skipped']}")
    print(f"INVALID:{summary['invalid']}")


if __name__ == '__main__':
    main()
