param(
    [string]$BackupDir = "",
    [int]$RetentionDays = 30,
    [int]$KeepMinimum = 7,
    [ValidateSet("full", "critical")]
    [string]$Scope = "full",
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
    "--scope", $Scope,
    "--timeout-seconds", $TimeoutSeconds
)
if ($BackupDir) {
    $arguments += @("--backup-dir", $BackupDir)
}
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "MySQL backup failed."
}
