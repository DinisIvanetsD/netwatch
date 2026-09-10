$ErrorActionPreference = "Stop"

$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator permission is required to restore Windows Internet Connection Sharing."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $repoRoot ".netwatch-port53-result.json"
if (-not (Test-Path -LiteralPath $resultPath)) {
    throw "No NetWatch port-53 state file exists; the original service state is unknown."
}

$state = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if ($state.status -eq "restored") {
    Write-Output "Windows Internet Connection Sharing was already restored."
    exit 0
}
if ($state.status -ne "ready") {
    throw "The recorded operation is not in a restorable state: $($state.status)."
}

if ($state.sharedAccessWasRunning -eq $true) {
    $service = Get-Service -Name "SharedAccess" -ErrorAction Stop
    if ($service.Status -ne [System.ServiceProcess.ServiceControllerStatus]::Running) {
        Start-Service -Name "SharedAccess"
        (Get-Service -Name "SharedAccess").WaitForStatus(
            [System.ServiceProcess.ServiceControllerStatus]::Running,
            [TimeSpan]::FromSeconds(15)
        )
    }
    $message = "Windows Internet Connection Sharing is running again."
}
else {
    $service = Get-Service -Name "SharedAccess" -ErrorAction Stop
    if ($service.Status -ne [System.ServiceProcess.ServiceControllerStatus]::Stopped) {
        Stop-Service -Name "SharedAccess" -Force
        (Get-Service -Name "SharedAccess").WaitForStatus(
            [System.ServiceProcess.ServiceControllerStatus]::Stopped,
            [TimeSpan]::FromSeconds(15)
        )
    }
    $message = "Windows Internet Connection Sharing was originally stopped; no service was started."
}

$state.status = "restored"
$state.message = $message
$state.completedAt = [DateTimeOffset]::UtcNow.ToString("O")
$state | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding utf8

Write-Output $message
