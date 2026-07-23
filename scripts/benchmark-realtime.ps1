param(
    [string]$DiagnosticsUrl = "http://127.0.0.1:8001/api/system/performance",
    [int]$Samples = 10,
    [int]$IntervalMs = 500,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
if ($Samples -lt 1 -or $Samples -gt 600) {
    throw "Samples must be between 1 and 600."
}
if ($IntervalMs -lt 50 -or $IntervalMs -gt 60000) {
    throw "IntervalMs must be between 50 and 60000."
}

$snapshots = @()
for ($index = 0; $index -lt $Samples; $index += 1) {
    $started = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-RestMethod -Uri $DiagnosticsUrl -Method Get -TimeoutSec 10
    } catch {
        throw "Realtime diagnostics unavailable at $DiagnosticsUrl`: $($_.Exception.Message)"
    }
    $started.Stop()
    $snapshots += [ordered]@{
        sample = $index + 1
        request_ms = [Math]::Round($started.Elapsed.TotalMilliseconds, 2)
        collected_at = (Get-Date).ToString("o")
        database = $response.database
        realtime = $response.realtime
        quote_persistence = $response.quote_persistence
        backtest_workload = $response.backtest_workload
        asset_quote_refresh = $response.asset_quote_refresh
    }
    if ($index -lt $Samples - 1) {
        Start-Sleep -Milliseconds $IntervalMs
    }
}

$gitCommit = $null
try {
    $gitCommit = (git rev-parse HEAD 2>$null).Trim()
} catch {
    $gitCommit = $null
}

$result = [ordered]@{
    schema_version = 1
    measured_at = (Get-Date).ToString("o")
    git_commit = $gitCommit
    diagnostics_url = $DiagnosticsUrl
    sample_count = $snapshots.Count
    snapshots = $snapshots
}
$json = $result | ConvertTo-Json -Depth 12
if ($OutputPath) {
    $resolved = [System.IO.Path]::GetFullPath($OutputPath)
    [System.IO.File]::WriteAllText($resolved, $json, [System.Text.UTF8Encoding]::new($false))
}
$json
