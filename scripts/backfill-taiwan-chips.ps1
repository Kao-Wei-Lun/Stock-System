param(
    [string]$Start = "2012-05-02",
    [string]$End = "",
    [ValidateSet("all", "twse", "tpex")]
    [string]$Sources = "all",
    [double]$Sleep = 0.15,
    [switch]$ForceRefresh,
    [switch]$IncludeWeekends,
    [int]$MaxDays = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot "venv\Scripts\python.exe"
$script = Join-Path $repoRoot "scripts\backfill_taiwan_chips.py"

if (-not (Test-Path $python)) {
    throw "Virtual environment python not found at $python"
}

if (-not $End) {
    $End = Get-Date -Format "yyyy-MM-dd"
}

$arguments = @(
    $script,
    "--start", $Start,
    "--end", $End,
    "--sources", $Sources,
    "--sleep", $Sleep.ToString([System.Globalization.CultureInfo]::InvariantCulture)
)

if ($ForceRefresh) {
    $arguments += "--force-refresh"
}
if ($IncludeWeekends) {
    $arguments += "--include-weekends"
}
if ($MaxDays -gt 0) {
    $arguments += @("--max-days", "$MaxDays")
}

Push-Location $repoRoot
try {
    & $python @arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
