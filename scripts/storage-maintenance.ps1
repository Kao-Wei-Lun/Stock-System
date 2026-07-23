param(
    [ValidateSet("archive-chip", "cleanup-chip", "summarize-sync", "cleanup-sync")]
    [string]$Action,

    [string]$CutoffDate = "",
    [switch]$Execute,
    [string]$BackupId = "",
    [string]$BackupDir = "",
    [int]$MaxRuntimeSeconds = 60,
    [int]$MaxGroups = 1,
    [int]$BatchSize = 5000,
    [int]$ArchiveGraceDays = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = "python"
}
$arguments = @(
    (Join-Path $projectRoot "backend\storage_maintenance.py"),
    $Action,
    "--max-runtime-seconds", $MaxRuntimeSeconds,
    "--max-groups", $MaxGroups,
    "--batch-size", $BatchSize,
    "--archive-grace-days", $ArchiveGraceDays
)
if ($CutoffDate) {
    $arguments += @("--cutoff-date", $CutoffDate)
}
if ($BackupId) {
    $arguments += @("--backup-id", $BackupId)
}
if ($BackupDir) {
    $arguments += @("--backup-dir", $BackupDir)
}
if ($Execute) {
    $arguments += "--execute"
}
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Storage maintenance command failed."
}
