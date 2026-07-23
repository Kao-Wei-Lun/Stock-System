param(
    [ValidateSet("audit", "dry-run")]
    [string]$Command = "audit",

    [string]$Today = "",
    [int]$MaxRuntimeSeconds = 300,
    [string]$BackupDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonPath = Join-Path $projectRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    $pythonPath = "python"
}
$arguments = @(
    (Join-Path $projectRoot "backend\storage_lifecycle.py"),
    $Command,
    "--max-runtime-seconds", $MaxRuntimeSeconds
)
if ($Today) {
    $arguments += @("--today", $Today)
}
if ($BackupDir) {
    $arguments += @("--backup-dir", $BackupDir)
}
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Storage lifecycle command failed."
}
