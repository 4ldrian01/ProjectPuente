"""
train_lora.py — LoRA fine-tuning script for Chavacano formal/street adapters.

Usage:
    cd ml_models
    python train_lora.py --mode formal --dataset ../Datasets/processed/001_chavacano/
    python train_lora.py --mode street --dataset ../Datasets/processed/001_chavacano/

This trains a LoRA adapter on top of the NLLB-200-distilled-600M base model
using parallel sentence data from the Datasets/processed/ directory.

Output:
    ml_models/lora-cbk-formal/   (or lora-cbk-street/)
        adapter_config.json
        adapter_model.bin
"""

import argparse
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="Train LoRA adapter for NLLB-200")
    parser.add_argument(
        "--mode",
        choices=["formal", "street"],
        required=True,
        help="Sociolinguistic register: formal (high variety) or street (low variety)",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="../Datasets/processed/001_chavacano/",
        help="Path to processed dataset directory containing NLLB-ready JSON files",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="./nllb-200-distilled-600M",
        help="Path to the base NLLB-200 model directory",
    )
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Training batch size")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha scaling")
    parser.add_argument("--lora-dropout", type=float, default=0.05, help="LoRA dropout")
    return parser.parse_args()


def load_parallel_data(dataset_dir):
    """Load parallel sentence pairs from processed JSON files."""
    pairs = []
    for filename in os.listdir(dataset_dir):
        if not filename.endswith("_nllb.json"):
            continue
        filepath = os.path.join(dataset_dir, filename)
        print(f"  Loading: {filename}")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for entry in data:
                src = entry.get("eng") or entry.get("en") or entry.get("source", "")
                tgt = entry.get("cbk") or entry.get("chavacano") or entry.get("target", "")
                if src.strip() and tgt.strip():
                    pairs.append((src.strip(), tgt.strip()))
    return pairs


def main():
    args = parse_args()

    # ── Validate prerequisites ──
    if not os.path.isdir(args.base_model):
        print(f"ERROR: Base model not found at {args.base_model}")
        print("Run: python download_model.py")
        sys.exit(1)

    if not os.path.isdir(args.dataset):
        print(f"ERROR: Dataset directory not found at {args.dataset}")
        sys.exit(1)

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model, TaskType
    except ImportError as e:
        print(f"ERROR: Missing dependency: {e}")
        print("Run: pip install torch transformers peft sentencepiece")
        sys.exit(1)

    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"lora-cbk-{args.mode}",
    )

    # ── Load data ──
    print(f"\nLoading {args.mode} training data from {args.dataset} ...")
    pairs = load_parallel_data(args.dataset)
    print(f"  Loaded {len(pairs)} parallel sentence pairs")

    if len(pairs) < 10:
        print("WARNING: Very few training samples. Results may be poor.")

    # ── Load base model + tokenizer ──
    print(f"\nLoading base model: {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        args.base_model,
        local_files_only=True,
        torch_dtype=torch.float32,
    )

    # ── Configure LoRA ──
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "v_proj"],  # Attention projection layers
        bias="none",
    )

    print(f"\nApplying LoRA config: r={args.lora_r}, alpha={args.lora_alpha}")
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # ── Prepare dataset ──
    print("\nTokenizing training data ...")
    tokenizer.src_lang = "eng_Latn"

    train_encodings = []
    for src, tgt in pairs:
        inputs = tokenizer(src, truncation=True, max_length=128, padding="max_length")
        labels = tokenizer(
            text_target=tgt, truncation=True, max_length=128, padding="max_length",
        )
        inputs["labels"] = labels["input_ids"]
        train_encodings.append(inputs)

    # ── Training loop (simplified — use Trainer for production) ──
    from torch.utils.data import DataLoader, Dataset

    class PairDataset(Dataset):
        def __init__(self, encodings):
            self.encodings = encodings

        def __len__(self):
            return len(self.encodings)

        def __getitem__(self, idx):
            return {k: torch.tensor(v) for k, v in self.encodings[idx].items()}

    dataset = PairDataset(train_encodings)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    model.train()

    print(f"\nTraining LoRA adapter ({args.mode}) for {args.epochs} epochs ...")
    for epoch in range(args.epochs):
        total_loss = 0.0
        for batch_idx, batch in enumerate(loader):
            outputs = model(**batch)
            loss = outputs.loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            total_loss += loss.item()

            if (batch_idx + 1) % 10 == 0:
                print(f"  Epoch {epoch+1}/{args.epochs}, Batch {batch_idx+1}, Loss: {loss.item():.4f}")

        avg_loss = total_loss / max(len(loader), 1)
        print(f"  Epoch {epoch+1}/{args.epochs} complete — Avg Loss: {avg_loss:.4f}")

    # ── Save adapter ──
    print(f"\nSaving LoRA adapter to: {output_dir}")
    model.save_pretrained(output_dir)

    print(f"\n{'='*60}")
    print(f"  LoRA adapter trained successfully!")
    print(f"  Mode: {args.mode}")
    print(f"  Output: {output_dir}")
    print(f"  Training samples: {len(pairs)}")
    print(f"{'='*60}")
    print("\nRestart the Django server to load the new adapter.")


if __name__ == "__main__":
    main()
