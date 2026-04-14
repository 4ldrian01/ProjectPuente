#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

resolve_python_bin() {
  if [[ -n "${PUENTE_PYTHON_BIN:-}" && -x "${PUENTE_PYTHON_BIN}" ]]; then
    echo "${PUENTE_PYTHON_BIN}"
    return
  fi

  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    echo "${VIRTUAL_ENV}/bin/python"
    return
  fi

  if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
    echo "${ROOT_DIR}/.venv/bin/python"
    return
  fi

  if [[ -x "${ROOT_DIR}/venv/bin/python" ]]; then
    echo "${ROOT_DIR}/venv/bin/python"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi

  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi

  echo "ERROR: No usable python interpreter found." >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/wiki_sync_pipeline.sh
  bash scripts/wiki_sync_pipeline.sh --dry-run

Behavior:
  - Runs scripts/clean_and_pad_json.py on canonical JSON
  - Seeds backend CulturalTerm via manage.py seed_wiki --prune
  - In apply mode, runs manage.py migrate before seed
USAGE
}

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
  shift
fi

if [[ $# -ne 0 ]]; then
  usage
  exit 1
fi

PYTHON_BIN="$(resolve_python_bin)"

echo "Using python: ${PYTHON_BIN}"

if [[ ${DRY_RUN} -eq 1 ]]; then
  echo "[1/2] Validating canonical JSON (dry-run)"
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/clean_and_pad_json.py" --dry-run

  echo "[2/2] Validating DB sync (dry-run prune seed)"
  pushd "${ROOT_DIR}/backend" >/dev/null
  "${PYTHON_BIN}" manage.py seed_wiki --dry-run --prune
  popd >/dev/null

  echo "Done (dry-run)."
  exit 0
fi

echo "[1/3] Cleaning + padding canonical JSON"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/clean_and_pad_json.py"

echo "[2/3] Applying migrations"
pushd "${ROOT_DIR}/backend" >/dev/null
"${PYTHON_BIN}" manage.py migrate

echo "[3/3] Seeding wiki table with prune"
"${PYTHON_BIN}" manage.py seed_wiki --prune
popd >/dev/null

echo "Done (apply mode)."
