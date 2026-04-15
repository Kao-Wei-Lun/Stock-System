param(
    [string]$Start = "",
    [string]$End = "",
    [int]$Limit = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot "venv\Scripts\python.exe"
$script = Join-Path $repoRoot "scripts\backfill_taifex_structured.py"

if (-not (Test-Path $python)) {
    throw "Virtual environment python not found at $python"
}

$arguments = @($script)
if ($Start) {
    $arguments += @("--start", $Start)
}
if ($End) {
    $arguments += @("--end", $End)
}
if ($Limit -gt 0) {
    $arguments += @("--limit", "$Limit")
}

Push-Location $repoRoot
try {
    & $python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
