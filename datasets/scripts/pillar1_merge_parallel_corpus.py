#!/usr/bin/env python3
"""PILLAR 1: Merge metadata-rich parallel corpora for seq2seq training.

Why this script exists:
- Seq2Seq objectives minimize cross-entropy over aligned pairs (x, y).
- Mixing dictionary rows into this tensor (for example: word/POS/definition)
  injects non-aligned feature distributions and destabilizes gradients.
- The result is noisy loss surfaces and avoidable training/runtime failures.

This script enforces strict contracts:
- Only metadata-rich JSON files (`{"metadata": ..., "entries": [...]}`) are read.
- Candidate files are rejected if they look like lexicon/monolingual pillars.
- Records are normalized into one canonical pair schema:
    source_text, target_text, source_lang, target_lang
- Duplicate aligned pairs are removed deterministically.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from _path_utils import ensure_parent_dir, pillar_processed_root, resolve_datasets_dir, resolve_project_root

# Filenames with these markers are never treated as parallel corpora.
FILENAME_BLOCKLIST = ('lexicon', 'dictionary', 'glossary', 'monolingual', 'wiki')

# Approximate aliases seen in this repository and in standard NMT payloads.
APP_TEXT_KEYS = {
    'en': ('english', 'eng', 'en'),
    'es': ('spanish', 'espanol', 'es'),
    'cbk': ('chavacano', 'cbk', 'chabacano'),
    'tl': ('tagalog', 'tl', 'tgl'),
    'ceb': ('cebuano', 'ceb', 'bisaya'),
    'hil': ('hiligaynon', 'hil'),
}

FLORES_TO_APP = {
    'eng_Latn': 'en',
    'spa_Latn': 'es',
    'cbk_Latn': 'cbk',
    'tgl_Latn': 'tl',
    'ceb_Latn': 'ceb',
    'hil_Latn': 'hil',
}


def parse_args() -> argparse.Namespace:
    project_root = resolve_project_root()
    datasets_dir = resolve_datasets_dir(project_root)

    default_input = datasets_dir / 'processed' / '001_chavacano'
    default_output = (
        pillar_processed_root(datasets_dir)
        / 'parallel'
        / 'master_parallel_corpus_nmt.json'
    )

    parser = argparse.ArgumentParser(
        description='Merge strict metadata-rich parallel JSON files into one master corpus.',
    )
    parser.add_argument(
        '--input-dir',
        action='append',
        default=[str(default_input)],
        help='Directory containing metadata-rich parallel JSON files. Can be repeated.',
    )
    parser.add_argument(
        '--output-json',
        type=str,
        default=str(default_output),
        help='Output path for merged master parallel corpus JSON.',
    )
    parser.add_argument(
        '--source-lang',
        type=str,
        default='cbk_Latn',
        help='Canonical source language code for output records.',
    )
    parser.add_argument(
        '--target-lang',
        type=str,
        default='eng_Latn',
        help='Canonical target language code for output records.',
    )
    parser.add_argument(
        '--min-alignment-score',
        type=float,
        default=0.0,
        help='Optional floor for entry alignment_score (default keeps all).',
    )
    parser.add_argument(
        '--min-parallel-ratio',
        type=float,
        default=0.60,
        help='Reject a file if fewer than this ratio of entries contain valid pairs.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print per-file reject reasons for non-parallel records.',
    )
    return parser.parse_args()


def to_text(value: object) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_pair_key(src: str, tgt: str) -> Tuple[str, str]:
    return (to_text(src).casefold(), to_text(tgt).casefold())


def app_code_from_lang_code(lang_code: str) -> str:
    raw = str(lang_code or '').strip()
    if raw in FLORES_TO_APP:
        return FLORES_TO_APP[raw]
    if '_' in raw:
        raw = raw.split('_', 1)[0]
    return raw.casefold()


def build_field_aliases(lang_code: str, generic_keys: Sequence[str]) -> Tuple[str, ...]:
    app_code = app_code_from_lang_code(lang_code)
    app_keys = APP_TEXT_KEYS.get(app_code, ())

    # Keep canonical first, then language-specific aliases, then generic fallbacks.
    merged = list(dict.fromkeys([*app_keys, *generic_keys]))
    return tuple(merged)


def pick_text(entry: Dict[str, object], aliases: Sequence[str]) -> str:
    for key in aliases:
        value = entry.get(key)
        text = to_text(value)
        if text:
            return text
    return ''


def is_blocklisted_file(path: Path) -> bool:
    name = path.name.casefold()
    return any(marker in name for marker in FILENAME_BLOCKLIST)


def iter_json_files(input_dirs: Iterable[Path]) -> Iterable[Path]:
    for input_dir in input_dirs:
        if not input_dir.is_dir():
            continue
        for path in sorted(input_dir.rglob('*.json')):
            yield path


def load_metadata_rich_payload(path: Path) -> Optional[Dict[str, object]]:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get('metadata'), dict):
        return None
    if not isinstance(payload.get('entries'), list):
        return None
    return payload


def as_float(value: object, default: float = 1.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    args = parse_args()
    project_root = resolve_project_root()

    input_dirs = [Path(raw).expanduser().resolve() for raw in args.input_dir]
    output_path = Path(args.output_json).expanduser().resolve()

    source_aliases = build_field_aliases(
        args.source_lang,
        generic_keys=('source_text', 'source', 'src', 'input_text', 'input'),
    )
    target_aliases = build_field_aliases(
        args.target_lang,
        generic_keys=('target_text', 'target', 'tgt', 'reference', 'label'),
    )

    merged_entries: List[Dict[str, object]] = []
    seen_pairs = set()

    files_seen = 0
    files_accepted = 0
    files_rejected = 0
    rejected_by_shape = 0
    rejected_by_name = 0
    rejected_by_ratio = 0
    duplicate_pairs = 0
    below_alignment_floor = 0

    source_files: List[Dict[str, object]] = []

    for path in iter_json_files(input_dirs):
        files_seen += 1

        if is_blocklisted_file(path):
            files_rejected += 1
            rejected_by_name += 1
            if args.verbose:
                print(f'[SKIP:NAME] {path}')
            continue

        payload = load_metadata_rich_payload(path)
        if payload is None:
            files_rejected += 1
            rejected_by_shape += 1
            if args.verbose:
                print(f'[SKIP:SHAPE] {path}')
            continue

        metadata = payload['metadata']
        entries = payload['entries']

        valid_pairs = 0
        local_keys = set()
        local_pairs: List[Dict[str, object]] = []

        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue

            src_text = pick_text(entry, source_aliases)
            tgt_text = pick_text(entry, target_aliases)

            if not src_text or not tgt_text:
                continue

            alignment_score = as_float(entry.get('alignment_score'), default=1.0)
            if alignment_score < args.min_alignment_score:
                below_alignment_floor += 1
                continue

            pair_key = normalize_pair_key(src_text, tgt_text)
            if pair_key in seen_pairs or pair_key in local_keys:
                duplicate_pairs += 1
                continue

            local_keys.add(pair_key)
            valid_pairs += 1

            local_pairs.append(
                {
                    'source_text': src_text,
                    'target_text': tgt_text,
                    'source_lang': args.source_lang,
                    'target_lang': args.target_lang,
                    'alignment_score': round(alignment_score, 4),
                    'category': to_text(entry.get('category')),
                    'record_type': to_text(entry.get('type')),
                    'source_dataset': to_text(metadata.get('source')) or path.name,
                    'source_file': str(path.relative_to(project_root)),
                    'source_index': idx,
                }
            )

        ratio = (valid_pairs / len(entries)) if entries else 0.0
        if ratio < args.min_parallel_ratio:
            files_rejected += 1
            rejected_by_ratio += 1
            if args.verbose:
                print(f'[SKIP:RATIO {ratio:.2f}] {path}')
            continue

        files_accepted += 1
        source_files.append(
            {
                'file': str(path.relative_to(project_root)),
                'records_total': len(entries),
                'records_accepted': len(local_pairs),
                'parallel_ratio': round(ratio, 4),
                'source': to_text(metadata.get('source')),
            }
        )

        seen_pairs.update(local_keys)
        merged_entries.extend(local_pairs)

    for index, record in enumerate(merged_entries, start=1):
        record['id'] = f'parallel-{index:08d}'

    output_payload = {
        'metadata': {
            'dataset_type': 'parallel_corpus',
            'pillar': 'parallel',
            'contract_version': '1.0',
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'source_lang': args.source_lang,
            'target_lang': args.target_lang,
            'total_records': len(merged_entries),
            'files_seen': files_seen,
            'files_accepted': files_accepted,
            'files_rejected': files_rejected,
            'rejections': {
                'name_blocklist': rejected_by_name,
                'invalid_shape': rejected_by_shape,
                'low_parallel_ratio': rejected_by_ratio,
            },
            'dedupe_removed': duplicate_pairs,
            'below_alignment_floor': below_alignment_floor,
            # This rationale is intentionally explicit for future contributors.
            'loss_safety_note': (
                'Parallel tensors must contain aligned sequence pairs only. '
                'Lexicon entries are retrieval features, not seq2seq targets.'
            ),
        },
        'source_files': source_files,
        'entries': merged_entries,
    }

    ensure_parent_dir(output_path)
    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    print('PILLAR1_MERGE_DONE')
    print(f'OUTPUT:{output_path}')
    print(f'TOTAL_RECORDS:{len(merged_entries)}')
    print(f'FILES_SEEN:{files_seen}')
    print(f'FILES_ACCEPTED:{files_accepted}')
    print(f'FILES_REJECTED:{files_rejected}')


if __name__ == '__main__':
    main()
