# Project PUENTE - Phase A Kaggle Training Runbook

Use this runbook when Colab GPU quota is exhausted and you need to continue training on Kaggle.

## Scope

- Runtime: Kaggle notebook with GPU accelerator enabled
- Project path: `/kaggle/working/ProjectPuente` (recommended)
- Launcher: `notebooks/scripts/run_kaggle_phase_a_training.sh`
- Pipeline: `notebooks/scripts/colab_lora_training_pipeline.py` (runtime-aware)

## 1) Prepare Kaggle Notebook Environment

1. Create a new Kaggle notebook.
2. In notebook settings, open `Settings` (right sidebar) and set:
	- `Accelerator`: `GPU T4 x2`
	- `Internet`: On (required for repo clone and model download)
3. Click `Turn on GPU T4 x2` and wait until the runtime reconnects.
4. Verify status at the top-right runtime indicator shows GPU enabled.
3. Open a terminal in Kaggle notebook.
4. Clone your repository to working storage:

```bash
git clone https://github.com/4ldrian01/ProjectPuente.git /kaggle/working/ProjectPuente
cd /kaggle/working/ProjectPuente
git checkout development
git pull --ff-only origin development
```

## 2) Validate Runtime and Dataset Layout

Ensure project root contains expected folders:

- `backend/`
- `frontend/`
- `datasets/`
- `notebooks/`

Check split files:

```bash
PRJ=/kaggle/working/ProjectPuente
ls -lah "$PRJ/datasets/processed/80-10-10_split/01_chavacano"/{train,eval,test}.jsonl
```

Confirm CUDA before starting training:

```bash
python - <<'PY'
import torch, sys
print('cuda_available =', torch.cuda.is_available())
if not torch.cuda.is_available():
	print('ERROR: GPU not active. Re-open Kaggle Settings and re-enable Accelerator: GPU T4 x2.')
	sys.exit(1)
print('gpu_count =', torch.cuda.device_count())
print('active_gpu =', torch.cuda.get_device_name(0))
PY
```

## 3) Optional HF Token Setup

```bash
PRJ=/kaggle/working/ProjectPuente
mkdir -p "$PRJ/.secrets"
chmod 700 "$PRJ/.secrets"
printf '%s\n' 'hf_your_token_here' > "$PRJ/.secrets/hf_token"
chmod 600 "$PRJ/.secrets/hf_token"
```

## 4) Launch Training (Recommended)

```bash
set -euo pipefail

PRJ=/kaggle/working/ProjectPuente
cd "$PRJ"

export PUENTE_PROJECT_ROOT="$PRJ"
export PUENTE_DRIVE_ROOT="$PRJ"
export PUENTE_SOURCE_FLORES=cbk_Latn
export PUENTE_TARGET_FLORES=eng_Latn
export PUENTE_SOURCE_TRANSLATION_KEY=cbk
export PUENTE_TARGET_TRANSLATION_KEY=en
export PUENTE_DATASET_REL_DIR=datasets/processed/80-10-10_split/01_chavacano
export PUENTE_RUN_NAME=lora-cbk-full-kaggle
export PUENTE_REQUIRE_GPU=true

# Optional: resume from prior checkpoint directory
# export PUENTE_RESUME_FROM_CHECKPOINT="$PRJ/models/checkpoints/checkpoint-500"

LOG="$PRJ/outputs/$PUENTE_RUN_NAME/train_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$LOG")"

nohup bash notebooks/scripts/run_kaggle_phase_a_training.sh > "$LOG" 2>&1 &
echo "Started PID=$!"
echo "Log=$LOG"

sleep 12
sed -n '1,220p' "$LOG"
tail -f "$LOG"
```

## 5) Output Locations

- Checkpoints: `<project_root>/models/checkpoints/`
- Final adapter: `<project_root>/models/lora_adapters/<run_name>/`
- Metrics and config: `<project_root>/outputs/<run_name>/`

## 6) Troubleshooting

- If GPU check fails, re-open notebook settings and confirm Accelerator is GPU.
- If split files are missing, set `PUENTE_DATASET_REL_DIR` to the exact split directory.
- If HF rate limits occur, set token at `.secrets/hf_token`.
- If notebook session restarts, rerun launch block and follow latest log file.
- If you need reproducible persistence, click `Save Version` in Kaggle to capture notebook outputs under `/kaggle/working`.
