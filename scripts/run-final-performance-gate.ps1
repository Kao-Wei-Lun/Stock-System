param(
    [string]$BaseUrl = "http://127.0.0.1:8001",
    [switch]$IncludeLiveChecks,
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [string]$WorkingDirectory,
        [string]$FilePath,
        [string[]]$Arguments
    )
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw ("Command failed: {0} {1}" -f $FilePath, ($Arguments -join " "))
        }
    }
    finally {
        Pop-Location
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$frontendDir = Join-Path $repoRoot "frontend"
$python = Join-Path $repoRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = (Get-Command python -ErrorAction Stop).Source
}
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputPath = Join-Path $repoRoot "docs\performance\final-gate-$stamp.json"
}
$resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
[IO.Directory]::CreateDirectory((Split-Path -Parent $resolvedOutput)) | Out-Null

$steps = [System.Collections.Generic.List[object]]::new()
function Invoke-GateStep {
    param([string]$Name, [scriptblock]$Action)
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        & $Action
        $watch.Stop()
        $steps.Add([ordered]@{ name = $Name; passed = $true; elapsed_ms = [Math]::Round($watch.Elapsed.TotalMilliseconds, 2) })
    }
    catch {
        $watch.Stop()
        $steps.Add([ordered]@{ name = $Name; passed = $false; elapsed_ms = [Math]::Round($watch.Elapsed.TotalMilliseconds, 2) })
        throw
    }
}

Invoke-GateStep "backend_tests" {
    Invoke-Checked -WorkingDirectory $repoRoot -FilePath $python -Arguments @("-m", "pytest", "backend/tests", "-q")
}
Invoke-GateStep "frontend_tests" {
    Invoke-Checked -WorkingDirectory $frontendDir -FilePath "npm.cmd" -Arguments @("test", "--", "--run")
}
Invoke-GateStep "frontend_build" {
    Invoke-Checked -WorkingDirectory $frontendDir -FilePath "npm.cmd" -Arguments @("run", "build")
}
Invoke-GateStep "bundle_budget" {
    Invoke-Checked -WorkingDirectory $repoRoot -FilePath "node" -Arguments @(
        "scripts/check-frontend-bundle.mjs",
        "--enforce",
        "--max-static-gzip-bytes=190000",
        "--max-selected-gzip-bytes=190000",
        "--max-static-files=9"
    )
}
Invoke-GateStep "backtest_isolation" {
    Invoke-Checked -WorkingDirectory $repoRoot -FilePath $python -Arguments @(
        "scripts/benchmark-backtest-isolation.py",
        "--bars", "100000",
        "--executor-kind", "process",
        "--max-heartbeat-p95-ms", "30",
        "--max-heartbeat-max-ms", "100"
    )
}

if ($IncludeLiveChecks) {
    Invoke-GateStep "backend_ready" {
        $ready = Invoke-RestMethod -Uri "$($BaseUrl.TrimEnd('/'))/api/ready" -TimeoutSec 10
        if ($ready.status -ne "ready") { throw "Backend is not ready." }
    }
    Invoke-GateStep "terminal_http_benchmark" {
        & (Join-Path $PSScriptRoot "benchmark-terminal.ps1") -BaseUrl $BaseUrl -ColdRuns 3 -WarmRuns 5 | Out-Null
    }
    Invoke-GateStep "realtime_diagnostics" {
        & (Join-Path $PSScriptRoot "benchmark-realtime.ps1") `
            -DiagnosticsUrl "$($BaseUrl.TrimEnd('/'))/api/system/performance" `
            -Samples 10 -IntervalMs 500 | Out-Null
    }
    Invoke-GateStep "database_explain" {
        Invoke-Checked -WorkingDirectory $repoRoot -FilePath $python -Arguments @(
            "scripts/check-db-performance-plan.py",
            "--ticker", "*TMFF",
            "--interval", "1m",
            "--limit", "400"
        )
    }
}

$commit = (& git -C $repoRoot rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0) { $commit = $null }
$result = [ordered]@{
    schema_version = 1
    measured_at = (Get-Date).ToString("o")
    git_commit = $commit
    live_checks_included = [bool]$IncludeLiveChecks
    passed = -not ($steps | Where-Object { -not $_.passed })
    steps = $steps
}
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedOutput -Encoding UTF8
Write-Host "Final performance gate passed: $resolvedOutput" -ForegroundColor Green
