#!/usr/bin/env python3
"""Prepare final Cebuano-English training splits by merging new CCAligned data.

Workflow:
1) Read validated 5,000-line CCAligned source JSONL
2) Shuffle with random.seed(42) + random.shuffle
3) Split exactly into 4,000 / 500 / 500
4) Append to existing master train/val/test files
5) Write FINAL_ceb_en_{train,val,test}.jsonl and print integrity report
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path


SEED = 42
EXPECTED_NEW_TOTAL = 5000
NEW_TRAIN_COUNT = 4000
NEW_VAL_COUNT = 500
NEW_TEST_COUNT = 500

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_NEW_PATH = PROJECT_ROOT / "datasets" / "raw" / "ceb" / "ccaligned_v3_perfect.jsonl"
BASE_DIR = PROJECT_ROOT / "datasets" / "processed" / "80-10-10_split" / "02_cebuano"

MASTER_TRAIN_PATH = BASE_DIR / "master_ceb_en_train.jsonl"
MASTER_VAL_PATH = BASE_DIR / "master_ceb_en_val.jsonl"
MASTER_TEST_PATH = BASE_DIR / "master_ceb_en_test.jsonl"

FINAL_TRAIN_PATH = BASE_DIR / "FINAL_ceb_en_train.jsonl"
FINAL_VAL_PATH = BASE_DIR / "FINAL_ceb_en_val.jsonl"
FINAL_TEST_PATH = BASE_DIR / "FINAL_ceb_en_test.jsonl"


@dataclass(frozen=True)
class SplitBundle:
    train: list[dict]
    val: list[dict]
    test: list[dict]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Shuffle, split, and merge Cebuano-English CCAligned v3 data with "
            "existing master splits to generate FINAL training-ready JSONL files."
        )
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing FINAL output files if they already exist.",
    )
    return parser.parse_args()


def ensure_required_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Missing required input file: {path}")


def read_translation_jsonl(path: Path) -> list[dict]:
    """Read strict translation JSONL records: {"translation": {"ceb": str, "en": str}}."""
    ensure_required_file(path)

    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                raise ValueError(
                    f"Blank line found at {path}:{line_number}. Strict JSONL is required."
                )

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON at {path}:{line_number}: {exc.msg}"
                ) from exc

            if not isinstance(payload, dict):
                raise ValueError(f"Non-object JSON row at {path}:{line_number}.")

            translation = payload.get("translation")
            if not isinstance(translation, dict):
                raise ValueError(
                    f"Missing object key 'translation' at {path}:{line_number}."
                )

            ceb_text = translation.get("ceb")
            en_text = translation.get("en")
            if not isinstance(ceb_text, str) or not isinstance(en_text, str):
                raise ValueError(
                    f"Invalid schema at {path}:{line_number}: expected string "
                    "keys 'translation.ceb' and 'translation.en'."
                )

            records.append({"translation": {"ceb": ceb_text, "en": en_text}})

    return records


def write_jsonl_atomic(path: Path, records: list[dict], overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file exists: {path}. Use --overwrite to replace it."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    with tmp_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")

    tmp_path.replace(path)


def split_new_records(records: list[dict]) -> SplitBundle:
    if len(records) != EXPECTED_NEW_TOTAL:
        raise ValueError(
            f"Expected exactly {EXPECTED_NEW_TOTAL} new rows, found {len(records)}."
        )

    # Required by spec: secure deterministic shuffle with seed=42.
    random.seed(SEED)
    random.shuffle(records)

    train = records[:NEW_TRAIN_COUNT]
    val = records[NEW_TRAIN_COUNT:NEW_TRAIN_COUNT + NEW_VAL_COUNT]
    test = records[NEW_TRAIN_COUNT + NEW_VAL_COUNT:NEW_TRAIN_COUNT + NEW_VAL_COUNT + NEW_TEST_COUNT]

    if not (
        len(train) == NEW_TRAIN_COUNT
        and len(val) == NEW_VAL_COUNT
        and len(test) == NEW_TEST_COUNT
    ):
        raise RuntimeError("Unexpected split sizes after shuffling.")

    return SplitBundle(train=train, val=val, test=test)


def count_lines(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def main() -> None:
    args = parse_args()

    new_records = read_translation_jsonl(SOURCE_NEW_PATH)
    new_splits = split_new_records(new_records)

    master_train = read_translation_jsonl(MASTER_TRAIN_PATH)
    master_val = read_translation_jsonl(MASTER_VAL_PATH)
    master_test = read_translation_jsonl(MASTER_TEST_PATH)

    final_train = master_train + new_splits.train
    final_val = master_val + new_splits.val
    final_test = master_test + new_splits.test

    write_jsonl_atomic(FINAL_TRAIN_PATH, final_train, overwrite=args.overwrite)
    write_jsonl_atomic(FINAL_VAL_PATH, final_val, overwrite=args.overwrite)
    write_jsonl_atomic(FINAL_TEST_PATH, final_test, overwrite=args.overwrite)

    final_train_count = count_lines(FINAL_TRAIN_PATH)
    final_val_count = count_lines(FINAL_VAL_PATH)
    final_test_count = count_lines(FINAL_TEST_PATH)

    existing_train_count = len(master_train)
    existing_val_count = len(master_val)
    existing_test_count = len(master_test)

    new_train_count = len(new_splits.train)
    new_val_count = len(new_splits.val)
    new_test_count = len(new_splits.test)

    total_existing = existing_train_count + existing_val_count + existing_test_count
    total_new = new_train_count + new_val_count + new_test_count
    total_final = final_train_count + final_val_count + final_test_count

    print("FINAL_CEBUANO_DATASET_PREPARATION_COMPLETE")
    print("\nExisting master counts:")
    print(f"- master_train={existing_train_count} -> {MASTER_TRAIN_PATH}")
    print(f"- master_val={existing_val_count} -> {MASTER_VAL_PATH}")
    print(f"- master_test={existing_test_count} -> {MASTER_TEST_PATH}")
    print(f"- master_total={total_existing}")

    print("\nNew CCAligned split counts (seed=42):")
    print(f"- new_train={new_train_count}")
    print(f"- new_val={new_val_count}")
    print(f"- new_test={new_test_count}")
    print(f"- new_total={total_new}")

    print("\nFINAL merged counts:")
    print(f"- FINAL_train={final_train_count} -> {FINAL_TRAIN_PATH}")
    print(f"- FINAL_val={final_val_count} -> {FINAL_VAL_PATH}")
    print(f"- FINAL_test={final_test_count} -> {FINAL_TEST_PATH}")
    print(f"- FINAL_total={total_final}")

    expected_train = existing_train_count + NEW_TRAIN_COUNT
    expected_val = existing_val_count + NEW_VAL_COUNT
    expected_test = existing_test_count + NEW_TEST_COUNT
    expected_total = expected_train + expected_val + expected_test

    print("\nMathematical integrity check:")
    print(f"- expected_train={expected_train} | actual_train={final_train_count}")
    print(f"- expected_val={expected_val} | actual_val={final_val_count}")
    print(f"- expected_test={expected_test} | actual_test={final_test_count}")
    print(f"- expected_total={expected_total} | actual_total={total_final}")

    if not (
        final_train_count == expected_train
        and final_val_count == expected_val
        and final_test_count == expected_test
        and total_final == expected_total
    ):
        raise RuntimeError("Final count verification failed.")


if __name__ == "__main__":
    main()