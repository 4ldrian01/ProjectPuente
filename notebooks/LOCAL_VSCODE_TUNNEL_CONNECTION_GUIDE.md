# Project PUENTE - Local VS Code Connection Guide (Colab Tunnel)

This guide is the Phase A cloud workflow: local editing in VS Code + remote execution on a Google Colab runtime.

## 1) Install Required VS Code Extension

Install this exact extension in local VS Code:

- `ms-vscode.remote-server` (Remote - Tunnels)

## 2) Bring Up Tunnel in Colab

Open and run:

- `notebooks/colab_vscode_tunnel_setup.ipynb`

Run cells in order:

1. Cell 1 optionally mounts Drive at `/content/drive`.
2. Cell 2 installs `curl` and `tar`, then downloads/extracts the official standalone VS Code CLI to `/content/vscode-cli`.
3. Cell 3 starts tunnel host `puente-colab-rde` and prints the GitHub auth URL + one-time code.

Keep Cell 3 running while connected.

## 3) Connect from Local VS Code

1. Open Command Palette: `Ctrl+Shift+P`.
2. Run command: `Remote - Tunnels: Connect to Tunnel...`.
3. Sign in with the same account used when authenticating the Colab tunnel.
4. Select `puente-colab-rde`.

## 4) Open the Correct Remote Project Root

After connection, open one of these folders on the remote host:

- `/content/drive/MyDrive/ProjectPuenteCloud` (persistent; recommended)
- `/content/ProjectPuente` (non-Drive clone; ephemeral)

If you use the non-Drive path, runtime artifacts are lost when Colab resets.

## 5) Verify Remote Workspace Contract

Confirm these top-level folders are visible:

- `backend/`
- `frontend/`
- `datasets/`
- `ml_models/`
- `notebooks/`

If any are missing, re-run Cell 1 in the notebook and re-open the folder.

## 6) Launch Phase A Training Safely

Run from the remote terminal (inside the connected tunnel session):

```bash
# Optional explicit root (only needed when auto-detect is not correct)
# export PUENTE_PROJECT_ROOT=/content/ProjectPuente

# Preferred: launcher adds dependency bootstrap and preflight guardrails
bash notebooks/scripts/run_colab_phase_a_training.sh

# Direct pipeline execution (use when dependencies are already installed)
python "${PUENTE_PROJECT_ROOT:-$PWD}"/notebooks/scripts/colab_lora_training_pipeline.py
```

The workflow enforces:

- split-file existence checks for `train.jsonl`, `eval.jsonl`, `test.jsonl`
- schema checks for required translation keys (`translation.<source_key>` plus `translation.en`)
- checksum-safe source storage -> `/content/data` staging before training
- checkpoints written directly to artifact storage at configured save intervals (default 500 steps)

If you use direct `python` execution, install dependencies first:

```bash
python -m pip install -r notebooks/scripts/requirements_colab.txt
```

Sequential language workflow (beginner-safe):

1. Train one language pair at a time (`source -> en`).
2. Run evaluation/test for that single language.
3. Keep adapter + metrics for that run.
4. Change `PUENTE_SOURCE_FLORES`, `PUENTE_SOURCE_TRANSLATION_KEY`, `PUENTE_DATASET_REL_DIR`, and `PUENTE_RUN_NAME` for the next language.

## 7) Optional Session Stability

If Colab idles out too aggressively, paste the keep-alive snippet from the notebook's last markdown cell into browser DevTools console.
