#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [ValidateSet("Install", "Remove")]
    [string]$Action = "Install",

    [switch]$StartNow
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$taskName = "QuantVision Auto Start"
$projectRoot = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run-windows-autostart.ps1"

if ($Action -eq "Remove") {
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($null -ne $existingTask) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Removed scheduled task: $taskName"
    }
    else {
        Write-Host "Scheduled task does not exist: $taskName"
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "Autostart runner does not exist: $runner"
}

$windowsPowerShell = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$taskArguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}"' -f $runner

$taskAction = New-ScheduledTaskAction `
    -Execute $windowsPowerShell `
    -Argument $taskArguments `
    -WorkingDirectory $projectRoot
$taskTrigger = New-ScheduledTaskTrigger -AtStartup
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest
$taskSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

$task = New-ScheduledTask `
    -Action $taskAction `
    -Trigger $taskTrigger `
    -Principal $taskPrincipal `
    -Settings $taskSettings `
    -Description "Starts QuantVision after Windows and QuantVisionMySQL are ready."

Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
Write-Host "Installed scheduled task: $taskName"
Write-Host "Trigger: Windows startup"
Write-Host "Account: SYSTEM"

if ($StartNow) {
    Start-ScheduledTask -TaskName $taskName
    Write-Host "Started scheduled task for validation."
}
