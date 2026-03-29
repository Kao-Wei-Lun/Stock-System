param(
    [Parameter(Mandatory = $true)]
    [string]$Phase,

    [string]$CommitMessage = "",

    [switch]$AutoCommit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$phaseOrder = @(
    "phase-0",
    "phase-1",
    "phase-2",
    "phase-3",
    "phase-4",
    "phase-5",
    "phase-6",
    "phase-7",
    "phase-8"
)

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ("[STEP] {0}" -f $Message) -ForegroundColor Cyan
}

function Invoke-Step {
    param(
        [string]$Message,
        [scriptblock]$Action
    )

    Write-Step $Message
    & $Action
}

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-VenvPython {
    param([string]$RepoRoot)

    $venvPython = Join-Path $RepoRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return $venvPython
    }
    return $null
}

function Get-FrontendScripts {
    param([string]$RepoRoot)

    $packagePath = Join-Path $RepoRoot "frontend\package.json"
    if (-not (Test-Path $packagePath)) {
        return @{}
    }

    $packageJson = Get-Content $packagePath -Raw | ConvertFrom-Json
    if ($null -eq $packageJson.scripts) {
        return @{}
    }

    $scripts = @{}
    $packageJson.scripts.PSObject.Properties | ForEach-Object {
        $scripts[$_.Name] = $_.Value
    }
    return $scripts
}

function Invoke-CheckedCommand {
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

function Get-NextPhase {
    param([string]$CurrentPhase)

    $index = [Array]::IndexOf($phaseOrder, $CurrentPhase)
    if ($index -lt 0) {
        return $null
    }
    if ($index -ge ($phaseOrder.Count - 1)) {
        return $null
    }
    return $phaseOrder[$index + 1]
}

$repoRoot = Get-RepoRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$venvPython = Get-VenvPython -RepoRoot $repoRoot
$frontendScripts = Get-FrontendScripts -RepoRoot $repoRoot

Write-Host ("[INFO] Repo root: {0}" -f $repoRoot) -ForegroundColor Green
Write-Host ("[INFO] Phase gate: {0}" -f $Phase) -ForegroundColor Green

if (-not (Test-Path $backendDir)) {
    throw "Backend directory not found."
}

if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found."
}

if (-not $venvPython) {
    throw "Virtual environment python not found at venv\Scripts\python.exe"
}

Invoke-Step "Backend compile check" {
    Invoke-CheckedCommand -WorkingDirectory $repoRoot -FilePath $venvPython -Arguments @("-m", "compileall", "backend")
}

Invoke-Step "Backend test suite" {
    $pytestArgs = @("-m", "pytest")
    Invoke-CheckedCommand -WorkingDirectory $repoRoot -FilePath $venvPython -Arguments $pytestArgs
}

Invoke-Step "Frontend production build" {
    Invoke-CheckedCommand -WorkingDirectory $frontendDir -FilePath "npm.cmd" -Arguments @("run", "build")
}

if ($frontendScripts.ContainsKey("test")) {
    Invoke-Step "Frontend test suite" {
        Invoke-CheckedCommand -WorkingDirectory $frontendDir -FilePath "npm.cmd" -Arguments @("run", "test")
    }
}
else {
    Write-Host "[WARN] frontend/package.json does not define a test script. Skipping frontend tests." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[INFO] All phase gate checks passed." -ForegroundColor Green

if ($AutoCommit) {
    $finalCommitMessage = $CommitMessage
    if ([string]::IsNullOrWhiteSpace($finalCommitMessage)) {
        $finalCommitMessage = "${Phase}: pass delivery gate"
    }

    Invoke-Step "Git status" {
        Invoke-CheckedCommand -WorkingDirectory $repoRoot -FilePath "git" -Arguments @("status", "--short")
    }

    Invoke-Step "Git add" {
        Invoke-CheckedCommand -WorkingDirectory $repoRoot -FilePath "git" -Arguments @("add", "-A")
    }

    try {
        Invoke-Step "Git commit" {
            Invoke-CheckedCommand -WorkingDirectory $repoRoot -FilePath "git" -Arguments @("commit", "-m", $finalCommitMessage)
        }
    }
    catch {
        Write-Host "[WARN] Git commit failed. This usually means there are no staged changes to commit." -ForegroundColor Yellow
        Write-Host ("[WARN] Detail: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
    }
}

$nextPhase = Get-NextPhase -CurrentPhase $Phase
if ($nextPhase) {
    Write-Host ""
    Write-Host ("[NEXT] Proceed to {0}" -f $nextPhase) -ForegroundColor Cyan
}
else {
    Write-Host ""
    Write-Host "[NEXT] No next phase defined. Delivery plan is complete." -ForegroundColor Cyan
}
