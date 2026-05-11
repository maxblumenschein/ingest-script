# ---------------------------------------------------
# Cross-platform PowerShell launcher for ingest.py
# ---------------------------------------------------

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$IsWin = $env:OS -eq "Windows_NT"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# First-time setup check
if (-not (Test-Path "user_config.py")) {
    Write-Host ""
    Write-Host "  No user configuration found."
    Write-Host "  Run once to set up:  python onboard.py"
    Write-Host ""
    exit 1
}

$VenvDir = Join-Path $ScriptDir "venv"

if (-not (Test-Path $VenvDir)) {
    Write-Host "  Creating virtual environment…"
    python -m venv $VenvDir
}

if ($IsWin) {
    $PythonExe = Join-Path $VenvDir "Scripts\python.exe"
} else {
    $PythonExe = Join-Path $VenvDir "bin/python"
}

& $PythonExe -m pip install --quiet --upgrade pip
& $PythonExe -m pip install --quiet -r (Join-Path $ScriptDir "_internal\requirements.txt")

# Read author code from user_config.py
$AuthorCode = & $PythonExe -c "from user_config import AUTHOR_CODE; print(AUTHOR_CODE)" 2>$null

if (-not $AuthorCode) {
    Write-Host ""
    Write-Host "  AUTHOR_CODE missing from user_config.py"
    Write-Host "  Run: python onboard.py"
    Write-Host ""
    exit 1
}

$PythonScript = Join-Path $ScriptDir "_internal\ingest.py"
& $PythonExe $PythonScript $AuthorCode @args
