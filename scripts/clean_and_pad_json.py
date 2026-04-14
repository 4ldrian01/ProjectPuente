#!/usr/bin/env python3
"""Clean and pad Wiki-Voz JSON to the strict 200-entry target.

What this script does:
1) Loads wiki_voz_kb.json.
2) Normalizes categories to this strict taxonomy:
   - Idioms
   - False Cognates
   - Honorifics
   - Expressions
3) Drops entries that still cannot be mapped safely.
4) Ensures exactly 50 entries per target language:
   - Chavacano
   - Cebuano/Bisaya
   - Hiligaynon
   - Spanish
5) Generates placeholder entries for missing rows with [PENDING] in title.
6) Writes the cleaned 200-entry dataset back to wiki_voz_kb.json target files.

Default behavior writes to both copies that currently exist in this repository:
- datasets/processed/pillars/parallel/wiki_voz_kb.json
- frontend/public/data/wiki_voz_kb.json
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SOURCE_CANDIDATES = [
    PROJECT_ROOT / "datasets" / "processed" / "pillars" / "parallel" / "wiki_voz_kb.json",
    PROJECT_ROOT / "frontend" / "public" / "data" / "wiki_voz_kb.json",
]

DEFAULT_TARGETS = [
    PROJECT_ROOT / "datasets" / "processed" / "pillars" / "parallel" / "wiki_voz_kb.json",
    PROJECT_ROOT / "frontend" / "public" / "data" / "wiki_voz_kb.json",
]

TARGET_LANGUAGES = [
    "Chavacano",
    "Cebuano/Bisaya",
    "Hiligaynon",
    "Spanish",
]

CATEGORY_ORDER = [
    "Idioms",
    "False Cognates",
    "Honorifics",
    "Expressions",
]

CATEGORY_ALIASES = {
    "idiom": "Idioms",
    "idioms": "Idioms",
    "false cognate": "False Cognates",
    "false cognates": "False Cognates",
    "honorific": "Honorifics",
    "honorifics": "Honorifics",
    "expression": "Expressions",
    "expressions": "Expressions",
    # Rogue category mapping policy.
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

LANGUAGE_PREFIX = {
    "Chavacano": "cbk",
    "Cebuano/Bisaya": "ceb",
    "Hiligaynon": "hil",
    "Spanish": "es",
}

_SPLIT_RE = re.compile(r"[,|]")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    text = str(value or "")
    text = unicodedata.normalize("NFKC", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_category(raw_category: Any) -> Tuple[Optional[str], str]:
    raw = normalize_text(raw_category)
    if not raw:
        return None, raw

    canonical = CATEGORY_ALIASES.get(raw.casefold())
    return canonical, raw


def normalize_language(raw_language: Any) -> Optional[str]:
    raw = normalize_text(raw_language)
    if not raw:
        return None
    return LANGUAGE_ALIASES.get(raw.casefold())


def normalize_trigger_words(value: Any) -> List[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = _SPLIT_RE.split(value)
    else:
        raw_items = []

    dedupe = set()
    cleaned: List[str] = []
    for item in raw_items:
        trigger = normalize_text(item)
        if not trigger:
            continue
        key = trigger.casefold()
        if key in dedupe:
            continue
        dedupe.add(key)
        cleaned.append(trigger)
    return cleaned


def parse_entries(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("wiki_voz_entries", [])
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    return [row for row in rows if isinstance(row, dict)]


def clean_entry(row: Dict[str, Any], idx: int) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str], Optional[str]]:
    """Return (cleaned_entry, drop_reason, raw_category, mapped_category)."""
    raw_category = normalize_text(row.get("category"))
    mapped_category, _ = normalize_category(raw_category)
    if mapped_category is None:
        return None, "invalid_category", raw_category, None

    mapped_language = normalize_language(row.get("language"))
    if mapped_language is None:
        return None, "invalid_language", raw_category, mapped_category

    title = normalize_text(row.get("title") or row.get("term"))
    description = normalize_text(row.get("description") or row.get("definition"))
    if not title or not description:
        return None, "missing_text_fields", raw_category, mapped_category

    trigger_words = normalize_trigger_words(row.get("trigger_words") or row.get("triggerWords"))
    if not trigger_words:
        trigger_words = [title.casefold()]

    image_url = normalize_text(row.get("image_url") or row.get("imageUrl"))

    row_id = normalize_text(row.get("id"))
    if not row_id:
        prefix = LANGUAGE_PREFIX[mapped_language]
        row_id = f"{prefix}_auto_{idx + 1:03d}"

    cleaned = {
        "id": row_id,
        "trigger_words": trigger_words,
        "language": mapped_language,
        "category": mapped_category,
        "title": title,
        "description": description,
        "image_url": image_url,
    }
    return cleaned, None, raw_category, mapped_category


def choose_source_path(explicit_source: Optional[str]) -> Path:
    if explicit_source:
        source = Path(explicit_source).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")
        return source

    for candidate in DEFAULT_SOURCE_CANDIDATES:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        "No source wiki_voz_kb.json found. Checked: "
        + ", ".join(str(path) for path in DEFAULT_SOURCE_CANDIDATES)
    )


def resolve_targets(explicit_targets: Optional[Iterable[str]]) -> List[Path]:
    if explicit_targets:
        targets = [Path(item).expanduser().resolve() for item in explicit_targets]
        if not targets:
            raise ValueError("At least one target path is required.")
        return targets

    return list(DEFAULT_TARGETS)


def unique_stub_id(prefix: str, used_ids: set[str], counter: int) -> Tuple[str, int]:
    while True:
        candidate = f"{prefix}_pending_{counter:02d}"
        counter += 1
        if candidate not in used_ids:
            return candidate, counter


def make_stub_entry(language: str, category: str, ordinal: int, used_ids: set[str], id_counter: int) -> Tuple[Dict[str, Any], int]:
    prefix = LANGUAGE_PREFIX[language]
    row_id, next_counter = unique_stub_id(prefix, used_ids, id_counter)

    stub = {
        "id": row_id,
        "trigger_words": [f"pending_{prefix}_{ordinal:02d}"],
        "language": language,
        "category": category,
        "title": f"[PENDING] {language} {category} Stub {ordinal:02d}",
        "description": (
            f"[PENDING] Curate and replace this placeholder {language} entry "
            f"for the {category} category."
        ),
        "image_url": "/assets/pending_placeholder.png",
    }
    used_ids.add(row_id)
    return stub, next_counter


def clean_and_pad(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    raw_category_counts = Counter()
    mapped_category_counts = Counter()
    drop_reason_counts = Counter()
    rogue_category_counts = Counter()

    grouped_by_language: Dict[str, List[Dict[str, Any]]] = {lang: [] for lang in TARGET_LANGUAGES}
    used_ids: set[str] = set()

    for idx, row in enumerate(entries):
        raw_category = normalize_text(row.get("category"))
        if raw_category:
            raw_category_counts[raw_category] += 1

        cleaned, drop_reason, seen_raw_category, mapped_category = clean_entry(row, idx)
        if drop_reason:
            drop_reason_counts[drop_reason] += 1
            continue

        if seen_raw_category and seen_raw_category.casefold() == "culture":
            rogue_category_counts[seen_raw_category] += 1

        if mapped_category:
            mapped_category_counts[mapped_category] += 1

        row_id = cleaned["id"]
        if row_id in used_ids:
            # Deterministic dedupe for duplicate ids.
            suffix = 2
            base = row_id
            while f"{base}_{suffix}" in used_ids:
                suffix += 1
            cleaned["id"] = f"{base}_{suffix}"
            row_id = cleaned["id"]

        used_ids.add(row_id)
        grouped_by_language[cleaned["language"]].append(cleaned)

    overflow_by_language = {}
    for language in TARGET_LANGUAGES:
        rows = grouped_by_language[language]
        if len(rows) > 50:
            overflow_by_language[language] = len(rows) - 50
            grouped_by_language[language] = rows[:50]

    generated_stubs: List[Dict[str, Any]] = []
    generated_counts = Counter()

    for language in TARGET_LANGUAGES:
        current_count = len(grouped_by_language[language])
        needed = 50 - current_count
        if needed <= 0:
            continue

        id_counter = 1
        for ordinal in range(1, needed + 1):
            category = CATEGORY_ORDER[(ordinal - 1) % len(CATEGORY_ORDER)]
            stub, id_counter = make_stub_entry(
                language=language,
                category=category,
                ordinal=ordinal,
                used_ids=used_ids,
                id_counter=id_counter,
            )
            grouped_by_language[language].append(stub)
            generated_stubs.append(stub)
            generated_counts[language] += 1

    final_entries: List[Dict[str, Any]] = []
    for language in TARGET_LANGUAGES:
        rows = grouped_by_language[language]
        if len(rows) != 50:
            raise ValueError(f"Language {language} does not have exactly 50 rows (got {len(rows)}).")
        final_entries.extend(rows)

    if len(final_entries) != 200:
        raise ValueError(f"Final dataset size must be 200, got {len(final_entries)}.")

    summary = {
        "raw_total": len(entries),
        "final_total": len(final_entries),
        "raw_category_counts": dict(raw_category_counts),
        "mapped_category_counts": dict(mapped_category_counts),
        "drop_reason_counts": dict(drop_reason_counts),
        "rogue_category_counts": dict(rogue_category_counts),
        "overflow_by_language": overflow_by_language,
        "generated_counts": dict(generated_counts),
        "generated_stubs": generated_stubs,
        "final_language_counts": {
            language: len(grouped_by_language[language]) for language in TARGET_LANGUAGES
        },
        "final_entries": final_entries,
    }
    return summary


def write_targets(targets: List[Path], payload: Dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean and pad wiki_voz_kb.json to exactly 200 entries.")
    parser.add_argument(
        "--source",
        default="",
        help="Optional source file path. Defaults to first existing canonical candidate.",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Optional target file path. Repeat to write multiple copies.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze and print summary without writing files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    source_path = choose_source_path(args.source or None)
    targets = resolve_targets(args.target or None)

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    raw_entries = parse_entries(payload)
    summary = clean_and_pad(raw_entries)

    final_payload = {"wiki_voz_entries": summary["final_entries"]}

    if not args.dry_run:
        write_targets(targets, final_payload)

    print("WIKI_CLEAN_PAD_SUMMARY")
    print(f"source_file: {source_path}")
    print(f"target_files: {[str(path) for path in targets]}")
    print(f"dry_run: {args.dry_run}")
    print(f"raw_total: {summary['raw_total']}")
    print(f"final_total: {summary['final_total']}")
    print(f"raw_category_counts: {summary['raw_category_counts']}")
    print(f"mapped_category_counts: {summary['mapped_category_counts']}")
    print(f"rogue_category_counts: {summary['rogue_category_counts']}")
    print(f"drop_reason_counts: {summary['drop_reason_counts']}")
    print(f"overflow_by_language: {summary['overflow_by_language']}")
    print(f"generated_counts: {summary['generated_counts']}")
    print(f"final_language_counts: {summary['final_language_counts']}")

    print("\nGENERATED_PLACEHOLDER_ENTRIES")
    for row in summary["generated_stubs"]:
        print(json.dumps(row, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
