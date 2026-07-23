param(
    [Parameter(Mandatory = $true)]
    [string]$Manifest,

    [Parameter(Mandatory = $true)]
    [string]$TargetDatabase,

    [switch]$AllowExistingTarget,
    [switch]$AllowSourceOverwrite,
    [switch]$DryRun,
    [switch]$VerifyRestore
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
    "restore", $Manifest,
    "--target-database", $TargetDatabase
)
if ($AllowExistingTarget) { $arguments += "--allow-existing-target" }
if ($AllowSourceOverwrite) { $arguments += "--allow-source-overwrite" }
if ($DryRun) { $arguments += "--dry-run" }
if ($VerifyRestore) { $arguments += "--verify-restore" }
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "MySQL restore failed."
}
