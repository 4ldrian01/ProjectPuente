#!/usr/bin/env python3
"""
json_to_jsonl_converter.py

Hardware Safety Protocol (Phase 1) converter for Project PUENTE.

Purpose:
- Convert a metadata-rich JSON payload into JSONL (JSON Lines) for stream-safe
    training in HuggingFace + PyTorch pipelines.
- Target only the "entries" array and skip top-level metadata blocks.
- Deterministically shuffle with seed and split into train/eval/test (80/10/10).
- Validate zero-loss conversion and split integrity with strict checks.

Why JSONL is safer for training memory:
- Monolithic JSON arrays are often loaded into memory as one object graph.
- JSONL supports line-by-line iteration and streaming dataset readers.
- Streaming keeps memory usage near O(1) with respect to dataset size.

Complexity notes:
- Conversion time: O(n), where n = number of entries.
- Conversion space: O(1) additional memory (streaming parser + one entry at a time).
- Validation line counting: O(n) time, O(1) memory.
- Split pass: O(n) time, O(n) memory for deterministic seeded shuffle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path


def build_default_paths() -> tuple[Path, Path, Path, Path, Path, Path]:
    """Build canonical default paths from repository root."""
    # File location: datasets/scripts/json_to_jsonl_converter.py
    project_root = Path(__file__).resolve().parents[2]

    preferred_input_json = (
        project_root
        / 'datasets'
        / 'processed'
        / '001_chavacano'
        / 'master_parallel_corpus_nmt.json'
    )
    fallback_input_json = (
        project_root
        / 'datasets'
        / 'processed'
        / 'pillars'
        / 'parallel'
        / 'master_parallel_corpus_nmt.json'
    )

    output_dir = (
        project_root
        / 'datasets'
        / 'processed'
        / '001_chavacano'
    )

    output_jsonl = output_dir / 'master_parallel_corpus.jsonl'
    train_jsonl = (
        output_dir
        / 'train.jsonl'
    )
    eval_jsonl = (
        output_dir
        / 'eval.jsonl'
    )
    test_jsonl = (
        output_dir
        / 'test.jsonl'
    )
    return (
        preferred_input_json,
        fallback_input_json,
        output_jsonl,
        train_jsonl,
        eval_jsonl,
        test_jsonl,
    )


def parse_args() -> argparse.Namespace:
    """CLI arguments for conversion + optional split."""
    (
        default_input,
        default_input_fallback,
        default_output,
        default_train,
        default_eval,
        default_test,
    ) = build_default_paths()

    parser = argparse.ArgumentParser(
        description='Convert metadata-rich Project PUENTE JSON into streaming JSONL.',
    )
    parser.add_argument(
        '--input',
        type=Path,
        default=default_input,
        help='Source JSON file containing top-level metadata + entries.',
    )
    parser.add_argument(
        '--fallback-input',
        type=Path,
        default=default_input_fallback,
        help='Compatibility fallback if --input path does not exist.',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=default_output,
        help='Optional destination full JSONL file (one minified JSON object per line).',
    )
    parser.add_argument(
        '--write-master-jsonl',
        action='store_true',
        help='Also write full master JSONL (disabled by default to avoid giant intermediate files).',
    )
    parser.add_argument(
        '--train-output',
        type=Path,
        default=default_train,
        help='Output path for train split JSONL.',
    )
    parser.add_argument(
        '--eval-output',
        type=Path,
        default=default_eval,
        help='Output path for eval split JSONL.',
    )
    parser.add_argument(
        '--test-output',
        type=Path,
        default=default_test,
        help='Output path for test split JSONL.',
    )
    parser.add_argument(
        '--train-ratio',
        type=float,
        default=0.8,
        help='Train split ratio in [0, 1].',
    )
    parser.add_argument(
        '--eval-ratio',
        type=float,
        default=0.1,
        help='Eval split ratio in [0, 1].',
    )
    parser.add_argument(
        '--test-ratio',
        type=float,
        default=0.1,
        help='Test split ratio in [0, 1].',
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for deterministic shuffling.',
    )
    parser.add_argument(
        '--report-output',
        type=Path,
        default=default_train.parent / 'split_report.json',
        help='JSON report path with integrity and split metrics.',
    )
    parser.add_argument(
        '--expected-count',
        type=int,
        default=0,
        help='Optional strict expected entry count (0 disables check).',
    )
    return parser.parse_args()


def ensure_parent_dir(path: Path) -> None:
    """Create parent directory for a file path if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)


def count_jsonl_lines(path: Path) -> int:
    """Count physical lines in JSONL file (one record per line by contract)."""
    with path.open('r', encoding='utf-8') as handle:
        return sum(1 for _ in handle)


def resolve_input_path(primary: Path, fallback: Path) -> Path:
    if primary.is_file():
        return primary
    if fallback.is_file():
        return fallback
    return primary


def stream_entries(input_json: Path) -> list[dict]:
    """
    Stream-read `entries` from metadata-rich JSON.

    Returns a list of dict records for deterministic seeded shuffling.
    """
    try:
        import ijson
    except ImportError as exc:
        raise RuntimeError(
            'Missing dependency: ijson. Install with: pip install ijson'
        ) from exc

    records: list[dict] = []

    # ijson.items(..., 'entries.item') iterates only objects under top-level
    # "entries" and bypasses metadata/source_files blocks.
    with input_json.open('rb') as src:
        for entry in ijson.items(src, 'entries.item'):
            if not isinstance(entry, dict):
                continue

            records.append(entry)

    return records


def write_jsonl(path: Path, records: list[dict]) -> int:
    ensure_parent_dir(path)
    with path.open('w', encoding='utf-8') as handle:
        for record in records:
            handle.write(
                json.dumps(
                    to_json_compatible(record),
                    ensure_ascii=False,
                    separators=(',', ':'),
                )
            )
            handle.write('\n')
    return len(records)


def stable_signature(record: dict) -> str:
    payload = json.dumps(
        to_json_compatible(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def to_json_compatible(value):
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    if isinstance(value, dict):
        return {str(key): to_json_compatible(val) for key, val in value.items()}

    if isinstance(value, list):
        return [to_json_compatible(item) for item in value]

    return value


def ratio_split_counts(total: int, train_ratio: float, eval_ratio: float, test_ratio: float) -> tuple[int, int, int]:
    ratios = (train_ratio, eval_ratio, test_ratio)
    if any(r < 0 or r > 1 for r in ratios):
        raise ValueError('All split ratios must be within [0, 1].')

    ratio_sum = sum(ratios)
    if not math.isclose(ratio_sum, 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError('Split ratios must sum to 1.0 exactly.')

    targets = [total * ratio for ratio in ratios]
    base = [int(math.floor(x)) for x in targets]
    remainder = total - sum(base)

    fractional_order = sorted(
        range(3),
        key=lambda idx: (targets[idx] - base[idx], -idx),
        reverse=True,
    )

    for idx in fractional_order[:remainder]:
        base[idx] += 1

    return base[0], base[1], base[2]


def split_records(
    records: list[dict],
    train_ratio: float,
    eval_ratio: float,
    test_ratio: float,
    seed: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Deterministically shuffle and split records into train/eval/test subsets.
    """
    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)

    train_count, eval_count, test_count = ratio_split_counts(
        total=len(shuffled),
        train_ratio=train_ratio,
        eval_ratio=eval_ratio,
        test_ratio=test_ratio,
    )

    train_end = train_count
    eval_end = train_count + eval_count

    train_records = shuffled[:train_end]
    eval_records = shuffled[train_end:eval_end]
    test_records = shuffled[eval_end:eval_end + test_count]

    if (len(train_records) + len(eval_records) + len(test_records)) != len(shuffled):
        raise RuntimeError('Split integrity mismatch: subset sizes do not sum to total.')

    return train_records, eval_records, test_records


def validate_split_integrity(
    source_records: list[dict],
    train_records: list[dict],
    eval_records: list[dict],
    test_records: list[dict],
) -> tuple[bool, str]:
    source_counter = Counter(stable_signature(item) for item in source_records)
    split_counter = Counter(stable_signature(item) for item in [*train_records, *eval_records, *test_records])

    if source_counter != split_counter:
        missing = source_counter - split_counter
        extra = split_counter - source_counter
        return (
            False,
            f'integrity_failed missing={sum(missing.values())} extra={sum(extra.values())}',
        )

    return True, 'integrity_ok'


def main() -> int:
    args = parse_args()

    input_json = resolve_input_path(
        args.input.resolve(),
        args.fallback_input.resolve(),
    )
    output_jsonl = args.output.resolve()
    train_jsonl = args.train_output.resolve()
    eval_jsonl = args.eval_output.resolve()
    test_jsonl = args.test_output.resolve()
    report_output = args.report_output.resolve()

    print('=' * 72)
    print('Project PUENTE — Memory-Safe JSON -> JSONL 80/10/10 Converter')
    print('=' * 72)
    print(f'Input JSON : {input_json}')
    print(f'Train JSONL: {train_jsonl}')
    print(f'Eval JSONL : {eval_jsonl}')
    print(f'Test JSONL : {test_jsonl}')
    print(f'Seed       : {args.seed}')

    if not input_json.is_file():
        print('ERROR: Input file not found.')
        print('Expected:', input_json)
        return 1

    # TASK 1: Stream-read entries[] only.
    source_records = stream_entries(input_json)
    source_entry_count = len(source_records)

    if args.expected_count > 0 and source_entry_count != args.expected_count:
        print(
            f'ERROR: Expected {args.expected_count} entries, found {source_entry_count}. '
            'Aborting due to strict expected-count check.'
        )
        return 2

    if source_entry_count == 0:
        print('ERROR: No entries found under top-level "entries".')
        return 3

    # Optional giant master JSONL export (off by default).
    master_lines = 0
    if args.write_master_jsonl:
        master_lines = write_jsonl(output_jsonl, source_records)

    # TASK 2: Deterministic seeded shuffle and strict 80/10/10 split.
    train_records, eval_records, test_records = split_records(
        records=source_records,
        train_ratio=args.train_ratio,
        eval_ratio=args.eval_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    train_written = write_jsonl(train_jsonl, train_records)
    eval_written = write_jsonl(eval_jsonl, eval_records)
    test_written = write_jsonl(test_jsonl, test_records)

    # TASK 3: Integrity validation (zero-loss check + file line checks).
    train_lines = count_jsonl_lines(train_jsonl)
    eval_lines = count_jsonl_lines(eval_jsonl)
    test_lines = count_jsonl_lines(test_jsonl)

    integrity_ok, integrity_note = validate_split_integrity(
        source_records,
        train_records,
        eval_records,
        test_records,
    )

    print('-' * 72)
    print('Validation Report')
    print(f'entries[] objects in source JSON : {source_entry_count}')
    if args.write_master_jsonl:
        output_line_count = count_jsonl_lines(output_jsonl)
        print(f'physical lines in master JSONL   : {output_line_count}')
        if source_entry_count != output_line_count:
            print('FAILURE: Master JSONL count mismatch detected.')
            return 4
    else:
        print('master JSONL export              : skipped (by design)')

    print('-' * 72)
    print('80/10/10 Split Report')
    print(f'Train records (target/written) : {len(train_records)}/{train_written}')
    print(f'Eval records  (target/written) : {len(eval_records)}/{eval_written}')
    print(f'Test records  (target/written) : {len(test_records)}/{test_written}')
    print(f'Line counts from disk           : train={train_lines} eval={eval_lines} test={test_lines}')
    print(f'Integrity status                : {integrity_note}')

    if not integrity_ok:
        print('FAILURE: Split integrity mismatch detected.')
        return 5

    if (train_lines + eval_lines + test_lines) != source_entry_count:
        print('FAILURE: Combined split line counts do not match source entries count.')
        return 6

    report = {
        'input_json': str(input_json),
        'seed': args.seed,
        'ratios': {
            'train': args.train_ratio,
            'eval': args.eval_ratio,
            'test': args.test_ratio,
        },
        'counts': {
            'source_entries': source_entry_count,
            'master_jsonl_lines': master_lines,
            'train': train_lines,
            'eval': eval_lines,
            'test': test_lines,
            'combined_split_lines': train_lines + eval_lines + test_lines,
        },
        'paths': {
            'train': str(train_jsonl),
            'eval': str(eval_jsonl),
            'test': str(test_jsonl),
            'master_jsonl': str(output_jsonl) if args.write_master_jsonl else '',
        },
        'integrity': {
            'ok': integrity_ok,
            'note': integrity_note,
        },
    }
    ensure_parent_dir(report_output)
    report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Report JSON                    : {report_output}')
    print('SUCCESS: 80/10/10 JSONL split completed and validated.')

    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
