#!/usr/bin/env python3
"""Merge Cebuano-English 80/10/10 splits into master split files.

Input JSONL schema (one object per line):
{"translation": {"ceb": "...", "en": "..."}}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CEBUANO_SPLIT_DIR = (
    PROJECT_ROOT / "datasets" / "processed" / "80-10-10_split" / "02_cebuano"
)

SPLIT_FILES: dict[str, tuple[str, str, str]] = {
    "train": ("ceb_en_train.jsonl", "flores_ceb_en_train.jsonl", "master_ceb_en_train.jsonl"),
    "val": ("ceb_en_val.jsonl", "flores_ceb_en_val.jsonl", "master_ceb_en_val.jsonl"),
    "test": ("ceb_en_test.jsonl", "flores_ceb_en_test.jsonl", "master_ceb_en_test.jsonl"),
}


@dataclass(frozen=True)
class MergeStats:
    split_name: str
    conversational_count: int
    flores_count: int
    master_count: int
    conversational_duplicates: int
    flores_duplicates: int
    cross_source_duplicates: int
    output_path: Path


def _ensure_file_exists(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required input file: {path}")


def _iter_valid_records(path: Path) -> tuple[str, str]:
    """Yield validated (ceb, en) pairs from a strict JSONL file."""
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                raise ValueError(
                    f"Blank line at {path}:{line_number}. "
                    "This merge expects strict JSONL with one JSON object per line."
                )

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {exc.msg}"
                ) from exc

            translation = payload.get("translation") if isinstance(payload, dict) else None
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

            yield ceb_text, en_text


def _write_jsonl_record(handle: TextIO, ceb_text: str, en_text: str) -> None:
    record = {"translation": {"ceb": ceb_text, "en": en_text}}
    handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    handle.write("\n")


def _count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _merge_single_split(
    split_name: str,
    conversational_path: Path,
    flores_path: Path,
    output_path: Path,
) -> MergeStats:
    _ensure_file_exists(conversational_path)
    _ensure_file_exists(flores_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    conversational_seen: set[tuple[str, str]] = set()
    flores_seen: set[tuple[str, str]] = set()

    conversational_count = 0
    flores_count = 0
    conversational_duplicates = 0
    flores_duplicates = 0
    cross_source_duplicates = 0

    with output_path.open("w", encoding="utf-8") as out_handle:
        for ceb_text, en_text in _iter_valid_records(conversational_path):
            pair = (ceb_text, en_text)
            if pair in conversational_seen:
                conversational_duplicates += 1
            conversational_seen.add(pair)
            _write_jsonl_record(out_handle, ceb_text, en_text)
            conversational_count += 1

        for ceb_text, en_text in _iter_valid_records(flores_path):
            pair = (ceb_text, en_text)
            if pair in flores_seen:
                flores_duplicates += 1
            if pair in conversational_seen:
                cross_source_duplicates += 1
            flores_seen.add(pair)
            _write_jsonl_record(out_handle, ceb_text, en_text)
            flores_count += 1

    expected_total = conversational_count + flores_count
    actual_total = _count_lines(output_path)
    if actual_total != expected_total:
        raise RuntimeError(
            f"Integrity check failed for split '{split_name}': "
            f"expected {expected_total} lines but wrote {actual_total} lines."
        )

    return MergeStats(
        split_name=split_name,
        conversational_count=conversational_count,
        flores_count=flores_count,
        master_count=actual_total,
        conversational_duplicates=conversational_duplicates,
        flores_duplicates=flores_duplicates,
        cross_source_duplicates=cross_source_duplicates,
        output_path=output_path,
    )


def main() -> None:
    if not CEBUANO_SPLIT_DIR.is_dir():
        raise NotADirectoryError(
            f"Expected directory does not exist: {CEBUANO_SPLIT_DIR}"
        )

    stats: list[MergeStats] = []

    for split_name, (conv_name, flores_name, master_name) in SPLIT_FILES.items():
        conv_path = CEBUANO_SPLIT_DIR / conv_name
        flores_path = CEBUANO_SPLIT_DIR / flores_name
        master_path = CEBUANO_SPLIT_DIR / master_name

        split_stats = _merge_single_split(
            split_name=split_name,
            conversational_path=conv_path,
            flores_path=flores_path,
            output_path=master_path,
        )
        stats.append(split_stats)

    # Required count logs for master files (train/val/test).
    stats_by_split = {item.split_name: item for item in stats}
    print("CEBUANO_DATASET_MERGE_COMPLETE")
    print(
        "master_train_count="
        f"{stats_by_split['train'].master_count} -> {stats_by_split['train'].output_path}"
    )
    print(
        "master_val_count="
        f"{stats_by_split['val'].master_count} -> {stats_by_split['val'].output_path}"
    )
    print(
        "master_test_count="
        f"{stats_by_split['test'].master_count} -> {stats_by_split['test'].output_path}"
    )

    print("\\nDetailed diagnostics:")
    for item in stats:
        print(
            f"- {item.split_name}: conversational={item.conversational_count}, "
            f"flores={item.flores_count}, master={item.master_count}, "
            f"dup_in_conversational={item.conversational_duplicates}, "
            f"dup_in_flores={item.flores_duplicates}, "
            f"dup_cross_sources={item.cross_source_duplicates}"
        )


if __name__ == "__main__":
    main()