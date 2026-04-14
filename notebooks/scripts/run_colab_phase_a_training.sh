#!/usr/bin/env bash
set -euo pipefail

# Project PUENTE - Phase A (Cloud Training) launcher for Google Colab.
# This script executes the checksum-safe training pipeline from notebooks/scripts
# and supports both Drive-backed and non-Drive project roots under /content.

if [[ ! -d /content ]]; then
  echo "ERROR: This launcher is designed for Colab runtime paths under /content."
  exit 1
fi

export PYTHONUNBUFFERED=1

DEFAULT_DRIVE_PROJECT_ROOT="/content/drive/MyDrive/ProjectPuenteCloud"
DEFAULT_EPHEMERAL_PROJECT_ROOT="/content/ProjectPuente"

if [[ -z "${PUENTE_PROJECT_ROOT:-}" ]]; then
  if [[ -d "${DEFAULT_DRIVE_PROJECT_ROOT}" ]]; then
    export PUENTE_PROJECT_ROOT="${DEFAULT_DRIVE_PROJECT_ROOT}"
  elif [[ -d "${DEFAULT_EPHEMERAL_PROJECT_ROOT}" ]]; then
    export PUENTE_PROJECT_ROOT="${DEFAULT_EPHEMERAL_PROJECT_ROOT}"
  else
    echo "ERROR: Could not auto-detect project root." 
    echo "Set PUENTE_PROJECT_ROOT to your Colab project path (example: /content/ProjectPuente)."
    exit 1
  fi
fi

if [[ ! -d "${PUENTE_PROJECT_ROOT}" ]]; then
  echo "ERROR: Project root does not exist: ${PUENTE_PROJECT_ROOT}"
  exit 1
fi

if [[ "${PUENTE_PROJECT_ROOT}" == /content/drive/* ]] && [[ ! -d /content/drive/MyDrive ]]; then
  echo "ERROR: PUENTE_PROJECT_ROOT points to Drive, but Google Drive is not mounted."
  echo "Run Drive mount first or set PUENTE_PROJECT_ROOT to a non-Drive path (example: /content/ProjectPuente)."
  exit 1
fi

export PUENTE_DRIVE_ROOT="${PUENTE_DRIVE_ROOT:-${PUENTE_PROJECT_ROOT}}"
export PUENTE_ARTIFACT_ROOT="${PUENTE_ARTIFACT_ROOT:-${PUENTE_DRIVE_ROOT}}"
export PUENTE_DATASET_REL_DIR="${PUENTE_DATASET_REL_DIR:-datasets/processed/001_chavacano}"
export PUENTE_LOCAL_DATA_DIR="${PUENTE_LOCAL_DATA_DIR:-/content/data}"
export PUENTE_LOCAL_OUTPUT_ROOT="${PUENTE_LOCAL_OUTPUT_ROOT:-/content/outputs}"
export PUENTE_DRIVE_OUTPUT_REL_DIR="${PUENTE_DRIVE_OUTPUT_REL_DIR:-outputs}"

export PUENTE_MODEL_ID="${PUENTE_MODEL_ID:-facebook/nllb-200-distilled-600M}"
export PUENTE_SOURCE_FLORES="${PUENTE_SOURCE_FLORES:-cbk_Latn}"
export PUENTE_TARGET_FLORES="${PUENTE_TARGET_FLORES:-eng_Latn}"

export PUENTE_RUN_NAME="${PUENTE_RUN_NAME:-lora-cbk-to-eng-cloud}"
export PUENTE_EPOCHS="${PUENTE_EPOCHS:-3}"
export PUENTE_BATCH_SIZE_TRAIN="${PUENTE_BATCH_SIZE_TRAIN:-4}"
export PUENTE_BATCH_SIZE_EVAL="${PUENTE_BATCH_SIZE_EVAL:-4}"
export PUENTE_GRAD_ACCUM_STEPS="${PUENTE_GRAD_ACCUM_STEPS:-4}"
export PUENTE_LR="${PUENTE_LR:-0.0002}"
export PUENTE_GRADIENT_CHECKPOINTING="${PUENTE_GRADIENT_CHECKPOINTING:-true}"
export PUENTE_SAVE_STEPS="${PUENTE_SAVE_STEPS:-500}"

for split in train eval test; do
  split_path="${PUENTE_DRIVE_ROOT}/${PUENTE_DATASET_REL_DIR}/${split}.jsonl"
  if [[ ! -f "${split_path}" ]]; then
    echo "ERROR: Missing split file: ${split_path}"
    exit 1
  fi
done

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
