#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_ENV="${ROOT_DIR}/backend/.env"
BACKEND_ENV_EXAMPLE="${ROOT_DIR}/backend/.env.example"
LEGACY_BACKEND_ENV="${ROOT_DIR}/backend/backend/.env"
FRONTEND_ENV="${ROOT_DIR}/frontend/.env"
FRONTEND_ENV_EXAMPLE="${ROOT_DIR}/frontend/.env.example"

resolve_python_bin() {
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

set_kv() {
  local file="$1"
  local key="$2"
  local value="$3"

  local escaped
  escaped="$(printf '%s' "$value" | sed -e 's/[\\/&]/\\\\&/g')"

  if grep -q "^${key}=" "$file"; then
    sed -i "s/^${key}=.*/${key}=${escaped}/" "$file"
  else
    printf "%s=%s\n" "$key" "$value" >>"$file"
  fi
}

ensure_kv() {
  local file="$1"
  local key="$2"
  local value="$3"

  if ! grep -q "^${key}=" "$file"; then
    printf "%s=%s\n" "$key" "$value" >>"$file"
  fi
}

generate_secret_key() {
  local python_bin="$1"
  "$python_bin" -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
}

bootstrap_backend_env() {
  local python_bin="$1"

  if [[ ! -f "$BACKEND_ENV" ]]; then
    cp "$BACKEND_ENV_EXAMPLE" "$BACKEND_ENV"
  fi

  local current_secret
  current_secret="$(grep '^SECRET_KEY=' "$BACKEND_ENV" | cut -d= -f2- || true)"
  if [[ -z "$current_secret" || "$current_secret" == change-me-* ]]; then
    set_kv "$BACKEND_ENV" SECRET_KEY "$(generate_secret_key "$python_bin")"
  fi

  # Local-safe defaults; do not overwrite if user already set custom values.
  ensure_kv "$BACKEND_ENV" DEBUG "True"
  ensure_kv "$BACKEND_ENV" ALLOWED_HOSTS "localhost,127.0.0.1,0.0.0.0,projectpuente.local"
  ensure_kv "$BACKEND_ENV" CORS_ALLOW_ALL_ORIGINS "True"
  ensure_kv "$BACKEND_ENV" CORS_ALLOWED_ORIGINS "http://localhost:5173,http://127.0.0.1:5173,http://projectpuente.local:5173"
  ensure_kv "$BACKEND_ENV" CSRF_TRUSTED_ORIGINS "http://localhost:5173,http://127.0.0.1:5173,http://projectpuente.local:5173"
  ensure_kv "$BACKEND_ENV" PUENTE_LOAD_MODEL_ON_STARTUP "False"
  ensure_kv "$BACKEND_ENV" DRF_THROTTLE_ANON_RATE "240/min"
  ensure_kv "$BACKEND_ENV" ML_MODEL_PATH "ml_models/nllb-200-distilled-600M"
  ensure_kv "$BACKEND_ENV" HF_TOKEN ""
  ensure_kv "$BACKEND_ENV" HF_MODEL_ID "facebook/nllb-200-distilled-600M"
  ensure_kv "$BACKEND_ENV" HF_INFERENCE_TIMEOUT_SECONDS "90"
  ensure_kv "$BACKEND_ENV" STRICT_OFFLINE_MODE "True"
}

bootstrap_frontend_env() {
  if [[ ! -f "$FRONTEND_ENV" ]]; then
    cp "$FRONTEND_ENV_EXAMPLE" "$FRONTEND_ENV"
  fi

  ensure_kv "$FRONTEND_ENV" VITE_PUENTE_API_KEY ""
}

main() {
  local python_bin
  python_bin="$(resolve_python_bin)"

  if [[ ! -f "$BACKEND_ENV_EXAMPLE" ]]; then
    echo "ERROR: Missing backend env example: $BACKEND_ENV_EXAMPLE" >&2
    exit 1
  fi

  if [[ ! -f "$FRONTEND_ENV_EXAMPLE" ]]; then
    echo "ERROR: Missing frontend env example: $FRONTEND_ENV_EXAMPLE" >&2
    exit 1
  fi

  bootstrap_backend_env "$python_bin"
  bootstrap_frontend_env

  if [[ -f "$LEGACY_BACKEND_ENV" ]]; then
    rm -f "$LEGACY_BACKEND_ENV"
    echo "Removed legacy duplicate env path: $LEGACY_BACKEND_ENV"
  fi

  chmod 600 "$BACKEND_ENV" "$FRONTEND_ENV"

  echo "Local env bootstrap complete."
  echo "- backend env:  $BACKEND_ENV"
  echo "- frontend env: $FRONTEND_ENV"
}

main "$@"
