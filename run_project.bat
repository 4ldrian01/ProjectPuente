@echo off
REM ============================================================
REM  Project Puente — Run Both Servers (Windows) — VS Code terminal
REM ============================================================
REM  Backend:  http://0.0.0.0:8000  (LAN accessible)
REM  Frontend: http://0.0.0.0:5173  (LAN accessible)
REM ============================================================

setlocal

echo.
echo  ========================================
echo   Project Puente - Starting Servers
echo  ========================================
echo.

set "ROOT_DIR=%~dp0"
set "PS_SCRIPT=%ROOT_DIR%run_project.ps1"
set "EXIT_CODE=0"

if not exist "%PS_SCRIPT%" (
	echo [ERROR] run_project.ps1 not found.
	set "EXIT_CODE=1"
	goto :end
)

if not exist "%ROOT_DIR%backend\manage.py" (
	echo [ERROR] backend\manage.py not found. Run this script from the project root.
	set "EXIT_CODE=1"
	goto :end
)

if not exist "%ROOT_DIR%frontend\package.json" (
	echo [ERROR] frontend\package.json not found.
	set "EXIT_CODE=1"
	goto :end
)

where powershell >nul 2>nul
if errorlevel 1 (
	echo [ERROR] powershell was not found in PATH.
	set "EXIT_CODE=1"
	goto :end
)

echo [INFO] Running launcher in current terminal (no extra cmd/powershell windows)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%" %*
set "EXIT_CODE=%ERRORLEVEL%"

:end
endlocal
exit /b %EXIT_CODE%
