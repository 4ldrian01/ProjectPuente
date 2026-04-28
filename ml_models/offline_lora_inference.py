"""
Local/offline NLLB-200 + LoRA inference utility for Project PUENTE.

This script loads a base model and LoRA adapter strictly from local paths and
never attempts network downloads.

Example:
    cd /home/rauf/Desktop/Machine\ Learning/ProjectPuente
    source venv/bin/activate
    python ml_models/offline_lora_inference.py \
      --text "Buenas dias, kumusta tu familia?" \
      --src-lang cbk_Latn \
      --tgt-lang eng_Latn
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path


# Enforce offline behavior for Hugging Face tooling.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


APP_TO_FLORES = {
    "auto": "eng_Latn",
    "en": "eng_Latn",
    "es": "spa_Latn",
    "tl": "tgl_Latn",
    "cbk": "cbk_Latn",
    "ceb": "ceb_Latn",
    "hil": "hil_Latn",
}

SUPPORTED_FLORES = frozenset(APP_TO_FLORES.values())


def resolve_language_tag(language: str) -> str:
    """Resolve app code or FLORES tag to canonical FLORES language tag."""
    raw = str(language or "").strip()
    if not raw:
        raise ValueError("Language cannot be empty.")

    normalized = raw.casefold()
    if normalized in APP_TO_FLORES:
        return APP_TO_FLORES[normalized]

    for flores in SUPPORTED_FLORES:
        if flores.casefold() == normalized:
            return flores

    allowed = ", ".join(sorted(SUPPORTED_FLORES | set(APP_TO_FLORES.keys())))
    raise ValueError(f"Unsupported language '{language}'. Allowed values: {allowed}")


def validate_base_model_dir(base_model_dir: Path) -> None:
    """Ensure local base model directory has required NLLB files."""
    required_files = [
        "config.json",
        "generation_config.json",
        "tokenizer_config.json",
        "sentencepiece.bpe.model",
    ]

    missing = [name for name in required_files if not (base_model_dir / name).is_file()]
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(
            f"Base model directory is missing required files: {missing_text}"
        )

    weight_candidates = [
        "pytorch_model.bin",
        "model.safetensors",
        "model.safetensors.index.json",
    ]
    if not any((base_model_dir / name).exists() for name in weight_candidates):
        candidates = ", ".join(weight_candidates)
        raise FileNotFoundError(
            "Base model weights not found. Expected one of: "
            f"{candidates}"
        )


def validate_adapter_dir(adapter_dir: Path) -> None:
    """Ensure local adapter directory has required PEFT adapter files."""
    if not (adapter_dir / "adapter_config.json").is_file():
        raise FileNotFoundError(
            "Adapter configuration missing: adapter_config.json"
        )

    if not (
        (adapter_dir / "adapter_model.safetensors").is_file()
        or (adapter_dir / "adapter_model.bin").is_file()
    ):
        raise FileNotFoundError(
            "Adapter weights missing. Expected adapter_model.safetensors or adapter_model.bin"
        )


@dataclass
class OfflineTranslator:
    tokenizer: object
    model: object
    device: object

    def translate_text(
        self,
        text: str,
        src_lang: str,
        tgt_lang: str,
        *,
        max_new_tokens: int = 128,
        num_beams: int = 4,
    ) -> str:
        """Translate text from source language to target language using NLLB."""
        import torch

        clean_text = str(text or "").strip()
        if not clean_text:
            raise ValueError("Input text cannot be empty.")

        src_flores = resolve_language_tag(src_lang)
        tgt_flores = resolve_language_tag(tgt_lang)

        self.tokenizer.src_lang = src_flores
        encoded = self.tokenizer(
            clean_text,
            return_tensors="pt",
            truncation=True,
            max_length=256,
        )
        encoded = {name: tensor.to(self.device) for name, tensor in encoded.items()}

        forced_bos_token_id = self.tokenizer.convert_tokens_to_ids(tgt_flores)
        if forced_bos_token_id is None or forced_bos_token_id < 0:
            raise ValueError(f"Tokenizer could not resolve target language token: {tgt_flores}")

        with torch.no_grad():
            generated = self.model.generate(
                **encoded,
                forced_bos_token_id=forced_bos_token_id,
                max_new_tokens=max_new_tokens,
                num_beams=num_beams,
            )

        return self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]


def load_offline_translator(base_model_dir: Path, adapter_dir: Path) -> OfflineTranslator:
    """Load tokenizer + base model + LoRA adapter strictly from local paths."""
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency. Install torch, transformers, sentencepiece, and peft."
        ) from exc

    can_use_low_cpu_mem = False
    try:
        import accelerate  # noqa: F401

        can_use_low_cpu_mem = True
    except ImportError:
        can_use_low_cpu_mem = False

    validate_base_model_dir(base_model_dir)
    validate_adapter_dir(adapter_dir)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch_dtype = torch.float16 if device.type == "cuda" else torch.float32

    model_load_kwargs = {
        "local_files_only": True,
        "dtype": torch_dtype,
    }
    if device.type == "cpu" and can_use_low_cpu_mem:
        model_load_kwargs["low_cpu_mem_usage"] = True

    tokenizer = AutoTokenizer.from_pretrained(
        str(base_model_dir),
        local_files_only=True,
        use_fast=True,
    )

    try:
        model = AutoModelForSeq2SeqLM.from_pretrained(
            str(base_model_dir),
            **model_load_kwargs,
        )
    except TypeError as exc:
        # Backward compatibility for older transformers versions.
        if "dtype" not in str(exc):
            raise
        model_load_kwargs["torch_dtype"] = model_load_kwargs.pop("dtype")
        model = AutoModelForSeq2SeqLM.from_pretrained(
            str(base_model_dir),
            **model_load_kwargs,
        )
    if device.type == "cuda":
        model = model.to(device)

    model = PeftModel.from_pretrained(
        model,
        str(adapter_dir),
        local_files_only=True,
        is_trainable=False,
    )
    if device.type == "cuda":
        model = model.to(device)
    model.eval()

    return OfflineTranslator(tokenizer=tokenizer, model=model, device=device)


def build_arg_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Run local/offline NLLB-200 inference with a local LoRA adapter."
    )
    parser.add_argument(
        "--base-model-dir",
        type=Path,
        default=root / "nllb-200-distilled-600M",
        help="Path to local base model directory.",
    )
    parser.add_argument(
        "--adapter-dir",
        type=Path,
        default=root / "lora_adapters" / "lora-cbk-formal",
        help="Path to local LoRA adapter directory.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default="Buenas dias, kumusta tu familia?",
        help="Text to translate.",
    )
    parser.add_argument(
        "--src-lang",
        type=str,
        default="cbk_Latn",
        help="Source language (app code like cbk/ceb/en or FLORES tag).",
    )
    parser.add_argument(
        "--tgt-lang",
        type=str,
        default="eng_Latn",
        help="Target language (app code like en/cbk/ceb or FLORES tag).",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=128,
        help="Maximum tokens generated for translation output.",
    )
    parser.add_argument(
        "--num-beams",
        type=int,
        default=4,
        help="Beam search width for generation.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    base_model_dir = args.base_model_dir.resolve()
    adapter_dir = args.adapter_dir.resolve()

    print("=" * 80)
    print("Project PUENTE - Local Offline NLLB + LoRA Inference")
    print(f"Base model : {base_model_dir}")
    print(f"Adapter    : {adapter_dir}")
    print(f"Source     : {args.src_lang}")
    print(f"Target     : {args.tgt_lang}")
    print(f"Offline    : HF_HUB_OFFLINE={os.getenv('HF_HUB_OFFLINE')} | "
          f"TRANSFORMERS_OFFLINE={os.getenv('TRANSFORMERS_OFFLINE')}")
    print("=" * 80)

    try:
        translator = load_offline_translator(base_model_dir, adapter_dir)
        print(f"Loaded on device: {translator.device}")

        translated = translator.translate_text(
            args.text,
            args.src_lang,
            args.tgt_lang,
            max_new_tokens=args.max_new_tokens,
            num_beams=args.num_beams,
        )

        print("\nInput:")
        print(args.text)
        print("\nTranslation:")
        print(translated)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())