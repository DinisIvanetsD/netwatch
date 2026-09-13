param()

$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $desktopRoot

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm was not found on PATH. Install Node.js/npm before packaging."
}

Push-Location (Join-Path $repoRoot "frontend")
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend standalone build failed." }
} finally {
    Pop-Location
}

Push-Location $desktopRoot
try {
    & (Join-Path $PSScriptRoot "prepare-runtime.ps1") -IncludePython
    if ($LASTEXITCODE -ne 0) { throw "Runtime staging failed." }
    & (Join-Path $PSScriptRoot "validate-runtime.ps1") -IncludePython
    if ($LASTEXITCODE -ne 0) { throw "Runtime validation failed." }
} finally {
    Pop-Location
}
