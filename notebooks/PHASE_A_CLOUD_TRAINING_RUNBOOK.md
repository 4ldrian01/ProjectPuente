# Project PUENTE - Phase A Cloud Training Runbook

This runbook is the end-to-end cloud workflow for LoRA training using:

- local VS Code editor
- Google Colab runtime (T4 GPU)
- Remote Tunnel bridge

## Architecture Snapshot

1. Local VS Code connects to Colab via `ms-vscode.remote-server` (Remote - Tunnels).
2. Training data (`train.jsonl`, `eval.jsonl`, `test.jsonl`) remains versioned in Drive.
3. Before training, split files are copied to `/content/data` with SHA-256 verification.
4. Trainer reads only from `/content/data` to avoid Drive FUSE I/O bottlenecks.
5. Checkpoints and adapters are mirrored back to Drive during training.

## Why `/content/data` Is Faster Than Drive During Training

Colab Drive mount uses a network-backed FUSE layer. During tokenization, dataloader fetches, and repeated epoch access, this introduces higher latency and lower throughput versus local runtime storage. Staging split files to `/content/data` reduces read latency and keeps GPU pipelines fed more consistently, improving step-time stability.

## Prerequisites

- Google Colab runtime is active.
- Drive is mounted at `/content/drive`.
- Project root exists at `/content/drive/MyDrive/ProjectPuenteCloud`.
- Split files exist:
  - `/content/drive/MyDrive/ProjectPuenteCloud/datasets/processed/001_chavacano/train.jsonl`
  - `/content/drive/MyDrive/ProjectPuenteCloud/datasets/processed/001_chavacano/eval.jsonl`
  - `/content/drive/MyDrive/ProjectPuenteCloud/datasets/processed/001_chavacano/test.jsonl`

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
5. Open folder `/content/drive/MyDrive/ProjectPuenteCloud`.

## Step 3: Launch Cloud Training

From the remote tunnel terminal:

```bash
bash notebooks/scripts/run_colab_phase_a_training.sh
```

This launcher:

1. validates split JSONL presence
2. installs runtime dependencies
3. executes checksum-safe staging to `/content/data`
4. starts LoRA training
5. syncs checkpoints/adapters back to Drive

## Dynamic Runtime Overrides (Recommended)

You can override language pair, dataset path, and tuning values without editing code:

```bash
export PUENTE_SOURCE_FLORES=eng_Latn
export PUENTE_TARGET_FLORES=cbk_Latn
export PUENTE_DATASET_REL_DIR=datasets/processed/001_chavacano
export PUENTE_RUN_NAME=lora-eng-to-cbk-cloud
export PUENTE_EPOCHS=3
export PUENTE_BATCH_SIZE_TRAIN=4
export PUENTE_BATCH_SIZE_EVAL=4
export PUENTE_GRAD_ACCUM_STEPS=4
export PUENTE_LR=0.0002
export PUENTE_GRADIENT_CHECKPOINTING=true
bash notebooks/scripts/run_colab_phase_a_training.sh
```

## Reliability and Safety Controls Already Enabled

- SHA-256 validation on split staging and artifact mirroring.
- periodic checkpoint sync thread (time-based)
- checkpoint sync callback (step-based and save-event based)
- aggressive GPU cleanup hooks (`torch.cuda.empty_cache()` + `torch.cuda.ipc_collect()`)
- schema preflight for required split keys (`source_text`, `target_text` by default)

## Outputs and Persistence

Primary persistent output root:

- `/content/drive/MyDrive/ProjectPuenteCloud/outputs/<run_name>/`

Contains:

- trainer checkpoints (`trainer_runs/`)
- adapter folder (`adapter/`)
- adapter zip (`adapter.zip`)
- run config (`run_config.json`)
- metrics (`training_metrics.json`)

## Troubleshooting Quick Checks

1. If tunnel auth URL does not appear, re-run Cell 3 and re-auth.
2. If split file errors appear, verify exact filenames in `datasets/processed/001_chavacano/`.
3. If Colab runtime disconnects, restart runtime, re-run tunnel cells, then relaunch training.
4. If VRAM OOM occurs, lower `PUENTE_BATCH_SIZE_TRAIN` and/or increase `PUENTE_GRAD_ACCUM_STEPS`.

## Next Step After Phase A Training

1. Evaluate adapter outputs on held-out `test.jsonl` metrics.
2. Promote best adapter artifact from `outputs/<run_name>/adapter/`.
3. Sync adapter into backend runtime adapter path for local inference and API validation.