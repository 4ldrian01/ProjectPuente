"""
download_model.py — Download & save NLLB-200-distilled-600M for offline use.

Usage:
    cd ml_models
    python download_model.py

This script downloads the base model (~2.4 GB) from Hugging Face Hub
and saves it locally so the Django backend can load it without internet.
"""

import os
import sys


def main():
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError:
        print("ERROR: 'transformers' package not installed.")
        print("Run: pip install transformers sentencepiece protobuf")
        sys.exit(1)

    MODEL_NAME = "facebook/nllb-200-distilled-600M"
    SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nllb-200-distilled-600M")

    if os.path.isdir(SAVE_DIR) and os.listdir(SAVE_DIR):
        print(f"Model already exists at: {SAVE_DIR}")
        resp = input("Re-download? [y/N]: ").strip().lower()
        if resp != "y":
            print("Skipping download.")
            return

    print(f"Downloading tokenizer: {MODEL_NAME} ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    print(f"Saving tokenizer to: {SAVE_DIR}")
    tokenizer.save_pretrained(SAVE_DIR)

    print(f"\nDownloading model: {MODEL_NAME} (~2.4 GB) ...")
    print("This may take several minutes depending on your internet speed.")
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    print(f"Saving model to: {SAVE_DIR}")
    model.save_pretrained(SAVE_DIR)

    # Verify
    param_count = sum(p.numel() for p in model.parameters())
    print(f"\n{'='*60}")
    print(f"  Download complete!")
    print(f"  Location: {SAVE_DIR}")
    print(f"  Parameters: {param_count:,}")
    print(f"  Files: {len(os.listdir(SAVE_DIR))}")
    print(f"{'='*60}")
    print("\nRestart the Django server to load the model.")
    print("The backend will automatically detect and load it from apps.py.")


if __name__ == "__main__":
    main()
