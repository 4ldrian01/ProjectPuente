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
export PUENTE_LOCAL_DATA_DIR="${PUENTE_LOCAL_DATA_DIR:-/content/data}"
export PUENTE_LOCAL_OUTPUT_ROOT="${PUENTE_LOCAL_OUTPUT_ROOT:-/content/outputs}"
export PUENTE_DRIVE_OUTPUT_REL_DIR="${PUENTE_DRIVE_OUTPUT_REL_DIR:-outputs}"

detect_split_filenames() {
  local dataset_root="$1"

  if [[ -n "${PUENTE_TRAIN_FILENAME:-}" || -n "${PUENTE_EVAL_FILENAME:-}" || -n "${PUENTE_TEST_FILENAME:-}" ]]; then
    export PUENTE_TRAIN_FILENAME="${PUENTE_TRAIN_FILENAME:-train.jsonl}"
    export PUENTE_EVAL_FILENAME="${PUENTE_EVAL_FILENAME:-eval.jsonl}"
    export PUENTE_TEST_FILENAME="${PUENTE_TEST_FILENAME:-test.jsonl}"
    return
  fi

  local source_key target_key
  source_key="${PUENTE_SOURCE_TRANSLATION_KEY:-cbk}"
  target_key="${PUENTE_TARGET_TRANSLATION_KEY:-en}"

  local candidate_triplets=(
    "LATEST_${source_key}_${target_key}_train.jsonl LATEST_${source_key}_${target_key}_val.jsonl LATEST_${source_key}_${target_key}_test.jsonl"
    "LATEST_${source_key}_${target_key}_train.jsonl LATEST_${source_key}_${target_key}_eval.jsonl LATEST_${source_key}_${target_key}_test.jsonl"
    "FINAL_${source_key}_${target_key}_train.jsonl FINAL_${source_key}_${target_key}_val.jsonl FINAL_${source_key}_${target_key}_test.jsonl"
    "FINAL_${source_key}_${target_key}_train.jsonl FINAL_${source_key}_${target_key}_eval.jsonl FINAL_${source_key}_${target_key}_test.jsonl"
    "${source_key}_${target_key}_train.jsonl ${source_key}_${target_key}_val.jsonl ${source_key}_${target_key}_test.jsonl"
    "${source_key}_${target_key}_train.jsonl ${source_key}_${target_key}_eval.jsonl ${source_key}_${target_key}_test.jsonl"
    "train.jsonl eval.jsonl test.jsonl"
    "cbk_en_trial_train.jsonl cbk_en_trial_val.jsonl cbk_en_trial_test.jsonl"
  )

  local train_file eval_file test_file
  for triplet in "${candidate_triplets[@]}"; do
    read -r train_file eval_file test_file <<< "${triplet}"
    if [[ -f "${dataset_root}/${train_file}" ]] && [[ -f "${dataset_root}/${eval_file}" ]] && [[ -f "${dataset_root}/${test_file}" ]]; then
      export PUENTE_TRAIN_FILENAME="${train_file}"
      export PUENTE_EVAL_FILENAME="${eval_file}"
      export PUENTE_TEST_FILENAME="${test_file}"
      return
    fi
  done

  export PUENTE_TRAIN_FILENAME="train.jsonl"
  export PUENTE_EVAL_FILENAME="eval.jsonl"
  export PUENTE_TEST_FILENAME="test.jsonl"
}

if [[ -z "${PUENTE_DATASET_REL_DIR:-}" ]]; then
  source_key_for_dataset="${PUENTE_SOURCE_TRANSLATION_KEY:-cbk}"

  case "${source_key_for_dataset}" in
    ceb)
      dataset_candidates=(
        "datasets/processed/80-10-10_split/02_cebuano"
        "datasets/processed/02_cebuano"
        "datasets/processed/002_cebuano"
      )
      ;;
    cbk)
      dataset_candidates=(
        "datasets/processed/80-10-10_split/01_chavacano"
        "datasets/processed/01_chavacano"
        "datasets/processed/001_chavacano"
      )
      ;;
    *)
      dataset_candidates=(
        "datasets/processed/80-10-10_split/01_chavacano"
        "datasets/processed/80-10-10_split/02_cebuano"
        "datasets/processed/01_chavacano"
        "datasets/processed/001_chavacano"
        "datasets/processed/02_cebuano"
        "datasets/processed/002_cebuano"
      )
      ;;
  esac

  for candidate in "${dataset_candidates[@]}"; do
    candidate_root="${PUENTE_DRIVE_ROOT}/${candidate}"
    detect_split_filenames "${candidate_root}"
    if [[ -f "${candidate_root}/${PUENTE_TRAIN_FILENAME}" ]] && [[ -f "${candidate_root}/${PUENTE_EVAL_FILENAME}" ]] && [[ -f "${candidate_root}/${PUENTE_TEST_FILENAME}" ]]; then
      export PUENTE_DATASET_REL_DIR="${candidate}"
      break
    fi
  done
fi

if [[ -z "${PUENTE_DATASET_REL_DIR:-}" ]]; then
  if [[ "${PUENTE_SOURCE_TRANSLATION_KEY:-cbk}" == "ceb" ]]; then
    export PUENTE_DATASET_REL_DIR="datasets/processed/80-10-10_split/02_cebuano"
  else
    export PUENTE_DATASET_REL_DIR="datasets/processed/80-10-10_split/01_chavacano"
  fi
fi

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

dataset_root="${PUENTE_DRIVE_ROOT}/${PUENTE_DATASET_REL_DIR}"
detect_split_filenames "${dataset_root}"

declare -A split_to_filename=(
  [train]="${PUENTE_TRAIN_FILENAME}"
  [eval]="${PUENTE_EVAL_FILENAME}"
  [test]="${PUENTE_TEST_FILENAME}"
)

for split in train eval test; do
  split_filename="${split_to_filename[${split}]}"
  split_path="${dataset_root}/${split_filename}"
  if [[ ! -f "${split_path}" ]]; then
    echo "ERROR: Missing split file: ${split_path}"
    echo "Configured filenames: train=${PUENTE_TRAIN_FILENAME} eval=${PUENTE_EVAL_FILENAME} test=${PUENTE_TEST_FILENAME}"
    if [[ -d "${PUENTE_DRIVE_ROOT}/datasets/processed" ]]; then
      echo "Hint: set PUENTE_DATASET_REL_DIR to one of these detected split roots:"
      find "${PUENTE_DRIVE_ROOT}/datasets/processed" -maxdepth 4 -type f \( -name 'train.jsonl' -o -name '*_train.jsonl' \) 2>/dev/null \
        | sed "s#^${PUENTE_DRIVE_ROOT}/##" \
        | sed -E 's#/([^/]+_)?train\.jsonl$##' \
        | sort -u
    fi
    if [[ -d "${dataset_root}" ]]; then
      echo "Available JSONL files in ${dataset_root}:"
      find "${dataset_root}" -maxdepth 1 -type f -name '*.jsonl' -printf '  %f\n' | sort
    fi
    exit 1
  fi
done

echo "[data] Using dataset splits from: ${dataset_root}"
echo "[data] split filenames: train=${PUENTE_TRAIN_FILENAME} eval=${PUENTE_EVAL_FILENAME} test=${PUENTE_TEST_FILENAME}"
for split in train eval test; do
  split_filename="${split_to_filename[${split}]}"
  split_path="${dataset_root}/${split_filename}"
  split_rows="$(wc -l < "${split_path}")"
  split_size="$(du -h "${split_path}" | awk '{print $1}')"
  echo "[data] ${split}: ${split_filename} (${split_rows} rows, ${split_size})"
done

if [[ "${PUENTE_REQUIRE_GPU}" == "true" ]]; then
  python - <<'PY'
import sys
import torch

if not torch.cuda.is_available():
    print('ERROR: GPU is required but CUDA is not available in this Colab runtime.')
    print('Hint: In Colab, switch Runtime -> Change runtime type -> Hardware accelerator: GPU.')
    print('If quota is exhausted, retry later or use Kaggle fallback launcher.')
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
