param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = 'Stop'

function ConvertTo-PowerShellQuotedString {
    param([Parameter(Mandatory = $true)][string]$Value)

    return "'" + ($Value -replace "'", "''") + "'"
}

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $rootDir 'backend'
$frontendDir = Join-Path $rootDir 'frontend'

$pythonCandidates = @(
    (Join-Path $rootDir '.venv\Scripts\python.exe'),
    (Join-Path $rootDir 'venv\Scripts\python.exe')
)

$pythonExe = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonExe) {
    $pythonExe = 'python'
}

function Start-Backend {
    Push-Location $backendDir
    try {
        & $pythonExe manage.py runserver 0.0.0.0:8000
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

function Start-Frontend {
    Push-Location $frontendDir
    try {
        npm run dev -- --host 0.0.0.0
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

if ($BackendOnly -and $FrontendOnly) {
    throw 'Use only one of -BackendOnly or -FrontendOnly.'
}

if ($BackendOnly) {
    Start-Backend
}

if ($FrontendOnly) {
    Start-Frontend
}

$backendCommand = "Set-Location -LiteralPath $(ConvertTo-PowerShellQuotedString $backendDir); & $(ConvertTo-PowerShellQuotedString $pythonExe) manage.py runserver 0.0.0.0:8000"
$frontendCommand = "Set-Location -LiteralPath $(ConvertTo-PowerShellQuotedString $frontendDir); npm run dev -- --host 0.0.0.0"

Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $backendCommand | Out-Null
Start-Sleep -Seconds 3
Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $frontendCommand | Out-Null

Write-Host ''
Write-Host '  ========================================'
Write-Host '   Project Puente - Starting Servers'
Write-Host '  ========================================'
Write-Host ''
Write-Host "  [OK] Python   → $pythonExe"
Write-Host '  [OK] Backend  → http://0.0.0.0:8000  (LAN: http://YOUR_IP:8000)'
Write-Host '  [OK] Frontend → http://0.0.0.0:5173  (LAN: http://YOUR_IP:5173)'
Write-Host ''
Write-Host '  Tip: In VS Code, run the task named "Puente: Start full stack" for this launcher.'
