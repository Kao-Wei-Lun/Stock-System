param(
    [Parameter(Mandatory = $true)]
    [string]$Manifest,

    [string]$TargetDatabase = "",
    [switch]$KeepTarget
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
    "drill", $Manifest
)
if ($TargetDatabase) {
    $arguments += @("--target-database", $TargetDatabase)
}
if ($KeepTarget) {
    $arguments += "--keep-target"
}
& $pythonPath @arguments
if ($LASTEXITCODE -ne 0) {
    throw "MySQL restore drill failed."
}
