# 3-Pillar Data Architecture (PUENTE)

This folder enforces strict segregation to prevent tensor-shape collisions in NMT training.

## Pillar 1: Parallel Corpus (Seq2Seq)
- Script: `pillar1_merge_parallel_corpus.py`
- Input: metadata-rich parallel JSON files (`{"metadata":...,"entries":[...]}`)
- Output: `datasets/processed/pillars/parallel/master_parallel_corpus_nmt.json`
- Guardrail: lexicon and monolingual files are excluded.

## Pillar 2: Monolingual Corpus (Fluency / BT)
- Script: `pillar2_structure_monolingual.py`
- Input: raw `.txt` dumps
- Output: `datasets/processed/pillars/monolingual/chavacano_monolingual_corpus_nmt.json`
- Guardrail: records are single-sided (`source_text` only), no `target_text`.

## Pillar 3: Lexicon Database (Inference-Time Retrieval)
- Script: Django management command
- Command: `python backend/manage.py ingest_lexicon`
- Guardrail: lexicon rows are stored in SQL (`CulturalTerm`) and excluded from seq2seq tensors.

## JSONL Upgrade
- Script: `json_to_jsonl_stream.py`
- Dependency: `ijson` for streaming parse (`pip install ijson`)
- Output root: `datasets/processed/jsonl/`
- Benefit: line-wise streaming for PyTorch/HuggingFace loaders.

## Legacy Purge Protocol
- Script: `archive_legacy_data.py`
- Default: dry-run
- Apply moves: add `--apply`
- Output: `datasets/archive/legacy_cleanup_<timestamp>/archive_manifest.json`

## Suggested Run Order
1. `python datasets/scripts/pillar1_merge_parallel_corpus.py`
2. `python datasets/scripts/pillar2_structure_monolingual.py`
3. `python datasets/scripts/json_to_jsonl_stream.py --overwrite`
4. `python backend/manage.py ingest_lexicon`
5. `python datasets/scripts/archive_legacy_data.py` (dry-run)
6. `python datasets/scripts/archive_legacy_data.py --apply` (if manifest looks correct)
