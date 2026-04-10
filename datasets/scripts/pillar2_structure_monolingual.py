#!/usr/bin/env python3
"""PILLAR 2: Convert raw/unstructured monolingual text into strict JSON records.

Why this script exists:
- Monolingual corpora help fluency modeling and back-translation workflows.
- These records are intentionally single-sided (source_text only).
- Keeping them separate from seq2seq pairs prevents DataLoader collation errors
  and prevents accidental supervision with missing targets.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from _path_utils import ensure_parent_dir, pillar_processed_root, resolve_datasets_dir, resolve_project_root

SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+|\n+')
WHITESPACE_RE = re.compile(r'\s+')


def parse_args() -> argparse.Namespace:
    project_root = resolve_project_root()
    datasets_dir = resolve_datasets_dir(project_root)

    default_inputs = [
        datasets_dir / 'processed' / '01_chavacano' / 'wiki_monolingual_FINAL.txt',
        datasets_dir / 'processed' / '01_chavacano' / 'creole_rc_chavacano_text.txt',
        datasets_dir / 'processed' / '001_chavacano' / 'creole_rc_sentences.txt',
    ]

    default_output = (
        pillar_processed_root(datasets_dir)
        / 'monolingual'
        / 'chavacano_monolingual_corpus_nmt.json'
    )

    parser = argparse.ArgumentParser(
        description='Convert paragraph dumps into strict one-sentence monolingual JSON records.',
    )
    parser.add_argument(
        '--input',
        action='append',
        default=[str(path) for path in default_inputs],
        help='Input .txt file or directory. Can be repeated.',
    )
    parser.add_argument(
        '--output-json',
        type=str,
        default=str(default_output),
        help='Output JSON path for structured monolingual corpus.',
    )
    parser.add_argument(
        '--language',
        type=str,
        default='cbk_Latn',
        help='Language code assigned to source_text records.',
    )
    parser.add_argument('--min-chars', type=int, default=6, help='Minimum sentence length.')
    parser.add_argument('--max-chars', type=int, default=380, help='Maximum sentence length.')
    parser.add_argument('--min-alpha-ratio', type=float, default=0.55, help='Minimum alphabetic ratio.')
    parser.add_argument('--verbose', action='store_true', help='Print filtering details.')
    return parser.parse_args()


def to_text(value: object) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = WHITESPACE_RE.sub(' ', text)
    return text.strip(' \t\r\n')


def alpha_ratio(text: str) -> float:
    non_space = [ch for ch in text if not ch.isspace()]
    if not non_space:
        return 0.0
    alpha = sum(ch.isalpha() for ch in non_space)
    return alpha / len(non_space)


def iter_txt_files(paths: Sequence[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.casefold() == '.txt':
            yield path
            continue

        if path.is_dir():
            for child in sorted(path.rglob('*.txt')):
                if child.is_file():
                    yield child


def split_sentences(block: str) -> List[str]:
    # Split by punctuation boundaries and hard newlines.
    return [piece for piece in SENTENCE_SPLIT_RE.split(block) if piece and piece.strip()]


def is_quality_sentence(text: str, min_chars: int, max_chars: int, min_alpha_ratio: float) -> bool:
    if len(text) < min_chars or len(text) > max_chars:
        return False

    if len(text.split()) < 2:
        return False

    if alpha_ratio(text) < min_alpha_ratio:
        return False

    return True


def main() -> None:
    args = parse_args()
    project_root = resolve_project_root()

    input_paths = [Path(raw).expanduser().resolve() for raw in args.input]
    output_path = Path(args.output_json).expanduser().resolve()

    entries: List[Dict[str, object]] = []
    seen = set()

    files_seen = 0
    files_used = 0
    sentence_candidates = 0
    sentence_kept = 0
    filtered_quality = 0
    duplicate_removed = 0

    for path in iter_txt_files(input_paths):
        files_seen += 1

        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            if args.verbose:
                print(f'[SKIP:DECODE] {path}')
            continue

        files_used += 1
        rel_path = str(path.relative_to(project_root))

        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            line = to_text(raw_line)
            if not line:
                continue

            for candidate in split_sentences(line):
                sentence_candidates += 1
                sentence = to_text(candidate)
                if not sentence:
                    filtered_quality += 1
                    continue

                if not is_quality_sentence(
                    sentence,
                    min_chars=args.min_chars,
                    max_chars=args.max_chars,
                    min_alpha_ratio=args.min_alpha_ratio,
                ):
                    filtered_quality += 1
                    if args.verbose:
                        print(f'[FILTER:QUALITY] {rel_path}:{line_no} -> {sentence[:80]}')
                    continue

                key = sentence.casefold()
                if key in seen:
                    duplicate_removed += 1
                    continue
                seen.add(key)

                sentence_kept += 1
                entries.append(
                    {
                        'id': f'mono-{sentence_kept:08d}',
                        'source_text': sentence,
                        'source_lang': args.language,
                        'task': 'monolingual_fluency',
                        'source_file': rel_path,
                        'line_number': line_no,
                        'char_count': len(sentence),
                        'token_count_estimate': len(sentence.split()),
                    }
                )

    output_payload = {
        'metadata': {
            'dataset_type': 'monolingual_corpus',
            'pillar': 'monolingual',
            'contract_version': '1.0',
            'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'language': args.language,
            'files_seen': files_seen,
            'files_used': files_used,
            'sentence_candidates': sentence_candidates,
            'sentence_kept': sentence_kept,
            'filtered_quality': filtered_quality,
            'duplicates_removed': duplicate_removed,
            # Explicit guardrail: no target_text in this pillar by design.
            'loss_safety_note': (
                'Monolingual records are single-sided and excluded from supervised '
                'seq2seq loss tensors unless converted via back-translation.'
            ),
        },
        'entries': entries,
    }

    ensure_parent_dir(output_path)
    output_path.write_text(
        json.dumps(output_payload, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    print('PILLAR2_MONOLINGUAL_DONE')
    print(f'OUTPUT:{output_path}')
    print(f'FILES_SEEN:{files_seen}')
    print(f'FILES_USED:{files_used}')
    print(f'RECORDS:{len(entries)}')


if __name__ == '__main__':
    main()
