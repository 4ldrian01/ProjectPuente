# ML Models Setup

This directory holds local model/runtime tooling for NLLB and LoRA workflows.

## Core scripts

| Script | Purpose |
|---|---|
| `download_model.py` | Downloads base NLLB model to project-local path (or `ML_MODEL_PATH`) |
| `validate_model.py` | Smoke-tests local model loading and sample translation |
| `train_lora.py` | Trains LoRA adapters from strict parallel datasets |
| `training_preflight.py` | Read-only architecture/readiness audit |
| `evaluate_metrics.py` | General BLEU/chrF++ evaluator |
| `evaluate_spanish_baseline.py` | Spanish control-variable baseline evaluator |

## Required Python packages

(Provided by `backend/requirements.txt`)

| Package | Purpose |
|---|---|
| `torch` | Tensor runtime |
| `transformers` | Model/tokenizer loading |
| `huggingface_hub` | Download helper/runtime APIs |
| `sentencepiece` | Tokenization |
| `accelerate` | Runtime loading helpers |
| `peft` | LoRA adapters |
| `bitsandbytes` | Optional INT8 loading |
| `protobuf` | Serialization support |
| `sacrebleu` | Evaluation metrics |
| `pandas` | Data utility workflows |
| `pdfplumber` | PDF extraction workflows |
| `ijson` | Streaming JSON utilities |

## Expected local model path

Default backend expectation:

- `ml_models/nllb-200-distilled-600M`

`download_model.py` now resolves this path portably using project root (or `ML_MODEL_PATH` override).

## Adapter path contract

Backend loader expects:

- `ml_models/lora_adapters/lora-cbk-formal/`
- `ml_models/lora_adapters/lora-cbk-street/`

`train_lora.py` output paths should be aligned/copied to this contract before runtime adapter loading.

## Data contract for training

Use strict 3-pillar outputs:

- Parallel (seq2seq): `datasets/processed/pillars/parallel/master_parallel_corpus_nmt.json`
- Monolingual (fluency/BT): `datasets/processed/pillars/monolingual/chavacano_monolingual_corpus_nmt.json`
- JSONL mirrors: `datasets/processed/jsonl/pillars/...`
- Lexicon data is for SQL retrieval (`ingest_lexicon`), not seq2seq loss tensors.

## Preflight status meanings

`training_preflight.py` exit behavior:

- `0` -> no blockers
- `2` -> one or more blockers (e.g., missing base model directory)

## Quick workflow

```bash
cd ml_models
python download_model.py
python validate_model.py
python training_preflight.py
python train_lora.py --mode formal --dataset ../datasets/processed/pillars/parallel/
python train_lora.py --mode street --dataset ../datasets/processed/pillars/parallel/
```
