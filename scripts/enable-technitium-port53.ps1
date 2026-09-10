$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $repoRoot ".netwatch-port53-result.json"
$script:snapshotWasRunning = $null

if (Test-Path -LiteralPath $resultPath) {
    try {
        $priorState = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
        if ($priorState.status -in @("ready", "rolled_back", "rollback_failed") -and $null -ne $priorState.sharedAccessWasRunning) {
            $script:snapshotWasRunning = [bool]$priorState.sharedAccessWasRunning
        }
    }
    catch {
        # A corrupt prior result cannot safely provide a snapshot; the current
        # service state will be captured below instead.
    }
}

function Write-Result {
    param(
        [Parameter(Mandatory)] [string]$Status,
        [Parameter(Mandatory)] [string]$Message,
        [Nullable[bool]]$SharedAccessWasRunning
    )

    if ($null -eq $SharedAccessWasRunning) {
        $SharedAccessWasRunning = $script:snapshotWasRunning
    }
    if ($null -eq $SharedAccessWasRunning) {
        $SharedAccessWasRunning = $false
    }

    @{
        status = $Status
        message = $Message
        sharedAccessWasRunning = $SharedAccessWasRunning
        completedAt = [DateTimeOffset]::UtcNow.ToString("O")
    } | ConvertTo-Json | Set-Content -LiteralPath $resultPath -Encoding utf8
}

$principal = [Security.Principal.WindowsPrincipal]::new(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Result -Status "failed" -Message "Administrator permission was not granted."
    exit 1
}

$service = Get-Service -Name "SharedAccess" -ErrorAction Stop
$wasRunning = $service.Status -eq [System.ServiceProcess.ServiceControllerStatus]::Running
if ($null -eq $script:snapshotWasRunning) {
    $script:snapshotWasRunning = $wasRunning
}

try {
    if ($wasRunning) {
        Stop-Service -Name "SharedAccess" -Force
        (Get-Service -Name "SharedAccess").WaitForStatus(
            [System.ServiceProcess.ServiceControllerStatus]::Stopped,
            [TimeSpan]::FromSeconds(15)
        )
    }

    $udpOwner = Get-NetUDPEndpoint -LocalPort 53 -ErrorAction SilentlyContinue
    $tcpOwner = Get-NetTCPConnection -LocalPort 53 -State Listen -ErrorAction SilentlyContinue
    if ($udpOwner -or $tcpOwner) {
        throw "Port 53 is still occupied after stopping Windows Internet Connection Sharing."
    }

    docker info --format "{{.ServerVersion}}" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Docker became unavailable."
    }

    $internet = Invoke-WebRequest -Uri "https://www.msftconnecttest.com/connecttest.txt" -UseBasicParsing -TimeoutSec 10
    if ($internet.StatusCode -ne 200) {
        throw "The Internet connectivity check failed."
    }

    Write-Result -Status "ready" -Message "Port 53 is free; Docker and Internet connectivity remain available."
}
catch {
    $failureMessage = $_.Exception.Message
    $rollbackStatus = "rolled_back"
    if ($script:snapshotWasRunning -eq $true) {
        try {
            Start-Service -Name "SharedAccess"
            (Get-Service -Name "SharedAccess").WaitForStatus(
                [System.ServiceProcess.ServiceControllerStatus]::Running,
                [TimeSpan]::FromSeconds(15)
            )
        }
        catch {
            $rollbackStatus = "rollback_failed"
            $failureMessage = "$failureMessage Rollback also failed: $($_.Exception.Message)"
        }
    }
    Write-Result -Status $rollbackStatus -Message $failureMessage
    exit 1
}
