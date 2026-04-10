# Project PUENTE - Local VS Code Connection Guide (Colab Tunnel)

This guide is the Phase A cloud workflow: local editing in VS Code + remote execution on a Google Colab runtime.

## 1) Install Required VS Code Extension

Install this exact extension in local VS Code:

- `ms-vscode.remote-server` (Remote - Tunnels)

## 2) Bring Up Tunnel in Colab

Open and run:

- `notebooks/colab_vscode_tunnel_setup.ipynb`

Run cells in order:

1. Cell 1 mounts Drive at `/content/drive`.
2. Cell 2 installs `curl` and `tar`, then downloads/extracts the official standalone VS Code CLI to `/content/vscode-cli`.
3. Cell 3 starts tunnel host `puente-colab-rde` and prints the GitHub auth URL + one-time code.

Keep Cell 3 running while connected.

## 3) Connect from Local VS Code

1. Open Command Palette: `Ctrl+Shift+P`.
2. Run command: `Remote - Tunnels: Connect to Tunnel...`.
3. Sign in with the same account used when authenticating the Colab tunnel.
4. Select `puente-colab-rde`.

## 4) Open the Correct Remote Project Root

After connection, open this exact folder on the remote host:

- `/content/drive/MyDrive/ProjectPuenteCloud`

This path is the canonical root for cloud training and keeps all artifacts persistent in Drive.

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
bash notebooks/scripts/run_colab_phase_a_training.sh
```

The launcher enforces:

- split-file existence checks for `train.jsonl`, `eval.jsonl`, `test.jsonl`
- dependency install from `notebooks/scripts/requirements_colab.txt`
- checksum-safe Drive -> `/content/data` staging before training
- periodic and on-save checkpoint mirroring back to Drive

## 7) Optional Session Stability

If Colab idles out too aggressively, paste the keep-alive snippet from the notebook's last markdown cell into browser DevTools console.
