param([switch]$BuildFrontend)
$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $desktopRoot
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "npm was not found on PATH." }
if ($BuildFrontend) { Push-Location (Join-Path $repoRoot "frontend"); try { npm run build } finally { Pop-Location } }
Push-Location $desktopRoot
try { if (-not (Test-Path -LiteralPath (Join-Path $desktopRoot "node_modules"))) { npm install }; npm run dev } finally { Pop-Location }
