$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$pidPath = Join-Path $desktopRoot ".netwatch-desktop.pid"
if (-not (Test-Path -LiteralPath $pidPath)) { Write-Output "NetWatch Desktop is not running."; exit 0 }
$desktopProcessId = [int](Get-Content -LiteralPath $pidPath -Raw)
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $desktopProcessId" -ErrorAction SilentlyContinue
if ($process -and $process.Name -match "^electron(\.exe)?$" -and $process.CommandLine -like "*$desktopRoot*") {
  $owned = Get-Process -Id $desktopProcessId -ErrorAction Stop
  if ($owned.MainWindowHandle -ne 0) { [void]$owned.CloseMainWindow() }
  if (-not $owned.WaitForExit(5000)) {
    Stop-Process -Id $desktopProcessId -Force
    $owned.WaitForExit(1000)
    Write-Output "NetWatch Desktop force-stopped after graceful shutdown timeout."
  } else { Write-Output "NetWatch Desktop stopped gracefully." }
} elseif ($process) {
  Write-Output "Ignoring stale NetWatch PID $desktopProcessId; it belongs to another process."
}
Remove-Item -LiteralPath $pidPath -Force
