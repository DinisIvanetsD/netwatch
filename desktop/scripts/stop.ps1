$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $desktopRoot ".netwatch-desktop.pid"
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output "NetWatch Desktop is not running."; exit 0 }
$pid = [int](Get-Content -LiteralPath $pidPath -Raw)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $pid" -ErrorAction SilentlyContinue
if ($process -and $process.CommandLine -match "electron.*desktop") { Stop-Process -Id $pid -Force; Write-Output "NetWatch Desktop stopped." } elseif ($process) { throw "PID $pid does not belong to NetWatch Desktop; it was not stopped." }
Remove-Item -LiteralPath $pidPath -Force
