# Windows PowerShell launcher for BugSleuth development servers
$ErrorActionPreference = "Stop"

$venvPython = ".venv\Scripts\python.exe"
if (-Not (Test-Path $venvPython)) {
    Write-Host "Virtual environment not found at $venvPython. Using system python..." -ForegroundColor Yellow
    $venvPython = "python"
}

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   🔍 BugSleuth: AI Bug Detection & RCA Agent Dev Server        " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  Starting FastAPI on http://127.0.0.1:8000 ..." -ForegroundColor Green
Write-Host "  Starting Streamlit on http://127.0.0.1:8501 ..." -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop both processes.`n" -ForegroundColor Gray

& $venvPython scripts\run_dev.py
