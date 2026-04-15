#!/usr/bin/env bash
set -euo pipefail

# Project PUENTE - Phase A cloud launcher for Kaggle notebooks.
# Uses the same training pipeline as Colab, but with Kaggle runtime defaults.

if [[ ! -d /kaggle ]]; then
  echo "ERROR: This launcher is designed for Kaggle runtime paths under /kaggle."
  exit 1
fi

export PYTHONUNBUFFERED=1

DEFAULT_KAGGLE_PROJECT_ROOT="/kaggle/working/ProjectPuente"
DEFAULT_KAGGLE_WORKING_ROOT="/kaggle/working"

if [[ -z "${PUENTE_PROJECT_ROOT:-}" ]]; then
  if [[ -d "${DEFAULT_KAGGLE_PROJECT_ROOT}" ]]; then
    export PUENTE_PROJECT_ROOT="${DEFAULT_KAGGLE_PROJECT_ROOT}"
  elif [[ -d "${DEFAULT_KAGGLE_WORKING_ROOT}/notebooks/scripts" ]]; then
    export PUENTE_PROJECT_ROOT="${DEFAULT_KAGGLE_WORKING_ROOT}"
  else
    echo "ERROR: Could not auto-detect Kaggle project root."
    echo "Set PUENTE_PROJECT_ROOT (example: /kaggle/working/ProjectPuente)."
    exit 1
  fi
fi

if [[ ! -d "${PUENTE_PROJECT_ROOT}" ]]; then
  echo "ERROR: Project root does not exist: ${PUENTE_PROJECT_ROOT}"
  exit 1
fi

export PUENTE_DRIVE_ROOT="${PUENTE_DRIVE_ROOT:-${PUENTE_PROJECT_ROOT}}"
export PUENTE_ARTIFACT_ROOT="${PUENTE_ARTIFACT_ROOT:-${PUENTE_DRIVE_ROOT}}"
export PUENTE_LOCAL_DATA_DIR="${PUENTE_LOCAL_DATA_DIR:-/kaggle/working/data}"
export PUENTE_LOCAL_OUTPUT_ROOT="${PUENTE_LOCAL_OUTPUT_ROOT:-/kaggle/working/outputs}"
export PUENTE_DRIVE_OUTPUT_REL_DIR="${PUENTE_DRIVE_OUTPUT_REL_DIR:-outputs}"

if [[ -z "${PUENTE_DATASET_REL_DIR:-}" ]]; then
  dataset_candidates=(
    "datasets/processed/80-10-10_split/01_chavacano"
    "datasets/processed/01_chavacano"
    "datasets/processed/001_chavacano"
  )
  for candidate in "${dataset_candidates[@]}"; do
    candidate_root="${PUENTE_DRIVE_ROOT}/${candidate}"
    if [[ -f "${candidate_root}/train.jsonl" ]] && [[ -f "${candidate_root}/eval.jsonl" ]] && [[ -f "${candidate_root}/test.jsonl" ]]; then
      export PUENTE_DATASET_REL_DIR="${candidate}"
      break
    fi
  done
fi

export PUENTE_DATASET_REL_DIR="${PUENTE_DATASET_REL_DIR:-datasets/processed/001_chavacano}"

export PUENTE_MODEL_ID="${PUENTE_MODEL_ID:-facebook/nllb-200-distilled-600M}"
export PUENTE_SOURCE_FLORES="${PUENTE_SOURCE_FLORES:-cbk_Latn}"
export PUENTE_TARGET_FLORES="${PUENTE_TARGET_FLORES:-eng_Latn}"

export PUENTE_RUN_NAME="${PUENTE_RUN_NAME:-lora-cbk-to-eng-kaggle}"
export PUENTE_EPOCHS="${PUENTE_EPOCHS:-3}"
export PUENTE_BATCH_SIZE_TRAIN="${PUENTE_BATCH_SIZE_TRAIN:-4}"
export PUENTE_BATCH_SIZE_EVAL="${PUENTE_BATCH_SIZE_EVAL:-4}"
export PUENTE_GRAD_ACCUM_STEPS="${PUENTE_GRAD_ACCUM_STEPS:-4}"
export PUENTE_LR="${PUENTE_LR:-0.0002}"
export PUENTE_GRADIENT_CHECKPOINTING="${PUENTE_GRADIENT_CHECKPOINTING:-true}"
export PUENTE_SAVE_STEPS="${PUENTE_SAVE_STEPS:-500}"
export PUENTE_REQUIRE_GPU="${PUENTE_REQUIRE_GPU:-true}"
export PUENTE_RESUME_FROM_CHECKPOINT="${PUENTE_RESUME_FROM_CHECKPOINT:-}"

# Optional HF auth bootstrap for stable model downloads.
default_hf_token_file="${PUENTE_PROJECT_ROOT}/.secrets/hf_token"
export PUENTE_HF_TOKEN_FILE="${PUENTE_HF_TOKEN_FILE:-${default_hf_token_file}}"

if [[ -z "${HF_TOKEN:-}" ]] && [[ -f "${PUENTE_HF_TOKEN_FILE}" ]]; then
  hf_token_from_file="$(awk 'NF {print; exit}' "${PUENTE_HF_TOKEN_FILE}" | tr -d '\r')"
  if [[ -n "${hf_token_from_file}" ]]; then
    export HF_TOKEN="${hf_token_from_file}"
    echo "[auth] HF token loaded from PUENTE_HF_TOKEN_FILE."
  fi
fi

if [[ -n "${HF_TOKEN:-}" ]]; then
  echo "[auth] HF token available for authenticated model access."
else
  echo "[auth] HF token not set; proceeding unauthenticated (may be rate-limited)."
fi

for split in train eval test; do
  split_path="${PUENTE_DRIVE_ROOT}/${PUENTE_DATASET_REL_DIR}/${split}.jsonl"
  if [[ ! -f "${split_path}" ]]; then
    echo "ERROR: Missing split file: ${split_path}"
    if [[ -d "${PUENTE_DRIVE_ROOT}/datasets/processed" ]]; then
      echo "Hint: set PUENTE_DATASET_REL_DIR to one of these detected split roots:"
      find "${PUENTE_DRIVE_ROOT}/datasets/processed" -maxdepth 4 -type f -name 'train.jsonl' 2>/dev/null \
        | sed "s#^${PUENTE_DRIVE_ROOT}/##" \
        | sed 's#/train.jsonl$##' \
        | sort -u
    fi
    exit 1
  fi
done

echo "[data] Using dataset splits from: ${PUENTE_DRIVE_ROOT}/${PUENTE_DATASET_REL_DIR}"

if [[ "${PUENTE_REQUIRE_GPU}" == "true" ]]; then
  python - <<'PY'
import sys
import torch

if not torch.cuda.is_available():
    print('ERROR: Kaggle GPU is not enabled. In Kaggle notebook settings, set Accelerator to GPU.')
    sys.exit(1)

print(f'[gpu] Using GPU: {torch.cuda.get_device_name(0)}')
PY
fi

SCRIPT_DIR="${PUENTE_PROJECT_ROOT}/notebooks/scripts"
REQ_FILE="${SCRIPT_DIR}/requirements_colab.txt"
PIPELINE_SCRIPT="${SCRIPT_DIR}/colab_lora_training_pipeline.py"

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "ERROR: Missing requirements file: ${REQ_FILE}"
  exit 1
fi

if [[ ! -f "${PIPELINE_SCRIPT}" ]]; then
  echo "ERROR: Missing pipeline script: ${PIPELINE_SCRIPT}"
  exit 1
fi

python -m pip install -r "${REQ_FILE}"
python "${PIPELINE_SCRIPT}"
