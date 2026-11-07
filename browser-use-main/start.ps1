# =====================================================================
# Start Official Browser-Use Web UI (Port 7788)
# =====================================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting Official Browser-Use Web UI" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "Open your browser at: http://127.0.0.1:7788" -ForegroundColor Green
Write-Host "Press Ctrl+C to exit" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""

Push-Location "web-ui"
try {
    & ".\.venv\Scripts\python.exe" webui.py --ip 127.0.0.1 --port 7788
} finally {
    Pop-Location
}
