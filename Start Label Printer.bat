@echo off
setlocal
cd /d "%~dp0"
if exist "dist\AstroLabelPrinter.exe" (
    start "Astro Label Printer" "dist\AstroLabelPrinter.exe"
    exit /b 0
)
if not exist ".venv\Scripts\pythonw.exe" (
    echo Run Setup.ps1 and Build.ps1 first.
    pause
    exit /b 1
)
start "Astro Label Printer" ".venv\Scripts\pythonw.exe" "main.py"
