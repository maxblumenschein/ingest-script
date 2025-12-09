# ---------------------------------------------------
# Cross-platform PowerShell version of the Bash venv script
# ---------------------------------------------------

# --- Strict mode & UTF-8 output ---
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Get the directory of the script ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# --- Virtual environment directory ---
$VenvDir = Join-Path $ScriptDir "venv"

# --- Create virtual environment if it doesn't exist ---
if (-not (Test-Path $VenvDir)) {
    Write-Host "Creating virtual environment..."
    python -m venv $VenvDir
}

# --- Activate virtual environment ---
if ($IsWindows) {
    $ActivateScript = Join-Path $VenvDir "Scripts\Activate.ps1"
} else {
    $ActivateScript = Join-Path $VenvDir "bin/activate"
}

if (-not (Test-Path $ActivateScript)) {
    Write-Host "Error: Cannot find activation script at $ActivateScript" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
if ($IsWindows) {
    . $ActivateScript
} else {
    # For Unix/macOS, source the activate script in the current session
    bash -c "source '$ActivateScript'"
}

# --- Upgrade pip inside the venv ---
Write-Host "Upgrading pip..."
python -m pip install --upgrade pip

# --- Install required Python packages ---
Write-Host "Installing required packages..."
python -m pip install Pillow

# --- Run the Python script inside the venv ---
$PythonScript = Join-Path $ScriptDir "ingest.py"
if (-not (Test-Path $PythonScript)) {
    Write-Host "Error: $PythonScript not found!" -ForegroundColor Red
    exit 1
}

Write-Host "Running ingest.py..."
python $PythonScript

# --- Deactivate virtual environment ---
if ($IsWindows) {
    deactivate 2>$null
} else {
    bash -c "deactivate"
}

Write-Host "Execution completed."
