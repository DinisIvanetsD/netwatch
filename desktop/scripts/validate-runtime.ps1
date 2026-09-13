param([switch]$IncludePython)

$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $desktopRoot "runtime"

function Require-File($relativePath) {
    $path = Join-Path $runtimeRoot $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required runtime file is missing: $relativePath"
    }
}

if (-not (Test-Path -LiteralPath $runtimeRoot -PathType Container)) {
    throw "Runtime staging directory is missing: $runtimeRoot"
}
foreach ($file in @(
    "backend\main.py", "backend\sensor_main.py", "backend\requirements.txt",
    "frontend\.next\standalone\server.js", ".env.example"
)) { Require-File $file }

$invalidArtifacts = Get-ChildItem -LiteralPath $runtimeRoot -Force -Recurse -File |
    Where-Object { $_.Extension -in @('.pyc', '.pyo') -or $_.FullName -match '(^|\\)__pycache__(\\|$)' }
if ($invalidArtifacts) {
    throw "Runtime contains Python cache artifacts: $($invalidArtifacts.FullName -join ', ')"
}

if ($IncludePython) {
    Require-File "python\python.exe"
    Require-File "python\python3.dll"
    $versionedDlls = Get-ChildItem -LiteralPath (Join-Path $runtimeRoot "python") -Filter "python*.dll" -File |
        Where-Object { $_.Name -match '^python\d{2,3}\.dll$' }
    if (-not $versionedDlls) { throw "No version-specific Python DLL was staged." }
}

Write-Output "Runtime validation passed: $runtimeRoot"
