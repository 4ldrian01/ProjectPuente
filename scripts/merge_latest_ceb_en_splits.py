#!/usr/bin/env python3
"""Merge FLORES + Tatoeba Cebuano-English splits into LATEST JSONL files.

Requirements implemented:
1) Split-specific merge only (train->train, val->val, test->test)
2) Strict schema enforcement for every input row
3) Exact-match deduplication on the translation dictionary
4) Output schema locked to: {"translation": {"ceb": "...", "en": "..."}}
5) Clean terminal report with source counts, dropped duplicates, final counts
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPLIT_DIR = PROJECT_ROOT / "datasets" / "processed" / "80-10-10_split" / "02_cebuano"

SPLIT_FILES: dict[str, tuple[str, str, str]] = {
    "train": ("ceb_en_train.jsonl", "flores_ceb_en_train.jsonl", "LATEST_ceb_en_train.jsonl"),
    "val": ("ceb_en_val.jsonl", "flores_ceb_en_val.jsonl", "LATEST_ceb_en_val.jsonl"),
    "test": ("ceb_en_test.jsonl", "flores_ceb_en_test.jsonl", "LATEST_ceb_en_test.jsonl"),
}


@dataclass(frozen=True)
class SplitReport:
    split_name: str
    tatoeba_count: int
    flores_count: int
    combined_count: int
    duplicates_dropped: int
    final_count: int
    output_path: Path


def ensure_file_exists(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required input file: {path}")


def parse_strict_record(payload: object, *, path: Path, line_number: int) -> dict[str, dict[str, str]]:
    """Validate and normalize to strict output schema."""
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid JSON object at {path}:{line_number}: expected top-level object.")

    translation = payload.get("translation")
    if not isinstance(translation, dict):
        raise ValueError(
            f"Invalid schema at {path}:{line_number}: missing object key 'translation'."
        )

    ceb_text = translation.get("ceb")
    en_text = translation.get("en")
    if not isinstance(ceb_text, str) or not isinstance(en_text, str):
        raise ValueError(
            f"Invalid schema at {path}:{line_number}: expected string keys "
            "'translation.ceb' and 'translation.en'."
        )

    # Enforce exact output schema and key order.
    return {"translation": {"ceb": ceb_text, "en": en_text}}


def iter_strict_records(path: Path) -> Iterator[dict[str, dict[str, str]]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                raise ValueError(
                    f"Blank line found at {path}:{line_number}. Expected strict JSONL."
                )

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {exc.msg}"
                ) from exc

            yield parse_strict_record(payload, path=path, line_number=line_number)


def write_record(handle: TextIO, record: dict[str, dict[str, str]]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    handle.write("\n")


def translation_key(record: dict[str, dict[str, str]]) -> str:
    """Exact dedupe key: canonical string of translation dictionary only."""
    return json.dumps(record["translation"], ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def merge_split(split_name: str, tatoeba_path: Path, flores_path: Path, output_path: Path) -> SplitReport:
    ensure_file_exists(tatoeba_path)
    ensure_file_exists(flores_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    seen_translation_keys: set[str] = set()
    tatoeba_count = 0
    flores_count = 0
    duplicates_dropped = 0
    final_count = 0

    tmp_output = output_path.with_suffix(output_path.suffix + ".tmp")
    with tmp_output.open("w", encoding="utf-8") as out_handle:
        for record in iter_strict_records(tatoeba_path):
            tatoeba_count += 1
            key = translation_key(record)
            if key in seen_translation_keys:
                duplicates_dropped += 1
                continue

            seen_translation_keys.add(key)
            write_record(out_handle, record)
            final_count += 1

        for record in iter_strict_records(flores_path):
            flores_count += 1
            key = translation_key(record)
            if key in seen_translation_keys:
                duplicates_dropped += 1
                continue

            seen_translation_keys.add(key)
            write_record(out_handle, record)
            final_count += 1

    tmp_output.replace(output_path)

    combined_count = tatoeba_count + flores_count
    if final_count != (combined_count - duplicates_dropped):
        raise RuntimeError(
            f"Integrity check failed for split '{split_name}': "
            f"final_count={final_count}, combined_count={combined_count}, "
            f"duplicates_dropped={duplicates_dropped}."
        )

    return SplitReport(
        split_name=split_name,
        tatoeba_count=tatoeba_count,
        flores_count=flores_count,
        combined_count=combined_count,
        duplicates_dropped=duplicates_dropped,
        final_count=final_count,
        output_path=output_path,
    )


def main() -> None:
    if not SPLIT_DIR.is_dir():
        raise NotADirectoryError(f"Missing split directory: {SPLIT_DIR}")

    reports: list[SplitReport] = []

    for split_name, (tatoeba_name, flores_name, latest_name) in SPLIT_FILES.items():
        report = merge_split(
            split_name=split_name,
            tatoeba_path=SPLIT_DIR / tatoeba_name,
            flores_path=SPLIT_DIR / flores_name,
            output_path=SPLIT_DIR / latest_name,
        )
        reports.append(report)

    by_split = {report.split_name: report for report in reports}

    print("CEB_EN_LATEST_MERGE_COMPLETE")
    for split in ("train", "val", "test"):
        item = by_split[split]
        print(
            f"[{item.split_name}] "
            f"tatoeba={item.tatoeba_count} | "
            f"flores={item.flores_count} | "
            f"combined={item.combined_count} | "
            f"dropped_duplicates={item.duplicates_dropped} | "
            f"final={item.final_count} | "
            f"output={item.output_path}"
        )

    total_combined = sum(item.combined_count for item in reports)
    total_dropped = sum(item.duplicates_dropped for item in reports)
    total_final = sum(item.final_count for item in reports)

    print("\n[totals]")
    print(f"combined={total_combined}")
    print(f"dropped_duplicates={total_dropped}")
    print(f"final={total_final}")


if __name__ == "__main__":
    main()
