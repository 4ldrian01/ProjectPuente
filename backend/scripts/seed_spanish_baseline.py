"""Seed pure European Spanish baseline terms into CulturalTerm.

Usage:
  python backend/scripts/seed_spanish_baseline.py
  python backend/scripts/seed_spanish_baseline.py --dry-run
  python backend/scripts/seed_spanish_baseline.py --skip-existing
"""

import argparse
import os
import sys

# Ensure backend folder is importable so Django settings can be loaded.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django

django.setup()

from django.db import transaction

from core_api.models import CulturalTerm


SPANISH_BASELINE_ENTRIES = [
    {
        'term': 'Seguro',
        'definition': 'Certain; safe; secure. Used as a pure European Spanish baseline control term.',
        'language': 'es',
        'category': 'Spanish Baseline',
        'image_url': '',
    },
    {
        'term': 'Para siempre',
        'definition': 'Forever; for always. Baseline phrase for semantic comparison against local loanword usage.',
        'language': 'es',
        'category': 'Spanish Baseline',
        'image_url': '',
    },
    {
        'term': 'Buenos días',
        'definition': 'Good morning. Standard European Spanish greeting baseline for pronunciation and translation checks.',
        'language': 'es',
        'category': 'Spanish Baseline',
        'image_url': '',
    },
    {
        'term': 'Estoy de acuerdo',
        'definition': 'I agree. Baseline agreement expression used for control-variable translation evaluation.',
        'language': 'es',
        'category': 'Spanish Baseline',
        'image_url': '',
    },
    {
        'term': 'Muchas gracias',
        'definition': 'Thank you very much. Canonical Spanish courtesy phrase for baseline sociolinguistic contrast.',
        'language': 'es',
        'category': 'Spanish Baseline',
        'image_url': '',
    },
]


def parse_args():
    parser = argparse.ArgumentParser(
        description='Seed 5 pure European Spanish baseline terms into CulturalTerm.',
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


def process_entries(entries, dry_run=False, skip_existing=False):
    created = 0
    updated = 0
    skipped = 0

    for entry in entries:
        existing = CulturalTerm.objects.filter(term__iexact=entry['term']).first()

        if existing:
            if skip_existing:
                skipped += 1
                continue

            changed = False
            for field in ('definition', 'language', 'category', 'image_url'):
                new_value = entry[field]
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
            CulturalTerm.objects.create(**entry)
        created += 1

    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
    }


def main():
    args = parse_args()

    print('SEED_SPANISH_BASELINE_START')
    print(f'DRY_RUN:{args.dry_run}')
    print(f'SKIP_EXISTING:{args.skip_existing}')
    print(f'BASELINE_COUNT:{len(SPANISH_BASELINE_ENTRIES)}')

    if args.dry_run:
        summary = process_entries(
            SPANISH_BASELINE_ENTRIES,
            dry_run=True,
            skip_existing=args.skip_existing,
        )
    else:
        with transaction.atomic():
            summary = process_entries(
                SPANISH_BASELINE_ENTRIES,
                dry_run=False,
                skip_existing=args.skip_existing,
            )

    print('SEED_SPANISH_BASELINE_DONE')
    print(f"CREATED:{summary['created']}")
    print(f"UPDATED:{summary['updated']}")
    print(f"SKIPPED:{summary['skipped']}")


if __name__ == '__main__':
    main()
