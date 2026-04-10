#!/usr/bin/env python3
"""Task 3: Safe archival of legacy/raw duplicates to prevent data poisoning.

Safety principles:
- Never delete source files; move them to datasets/archive/<timestamp>/.
- Default mode is dry-run.
- Every move is logged in a manifest with reason and checksum.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from _path_utils import ensure_parent_dir, resolve_datasets_dir, resolve_project_root

DUPLICATE_NAME_RE = re.compile(r'\(\d+\)|copy', flags=re.IGNORECASE)

# Explicit source->processed mappings for this repository.
PROCESSED_GUARDRAIL_MAP = {
    '02_Chavacano/chavacano-to-english-parallel-sentences.csv': [
        '001_chavacano/chavacano_parallel_sentences_nllb.json',
    ],
    '02_Chavacano/cbk-en.txt.zip': [
        '001_chavacano/tatoeba_parallel_nllb.json',
    ],
    '02_Chavacano/cbk_zamwiki-latest-pages-articles.xml.bz2': [
        '01_chavacano/wiki_monolingual_FINAL.txt',
    ],
    '02_Chavacano/creole_rc': [
        '001_chavacano/creole_rc_chavacano_nllb.json',
    ],
}


def parse_args() -> argparse.Namespace:
    project_root = resolve_project_root()
    datasets_dir = resolve_datasets_dir(project_root)

    parser = argparse.ArgumentParser(
        description='Archive duplicate/legacy raw data safely into datasets/archive.',
    )
    parser.add_argument(
        '--raw-root',
        type=str,
        default=str(datasets_dir / 'raw'),
        help='Raw data root to scan.',
    )
    parser.add_argument(
        '--processed-root',
        type=str,
        default=str(datasets_dir / 'processed'),
        help='Processed data root used for "already processed" checks.',
    )
    parser.add_argument(
        '--archive-root',
        type=str,
        default=str(datasets_dir / 'archive'),
        help='Archive root where files will be moved.',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Apply moves. Default is dry-run.',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print every candidate and reason.',
    )
    return parser.parse_args()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def is_json_malformed(path: Path) -> bool:
    if path.suffix.casefold() != '.json':
        return False
    try:
        json.loads(path.read_text(encoding='utf-8'))
        return False
    except Exception:
        return True


def is_already_processed(path: Path, raw_root: Path, processed_root: Path) -> Optional[str]:
    rel = str(path.relative_to(raw_root)).replace('\\', '/')

    for raw_pattern, processed_targets in PROCESSED_GUARDRAIL_MAP.items():
        is_directory_mapping = not Path(raw_pattern).suffix

        if is_directory_mapping:
            if not rel.startswith(raw_pattern.rstrip('/') + '/'):
                continue
        else:
            if rel != raw_pattern:
                continue

        if any((processed_root / target).exists() for target in processed_targets):
            return raw_pattern

    return None


def collect_candidates(raw_root: Path, processed_root: Path) -> List[Dict[str, object]]:
    candidates: List[Dict[str, object]] = []
    seen_hashes: Dict[str, Path] = {}

    for path in sorted(raw_root.rglob('*')):
        if not path.is_file():
            continue

        reasons: List[str] = []

        if DUPLICATE_NAME_RE.search(path.name):
            reasons.append('duplicate_name_pattern')

        if is_json_malformed(path):
            reasons.append('malformed_json')

        processed_match = is_already_processed(path, raw_root, processed_root)
        if processed_match:
            reasons.append(f'already_processed:{processed_match}')

        file_hash = sha256_file(path)
        first_seen = seen_hashes.get(file_hash)
        if first_seen is None:
            seen_hashes[file_hash] = path
        else:
            reasons.append(f'duplicate_content:{first_seen.relative_to(raw_root)}')

        if reasons:
            candidates.append(
                {
                    'path': path,
                    'relative_path': path.relative_to(raw_root),
                    'sha256': file_hash,
                    'reasons': reasons,
                }
            )

    return candidates


def archive_candidates(
    candidates: Iterable[Dict[str, object]],
    raw_root: Path,
    archive_root: Path,
    apply: bool,
) -> Tuple[List[Dict[str, object]], int]:
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    batch_root = archive_root / f'legacy_cleanup_{timestamp}'

    moved_count = 0
    manifest_entries: List[Dict[str, object]] = []

    for item in candidates:
        src_path = item['path']
        rel_path = item['relative_path']
        dst_path = batch_root / rel_path

        manifest_entry = {
            'source': str(src_path),
            'destination': str(dst_path),
            'relative_path': str(rel_path),
            'sha256': item['sha256'],
            'reasons': item['reasons'],
            'status': 'planned' if not apply else 'moved',
        }

        if apply:
            ensure_parent_dir(dst_path)
            shutil.move(str(src_path), str(dst_path))
            moved_count += 1

        manifest_entries.append(manifest_entry)

    manifest_path = batch_root / 'archive_manifest.json'
    ensure_parent_dir(manifest_path)
    manifest_payload = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'apply' if apply else 'dry_run',
        'raw_root': str(raw_root),
        'archive_root': str(batch_root),
        'candidate_count': len(manifest_entries),
        'moved_count': moved_count,
        'entries': manifest_entries,
    }
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding='utf-8')

    return manifest_entries, moved_count


def main() -> None:
    args = parse_args()

    raw_root = Path(args.raw_root).expanduser().resolve()
    processed_root = Path(args.processed_root).expanduser().resolve()
    archive_root = Path(args.archive_root).expanduser().resolve()

    if not raw_root.is_dir():
        raise SystemExit(f'Raw root not found: {raw_root}')

    candidates = collect_candidates(raw_root=raw_root, processed_root=processed_root)

    if args.verbose:
        for item in candidates:
            print(f"CANDIDATE:{item['relative_path']} REASONS:{';'.join(item['reasons'])}")

    manifest_entries, moved_count = archive_candidates(
        candidates=candidates,
        raw_root=raw_root,
        archive_root=archive_root,
        apply=args.apply,
    )

    print('LEGACY_ARCHIVE_SCAN_DONE')
    print(f'MODE:{"apply" if args.apply else "dry_run"}')
    print(f'CANDIDATES:{len(manifest_entries)}')
    print(f'MOVED:{moved_count}')


if __name__ == '__main__':
    main()
