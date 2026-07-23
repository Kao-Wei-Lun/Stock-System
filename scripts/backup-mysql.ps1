param(
    [string]$BackupDir = "",
    [int]$RetentionDays = 30,
    [int]$KeepMinimum = 7,
    [int]$KeepMinimumPerScope = 1,
    [long]$MaxTotalBytes = 0,
    [ValidateSet("full", "critical", "market-history")]
    [string]$Scope = "full",
    [string]$StartDate = "",
    [string]$EndDate = "",
    [ValidateSet("gzip", "none")]
    [string]$Compression = "gzip",
    [int]$TimeoutSeconds = 3600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = "python"
}
$arguments = @(
    (Join-Path $projectRoot "backend\mysql_backup.py"),
    "backup",
    "--retention-days", $RetentionDays,
    "--keep-minimum", $KeepMinimum,
    "--keep-minimum-per-scope", $KeepMinimumPerScope,
    "--scope", $Scope,
    "--compression", $Compression,
    "--timeout-seconds", $TimeoutSeconds
)
if ($BackupDir) {
    $arguments += @("--backup-dir", $BackupDir)
}
if ($MaxTotalBytes -gt 0) {
    $arguments += @("--max-total-bytes", $MaxTotalBytes)
}
if ($StartDate) {
    $arguments += @("--start-date", $StartDate)
}
if ($EndDate) {
    $arguments += @("--end-date", $EndDate)
}
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "MySQL backup failed."
}
