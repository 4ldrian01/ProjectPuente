#!/usr/bin/env python3
"""Split Spanish-English synthetic JSONL into deterministic 80/10/10 files.

Input schema (one JSON object per line):
{"translation": {"es": "...", "en": "..."}}
"""

from __future__ import annotations

import json
import random
from pathlib import Path


SEED = 42
EXPECTED_TOTAL = 500
TRAIN_COUNT = 400
VAL_COUNT = 50
TEST_COUNT = 50

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "datasets" / "raw" / "es" / "spanish_500_syntethic.json"
OUTPUT_DIR = PROJECT_ROOT / "datasets" / "processed" / "004_spanish"

TRAIN_PATH = OUTPUT_DIR / "es_en_train.jsonl"
VAL_PATH = OUTPUT_DIR / "es_en_val.jsonl"
TEST_PATH = OUTPUT_DIR / "es_en_test.jsonl"


def read_jsonl_records(path: Path) -> list[dict]:
    """Read and validate JSONL records from disk."""
    records: list[dict] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                # Skip blank lines safely.
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at line {line_number} in {path}: {exc.msg}"
                ) from exc

            translation = payload.get("translation") if isinstance(payload, dict) else None
            if not isinstance(translation, dict):
                raise ValueError(
                    f"Line {line_number} in {path} is missing object key 'translation'."
                )

            es_text = translation.get("es")
            en_text = translation.get("en")
            if not isinstance(es_text, str) or not isinstance(en_text, str):
                raise ValueError(
                    f"Line {line_number} in {path} must contain string keys 'translation.es' and 'translation.en'."
                )

            records.append({"translation": {"es": es_text, "en": en_text}})

    return records


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records as JSONL (one compact JSON object per line)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def main() -> None:
    if not SOURCE_PATH.is_file():
        raise FileNotFoundError(
            f"Required input file does not exist: {SOURCE_PATH}"
        )

    records = read_jsonl_records(SOURCE_PATH)

    if len(records) != EXPECTED_TOTAL:
        raise ValueError(
            f"Expected exactly {EXPECTED_TOTAL} valid JSONL records in {SOURCE_PATH}, "
            f"but found {len(records)}."
        )

    random.seed(SEED)
    random.shuffle(records)

    train_records = records[:TRAIN_COUNT]
    val_records = records[TRAIN_COUNT:TRAIN_COUNT + VAL_COUNT]
    test_records = records[TRAIN_COUNT + VAL_COUNT:TRAIN_COUNT + VAL_COUNT + TEST_COUNT]

    if not (
        len(train_records) == TRAIN_COUNT
        and len(val_records) == VAL_COUNT
        and len(test_records) == TEST_COUNT
    ):
        raise RuntimeError("Internal split error: unexpected partition sizes.")

    write_jsonl(TRAIN_PATH, train_records)
    write_jsonl(VAL_PATH, val_records)
    write_jsonl(TEST_PATH, test_records)

    print("SPANISH_DATASET_SPLIT_COMPLETE")
    print(f"train_count={count_lines(TRAIN_PATH)} -> {TRAIN_PATH}")
    print(f"val_count={count_lines(VAL_PATH)} -> {VAL_PATH}")
    print(f"test_count={count_lines(TEST_PATH)} -> {TEST_PATH}")


if __name__ == "__main__":
    main()
