param(
    [switch]$IncludePython
)

$ErrorActionPreference = "Stop"
$desktopRoot = Split-Path -Parent $PSScriptRoot
$repoRoot = Split-Path -Parent $desktopRoot
$runtimeRoot = Join-Path $desktopRoot "runtime"

function Copy-Directory($source, $destination) {
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Required build directory was not found: $source"
    }
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $destination -Recurse -Force
}

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "frontend\.next\standalone\server.js"))) {
    throw "Frontend standalone build is missing. Run 'npm run build' in frontend first."
}

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$backendRuntime = Join-Path $runtimeRoot "backend"
$frontendRuntime = Join-Path $runtimeRoot "frontend"
New-Item -ItemType Directory -Force -Path $backendRuntime | Out-Null

foreach ($directory in @("api", "core", "database", "models", "schemas", "services")) {
    Copy-Directory (Join-Path $repoRoot "backend\$directory") (Join-Path $backendRuntime $directory)
}
foreach ($file in @("__init__.py", "main.py", "sensor_main.py", "alembic.ini")) {
    Copy-Item -LiteralPath (Join-Path $repoRoot "backend\$file") -Destination $backendRuntime -Force
}
Copy-Item -LiteralPath (Join-Path $repoRoot "backend\requirements.txt") -Destination $backendRuntime -Force
New-Item -ItemType Directory -Force -Path (Join-Path $backendRuntime "data") | Out-Null

Copy-Directory (Join-Path $repoRoot "frontend\.next\standalone") (Join-Path $frontendRuntime ".next\standalone")
# Next's standalone server resolves these paths relative to its own directory.
Copy-Directory (Join-Path $repoRoot "frontend\.next\static") (Join-Path $frontendRuntime ".next\standalone\.next\static")
if (Test-Path -LiteralPath (Join-Path $repoRoot "frontend\public")) {
    Copy-Directory (Join-Path $repoRoot "frontend\public") (Join-Path $frontendRuntime ".next\standalone\public")
}

$pythonCandidates = @(
    (Join-Path $repoRoot ".venv"),
    (Join-Path $repoRoot "backend\.venv")
)
$pythonSource = $pythonCandidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ "Scripts\python.exe") } | Select-Object -First 1
if ($IncludePython) {
    if (-not $pythonSource) {
        throw "A Python virtual environment was not found in the repository or backend."
    }
    $pythonRuntime = Join-Path $runtimeRoot "python"
    foreach ($stalePath in @("pyvenv.cfg", "Scripts", "Include")) {
        $staleTarget = Join-Path $pythonRuntime $stalePath
        if (-not (Test-Path -LiteralPath $staleTarget)) {
            continue
        }
        # The packaged interpreter must not keep venv metadata pointing to the
        # developer machine; otherwise Python ignores its bundled site-packages.
        Remove-Item -LiteralPath $staleTarget -Force -Recurse
    }
    $pythonHomeLine = Get-Content -LiteralPath (Join-Path $pythonSource "pyvenv.cfg") |
        Where-Object { $_ -match '^home\s*=' } |
        Select-Object -First 1
    $pythonHome = if ($pythonHomeLine) {
        ($pythonHomeLine -replace '^home\s*=\s*', '').Trim()
    } else {
        $null
    }
    if ($pythonHome -and (Test-Path -LiteralPath (Join-Path $pythonHome "python.exe"))) {
        # A venv's python.exe points back to its creator's base installation.
        # Copy the base interpreter and merge only the installed dependencies so
        # the desktop package does not depend on Python being installed later.
        foreach ($fileName in @(
            "python.exe", "pythonw.exe", "python3.dll", "python313.dll",
            "vcruntime140.dll", "vcruntime140_1.dll"
        )) {
            $sourceFile = Join-Path $pythonHome $fileName
            if (Test-Path -LiteralPath $sourceFile) {
                Copy-Item -LiteralPath $sourceFile -Destination $pythonRuntime -Force
            }
        }
        Copy-Directory (Join-Path $pythonHome "DLLs") (Join-Path $pythonRuntime "DLLs")
        Copy-Directory (Join-Path $pythonHome "Lib") (Join-Path $pythonRuntime "Lib")
        Copy-Directory (Join-Path $pythonSource "Lib\site-packages") (Join-Path $pythonRuntime "Lib\site-packages")
        Write-Output "Bundled standalone Python runtime from $pythonHome with dependencies from $pythonSource"
    } else {
        Copy-Directory $pythonSource $pythonRuntime
        Write-Output "Bundled Python virtual environment from $pythonSource (base interpreter metadata was unavailable)"
    }
}

Copy-Item -LiteralPath (Join-Path $repoRoot ".env.example") -Destination (Join-Path $runtimeRoot ".env.example") -Force
Write-Output "Prepared NetWatch desktop runtime at $runtimeRoot"
if ($IncludePython) {
    Write-Output "Python files are included in the desktop runtime"
} else {
    Write-Output "Python is resolved from the installed system or repository virtual environment."
}
