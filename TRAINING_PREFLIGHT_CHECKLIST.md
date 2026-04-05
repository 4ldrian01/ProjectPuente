# PUENTE Training Preflight Checklist

Use this checklist before running LoRA training, evaluation, or NLLB dataset pipelines.

## 1) Run the automated preflight

From the project root:

- `cd ml_models`
- `python training_preflight.py`

The command writes `ml_models/training_preflight_report.json` and exits with:

- `0` when no blockers were found
- `2` when one or more blockers were found

## 2) What the preflight validates

- Cross-layer architecture structure (backend/frontend/datasets/ml_models/notebooks)
- Backend/frontend language contract synchronization
- Active notebook pipeline script presence and path hygiene
- Processed dataset artifacts required by the NLLB prep pipeline
- Base NLLB model directory and key tokenizer/model files
- Environment template presence (`backend/.env.example`, `frontend/.env.example`)
- Python module availability in the current interpreter
- Legacy duplicate script candidates

## 3) Resolve blockers first

Typical blockers include:

- Missing `ml_models/nllb-200-distilled-600M/` model directory
- Missing required architecture files
- Missing `datasets/processed/001_chavacano/` structure
- Backend/frontend language scope mismatch

## 4) Cleanliness reminders before git push

- Keep only one active Python virtual environment (`.venv/` preferred)
- Remove legacy notebook scripts that are superseded by `_REFINED.py` versions
- Do not delete `datasets/` contents during cleanup
- Keep generated preflight JSON in `ml_models/` for readiness traceability
