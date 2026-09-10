$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $repoRoot ".netwatch-sensor.pid"

if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Output "NetWatch Windows sensor is not running."
    exit 0
}

$sensorPid = [int](Get-Content -LiteralPath $pidPath -Raw)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $sensorPid" -ErrorAction SilentlyContinue
$expectedPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
if ($process -and $process.ExecutablePath -eq $expectedPython -and $process.CommandLine -match "sensor_main:app") {
    Stop-Process -Id $sensorPid
    Write-Output "NetWatch Windows sensor stopped."
}
elseif ($process) {
    throw "PID $sensorPid does not belong to the NetWatch Windows sensor; it was not stopped."
}

Remove-Item -LiteralPath $pidPath -Force
