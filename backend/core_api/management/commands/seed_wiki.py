"""Seed CulturalTerm rows from cleaned wiki_voz_kb.json.

Usage:
  python manage.py seed_wiki
  python manage.py seed_wiki --path ../datasets/processed/pillars/parallel/wiki_voz_kb.json
  python manage.py seed_wiki --dry-run
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core_api.models import CulturalTerm

ALLOWED_LANGUAGES = {
    "Chavacano",
    "Cebuano/Bisaya",
    "Hiligaynon",
    "Spanish",
}

ALLOWED_CATEGORIES = {
    "Idioms",
    "False Cognates",
    "Honorifics",
    "Expressions",
}

CATEGORY_ALIASES = {
    "idiom": "Idioms",
    "idioms": "Idioms",
    "false cognate": "False Cognates",
    "false cognates": "False Cognates",
    "honorific": "Honorifics",
    "honorifics": "Honorifics",
    "expression": "Expressions",
    "expressions": "Expressions",
    "culture": "Expressions",
}

LANGUAGE_ALIASES = {
    "cbk": "Chavacano",
    "chavacano": "Chavacano",
    "chavacano (zamboanga)": "Chavacano",
    "zamboanga": "Chavacano",
    "ceb": "Cebuano/Bisaya",
    "cebuano": "Cebuano/Bisaya",
    "bisaya": "Cebuano/Bisaya",
    "cebuano/bisaya": "Cebuano/Bisaya",
    "hil": "Hiligaynon",
    "hiligaynon": "Hiligaynon",
    "ilonggo": "Hiligaynon",
    "es": "Spanish",
    "spanish": "Spanish",
}

SPLIT_RE = re.compile(r"[,|]")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    text = str(value or "")
    text = unicodedata.normalize("NFKC", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_category(value: Any) -> Optional[str]:
    raw = normalize_text(value)
    if not raw:
        return None

    canonical = CATEGORY_ALIASES.get(raw.casefold(), raw)
    if canonical not in ALLOWED_CATEGORIES:
        return None
    return canonical


def normalize_language(value: Any) -> Optional[str]:
    raw = normalize_text(value)
    if not raw:
        return None

    canonical = LANGUAGE_ALIASES.get(raw.casefold(), raw)
    if canonical not in ALLOWED_LANGUAGES:
        return None
    return canonical


def normalize_trigger_words(value: Any, fallback_term: str) -> List[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = SPLIT_RE.split(value)
    else:
        raw_items = []

    dedupe = set()
    output: List[str] = []
    for item in raw_items:
        cleaned = normalize_text(item)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in dedupe:
            continue
        dedupe.add(key)
        output.append(cleaned)

    if output:
        return output

    fallback = normalize_text(fallback_term)
    return [fallback.casefold()] if fallback else []


def load_entries(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("wiki_voz_entries", [])
    else:
        rows = []

    if not isinstance(rows, list):
        raise ValueError("Expected JSON array or object containing wiki_voz_entries list.")

    return [row for row in rows if isinstance(row, dict)]


def default_seed_path() -> Path:
    project_root = Path(__file__).resolve().parents[4]
    candidates = [
        project_root / "datasets" / "processed" / "pillars" / "parallel" / "wiki_voz_kb.json",
        project_root / "frontend" / "public" / "data" / "wiki_voz_kb.json",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return candidates[0]


def map_row(row: Dict[str, Any]) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    term = normalize_text(row.get("term") or row.get("title"))
    definition = normalize_text(row.get("definition") or row.get("description"))
    language = normalize_language(row.get("language"))
    category = normalize_category(row.get("category"))

    if not term or not definition or not language or not category:
        return None

    image_url = normalize_text(row.get("image_url") or row.get("imageUrl"))
    trigger_words = normalize_trigger_words(
        row.get("trigger_words") or row.get("triggerWords"),
        fallback_term=term,
    )

    defaults = {
        "definition": definition,
        "trigger_words": trigger_words,
        "image_url": image_url,
        "category": category,
    }
    return term, language, defaults


class Command(BaseCommand):
    help = "Seed the CulturalTerm table from cleaned wiki_voz_kb.json using update_or_create()."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(default_seed_path()),
            help="Path to wiki_voz_kb.json (default: canonical dataset path).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and simulate writes without persisting changes.",
        )
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Delete CulturalTerm rows not present in the JSON after upsert.",
        )

    def handle(self, *args, **options):
        json_path = Path(options["path"]).expanduser().resolve()
        dry_run = bool(options["dry_run"])
        prune = bool(options["prune"])

        if not json_path.is_file():
            raise CommandError(f"JSON file not found: {json_path}")

        try:
            rows = load_entries(json_path)
        except Exception as exc:
            raise CommandError(f"Failed to parse JSON file: {exc}") from exc

        created = 0
        updated = 0
        invalid = 0
        deleted = 0
        seeded_ids = set()

        @transaction.atomic
        def _seed() -> None:
            nonlocal created, updated, invalid, deleted

            for row in rows:
                mapped = map_row(row)
                if mapped is None:
                    invalid += 1
                    continue

                term, language, defaults = mapped
                obj, was_created = CulturalTerm.objects.update_or_create(
                    term=term,
                    language=language,
                    defaults=defaults,
                )
                seeded_ids.add(obj.pk)
                if was_created:
                    created += 1
                else:
                    updated += 1

            if prune:
                deleted, _ = CulturalTerm.objects.exclude(pk__in=seeded_ids).delete()

            if dry_run:
                transaction.set_rollback(True)

        _seed()

        self.stdout.write("SEED_WIKI_DONE")
        self.stdout.write(f"path: {json_path}")
        self.stdout.write(f"dry_run: {dry_run}")
        self.stdout.write(f"prune: {prune}")
        self.stdout.write(f"rows_read: {len(rows)}")
        self.stdout.write(f"created: {created}")
        self.stdout.write(f"updated: {updated}")
        self.stdout.write(f"invalid_skipped: {invalid}")
        self.stdout.write(f"deleted: {deleted}")
