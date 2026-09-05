[CmdletBinding()]
param(
    [switch]$SkipInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$buildDir = Join-Path $repoRoot "build"
$distDir = Join-Path $repoRoot "dist"
$output = Join-Path $distDir "AstroLabelPrinter.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Run Setup.ps1 before building."
}
if (-not $SkipInstall) {
    & $python -m pip install -r (Join-Path $repoRoot "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Could not install runtime dependencies." }
    & $python -m pip install "pyinstaller==6.16.0"
    if ($LASTEXITCODE -ne 0) { throw "Could not install PyInstaller." }
}

$running = Get-Process -Name "AstroLabelPrinter", "Astro Label Printer" -ErrorAction SilentlyContinue | Where-Object {
    try { $_.Path -and ([IO.Path]::GetFullPath($_.Path) -eq [IO.Path]::GetFullPath($output)) }
    catch { $false }
}
if ($running) {
    $running | Stop-Process -Force
    Start-Sleep -Milliseconds 500
}
if (Test-Path -LiteralPath $buildDir) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}
if (Test-Path -LiteralPath $output) {
    Remove-Item -LiteralPath $output -Force
}

Push-Location $repoRoot
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "AstroLabelPrinter" `
        --collect-all "ttkbootstrap" `
        --hidden-import "win32timezone" `
        "main.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $output)) {
    throw "The expected executable was not created at $output"
}
Write-Host "Build completed: $output" -ForegroundColor Green
