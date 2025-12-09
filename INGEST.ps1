# ---------------------------------------------------
# Cross-platform PowerShell version of the Bash venv script
# ---------------------------------------------------

# --- Strict mode & UTF-8 output ---
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Detect platform ---
$IsWindows = $env:OS -eq "Windows_NT"

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
    if (-not (Test-Path $ActivateScript)) {
        Write-Host "Error: Cannot find activation script at $ActivateScript" -ForegroundColor Red
        exit 1
    }

    # Dot-source to activate in current session
    . $ActivateScript
} else {
    $ActivateScript = Join-Path $VenvDir "bin/activate"
    if (-not (Test-Path $ActivateScript)) {
        Write-Host "Error: Cannot find activation script at $ActivateScript" -ForegroundColor Red
        exit 1
    }

    # For Unix/macOS: run the Python commands using the venv python directly
    $PythonExe = Join-Path $VenvDir "bin/python"
}

# --- Determine which Python to use ---
if ($IsWindows) {
    $PythonExe = Join-Path $VenvDir "Scripts\python.exe"
}

# --- Upgrade pip inside the venv ---
Write-Host "Upgrading pip..."
& $PythonExe -m pip install --upgrade pip

# --- Install required Python packages ---
Write-Host "Installing required packages..."
& $PythonExe -m pip install Pillow

# --- Run the Python script inside the venv ---
$PythonScript = Join-Path $ScriptDir "ingest.py"
if (-not (Test-Path $PythonScript)) {
    Write-Host "Error: $PythonScript not found!" -ForegroundColor Red
    exit 1
}

Write-Host "Running ingest.py..."
# Pass any arguments after the script
& $PythonExe $PythonScript "SCJ"

Write-Host "Execution completed."
