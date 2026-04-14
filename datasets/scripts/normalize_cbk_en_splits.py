#!/usr/bin/env python3
"""Normalize generic Chavacano split JSONL files to production schema.

This script transforms:
- train.jsonl -> cbk_en_train.jsonl
- eval.jsonl  -> cbk_en_val.jsonl
- test.jsonl  -> cbk_en_test.jsonl

Each input line is converted from the verbose schema to:
{"translation": {"cbk": "<source_text>", "en": "<target_text>"}}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


RENAME_MAP = {
    'train.jsonl': 'cbk_en_train.jsonl',
    'eval.jsonl': 'cbk_en_val.jsonl',
    'test.jsonl': 'cbk_en_test.jsonl',
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Rename and normalize generic split JSONL files to the Hugging Face '
            'Seq2Seq translation schema.'
        )
    )
    parser.add_argument(
        '--input-dir',
        type=Path,
        required=True,
        help='Directory containing train.jsonl, eval.jsonl, and test.jsonl.',
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='Destination directory for normalized outputs (defaults to --input-dir).',
    )
    parser.add_argument(
        '--encoding',
        type=str,
        default='utf-8',
        help='Text encoding for input and output files (default: utf-8).',
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite output files if they already exist.',
    )
    return parser.parse_args()


def validate_required_inputs(input_dir: Path) -> None:
    missing = [name for name in RENAME_MAP if not (input_dir / name).is_file()]
    if missing:
        missing_csv = ', '.join(missing)
        raise FileNotFoundError(
            f'Missing required input file(s) in {input_dir}: {missing_csv}'
        )


def normalize_record(record: object, line_number: int, file_name: str) -> dict[str, dict[str, str]]:
    if not isinstance(record, dict):
        raise ValueError(f'{file_name}:{line_number} is not a JSON object.')

    source_text = record.get('source_text')
    target_text = record.get('target_text')

    if not isinstance(source_text, str) or not source_text:
        raise ValueError(
            f'{file_name}:{line_number} has invalid or empty source_text.'
        )

    if not isinstance(target_text, str) or not target_text:
        raise ValueError(
            f'{file_name}:{line_number} has invalid or empty target_text.'
        )

    return {
        'translation': {
            'cbk': source_text,
            'en': target_text,
        }
    }


def transform_file(
    input_path: Path,
    output_path: Path,
    encoding: str,
    overwrite: bool,
) -> int:
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f'Output already exists: {output_path}. Use --overwrite to replace it.'
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    transformed_count = 0

    with input_path.open('r', encoding=encoding) as src, output_path.open(
        'w', encoding=encoding
    ) as dst:
        for line_number, raw_line in enumerate(src, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f'{input_path.name}:{line_number} contains invalid JSON.'
                ) from exc

            normalized = normalize_record(record, line_number, input_path.name)
            dst.write(json.dumps(normalized, ensure_ascii=False))
            dst.write('\n')
            transformed_count += 1

    return transformed_count


def main() -> None:
    args = parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = (args.output_dir or args.input_dir).resolve()

    if not input_dir.is_dir():
        raise NotADirectoryError(f'Input directory does not exist: {input_dir}')

    validate_required_inputs(input_dir)

    print('Starting normalization...')
    print(f'Input directory: {input_dir}')
    print(f'Output directory: {output_dir}')

    total_lines = 0
    processed_files = 0

    for input_name, output_name in RENAME_MAP.items():
        source_path = input_dir / input_name
        destination_path = output_dir / output_name

        line_count = transform_file(
            input_path=source_path,
            output_path=destination_path,
            encoding=args.encoding,
            overwrite=args.overwrite,
        )

        processed_files += 1
        total_lines += line_count

        print('')
        print(f'Processed file: {input_name}')
        print(f'Transformed lines: {line_count}')
        print(f'Saved to: {destination_path}')

    print('')
    print('Normalization complete.')
    print(f'Files processed: {processed_files}')
    print(f'Total transformed lines: {total_lines}')


if __name__ == '__main__':
    main()
