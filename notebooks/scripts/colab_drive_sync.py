"""Drive <-> local data sync utility for Colab training workloads.

Purpose:
- Stage train/eval/test JSONL from Google Drive to local Colab storage (/content/data).
- Verify integrity with SHA-256 after every copy.
- Mirror checkpoints or adapters back to Drive with checksum validation.

Why this matters:
- Drive FUSE reads are slower than local ephemeral storage.
- Loading JSONL from /content/data significantly reduces data-loader I/O bottlenecks.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Dict, Tuple


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def copy_file_with_checksum(src: Path, dst: Path) -> None:
    ensure_parent_dir(dst)
    tmp_dst = dst.with_suffix(dst.suffix + '.tmp')
    shutil.copy2(src, tmp_dst)

    src_hash = sha256_file(src)
    dst_hash = sha256_file(tmp_dst)
    if src_hash != dst_hash:
        raise RuntimeError(
            f'Checksum mismatch after copy: src={src} dst={dst} '
            f'src_hash={src_hash} dst_hash={dst_hash}'
        )

    tmp_dst.replace(dst)


def file_unchanged(src: Path, dst: Path) -> bool:
    if not dst.exists():
        return False

    src_stat = src.stat()
    dst_stat = dst.stat()
    if src_stat.st_size != dst_stat.st_size:
        return False

    return sha256_file(src) == sha256_file(dst)


def sync_tree_with_checksums(src_root: Path, dst_root: Path) -> Tuple[int, int]:
    copied = 0
    skipped = 0

    if not src_root.exists():
        return copied, skipped

    for src in src_root.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        dst = dst_root / rel

        if file_unchanged(src, dst):
            skipped += 1
            continue

        copy_file_with_checksum(src, dst)
        copied += 1

    return copied, skipped


def stage_split_jsonl(drive_dataset_dir: Path, local_data_dir: Path, filenames: Dict[str, str]) -> Dict[str, Path]:
    """Copy train/eval/test JSONL from Drive to local data dir with hash checks."""
    local_paths: Dict[str, Path] = {}

    for split_name, filename in filenames.items():
        src = drive_dataset_dir / filename
        dst = local_data_dir / filename
        if not src.exists():
            raise FileNotFoundError(f'Missing split file on Drive: {src}')

        if not file_unchanged(src, dst):
            copy_file_with_checksum(src, dst)

        local_paths[split_name] = dst

    return local_paths
