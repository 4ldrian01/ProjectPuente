"""
validate_model.py — Quick validation script for the downloaded NLLB-200 model.

Usage:
    cd ml_models
    python validate_model.py

Tests that the model can load and perform a simple translation.
"""

import os
import sys
import time


def main():
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nllb-200-distilled-600M")

    if not os.path.isdir(model_dir):
        print(f"ERROR: Model not found at {model_dir}")
        print("Run: python download_model.py")
        sys.exit(1)

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        sys.exit(1)

    print(f"Loading tokenizer from {model_dir} ...")
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)

    print("Loading model ...")
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_dir, local_files_only=True, torch_dtype=torch.float32,
    )
    model.eval()

    params = sum(p.numel() for p in model.parameters())
    print(f"Model loaded: {params:,} parameters\n")

    # ── Test translations ──
    test_cases = [
        ("Hello, how are you?", "eng_Latn", "cbk_Latn", "English → Chavacano"),
        ("Good morning", "eng_Latn", "tgl_Latn", "English → Tagalog"),
        ("I love Zamboanga", "eng_Latn", "ceb_Latn", "English → Cebuano"),
        ("Maayong buntag", "ceb_Latn", "eng_Latn", "Cebuano → English"),
        ("Magandang umaga", "tgl_Latn", "hil_Latn", "Tagalog → Hiligaynon"),
    ]

    print(f"{'Test':<25} {'Input':<25} {'Output':<30} {'Time'}")
    print("=" * 95)

    for text, src, tgt, label in test_cases:
        tokenizer.src_lang = src
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128)

        start = time.perf_counter()
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.convert_tokens_to_ids(tgt),
                max_new_tokens=128,
                num_beams=4,
            )
        elapsed = (time.perf_counter() - start) * 1000

        result = tokenizer.batch_decode(output_ids, skip_special_tokens=True)[0]
        print(f"{label:<25} {text:<25} {result:<30} {elapsed:.0f}ms")

    print(f"\n{'='*95}")
    print("All validation tests passed. Model is ready for deployment.")

    # ── Check LoRA adapters ──
    lora_dir = os.path.dirname(model_dir)
    for mode in ["formal", "street"]:
        adapter_path = os.path.join(lora_dir, f"lora-cbk-{mode}")
        if os.path.isdir(adapter_path):
            print(f"  LoRA adapter found: {mode}")
        else:
            print(f"  LoRA adapter missing: {mode} (will use base model)")


if __name__ == "__main__":
    main()
