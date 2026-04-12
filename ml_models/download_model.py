"""
download_model.py - Explicit offline base-model downloader for Project PUENTE.

This script implements the thesis "Cloud-to-Local" handoff for Phase B
(offline defense mode) by downloading the base NLLB weights to the project-local
directory used by Django startup.

Default target directory:
    <project-root>/ml_models/nllb-200-distilled-600M

Usage:
    cd ml_models
    python download_model.py

Optional environment variables:
    HF_TOKEN=<your_huggingface_token>
    ML_MODEL_PATH=<absolute-or-project-relative-model-path>
"""

from pathlib import Path
import os
import sys


MODEL_ID = 'facebook/nllb-200-distilled-600M'


def _resolve_target_dir() -> Path:
    """Resolve model output directory from ML_MODEL_PATH or project default."""
    project_root = Path(__file__).resolve().parents[1]
    configured = os.getenv('ML_MODEL_PATH', '').strip()

    if configured:
        candidate = Path(configured)
        if not candidate.is_absolute():
            candidate = project_root / candidate
        return candidate.resolve()

    return (project_root / 'ml_models' / 'nllb-200-distilled-600M').resolve()


def main():
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: 'huggingface_hub' is not installed.")
        print("Run: pip install huggingface_hub")
        sys.exit(1)

    target_dir = _resolve_target_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    if any(target_dir.iterdir()):
        print(f'Model directory is not empty: {target_dir}')
        answer = input('Re-download and overwrite files? [y/N]: ').strip().lower()
        if answer != 'y':
            print('Skipping download.')
            return

    hf_token = os.getenv('HF_TOKEN', '').strip() or None

    print('=' * 72)
    print('Project PUENTE - Offline Base Model Download')
    print(f'Model ID   : {MODEL_ID}')
    print(f'Target Path: {target_dir}')
    print('=' * 72)

    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        resume_download=True,
        token=hf_token,
    )

    expected_files = [
        'config.json',
        'generation_config.json',
        'tokenizer_config.json',
        'sentencepiece.bpe.model',
    ]
    missing = [name for name in expected_files if not (target_dir / name).exists()]

    print('\nDownload complete.')
    if missing:
        print('WARNING: Some expected files are missing:')
        for item in missing:
            print(f' - {item}')
    else:
        print('Verification passed: essential model/tokenizer files detected.')

    print('\nNext step: place LoRA adapters under:')
    print('  <project-root>/ml_models/lora_adapters/')


if __name__ == '__main__':
    main()
