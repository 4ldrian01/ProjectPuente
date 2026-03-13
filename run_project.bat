@echo off
REM ============================================================
REM  Project Puente — Run Both Servers (Windows) — LAN Ready
REM ============================================================
REM  Backend:  http://0.0.0.0:8000  (LAN accessible)
REM  Frontend: http://localhost:5173
REM ============================================================

echo.
echo  ========================================
echo   Project Puente - Starting Servers
echo  ========================================
echo.

set "ROOT_DIR=%~dp0"
set "PYTHON_EXE=python"

if exist "%ROOT_DIR%.venv\Scripts\python.exe" (
	set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"
) else if exist "%ROOT_DIR%venv\Scripts\python.exe" (
	set "PYTHON_EXE=%ROOT_DIR%venv\Scripts\python.exe"
)

REM Start Backend (Django) — bind 0.0.0.0 for LAN access
start "Puente Backend" cmd /k "cd /d ""%ROOT_DIR%backend"" && ""%PYTHON_EXE%"" manage.py runserver 0.0.0.0:8000"

REM Wait a moment for backend to initialize
timeout /t 5 /nobreak >nul

REM Start Frontend (Vite) — bind 0.0.0.0 for LAN access
start "Puente Frontend" cmd /k "cd /d ""%ROOT_DIR%frontend"" && npm run dev -- --host 0.0.0.0"

echo.
echo  [OK] Python   → %PYTHON_EXE%
echo  [OK] Backend  → http://0.0.0.0:8000  (LAN: http://YOUR_IP:8000)
echo  [OK] Frontend → http://0.0.0.0:5173  (LAN: http://YOUR_IP:5173)
echo.
echo  Press any key to close this launcher...
pause >nul
