# Project PUENTE - Phase A Cloud Training Runbook

This runbook is the end-to-end cloud workflow for LoRA training using:

- local VS Code editor
- Google Colab runtime (T4 GPU)
- Remote Tunnel bridge

If Colab GPU quota is exhausted, use Kaggle with:

- `notebooks/KAGGLE_PHASE_A_TRAINING_RUNBOOK.md`
- `notebooks/scripts/run_kaggle_phase_a_training.sh`

## Architecture Snapshot

1. Local VS Code connects to Colab via `ms-vscode.remote-server` (Remote - Tunnels).
2. Training data (`train.jsonl`, `eval.jsonl`, `test.jsonl`) lives under the configured project root.
3. Before training, split files are copied to runtime-local data storage with SHA-256 verification.
4. Trainer reads from runtime-local data storage to avoid slow mounted/project storage I/O bottlenecks.
5. Checkpoints are written directly to artifact storage during training; final adapters are saved there after training.

## Why Local Runtime Storage Is Faster During Training

Colab Drive mount uses a network-backed FUSE layer. During tokenization, dataloader fetches, and repeated epoch access, this introduces higher latency and lower throughput versus local runtime storage. Staging split files to `/content/data` reduces read latency and keeps GPU pipelines fed more consistently, improving step-time stability.

On Kaggle, equivalent staging happens to `/kaggle/working/data`.

## Prerequisites

- Google Colab runtime is active.
- Project root exists at either `/content/drive/MyDrive/ProjectPuenteCloud` (persistent) or `/content/ProjectPuente` (ephemeral).
- Split files exist:
  - `<project_root>/datasets/processed/80-10-10_split/01_chavacano/train.jsonl`
  - `<project_root>/datasets/processed/80-10-10_split/01_chavacano/eval.jsonl`
  - `<project_root>/datasets/processed/80-10-10_split/01_chavacano/test.jsonl`

Notes:
- Launcher and pipeline now auto-detect known split roots when `PUENTE_DATASET_REL_DIR` is unset.
- You can still override manually for other languages or custom dataset folders.

## Step 1: Start Colab Tunnel

Open notebook:

- `notebooks/colab_vscode_tunnel_setup.ipynb`

Run:

1. Cell 1
2. Cell 2
3. Cell 3 (keep running)

Authenticate using the URL/code printed by Cell 3.

## Step 2: Connect Local VS Code

1. Install extension `ms-vscode.remote-server`.
2. Open Command Palette (`Ctrl+Shift+P`).
3. Run `Remote - Tunnels: Connect to Tunnel...`.
4. Select tunnel `puente-colab-rde`.
5. Open folder `/content/drive/MyDrive/ProjectPuenteCloud` (or `/content/ProjectPuente` for non-Drive runs).

## Step 3: Launch Cloud Training

From the remote tunnel terminal:

```bash
# Optional explicit root (only needed when auto-detect is not correct)
# export PUENTE_PROJECT_ROOT=/content/ProjectPuente

# Preferred: launcher installs dependencies and runs pipeline safely
bash notebooks/scripts/run_colab_phase_a_training.sh

# Kaggle launcher (use in Kaggle runtime instead of Colab launcher)
# bash notebooks/scripts/run_kaggle_phase_a_training.sh

# Direct pipeline execution (use when dependencies are already installed)
python "${PUENTE_PROJECT_ROOT:-$PWD}"/notebooks/scripts/colab_lora_training_pipeline.py
```

This workflow:

1. validates split JSONL presence
2. validates dataset schema using one of these accepted contracts:
  - `{"translation": {"<source_key>": "...", "en": "..."}}`
  - `{"source_text": "...", "target_text": "..."}`
  - `{"source": "...", "target": "..."}`
  - `{"<source_key>": "...", "en": "..."}`
3. executes checksum-safe staging to runtime-local data storage
4. starts LoRA training
5. writes checkpoints and final adapter artifacts to artifact storage

If you use direct `python` execution, install dependencies first:

```bash
python -m pip install -r notebooks/scripts/requirements_colab.txt
```

## Dynamic Runtime Overrides (Recommended)

You can override language pair, dataset path, and tuning values without editing code:

```bash
export PUENTE_PROJECT_ROOT=/content/ProjectPuente
export PUENTE_SOURCE_FLORES=cbk_Latn
export PUENTE_TARGET_FLORES=eng_Latn
export PUENTE_SOURCE_TRANSLATION_KEY=cbk
export PUENTE_TARGET_TRANSLATION_KEY=en
export PUENTE_DATASET_REL_DIR=datasets/processed/80-10-10_split/01_chavacano
export PUENTE_RUN_NAME=lora-cbk-to-eng-cloud
export PUENTE_EPOCHS=3
export PUENTE_BATCH_SIZE_TRAIN=4
export PUENTE_BATCH_SIZE_EVAL=4
export PUENTE_GRAD_ACCUM_STEPS=4
export PUENTE_LR=0.0002
export PUENTE_GRADIENT_CHECKPOINTING=true
export PUENTE_SAVE_STEPS=500
bash notebooks/scripts/run_colab_phase_a_training.sh

# Optional direct invocation after exports
python "${PUENTE_PROJECT_ROOT:-$PWD}"/notebooks/scripts/colab_lora_training_pipeline.py
```

Sequential training policy (recommended):

1. Train one source language at a time (for example: `cbk -> en`).
2. Evaluate on that language's held-out test split.
3. Save metrics and adapter artifact.
4. Start a fresh run for the next language (`ceb -> en`, then `es -> en`, etc.).

For other source languages, update only these environment variables:

- `PUENTE_SOURCE_FLORES` (example: `ceb_Latn`, `spa_Latn`)
- `PUENTE_SOURCE_TRANSLATION_KEY` (example: `ceb`, `es`)
- `PUENTE_DATASET_REL_DIR`
- `PUENTE_RUN_NAME`

## Reliability and Safety Controls Already Enabled

- SHA-256 validation on split staging and artifact mirroring.
- checkpoints written directly to Drive on trainer save steps (`PUENTE_SAVE_STEPS`, default 500)
- aggressive GPU cleanup hooks (`torch.cuda.empty_cache()` + `torch.cuda.ipc_collect()`)
- schema preflight for required translation keys (`translation.<source_key>` plus `translation.en`)

## Outputs and Persistence

Primary outputs are written under the artifact root (defaults to `PUENTE_DRIVE_ROOT`):

- checkpoints: `<artifact_root>/models/checkpoints/`
- final adapter: `<artifact_root>/models/lora_adapters/<run_name>/`
- run metadata: `<artifact_root>/outputs/<run_name>/`

Run metadata contains:

- run config (`run_config.json`)
- metrics (`training_metrics.json`)

Ephemeral local runtime artifacts (not guaranteed after Colab reset):

- `/content/outputs/<run_name>/adapter/`
- `/content/outputs/<run_name>/adapter.zip`

## Troubleshooting Quick Checks

1. If tunnel auth URL does not appear, re-run Cell 3 and re-auth.
2. If split file errors appear, verify exact filenames in the configured `PUENTE_DATASET_REL_DIR`.
3. If Colab runtime disconnects, restart runtime, re-run tunnel cells, then relaunch training.
4. If VRAM OOM occurs, lower `PUENTE_BATCH_SIZE_TRAIN` and/or increase `PUENTE_GRAD_ACCUM_STEPS`.
5. If Colab GPU quota is blocked, migrate to Kaggle and run `notebooks/scripts/run_kaggle_phase_a_training.sh`.

## Next Step After Phase A Training

1. Evaluate adapter outputs on held-out `test.jsonl` metrics.
2. Promote best adapter artifact from `models/lora_adapters/<run_name>/`.
3. Sync adapter into backend runtime adapter path for local inference and API validation.