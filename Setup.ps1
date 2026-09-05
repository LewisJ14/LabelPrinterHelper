$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $project ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    python -m venv (Join-Path $project ".venv")
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Could not update pip." }
& $python -m pip install -r (Join-Path $project "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Could not install the required packages." }
Write-Host "Astro Label Printer is ready. Open 'Start Label Printer.bat' to run it."
