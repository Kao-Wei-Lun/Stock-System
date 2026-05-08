$WhatIfMode = $false
foreach ($Arg in $args) {
    if ($Arg -eq "-WhatIf" -or $Arg -eq "--what-if") {
        $WhatIfMode = $true
    }
}

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $ProjectRoot "log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$TaipeiZone = [System.TimeZoneInfo]::FindSystemTimeZoneById("Taipei Standard Time")
$ReportDate = [System.TimeZoneInfo]::ConvertTimeFromUtc([datetime]::UtcNow, $TaipeiZone).ToString("yyyy-MM-dd")
$RunLog = Join-Path $LogDir "ai_daily_tw_report_$ReportDate.task.log"
$Python = (Get-Command python.exe -ErrorAction Stop).Source

Set-Location $ProjectRoot

$Arguments = @(
    "scripts\send_daily_tw_report_email.py",
    "--date", $ReportDate,
    "--to", "weilunkao1013@gmail.com,heas54321@gmail.com,poyen.justin@gmail.com",
    "--out", "log\ai_daily_tw_report_$ReportDate.md",
    "--html-out", "log\ai_daily_tw_report_$ReportDate.html",
    "--eml-out", "log\ai_daily_tw_report_$ReportDate.eml"
)

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] Starting daily TW report email" | Out-File -FilePath $RunLog -Encoding utf8
"ProjectRoot=$ProjectRoot" | Out-File -FilePath $RunLog -Encoding utf8 -Append
"Python=$Python" | Out-File -FilePath $RunLog -Encoding utf8 -Append
"ReportDate=$ReportDate" | Out-File -FilePath $RunLog -Encoding utf8 -Append

if ($WhatIfMode) {
    "WhatIf=true" | Out-File -FilePath $RunLog -Encoding utf8 -Append
    "Command=$Python $($Arguments -join ' ')" | Out-File -FilePath $RunLog -Encoding utf8 -Append
    Write-Output "WhatIf OK. Command would be: $Python $($Arguments -join ' ')"
    exit 0
}

& $Python @Arguments 2>&1 | Out-File -FilePath $RunLog -Encoding utf8 -Append
$ExitCode = $LASTEXITCODE

"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ExitCode=$ExitCode" | Out-File -FilePath $RunLog -Encoding utf8 -Append

if ($ExitCode -ne 0) {
    throw "Daily TW report email failed with exit code $ExitCode. See $RunLog"
}
