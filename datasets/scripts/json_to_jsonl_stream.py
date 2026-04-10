#!/usr/bin/env python3
"""Task 2: Memory-safe JSON -> JSONL conversion for NMT payloads.

Why JSONL protects consumer hardware:
- Standard JSON arrays usually require full deserialization before iteration.
- JSONL keeps one object per line, enabling streaming DataLoader patterns.
- Streaming keeps memory closer to O(batch_size), not O(dataset_size).

This script is intentionally strict:
- Uses `ijson` streaming parser (no full-array loads).
- Converts only approved NMT payload records.
- Rejects lexicon-style entries from training JSONL exports.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from _path_utils import ensure_parent_dir, resolve_datasets_dir, resolve_project_root

try:
    import ijson
except ImportError as exc:  # pragma: no cover - runtime guard
    raise SystemExit(
        'Missing dependency: ijson\n'
        'Install it for streaming safety:\n'
        '  pip install ijson\n'
        'This converter intentionally refuses unsafe full-memory JSON loading.'
    ) from exc

WHITESPACE_RE = re.compile(r'\s+')


def parse_args() -> argparse.Namespace:
    project_root = resolve_project_root()
    datasets_dir = resolve_datasets_dir(project_root)

    parser = argparse.ArgumentParser(
        description='Stream-convert approved JSON NMT payloads to JSONL.',
    )
    parser.add_argument(
        '--input',
        action='append',
        default=[
            str(datasets_dir / 'processed' / '001_chavacano'),
            str(datasets_dir / 'processed' / 'pillars'),
        ],
        help='Input file or directory. Can be repeated.',
    )
    parser.add_argument(
        '--output-root',
        type=str,
        default=str(datasets_dir / 'processed' / 'jsonl'),
        help='Root directory where converted JSONL files are written.',
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing JSONL outputs.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print per-file reject details.',
    )
    return parser.parse_args()


def to_text(value: object) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = WHITESPACE_RE.sub(' ', text)
    return text


def pick_text(entry: Dict[str, object], keys: Sequence[str]) -> str:
    for key in keys:
        value = to_text(entry.get(key))
        if value:
            return value
    return ''


def iter_json_files(paths: Sequence[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.casefold() == '.json':
            yield path
            continue

        if path.is_dir():
            for child in sorted(path.rglob('*.json')):
                if child.is_file():
                    yield child


def detect_root_kind(path: Path) -> str:
    with path.open('r', encoding='utf-8') as handle:
        while True:
            char = handle.read(1)
            if not char:
                return 'empty'
            if char.isspace():
                continue
            if char == '{':
                return 'object'
            if char == '[':
                return 'array'
            return 'unknown'


def iter_records(path: Path) -> Iterator[Dict[str, object]]:
    root_kind = detect_root_kind(path)
    prefix = 'entries.item' if root_kind == 'object' else 'item'

    if root_kind not in {'object', 'array'}:
        return

    with path.open('rb') as handle:
        for record in ijson.items(handle, prefix):
            if isinstance(record, dict):
                yield record


def normalize_record(entry: Dict[str, object]) -> Tuple[Optional[Dict[str, object]], str]:
    # Reject lexicon-style rows so they never leak into seq2seq JSONL files.
    if ('word' in entry and 'definition' in entry) or ('term' in entry and 'definition' in entry):
        return None, 'lexicon_row'

    src = ''
    tgt = ''

    # Preferred canonical record shape.
    canonical_src = to_text(entry.get('source_text'))
    canonical_tgt = to_text(entry.get('target_text'))
    if canonical_src and canonical_tgt:
        src = canonical_src
        tgt = canonical_tgt

    # Generic source/target fallback.
    if not src or not tgt:
        generic_src = to_text(entry.get('source') or entry.get('src'))
        generic_tgt = to_text(entry.get('target') or entry.get('tgt') or entry.get('reference'))
        if generic_src and generic_tgt:
            src = generic_src
            tgt = generic_tgt

    # Common repository shape: chavacano + english.
    if not src or not tgt:
        cbk = pick_text(entry, ('chavacano', 'cbk', 'chabacano'))
        eng = pick_text(entry, ('english', 'eng', 'en'))
        if cbk and eng:
            src = cbk
            tgt = eng

    # Parallel record contract.
    if src and tgt and src.casefold() != tgt.casefold():
        normalized = {
            'source_text': src,
            'target_text': tgt,
            'source_lang': to_text(entry.get('source_lang')) or 'cbk_Latn',
            'target_lang': to_text(entry.get('target_lang')) or 'eng_Latn',
            'record_type': 'parallel',
        }

        if entry.get('alignment_score') is not None:
            try:
                normalized['alignment_score'] = float(entry['alignment_score'])
            except (TypeError, ValueError):
                pass

        if entry.get('source_dataset'):
            normalized['source_dataset'] = to_text(entry.get('source_dataset'))
        elif entry.get('source'):
            normalized['source_dataset'] = to_text(entry.get('source'))

        return normalized, 'parallel'

    # Monolingual record contract (single-sided by design).
    mono = pick_text(entry, ('source_text', 'text'))
    if mono:
        normalized = {
            'source_text': mono,
            'source_lang': to_text(entry.get('source_lang') or entry.get('language')) or 'cbk_Latn',
            'task': to_text(entry.get('task')) or 'monolingual_fluency',
            'record_type': 'monolingual',
        }
        return normalized, 'monolingual'

    return None, 'unknown_shape'


def build_output_path(
    input_path: Path,
    output_root: Path,
    processed_root: Path,
) -> Path:
    try:
        relative = input_path.relative_to(processed_root)
    except ValueError:
        relative = Path(input_path.name)

    return (output_root / relative).with_suffix('.jsonl')


def convert_file(
    input_path: Path,
    output_path: Path,
    overwrite: bool,
) -> Dict[str, object]:
    if output_path.exists() and not overwrite:
        return {
            'input': str(input_path),
            'output': str(output_path),
            'status': 'skipped_existing',
            'written': 0,
            'rejected': 0,
        }

    ensure_parent_dir(output_path)

    written = 0
    rejected = 0
    rejected_reasons: Dict[str, int] = {}

    with output_path.open('w', encoding='utf-8') as out_handle:
        for entry in iter_records(input_path):
            normalized, reason = normalize_record(entry)
            if not normalized:
                rejected += 1
                rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1
                continue

            out_handle.write(json.dumps(normalized, ensure_ascii=False) + '\n')
            written += 1

    meta_path = output_path.with_suffix('.jsonl.meta.json')
    ensure_parent_dir(meta_path)
    meta_path.write_text(
        json.dumps(
            {
                'generated_at_utc': datetime.now(timezone.utc).isoformat(),
                'input': str(input_path),
                'output': str(output_path),
                'written_records': written,
                'rejected_records': rejected,
                'rejected_reasons': rejected_reasons,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )

    status = 'ok' if written > 0 else 'empty_after_filter'
    return {
        'input': str(input_path),
        'output': str(output_path),
        'status': status,
        'written': written,
        'rejected': rejected,
        'rejected_reasons': rejected_reasons,
    }


def main() -> None:
    args = parse_args()
    project_root = resolve_project_root()
    datasets_dir = resolve_datasets_dir(project_root)
    processed_root = datasets_dir / 'processed'

    input_paths = [Path(raw).expanduser().resolve() for raw in args.input]
    output_root = Path(args.output_root).expanduser().resolve()

    reports: List[Dict[str, object]] = []
    files_seen = 0

    for input_path in iter_json_files(input_paths):
        files_seen += 1
        output_path = build_output_path(input_path, output_root, processed_root)
        report = convert_file(
            input_path=input_path,
            output_path=output_path,
            overwrite=args.overwrite,
        )
        reports.append(report)

        if args.verbose:
            print(
                f"[{report['status']}] {report['input']} -> {report['output']} "
                f"written={report['written']} rejected={report['rejected']}"
            )

    total_written = sum(int(item.get('written', 0)) for item in reports)
    total_rejected = sum(int(item.get('rejected', 0)) for item in reports)

    run_report = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'files_seen': files_seen,
        'files_processed': len(reports),
        'total_written': total_written,
        'total_rejected': total_rejected,
        'reports': reports,
        'memory_note': (
            'Outputs are JSONL for line-wise streaming in PyTorch/HuggingFace '
            'to reduce peak RAM pressure on consumer devices.'
        ),
    }

    run_report_path = output_root / 'jsonl_conversion_report.json'
    ensure_parent_dir(run_report_path)
    run_report_path.write_text(
        json.dumps(run_report, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    print('JSONL_CONVERSION_DONE')
    print(f'FILES_SEEN:{files_seen}')
    print(f'TOTAL_WRITTEN:{total_written}')
    print(f'TOTAL_REJECTED:{total_rejected}')
    print(f'RUN_REPORT:{run_report_path}')


if __name__ == '__main__':
    main()
