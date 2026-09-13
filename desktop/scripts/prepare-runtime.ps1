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
    $sourceRoot = (Resolve-Path -LiteralPath $source).Path.TrimEnd('\')
    foreach ($item in Get-ChildItem -LiteralPath $sourceRoot -Force -Recurse) {
        $relativePath = $item.FullName.Substring($sourceRoot.Length).TrimStart('\')
        if ($relativePath -match '(^|\\)__pycache__(\\|$)' -or $item.Extension -in @('.pyc', '.pyo')) {
            continue
        }
        $target = Join-Path $destination $relativePath
        if ($item.PSIsContainer) {
            [System.IO.Directory]::CreateDirectory($target) | Out-Null
        } else {
            [System.IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
            Copy-Item -LiteralPath $item.FullName -Destination $target -Force
        }
    }
}

function Clear-RuntimeStagingDirectory($path) {
    $resolvedDesktop = (Resolve-Path -LiteralPath $desktopRoot).Path.TrimEnd('\')
    $resolvedTarget = [System.IO.Path]::GetFullPath($path).TrimEnd('\')
    $expectedTarget = Join-Path $resolvedDesktop 'runtime'
    if ($resolvedTarget -ne [System.IO.Path]::GetFullPath($expectedTarget).TrimEnd('\') -or
        (Split-Path -Parent $resolvedTarget) -ne $resolvedDesktop -or
        (Split-Path -Leaf $resolvedTarget) -ne 'runtime') {
        throw "Refusing to clear unexpected runtime staging path: $resolvedTarget"
    }
    if (Test-Path -LiteralPath $resolvedTarget) {
        Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $resolvedTarget | Out-Null
}

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "frontend\.next\standalone\server.js"))) {
    throw "Frontend standalone build is missing. Run 'npm run build' in frontend first."
}

Clear-RuntimeStagingDirectory $runtimeRoot
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
    (Join-Path $repoRoot "backend\.venv"),
    (Join-Path $repoRoot ".venv")
)
$pythonSource = $pythonCandidates | Where-Object { Test-Path -LiteralPath (Join-Path $_ "Scripts\python.exe") } | Select-Object -First 1
if ($IncludePython) {
    if (-not $pythonSource) {
        throw "A Python virtual environment was not found in the repository or backend."
    }
    $pythonRuntime = Join-Path $runtimeRoot "python"
    New-Item -ItemType Directory -Force -Path $pythonRuntime | Out-Null
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
        $versionedPythonDll = Get-ChildItem -LiteralPath $pythonHome -Filter 'python*.dll' -File |
            Where-Object { $_.Name -match '^python\d{2,3}\.dll$' } |
            Sort-Object Name -Descending |
            Select-Object -First 1
        if (-not $versionedPythonDll) {
            throw "Could not find the version-specific Python DLL in $pythonHome."
        }
        foreach ($fileName in @(
            "python.exe", "pythonw.exe", "python3.dll", $versionedPythonDll.Name,
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
