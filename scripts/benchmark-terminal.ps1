param(
    [string]$BaseUrl = "http://127.0.0.1:8001",
    [string]$Symbol = "*TMFF",
    [string]$Period = "1d",
    [string]$Interval = "1m",
    [ValidateRange(1, 5000)]
    [int]$Limit = 400,
    [ValidateRange(0, 2000)]
    [int]$Warmup = 250,
    [ValidateRange(1, 20)]
    [int]$ColdRuns = 3,
    [ValidateRange(1, 50)]
    [int]$WarmRuns = 5,
    [ValidateRange(1, 120)]
    [int]$TimeoutSeconds = 30,
    [string]$FrontendMetricsPath = "",
    [string]$OutputPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Net.Http

function Get-Percentile {
    param([double[]]$Values, [double]$Percentile)

    if ($Values.Count -eq 0) { return $null }
    $sorted = @($Values | Sort-Object)
    $index = [Math]::Max([Math]::Ceiling($Percentile * $sorted.Count) - 1, 0)
    return [Math]::Round([double]$sorted[$index], 2)
}

function Get-Median {
    param([double[]]$Values)

    if ($Values.Count -eq 0) { return $null }
    $sorted = @($Values | Sort-Object)
    $middle = [Math]::Floor($sorted.Count / 2)
    if (($sorted.Count % 2) -eq 0) {
        return [Math]::Round(([double]$sorted[$middle - 1] + [double]$sorted[$middle]) / 2, 2)
    }
    return [Math]::Round([double]$sorted[$middle], 2)
}

function Get-HeaderValue {
    param($Response, [string]$Name)

    try { return (($Response.Headers.GetValues($Name) | Select-Object -First 1) -as [string]) }
    catch {
        try { return (($Response.Content.Headers.GetValues($Name) | Select-Object -First 1) -as [string]) }
        catch { return $null }
    }
}

function New-HttpClient {
    param([bool]$ConnectionClose)

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $client = [System.Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    $client.DefaultRequestHeaders.Accept.ParseAdd("application/json")
    if ($ConnectionClose) {
        $client.DefaultRequestHeaders.ConnectionClose = $true
    }
    return $client
}

function Invoke-BenchmarkRequest {
    param(
        [System.Net.Http.HttpClient]$Client,
        [string]$Url,
        [string]$RunType,
        [int]$RunNumber
    )

    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $response = $null
    try {
        $response = $Client.SendAsync(
            [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $Url),
            [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
        ).GetAwaiter().GetResult()
        $ttfbMs = $watch.Elapsed.TotalMilliseconds
        $bytes = $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
        $watch.Stop()
        $status = [int]$response.StatusCode
        if (-not $response.IsSuccessStatusCode) {
            throw "HTTP $status"
        }

        $dataCount = 0
        try {
            $json = [Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json
            if ($null -ne $json.data) { $dataCount = @($json.data).Count }
        }
        catch {
            throw "Response was not valid benchmark JSON"
        }

        return [ordered]@{
            run_type = $RunType
            run_number = $RunNumber
            status = $status
            ttfb_ms = [Math]::Round($ttfbMs, 2)
            total_ms = [Math]::Round($watch.Elapsed.TotalMilliseconds, 2)
            response_bytes = $bytes.Length
            data_count = $dataCount
            content_encoding = Get-HeaderValue -Response $response -Name "Content-Encoding"
            server_timing = Get-HeaderValue -Response $response -Name "Server-Timing"
            request_id = Get-HeaderValue -Response $response -Name "X-Request-ID"
        }
    }
    catch {
        throw "Benchmark request failed ($RunType run $RunNumber): $($_.Exception.Message)"
    }
    finally {
        if ($null -ne $response) { $response.Dispose() }
    }
}

function Get-RunSummary {
    param([object[]]$Runs)

    $ttfb = @($Runs | ForEach-Object { [double]$_.ttfb_ms })
    $total = @($Runs | ForEach-Object { [double]$_.total_ms })
    $bytes = @($Runs | ForEach-Object { [double]$_.response_bytes })
    return [ordered]@{
        count = $Runs.Count
        ttfb_ms = [ordered]@{ median = Get-Median $ttfb; p95 = Get-Percentile $ttfb 0.95; max = [Math]::Round(($ttfb | Measure-Object -Maximum).Maximum, 2) }
        total_ms = [ordered]@{ median = Get-Median $total; p95 = Get-Percentile $total 0.95; max = [Math]::Round(($total | Measure-Object -Maximum).Maximum, 2) }
        response_bytes = [ordered]@{ median = Get-Median $bytes; p95 = Get-Percentile $bytes 0.95; max = [Math]::Round(($bytes | Measure-Object -Maximum).Maximum, 2) }
    }
}

function Get-FrontendMetrics {
    $allowedMarks = @("qv:app-mounted", "qv:terminal-visible", "qv:chart-data-ready", "qv:chart-painted")
    $allowedRuntime = @("long_tasks", "realtime_transport", "realtime_paint")
    $metrics = [ordered]@{ source = "not_collected"; marks = [ordered]@{}; runtime = [ordered]@{} }
    foreach ($name in $allowedMarks) { $metrics.marks[$name] = $null }
    foreach ($name in $allowedRuntime) { $metrics.runtime[$name] = $null }
    if ([string]::IsNullOrWhiteSpace($FrontendMetricsPath)) { return $metrics }
    if (-not (Test-Path -LiteralPath $FrontendMetricsPath)) { throw "Frontend metrics file not found: $FrontendMetricsPath" }

    $source = Get-Content -LiteralPath $FrontendMetricsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($name in $allowedMarks) {
        $entry = $source.marks.$name
        if ($null -ne $entry -and $null -ne $entry.start_time_ms) {
            $metrics.marks[$name] = [ordered]@{ start_time_ms = [Math]::Round([double]$entry.start_time_ms, 2) }
        }
    }
    $runtimeProperty = $source.PSObject.Properties["runtime"]
    if ($null -ne $runtimeProperty) {
        foreach ($name in $allowedRuntime) {
            $entryProperty = $runtimeProperty.Value.PSObject.Properties[$name]
            if ($null -ne $entryProperty) {
                $entry = $entryProperty.Value
                $metrics.runtime[$name] = [ordered]@{
                    count = [int]($entry.count)
                    p50_ms = $entry.p50_ms
                    p95_ms = $entry.p95_ms
                    max_ms = $entry.max_ms
                }
            }
        }
    }
    $metrics.source = "browser_export"
    return $metrics
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputPath = Join-Path $repoRoot "docs\performance\terminal-$stamp.json"
}
$outputFullPath = [IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $outputFullPath
[IO.Directory]::CreateDirectory($outputDirectory) | Out-Null

$base = $BaseUrl.TrimEnd("/")
$encodedSymbol = [Uri]::EscapeDataString($Symbol)
$encodedPeriod = [Uri]::EscapeDataString($Period)
$encodedInterval = [Uri]::EscapeDataString($Interval)
$url = "$base/api/futopt/ohlc/$encodedSymbol`?period=$encodedPeriod&interval=$encodedInterval&refresh=false&limit=$Limit&warmup=$Warmup"

$cold = @()
for ($index = 1; $index -le $ColdRuns; $index++) {
    $client = New-HttpClient -ConnectionClose $true
    try { $cold += Invoke-BenchmarkRequest -Client $client -Url $url -RunType "cold" -RunNumber $index }
    finally { $client.Dispose() }
}

$warm = @()
$warmClient = New-HttpClient -ConnectionClose $false
try {
    for ($index = 1; $index -le $WarmRuns; $index++) {
        $warm += Invoke-BenchmarkRequest -Client $warmClient -Url $url -RunType "warm" -RunNumber $index
    }
}
finally { $warmClient.Dispose() }

$commit = (& git -C $repoRoot rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0) { $commit = $null }
$result = [ordered]@{
    schema_version = 1
    measured_at = (Get-Date).ToString("o")
    git_commit = $commit
    request = [ordered]@{ symbol = $Symbol; period = $Period; interval = $Interval; limit = $Limit; warmup = $Warmup; url = $url }
    runs = [ordered]@{ cold = $cold; warm = $warm }
    summary = [ordered]@{ cold = Get-RunSummary $cold; warm = Get-RunSummary $warm }
    frontend = Get-FrontendMetrics
}

$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outputFullPath -Encoding UTF8
Write-Host "Benchmark complete: $outputFullPath" -ForegroundColor Green
Write-Output ($result | ConvertTo-Json -Depth 8)
