#!/usr/bin/env bash
# ============================================================
#  Project Puente — Run Both Servers (Linux/macOS) — LAN Ready
# ============================================================
#  Backend:  http://0.0.0.0:8000  (LAN accessible)
#  Frontend: http://0.0.0.0:5173  (LAN accessible)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECTPUENTE_LOCAL_HOST="projectpuente.local"
LOCAL_HOST_FALLBACK="localhost"

BACKEND_ONLY=false
FRONTEND_ONLY=false

for arg in "$@"; do
	case "$arg" in
		--backend-only)
			BACKEND_ONLY=true
			;;
		--frontend-only)
			FRONTEND_ONLY=true
			;;
		*)
			echo "[ERROR] Unknown option: $arg"
			echo "Usage: $0 [--backend-only|--frontend-only]"
			exit 1
			;;
	esac
done

if [ "$BACKEND_ONLY" = true ] && [ "$FRONTEND_ONLY" = true ]; then
	echo "[ERROR] Use only one of --backend-only or --frontend-only."
	exit 1
fi

if [ ! -f "$SCRIPT_DIR/backend/manage.py" ]; then
	echo "[ERROR] backend/manage.py not found. Run this script from the project root."
	exit 1
fi

if [ ! -f "$SCRIPT_DIR/frontend/package.json" ]; then
	echo "[ERROR] frontend/package.json not found."
	exit 1
fi

if [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
	PYTHON_CMD="$VIRTUAL_ENV/bin/python"
elif [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
	PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
	PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
elif [ -x "$SCRIPT_DIR/../.venv/bin/python" ]; then
	PYTHON_CMD="$SCRIPT_DIR/../.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
	PYTHON_CMD="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
	PYTHON_CMD="$(command -v python)"
else
	echo "[ERROR] Python executable not found. Install Python 3.10+ or create a virtual environment."
	exit 1
fi

if [ ! -x "$PYTHON_CMD" ] && ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
	echo "[ERROR] Python executable not found: $PYTHON_CMD"
	exit 1
fi

if [ -d "$SCRIPT_DIR/.tools/node/bin" ]; then
	export PATH="$SCRIPT_DIR/.tools/node/bin:$PATH"
fi

if command -v npm >/dev/null 2>&1; then
	NPM_CMD="$(command -v npm)"
else
	echo "[ERROR] npm not found in PATH. Install Node.js 20+ or provide .tools/node/bin/npm."
	exit 1
fi

MODEL_PATH="$SCRIPT_DIR/ml_models/nllb-200-distilled-600M"
MODEL_PRELOAD_FLAG="${PUENTE_LOAD_MODEL_ON_STARTUP:-}"
if [ -z "$MODEL_PRELOAD_FLAG" ]; then
	if [ -d "$MODEL_PATH" ]; then
		MODEL_PRELOAD_FLAG="true"
	else
		MODEL_PRELOAD_FLAG="false"
	fi
fi

resolve_lan_ip() {
	if command -v hostname >/dev/null 2>&1; then
		local host_ip
		host_ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
		if [ -n "$host_ip" ]; then
			echo "$host_ip"
			return
		fi
	fi

	if command -v ip >/dev/null 2>&1; then
		local route_ip
		route_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") {print $(i+1); exit}}')"
		if [ -n "$route_ip" ]; then
			echo "$route_ip"
			return
		fi
	fi

	echo "YOUR_IP"
}

has_projectpuente_local_mapping() {
	if [ ! -r /etc/hosts ]; then
		return 1
	fi

	grep -Eiq '(^|[[:space:]])projectpuente\.local([[:space:]]|$)' /etc/hosts
}

is_port_in_use() {
	local port="$1"

	if command -v ss >/dev/null 2>&1; then
		ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)${port}$"
		return $?
	fi

	if command -v lsof >/dev/null 2>&1; then
		lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
		return $?
	fi

	if command -v netstat >/dev/null 2>&1; then
		netstat -an 2>/dev/null | grep -E "[\.:]${port}[[:space:]].*LISTEN" >/dev/null
		return $?
	fi

	return 1
}

LOCAL_APP_HOST="$LOCAL_HOST_FALLBACK"
if has_projectpuente_local_mapping; then
	LOCAL_APP_HOST="$PROJECTPUENTE_LOCAL_HOST"
fi

if [ "$BACKEND_ONLY" = true ]; then
	if is_port_in_use 8000; then
		echo "[ERROR] Port 8000 is already in use. Stop the existing process before running backend-only mode."
		exit 1
	fi
	echo "[INFO] Preferred local backend URL: http://${LOCAL_APP_HOST}:8000"
	if [ "$LOCAL_APP_HOST" != "$PROJECTPUENTE_LOCAL_HOST" ]; then
		echo "[WARN] projectpuente.local is not mapped in /etc/hosts."
		echo "       Add with: echo '127.0.0.1 projectpuente.local' | sudo tee -a /etc/hosts"
	fi
	cd "$SCRIPT_DIR/backend"
	PUENTE_LOAD_MODEL_ON_STARTUP="$MODEL_PRELOAD_FLAG" "$PYTHON_CMD" manage.py runserver 0.0.0.0:8000
	exit $?
fi

if [ "$FRONTEND_ONLY" = true ]; then
	if is_port_in_use 5173; then
		echo "[ERROR] Port 5173 is already in use. Stop the existing process before running frontend-only mode."
		exit 1
	fi
	echo "[INFO] Preferred local frontend URL: http://${LOCAL_APP_HOST}:5173"
	if [ "$LOCAL_APP_HOST" != "$PROJECTPUENTE_LOCAL_HOST" ]; then
		echo "[WARN] projectpuente.local is not mapped in /etc/hosts."
		echo "       Add with: echo '127.0.0.1 projectpuente.local' | sudo tee -a /etc/hosts"
	fi
	cd "$SCRIPT_DIR/frontend"
	"$NPM_CMD" run dev -- --host 0.0.0.0 --strictPort
	exit $?
fi

if is_port_in_use 8000; then
	echo "[ERROR] Port 8000 is already in use. Stop the existing process before starting the full stack."
	exit 1
fi

if is_port_in_use 5173; then
	echo "[ERROR] Port 5173 is already in use. Stop the existing process before starting the full stack."
	exit 1
fi

echo ""
echo "  ========================================"
echo "   Project Puente - Starting Servers"
echo "  ========================================"
echo ""

if [ "$MODEL_PRELOAD_FLAG" = "true" ]; then
	echo "  [INFO] Model preload: enabled (path: $MODEL_PATH)"
else
	echo "  [INFO] Model preload: disabled (missing local model path: $MODEL_PATH)"
	echo "         Backend still starts; translate/BTVL will return 503 until model files are available."
fi
echo ""

# Start Backend (Django)
cd "$SCRIPT_DIR/backend"
PUENTE_LOAD_MODEL_ON_STARTUP="$MODEL_PRELOAD_FLAG" "$PYTHON_CMD" manage.py runserver 0.0.0.0:8000 &
BACKEND_PID=$!

sleep 3

# Start Frontend (Vite)
cd "$SCRIPT_DIR/frontend"
"$NPM_CMD" run dev -- --host 0.0.0.0 --strictPort &
FRONTEND_PID=$!

LAN_IP="$(resolve_lan_ip)"

echo ""
echo "  [OK] Python   -> $PYTHON_CMD"
echo "  [OK] npm      -> $NPM_CMD"
echo "  [OK] Backend  -> http://${LOCAL_APP_HOST}:8000  (LAN: http://${LAN_IP}:8000)"
echo "  [OK] Frontend -> http://${LOCAL_APP_HOST}:5173  (LAN: http://${LAN_IP}:5173)"
if [ "$LOCAL_APP_HOST" != "$PROJECTPUENTE_LOCAL_HOST" ]; then
	echo "  [WARN] projectpuente.local mapping not found in /etc/hosts."
	echo "         Add with: echo '127.0.0.1 projectpuente.local' | sudo tee -a /etc/hosts"
fi
echo ""
echo "  Running in current terminal (no extra windows). Press Ctrl+C to stop both servers."

cleanup() {
	kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT
wait
