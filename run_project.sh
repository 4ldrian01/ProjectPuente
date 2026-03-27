#!/usr/bin/env bash
# ============================================================
#  Project Puente — Run Both Servers (Linux/macOS) — LAN Ready
# ============================================================
#  Backend:  http://0.0.0.0:8000  (LAN accessible)
#  Frontend: http://0.0.0.0:5173  (LAN accessible)
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
	PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
	PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
	PYTHON_CMD="$(command -v python3)"
else
	PYTHON_CMD="$(command -v python)"
fi

if ! command -v "$PYTHON_CMD" >/dev/null 2>&1; then
	echo "[ERROR] Python executable not found: $PYTHON_CMD"
	exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
	echo "[ERROR] npm not found in PATH. Install Node.js 20+."
	exit 1
fi

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

if [ "$BACKEND_ONLY" = true ]; then
	if is_port_in_use 8000; then
		echo "[ERROR] Port 8000 is already in use. Stop the existing process before running backend-only mode."
		exit 1
	fi
	cd "$SCRIPT_DIR/backend"
	PUENTE_LOAD_MODEL_ON_STARTUP=true "$PYTHON_CMD" manage.py runserver 0.0.0.0:8000
	exit $?
fi

if [ "$FRONTEND_ONLY" = true ]; then
	if is_port_in_use 5173; then
		echo "[ERROR] Port 5173 is already in use. Stop the existing process before running frontend-only mode."
		exit 1
	fi
	cd "$SCRIPT_DIR/frontend"
	npm run dev -- --host 0.0.0.0
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

# Start Backend (Django)
cd "$SCRIPT_DIR/backend"
PUENTE_LOAD_MODEL_ON_STARTUP=true "$PYTHON_CMD" manage.py runserver 0.0.0.0:8000 &
BACKEND_PID=$!

sleep 3

# Start Frontend (Vite)
cd "$SCRIPT_DIR/frontend"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")
if [ -z "$LAN_IP" ]; then
	LAN_IP="YOUR_IP"
fi

echo ""
echo "  [OK] Python   -> $PYTHON_CMD"
echo "  [OK] Backend  -> http://0.0.0.0:8000  (LAN: http://${LAN_IP}:8000)"
echo "  [OK] Frontend -> http://0.0.0.0:5173  (LAN: http://${LAN_IP}:5173)"
echo ""
echo "  Running in current terminal (no extra windows). Press Ctrl+C to stop both servers."

cleanup() {
	kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT
wait
