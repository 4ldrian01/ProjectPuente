param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-PortListening {
    param([Parameter(Mandatory = $true)][int]$Port)

    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    }
    catch {
        return $false
    }
}

function Wait-PortListening {
    param(
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }

    return $false
}

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $rootDir 'backend'
$frontendDir = Join-Path $rootDir 'frontend'

if (-not (Test-Path (Join-Path $backendDir 'manage.py'))) {
    throw 'backend/manage.py not found. Run this script from the project root.'
}

if (-not (Test-Path (Join-Path $frontendDir 'package.json'))) {
    throw 'frontend/package.json not found. Run this script from the project root.'
}

$pythonCandidates = @(
    (Join-Path $rootDir '.venv\Scripts\python.exe'),
    (Join-Path $rootDir 'venv\Scripts\python.exe')
)

$pythonExe = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $pythonExe) {
    $pythonExe = 'python'
}

if (-not (Get-Command $pythonExe -ErrorAction SilentlyContinue)) {
    throw "Python executable not found: $pythonExe"
}

$npmCommand = (Get-Command npm -ErrorAction SilentlyContinue).Source
if (-not $npmCommand) {
    throw 'npm command not found. Install Node.js 20+.'
}

function Start-Backend {
    Push-Location $backendDir
    try {
        $env:PUENTE_LOAD_MODEL_ON_STARTUP = 'true'
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
        & $npmCommand run dev -- --host 0.0.0.0
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

function Stop-ProcessTree {
    param([System.Diagnostics.Process]$Process)

    if (-not $Process) {
        return
    }

    try {
        if ($Process.HasExited) {
            return
        }
    }
    catch {
        return
    }

    try {
        taskkill /PID $Process.Id /T /F | Out-Null
    }
    catch {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
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

if (Test-PortListening -Port 8000) {
    Write-Warning 'Port 8000 is already listening. Backend may fail to start in a new process.'
}

if (Test-PortListening -Port 5173) {
    Write-Warning 'Port 5173 is already listening. Frontend may fail to start in a new process.'
}

$previousLoadFlag = $env:PUENTE_LOAD_MODEL_ON_STARTUP
$env:PUENTE_LOAD_MODEL_ON_STARTUP = 'true'

$backendProc = $null
$frontendProc = $null

try {
    $backendProc = Start-Process -FilePath $pythonExe -ArgumentList @('manage.py', 'runserver', '0.0.0.0:8000') -WorkingDirectory $backendDir -NoNewWindow -PassThru
    Start-Sleep -Seconds 3
    $frontendProc = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/c', 'npm run dev -- --host 0.0.0.0') -WorkingDirectory $frontendDir -NoNewWindow -PassThru

    $backendReady = Wait-PortListening -Port 8000 -TimeoutSeconds 45
    $frontendReady = Wait-PortListening -Port 5173 -TimeoutSeconds 60

    if (-not $backendReady) {
        Write-Warning 'Backend did not open port 8000 within timeout. Check backend output for errors.'
    }

    if (-not $frontendReady) {
        Write-Warning 'Frontend did not open port 5173 within timeout. Check frontend output for errors.'
    }

    if ($backendProc.HasExited) {
        Write-Warning "Backend process exited early (PID $($backendProc.Id), ExitCode $($backendProc.ExitCode))."
    }

    if ($frontendProc.HasExited) {
        Write-Warning "Frontend process exited early (PID $($frontendProc.Id), ExitCode $($frontendProc.ExitCode))."
    }

    $lanHost = $env:COMPUTERNAME
    try {
        $candidateIp = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object {
                $_.IPAddress -ne '127.0.0.1' -and
                $_.IPAddress -notlike '169.254*' -and
                $_.InterfaceOperationalStatus -eq 'Up'
            } |
            Select-Object -ExpandProperty IPAddress -First 1

        if ($candidateIp) {
            $lanHost = $candidateIp
        }
    }
    catch {
        # Keep hostname fallback.
    }

    Write-Host ''
    Write-Host '  ========================================'
    Write-Host '   Project Puente - Starting Servers'
    Write-Host '  ========================================'
    Write-Host ''
    Write-Host "  [OK] Python   -> $pythonExe"
    Write-Host ("  [{0}] Backend  -> http://0.0.0.0:8000  (LAN: http://{1}:8000)" -f ($(if ($backendReady) { 'OK' } else { 'WARN' }), $lanHost))
    Write-Host ("  [{0}] Frontend -> http://0.0.0.0:5173  (LAN: http://{1}:5173)" -f ($(if ($frontendReady) { 'OK' } else { 'WARN' }), $lanHost))
    Write-Host ''
    Write-Host '  Running in current terminal (no extra windows). Press Ctrl+C to stop both servers.'

    while ($true) {
        if ($backendProc.HasExited) {
            Write-Warning "Backend process exited (PID $($backendProc.Id), ExitCode $($backendProc.ExitCode))."
            break
        }

        if ($frontendProc.HasExited) {
            Write-Warning "Frontend process exited (PID $($frontendProc.Id), ExitCode $($frontendProc.ExitCode))."
            break
        }

        Start-Sleep -Milliseconds 500
    }
}
finally {
    Stop-ProcessTree -Process $backendProc
    Stop-ProcessTree -Process $frontendProc

    if ($null -eq $previousLoadFlag) {
        Remove-Item Env:PUENTE_LOAD_MODEL_ON_STARTUP -ErrorAction SilentlyContinue
    }
    else {
        $env:PUENTE_LOAD_MODEL_ON_STARTUP = $previousLoadFlag
    }
}
