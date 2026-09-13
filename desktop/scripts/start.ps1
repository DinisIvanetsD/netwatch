$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $desktopRoot
$pidPath = Join-Path $desktopRoot ".netwatch-desktop.pid"
if (Test-Path -LiteralPath $pidPath) { $oldPid = [int](Get-Content -LiteralPath $pidPath -Raw); if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { Write-Output "NetWatch Desktop is already running (PID $oldPid)."; exit 0 }; Remove-Item -LiteralPath $pidPath -Force }
if (-not (Test-Path -LiteralPath (Join-Path $desktopRoot "node_modules\electron\dist\electron.exe"))) { throw "Desktop dependencies are missing. Run desktop\scripts\dev.ps1 first." }
$process = Start-Process -FilePath (Join-Path $desktopRoot "node_modules\electron\dist\electron.exe") -ArgumentList @($desktopRoot) -WorkingDirectory $repoRoot -PassThru
[IO.File]::WriteAllText($pidPath, [string]$process.Id)
Write-Output "NetWatch Desktop started (PID $($process.Id))."
