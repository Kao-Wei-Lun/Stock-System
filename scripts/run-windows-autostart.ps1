[CmdletBinding()]
param(
    [ValidateRange(30, 900)]
    [int]$MySqlWaitSeconds = 180,

    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $projectRoot ".runtime"
$logPath = Join-Path $runtimeDir "windows-autostart.log"
$startScript = Join-Path $PSScriptRoot "start.bat"

New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

function Write-AutostartLog {
    param([Parameter(Mandatory = $true)][string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $logPath -Encoding UTF8 -Value "[$timestamp] $Message"
}

function Test-LocalTcpPort {
    param(
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port,
        [int]$TimeoutMilliseconds = 1000
    )

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $connect.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            return $false
        }
        $client.EndConnect($connect)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Test-QuantVisionReady {
    try {
        $result = Invoke-RestMethod -Uri "http://127.0.0.1:8001/api/ready" -TimeoutSec 3
        return $result.ready -eq $true
    }
    catch {
        return $false
    }
}

try {
    if (-not (Test-Path -LiteralPath $startScript -PathType Leaf)) {
        throw "QuantVision start script does not exist: $startScript"
    }

    if (Test-QuantVisionReady) {
        Write-AutostartLog "QuantVision is already ready; no duplicate process was started."
        exit 0
    }

    $mysqlService = Get-Service -Name "QuantVisionMySQL" -ErrorAction Stop
    if ($mysqlService.Status -ne [System.ServiceProcess.ServiceControllerStatus]::Running) {
        Write-AutostartLog "Starting QuantVisionMySQL Windows service."
        Start-Service -Name "QuantVisionMySQL"
    }

    $deadline = (Get-Date).AddSeconds($MySqlWaitSeconds)
    do {
        $mysqlService.Refresh()
        $mysqlReady = (
            $mysqlService.Status -eq [System.ServiceProcess.ServiceControllerStatus]::Running -and
            (Test-LocalTcpPort -HostName "127.0.0.1" -Port 3306)
        )
        if ($mysqlReady) {
            break
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    if (-not $mysqlReady) {
        throw "QuantVisionMySQL did not become ready within $MySqlWaitSeconds seconds."
    }

    if ($CheckOnly) {
        Write-AutostartLog "Autostart preflight passed (check-only mode)."
        exit 0
    }

    Write-AutostartLog "MySQL is ready; starting the supervised QuantVision backend."
    & $startScript backend
    $backendExitCode = $LASTEXITCODE
    Write-AutostartLog "QuantVision supervisor exited with code $backendExitCode."
    exit $backendExitCode
}
catch {
    Write-AutostartLog "Autostart failed: $($_.Exception.Message)"
    Write-Error $_
    exit 1
}
