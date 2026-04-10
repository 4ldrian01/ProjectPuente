"""Shared path helpers for dataset ETL scripts.

This module keeps dataset scripts portable across Linux/Windows and avoids
hard-coded absolute paths.
"""

from __future__ import annotations

from pathlib import Path


def resolve_project_root() -> Path:
    """Return repository root from datasets/scripts/<file>.py."""
    return Path(__file__).resolve().parents[2]


def resolve_datasets_dir(project_root: Path) -> Path:
    """Return canonical datasets directory with compatibility fallback."""
    primary = project_root / 'datasets'
    if primary.exists():
        return primary

    fallback = project_root / 'Datasets'
    if fallback.exists():
        return fallback

    return primary


def pillar_processed_root(datasets_dir: Path) -> Path:
    """Root for the strict 3-pillar processed artifacts."""
    return datasets_dir / 'processed' / 'pillars'


def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
