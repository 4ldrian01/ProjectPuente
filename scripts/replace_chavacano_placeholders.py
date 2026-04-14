#!/usr/bin/env python3
"""Replace Chavacano placeholder entries in wiki_voz_kb.json safely.

Goals:
- Keep schema valid for strict Wiki-Voz taxonomy.
- Preserve dataset shape (200 total, 50 per language).
- Support progressive curation without breaking existing IDs.

Examples:
  python scripts/replace_chavacano_placeholders.py \
      --export-template scripts/chavacano_curation_template.json --dry-run

  python scripts/replace_chavacano_placeholders.py \
      --replacements scripts/chavacano_curated_updates.json

    # Optional compatibility mode for intentionally updating already-curated rows:
    python scripts/replace_chavacano_placeholders.py \
            --replacements scripts/chavacano_curated_updates.json --allow-existing-targets
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

EXPECTED_LANGUAGES = [
    "Chavacano",
    "Cebuano/Bisaya",
    "Hiligaynon",
    "Spanish",
]

ALLOWED_CATEGORIES = [
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
    "culture": "Expressions",
}

LANGUAGE_ALIASES = {
    "cbk": "Chavacano",
    "chavacano": "Chavacano",
    "chavacano (zamboanga)": "Chavacano",
    "zamboanga": "Chavacano",
}

WHITESPACE_RE = re.compile(r"\s+")
SPLIT_RE = re.compile(r"[,|]")


def normalize_text(value: Any) -> str:
    text = str(value or "")
    text = unicodedata.normalize("NFKC", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def parse_entries(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("wiki_voz_entries", [])
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []

    if not isinstance(rows, list):
        raise ValueError("Payload must contain a list of entries.")

    return [row for row in rows if isinstance(row, dict)]


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


def load_entries(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_entries(payload)


def write_entries(paths: List[Path], entries: List[Dict[str, Any]]) -> None:
    payload = {"wiki_voz_entries": entries}
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


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
    if canonical != "Chavacano":
        return None
    return canonical


def normalize_trigger_words(value: Any, fallback_title: str) -> List[str]:
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

    fallback = normalize_text(fallback_title)
    return [fallback.casefold()] if fallback else []


def is_chavacano_placeholder(entry: Dict[str, Any]) -> bool:
    language = normalize_text(entry.get("language"))
    title = normalize_text(entry.get("title") or entry.get("term"))
    description = normalize_text(entry.get("description") or entry.get("definition"))

    if language != "Chavacano":
        return False

    return title.startswith("[PENDING]") or description.startswith("[PENDING]")


def collect_placeholders(entries: List[Dict[str, Any]]) -> List[Tuple[int, Dict[str, Any]]]:
    return [
        (index, row)
        for index, row in enumerate(entries)
        if is_chavacano_placeholder(row)
    ]


def parse_replacements_payload(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("replacements") or payload.get("wiki_voz_entries") or []
    else:
        rows = []

    if not isinstance(rows, list):
        raise ValueError("Replacement payload must be a list.")

    return [row for row in rows if isinstance(row, dict)]


def normalize_replacement(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized_id = normalize_text(row.get("id")) or None
    title = normalize_text(row.get("title") or row.get("term"))
    description = normalize_text(row.get("description") or row.get("definition"))
    category = normalize_category(row.get("category"))
    language = normalize_language(row.get("language") or "Chavacano")
    trigger_words = normalize_trigger_words(row.get("trigger_words") or row.get("triggerWords"), title)
    image_url = normalize_text(row.get("image_url") or row.get("imageUrl") or "")

    if not title:
        raise ValueError("Replacement row missing title/term.")
    if not description:
        raise ValueError("Replacement row missing description/definition.")
    if not category:
        raise ValueError(f"Replacement row has invalid category: {row.get('category')!r}")
    if not language:
        raise ValueError(f"Replacement row has invalid language: {row.get('language')!r}")
    if not trigger_words:
        raise ValueError("Replacement row must include trigger_words or a non-empty title.")

    return {
        "id": normalized_id,
        "trigger_words": trigger_words,
        "language": "Chavacano",
        "category": category,
        "title": title,
        "description": description,
        "image_url": image_url,
    }


def export_template(entries: List[Dict[str, Any]], output_path: Path) -> int:
    placeholders = collect_placeholders(entries)
    template_rows = []

    for _, row in placeholders:
        template_rows.append(
            {
                "id": normalize_text(row.get("id")),
                "trigger_words": row.get("trigger_words") or [],
                "language": "Chavacano",
                "category": normalize_text(row.get("category")),
                "title": normalize_text(row.get("title") or row.get("term")),
                "description": normalize_text(row.get("description") or row.get("definition")),
                "image_url": normalize_text(row.get("image_url") or ""),
            }
        )

    payload = {
        "meta": {
            "note": "Edit rows under replacements, then run --replacements <this-file> to apply.",
            "placeholder_count": len(template_rows),
        },
        "replacements": template_rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return len(template_rows)


def apply_replacements(entries: List[Dict[str, Any]], replacements: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _apply_replacements(entries, replacements, allow_existing_targets=False)


def _apply_replacements(
    entries: List[Dict[str, Any]],
    replacements: List[Dict[str, Any]],
    allow_existing_targets: bool,
) -> Dict[str, Any]:
    placeholders = collect_placeholders(entries)
    placeholder_by_id = {
        normalize_text(row.get("id")): (index, row)
        for index, row in placeholders
    }
    chavacano_by_id = {
        normalize_text(row.get("id")): (index, row)
        for index, row in enumerate(entries)
        if normalize_text(row.get("language")) == "Chavacano"
    }
    available_ids = [normalize_text(row.get("id")) for _, row in placeholders]

    used_target_ids = set()
    placeholder_target_count = 0
    non_placeholder_target_count = 0
    normalized_rows: List[Dict[str, Any]] = []

    for row in replacements:
        normalized_rows.append(normalize_replacement(row))

    for replacement in normalized_rows:
        target_id = replacement["id"]
        target_entry: Optional[Tuple[int, Dict[str, Any]]] = None

        if target_id:
            if target_id in used_target_ids:
                raise ValueError(f"Replacement id {target_id!r} is repeated.")

            if target_id in placeholder_by_id:
                target_entry = placeholder_by_id[target_id]
                placeholder_target_count += 1
            elif target_id in chavacano_by_id:
                if not allow_existing_targets:
                    raise ValueError(
                        f"Replacement id {target_id!r} is an existing curated Chavacano row, not a placeholder. "
                        "Use --allow-existing-targets only when you intentionally want to update already-curated entries."
                    )

                # Optional compatibility mode for intentional re-curation.
                target_entry = chavacano_by_id[target_id]
                non_placeholder_target_count += 1
            else:
                raise ValueError(
                    f"Replacement id {target_id!r} is not a known Chavacano placeholder or Chavacano row id."
                )
        else:
            target_id = None
            for candidate_id in available_ids:
                if candidate_id not in used_target_ids:
                    target_id = candidate_id
                    break
            if target_id is None:
                raise ValueError("No remaining placeholders available for replacement assignment.")
            target_entry = placeholder_by_id[target_id]
            placeholder_target_count += 1

        if target_entry is None:
            raise ValueError("Internal error: replacement target could not be resolved.")

        index, current_row = target_entry
        replacement["id"] = target_id
        replacement["image_url"] = replacement["image_url"] or normalize_text(current_row.get("image_url") or "/assets/pending_placeholder.png")
        entries[index] = {
            "id": target_id,
            "trigger_words": replacement["trigger_words"],
            "language": "Chavacano",
            "category": replacement["category"],
            "title": replacement["title"],
            "description": replacement["description"],
            "image_url": replacement["image_url"],
        }
        used_target_ids.add(target_id)

    validate_dataset(entries)

    remaining_placeholders = collect_placeholders(entries)
    return {
        "replaced_count": len(used_target_ids),
        "placeholder_target_count": placeholder_target_count,
        "non_placeholder_target_count": non_placeholder_target_count,
        "remaining_placeholder_count": len(remaining_placeholders),
        "remaining_placeholder_ids": [normalize_text(row.get("id")) for _, row in remaining_placeholders],
    }


def validate_dataset(entries: List[Dict[str, Any]]) -> None:
    if len(entries) != 200:
        raise ValueError(f"Dataset must contain exactly 200 entries, got {len(entries)}.")

    ids = [normalize_text(row.get("id")) for row in entries]
    if any(not row_id for row_id in ids):
        raise ValueError("All entries must have non-empty ids.")

    id_counts = Counter(ids)
    duplicated_ids = [row_id for row_id, count in id_counts.items() if count > 1]
    if duplicated_ids:
        raise ValueError(f"Duplicate ids detected: {duplicated_ids[:5]}")

    language_counts = Counter(normalize_text(row.get("language")) for row in entries)
    for language in EXPECTED_LANGUAGES:
        if language_counts.get(language, 0) != 50:
            raise ValueError(
                f"Language {language} must have 50 entries, got {language_counts.get(language, 0)}."
            )

    if set(language_counts.keys()) != set(EXPECTED_LANGUAGES):
        raise ValueError(f"Unexpected language set: {sorted(language_counts.keys())}")

    for row in entries:
        category = normalize_category(row.get("category"))
        if category is None:
            raise ValueError(f"Entry has unsupported category: {row.get('category')!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replace Chavacano placeholders safely.")
    parser.add_argument("--source", default="", help="Optional source file path.")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Optional target file path. Repeat to write multiple copies.",
    )
    parser.add_argument(
        "--replacements",
        default="",
        help="Path to replacement JSON file.",
    )
    parser.add_argument(
        "--export-template",
        default="",
        help="Write current placeholders to this JSON template path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without writing target files.",
    )
    parser.add_argument(
        "--allow-existing-targets",
        action="store_true",
        help=(
            "Allow replacement IDs to target already-curated Chavacano rows. "
            "By default, replacements must target placeholders only."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    source_path = choose_source_path(args.source or None)
    targets = resolve_targets(args.target or None)

    entries = load_entries(source_path)

    if args.export_template:
        template_path = Path(args.export_template).expanduser().resolve()
        count = export_template(entries, template_path)
        print("CHAVACANO_TEMPLATE_EXPORTED")
        print(f"source_file: {source_path}")
        print(f"template_path: {template_path}")
        print(f"placeholder_count: {count}")

    if not args.replacements:
        if args.export_template:
            return 0
        raise SystemExit("--replacements is required unless --export-template is used.")

    replacements_path = Path(args.replacements).expanduser().resolve()
    if not replacements_path.is_file():
        raise FileNotFoundError(f"Replacements file not found: {replacements_path}")

    replacement_rows = parse_replacements_payload(replacements_path)
    summary = _apply_replacements(
        entries,
        replacement_rows,
        allow_existing_targets=args.allow_existing_targets,
    )

    if not args.dry_run:
        write_entries(targets, entries)

    print("CHAVACANO_PLACEHOLDER_REPLACEMENT_DONE")
    print(f"source_file: {source_path}")
    print(f"target_files: {[str(path) for path in targets]}")
    print(f"replacements_file: {replacements_path}")
    print(f"dry_run: {args.dry_run}")
    print(f"allow_existing_targets: {args.allow_existing_targets}")
    print(f"requested_replacements: {len(replacement_rows)}")
    print(f"applied_replacements: {summary['replaced_count']}")
    print(f"placeholder_targets: {summary['placeholder_target_count']}")
    print(f"non_placeholder_targets: {summary['non_placeholder_target_count']}")
    print(f"remaining_placeholder_count: {summary['remaining_placeholder_count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
