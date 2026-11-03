# ---------------------------------------------------
# Cross-platform PowerShell launcher for process.py
# ---------------------------------------------------

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$IsWin = $env:OS -eq "Windows_NT"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# First-time setup check
if (-not (Test-Path "config.json") -and -not (Test-Path "user_config.py")) {
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
& $PythonExe -m pip install --quiet -r (Join-Path (Join-Path $ScriptDir "_internal") "requirements.txt")

# process.py reads the paths from config.json and asks who is working
# (Enter = last user).
$PythonScript = (Join-Path (Join-Path $ScriptDir "_internal") "process.py")
& $PythonExe $PythonScript @args
