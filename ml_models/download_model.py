"""
download_model.py - Explicit offline base-model downloader for Project PUENTE.

This script implements the thesis "Cloud-to-Local" handoff for Phase B
(offline defense mode) by downloading the base NLLB weights to the exact
local directory used by Django startup:

  /home/rauf/Desktop/Machine Learning/ProjectPuente/ml_models/nllb-200-distilled-600M

Usage:
  cd ml_models
  python download_model.py

Optional environment variable:
  HF_TOKEN=<your_huggingface_token>
"""

from pathlib import Path
import os
import sys


MODEL_ID = 'facebook/nllb-200-distilled-600M'
TARGET_DIR = Path('/home/rauf/Desktop/Machine Learning/ProjectPuente/ml_models/nllb-200-distilled-600M')


def main():
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: 'huggingface_hub' is not installed.")
        print("Run: pip install huggingface_hub")
        sys.exit(1)

    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    if any(TARGET_DIR.iterdir()):
        print(f'Model directory is not empty: {TARGET_DIR}')
        answer = input('Re-download and overwrite files? [y/N]: ').strip().lower()
        if answer != 'y':
            print('Skipping download.')
            return

    hf_token = os.getenv('HF_TOKEN', '').strip() or None

    print('=' * 72)
    print('Project PUENTE - Offline Base Model Download')
    print(f'Model ID   : {MODEL_ID}')
    print(f'Target Path: {TARGET_DIR}')
    print('=' * 72)

    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(TARGET_DIR),
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
    missing = [name for name in expected_files if not (TARGET_DIR / name).exists()]

    print('\nDownload complete.')
    if missing:
        print('WARNING: Some expected files are missing:')
        for item in missing:
            print(f' - {item}')
    else:
        print('Verification passed: essential model/tokenizer files detected.')

    print('\nNext step: place LoRA adapters under:')
    print('  /home/rauf/Desktop/Machine Learning/ProjectPuente/ml_models/lora_adapters/')


if __name__ == '__main__':
    main()
