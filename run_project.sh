#!/usr/bin/env bash
# ============================================================
#  Project Puente — Run Both Servers (Linux/macOS) — LAN Ready
# ============================================================
#  Backend:  http://0.0.0.0:8000  (LAN accessible)
#  Frontend: http://0.0.0.0:5173  (LAN accessible)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
	PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -x "$SCRIPT_DIR/venv/bin/python" ]; then
	PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
	PYTHON_CMD="$(command -v python3)"
else
	PYTHON_CMD="$(command -v python)"
fi

echo ""
echo "  ========================================"
echo "   Project Puente - Starting Servers"
echo "  ========================================"
echo ""

# Start Backend (Django)
cd "$SCRIPT_DIR/backend"
"$PYTHON_CMD" manage.py runserver 0.0.0.0:8000 &
BACKEND_PID=$!

sleep 3

# Start Frontend (Vite)
cd "$SCRIPT_DIR/frontend"
npm run dev -- --host 0.0.0.0 &
FRONTEND_PID=$!

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")

echo ""
echo "  [OK] Python   → $PYTHON_CMD"
echo "  [OK] Backend  → http://0.0.0.0:8000  (LAN: http://${LAN_IP}:8000)"
echo "  [OK] Frontend → http://0.0.0.0:5173  (LAN: http://${LAN_IP}:5173)"
echo ""
echo "  Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
