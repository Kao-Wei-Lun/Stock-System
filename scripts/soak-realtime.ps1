param(
    [string]$BaseUrl = "http://127.0.0.1:8001",
    [ValidateRange(1, 1440)]
    [int]$DurationMinutes = 60,
    [ValidateRange(0, 86400)]
    [int]$DurationSeconds = 0,
    [ValidateRange(1, 300)]
    [int]$SampleIntervalSeconds = 10,
    [string[]]$FuturesSymbols = @("*TMFF", "*TXFF"),
    [string]$StockSymbol = "2330.TW",
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NestedValue {
    param($Object, [string[]]$Path)
    $value = $Object
    foreach ($part in $Path) {
        if ($null -eq $value) { return $null }
        $property = $value.PSObject.Properties[$part]
        if ($null -eq $property) { return $null }
        $value = $property.Value
    }
    return $value
}

function Get-Maximum {
    param([object[]]$Values)
    $numbers = @($Values | Where-Object { $null -ne $_ } | ForEach-Object { [double]$_ })
    if ($numbers.Count -eq 0) { return $null }
    return [Math]::Round([double](($numbers | Measure-Object -Maximum).Maximum), 3)
}

function Get-CounterDelta {
    param([object[]]$Objects, [string]$CounterName)
    if ($Objects.Count -eq 0) { return $null }
    $first = Get-NestedValue $Objects[0] @("realtime", "counters", $CounterName)
    $last = Get-NestedValue $Objects[-1] @("realtime", "counters", $CounterName)
    if ($null -eq $first -or $null -eq $last) { return $null }
    return [Math]::Max(0, [long]$last - [long]$first)
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputPath = Join-Path $repoRoot "docs\performance\soak-$stamp.json"
}
$resolvedOutput = [IO.Path]::GetFullPath($OutputPath)
[IO.Directory]::CreateDirectory((Split-Path -Parent $resolvedOutput)) | Out-Null
$base = $BaseUrl.TrimEnd("/")
$requestedSeconds = if ($DurationSeconds -gt 0) { $DurationSeconds } else { $DurationMinutes * 60 }
$deadline = (Get-Date).AddSeconds($requestedSeconds)
$samples = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[object]]::new()

while ((Get-Date) -lt $deadline) {
    $sample = [ordered]@{
        collected_at = (Get-Date).ToString("o")
        health_ok = $false
        diagnostics = $null
        instruments = [System.Collections.Generic.List[object]]::new()
    }
    try {
        $health = Invoke-RestMethod -Uri "$base/api/health" -TimeoutSec 10
        $sample.health_ok = $health.status -eq "ok"
        $sample.diagnostics = Invoke-RestMethod -Uri "$base/api/system/performance" -TimeoutSec 10
        foreach ($symbol in $FuturesSymbols) {
            $encoded = [Uri]::EscapeDataString($symbol)
            $payload = Invoke-RestMethod `
                -Uri "$base/api/futopt/ohlc/$encoded`?period=1d&interval=1m&refresh=false&limit=400" `
                -TimeoutSec 20
            $rows = @($payload.data)
            $latest = if ($rows.Count) { $rows[-1].date } else { $null }
            $sample.instruments.Add([ordered]@{
                kind = "future"
                symbol = $symbol
                row_count = $rows.Count
                latest_timestamp = $latest
            })
        }
        $encodedStock = [Uri]::EscapeDataString($StockSymbol)
        $quote = Invoke-RestMethod -Uri "$base/api/quote/$encodedStock" -TimeoutSec 20
        $sample.instruments.Add([ordered]@{
            kind = "stock"
            symbol = $StockSymbol
            available = $null -ne $quote
        })
        $samples.Add($sample)
    }
    catch {
        $failures.Add([ordered]@{
            collected_at = (Get-Date).ToString("o")
            category = "sample_failed"
        })
    }
    $remainingMs = [Math]::Floor(($deadline - (Get-Date)).TotalMilliseconds)
    if ($remainingMs -gt 0) {
        $sleepMs = [Math]::Min($remainingMs, $SampleIntervalSeconds * 1000)
        Start-Sleep -Milliseconds $sleepMs
    }
}

$diagnostics = @($samples | ForEach-Object { $_.diagnostics } | Where-Object { $null -ne $_ })
$commit = (& git -C $repoRoot rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0) { $commit = $null }
$result = [ordered]@{
    schema_version = 1
    measured_at = (Get-Date).ToString("o")
    git_commit = $commit
    requested_duration_seconds = $requestedSeconds
    sample_interval_seconds = $SampleIntervalSeconds
    sample_count = $samples.Count
    failure_count = $failures.Count
    passed = $samples.Count -gt 0 -and $failures.Count -eq 0
    summary = [ordered]@{
        quote_pending_max = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("quote_persistence", "pending") })
        realtime_queue_depth_max = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("realtime", "queue_depth", "max_ms") })
        quote_queue_age_max_ms = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("realtime", "persistence_queue_age", "max_ms") })
        broadcast_p95_max_ms = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("realtime", "broadcast_latency", "p95_ms") })
        broadcast_max_ms = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("realtime", "broadcast_latency", "max_ms") })
        db_wait_p95_max_ms = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("database", "wait", "p95_ms") })
        db_query_p95_max_ms = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("database", "query", "p95_ms") })
        backtest_active_max = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("backtest_workload", "active") })
        asset_refresh_in_flight_max = Get-Maximum @($diagnostics | ForEach-Object { Get-NestedValue $_ @("asset_quote_refresh", "in_flight") })
        ingress_delta = Get-CounterDelta $diagnostics "ingress"
        broadcast_delta = Get-CounterDelta $diagnostics "broadcast"
        persistence_flush_delta = Get-CounterDelta $diagnostics "persistence_flush"
        coalesced_delta = Get-CounterDelta $diagnostics "coalesced"
        dropped_delta = Get-CounterDelta $diagnostics "dropped"
    }
    failures = $failures
    samples = $samples
}
$result | ConvertTo-Json -Depth 14 | Set-Content -LiteralPath $resolvedOutput -Encoding UTF8
Write-Host "Soak test complete: $resolvedOutput" -ForegroundColor Green
if (-not $result.passed) {
    throw "Soak test did not complete every sample successfully. Review the sanitized result file."
}
