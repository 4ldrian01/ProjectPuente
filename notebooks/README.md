# Notebooks Setup

Notebooks are used for model validation, data processing experiments, and cloud training workflows.

## Core notebook files

- `lora_training.ipynb`
- `model_validation.ipynb`
- `sample.ipynb`
- `colab_vscode_tunnel_setup.ipynb`

## Script pipeline in `notebooks/scripts/`

| Script | Purpose |
|---|---|
| `run_nllb_pipeline.py` | Master preprocessing orchestrator |
| `extract_chavacano_pdf_REFINED.py` | PDF extraction |
| `process_chavacano_csv_REFINED.py` | CSV cleanup/normalization |
| `process_tatoeba_REFINED.py` | Tatoeba processing |
| `harvest_creole_rc_REFINED.py` | Creole RC harvesting |
| `process_wiki_dump.py` | Wiki dump processing |
| `deep_clean_wiki.py` | Aggressive text cleanup |
| `colab_lora_training_pipeline.py` | Colab GPU LoRA training orchestration |
| `colab_drive_sync.py` | Cloud Drive sync helpers |
| `requirements_colab.txt` | Colab dependency manifest |

## Recommended notebook environment

### Minimum

- Python 3.12
- `jupyterlab`
- `ipykernel`
- packages from `backend/requirements.txt`

### Colab/cloud workflow

Install:

- `notebooks/scripts/requirements_colab.txt`

Includes core stack (`torch`, `transformers`, `datasets`, `peft`, etc.) and reliability/eval helpers (`huggingface_hub`, `evaluate`, `sacrebleu`, `pandas`, `pyyaml`).

## Data handoff contract (3 pillars)

- Parallel pillar: `../datasets/processed/pillars/parallel/master_parallel_corpus_nmt.json`
- Monolingual pillar: `../datasets/processed/pillars/monolingual/chavacano_monolingual_corpus_nmt.json`
- JSONL streaming mirror: `../datasets/processed/jsonl/pillars/`
- Lexicon ingestion source: `../datasets/processed/001_chavacano/chavacano_lexicon_nllb.json`

## Typical prep sequence

```bash
python ../datasets/scripts/pillar1_merge_parallel_corpus.py
python ../datasets/scripts/pillar2_structure_monolingual.py
python ../datasets/scripts/json_to_jsonl_stream.py --overwrite
python ../backend/manage.py ingest_lexicon
```

## Notes

- Notebook workloads can require broader packages than backend runtime APIs.
- Keep training/inference model paths aligned with backend `ML_MODEL_PATH` to avoid drift between notebook and service runs.
