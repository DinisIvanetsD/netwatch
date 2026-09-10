param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8765
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $repoRoot "backend"
$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pidPath = Join-Path $repoRoot ".netwatch-sensor.pid"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "NetWatch Python environment was not found. Install backend dependencies first."
}

if (Test-Path -LiteralPath $pidPath) {
    $existingPid = [int](Get-Content -LiteralPath $pidPath -Raw)
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Output "NetWatch Windows sensor is already running (PID $existingPid)."
        exit 0
    }
    Remove-Item -LiteralPath $pidPath -Force
}

$occupied = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($occupied) {
    throw "TCP port $Port is already in use. Choose another local sensor port."
}

$process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @("-m", "uvicorn", "sensor_main:app", "--host", "127.0.0.1", "--port", $Port) `
    -WorkingDirectory $backendPath `
    -WindowStyle Hidden `
    -PassThru

[System.IO.File]::WriteAllText($pidPath, [string]$process.Id)

for ($attempt = 0; $attempt -lt 30; $attempt += 1) {
    Start-Sleep -Milliseconds 250
    if ($process.HasExited) {
        Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
        throw "The NetWatch Windows sensor exited before becoming ready."
    }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 1
        if ($health.status -eq "healthy" -and $health.authenticated) {
            Write-Output "NetWatch Windows sensor is ready on 127.0.0.1:$Port (PID $($process.Id))."
            exit 0
        }
    }
    catch {
        # The process can need a moment before the loopback endpoint is ready.
    }
}

Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $pidPath -Force -ErrorAction SilentlyContinue
throw "The NetWatch Windows sensor did not become ready."
