# ML Models Setup

This directory holds the local NLLB-200 base model and LoRA adapters used by the Django backend.

## Required Python packages

These are the direct packages used by `download_model.py`, `validate_model.py`, and `train_lora.py`.

| Package | Required for | Purpose |
|---|---|---|
| `torch` | validate + train + runtime | Core tensor/model runtime |
| `transformers` | all ML scripts | Model/tokenizer loading |
| `sentencepiece` | download + validate + runtime | Tokenizer backend |
| `accelerate` | runtime | Loading and device helpers |
| `peft` | train + runtime | LoRA adapter creation and loading |
| `bitsandbytes` | optional runtime | 8-bit quantization on supported setups |
| `protobuf` | download/runtime | Model serialization support |

## Optional training/evaluation extras

| Package | Purpose |
|---|---|
| `datasets` | Hugging Face dataset handling |
| `evaluate` | Evaluation pipelines |
| `sacrebleu` | Translation metric scoring |
| `wandb` | Optional experiment tracking |

## Baseline evaluation scripts

| Script | Purpose | Output |
|---|---|---|
| `evaluate_metrics.py` | General offline BLEU + chrF++ evaluator across supported language pairs | `evaluation_results.json` |
| `evaluate_spanish_baseline.py` | Pure Spanish (`spa_Latn`) → English (`eng_Latn`) control-variable baseline evaluation | `spanish_baseline_metrics.json` |
| `training_preflight.py` | Read-only architecture/training readiness audit (no installs) | `training_preflight_report.json` |

## Directory Structure (after setup)

```
ml_models/
├── README.md
├── download_model.py
├── train_lora.py
├── validate_model.py
├── nllb-200-distilled-600M/
│   ├── config.json
│   ├── pytorch_model.bin             (~2.4 GB full precision download)
│   ├── sentencepiece.bpe.model
│   ├── tokenizer_config.json
│   ├── tokenizer.json
│   └── special_tokens_map.json
├── lora-cbk-formal/
│   ├── adapter_config.json
│   └── adapter_model.bin
└── lora-cbk-street/
    ├── adapter_config.json
    └── adapter_model.bin
```

## What each script needs

| Script | Packages |
|---|---|
| `download_model.py` | `transformers`, `sentencepiece`, `protobuf` |
| `validate_model.py` | `torch`, `transformers`, `sentencepiece` |
| `train_lora.py` | `torch`, `transformers`, `sentencepiece`, `peft` |
| `training_preflight.py` | Python standard library only |

## Canonical training paths

- Preferred processed corpus directory: `../datasets/processed/001_chavacano/`
- `train_lora.py` now resolves this canonical path first and keeps a fallback for older `Datasets/` naming.

## Notes

- The backend loads the base model from this directory at startup via `core_api/apps.py`.
- If the LoRA adapter folders are missing, translation still works with the base NLLB model.
- See `../backend/README.md` for runtime/backend dependency details and `../notebooks/README.md` for notebook-only extras.

## Supported FLORES Codes

| Language | FLORES Code |
|---|---|
| English | `eng_Latn` |
| Spanish | `spa_Latn` |
| Tagalog | `tgl_Latn` |
| Chavacano | `cbk_Latn` |
| Cebuano | `ceb_Latn` |
| Hiligaynon | `hil_Latn` |
