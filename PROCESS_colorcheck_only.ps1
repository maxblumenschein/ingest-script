# Color accuracy check only (test phase) — reads the images in the source
# folder and reports dE / white balance / exposure. Nothing is moved,
# renamed, or written into the image files (only a log in SRC/__log__).
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
& (Join-Path $ScriptDir "PROCESS.ps1") --colorcheck-only @args
