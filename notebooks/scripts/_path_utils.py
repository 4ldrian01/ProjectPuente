"""Path helpers for notebook processing scripts.

These helpers keep scripts portable across Windows (case-insensitive paths)
and Linux/macOS (case-sensitive paths) by resolving repository directories
using canonical names with safe fallbacks.
"""

from pathlib import Path


def resolve_datasets_dir(project_root: Path) -> Path:
    """Return the canonical datasets directory with compatibility fallback."""
    primary = project_root / 'datasets'
    if primary.exists():
        return primary

    fallback = project_root / 'Datasets'
    if fallback.exists():
        return fallback

    # Default to canonical path for newly created setups.
    return primary
