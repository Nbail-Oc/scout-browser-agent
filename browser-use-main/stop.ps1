# =====================================================================
# Stop script for Browser-Use Web UI Services
# =====================================================================

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Stopping Browser-Use Services" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

function Stop-PortProcess([int]$Port, [string]$ServiceName) {
    Write-Host "[*] Checking for $ServiceName on port $Port..." -ForegroundColor Yellow
    
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        foreach ($conn in $connections) {
            $pidToKill = $conn.OwningProcess
            if ($pidToKill -gt 0) {
                try {
                    $proc = Get-Process -Id $pidToKill -ErrorAction SilentlyContinue
                    if ($proc) {
                        Write-Host "[*] Stopping $ServiceName (Process: $($proc.ProcessName), PID: $($pidToKill))..." -ForegroundColor Yellow
                        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
                        Write-Host "[OK] Stopped $ServiceName (PID $pidToKill)" -ForegroundColor Green
                    }
                } catch {
                    Write-Host "[!] Could not stop PID $($pidToKill)" -ForegroundColor Red
                }
            }
        }
    } else {
        Write-Host "[INFO] No process listening on port $Port ($ServiceName)" -ForegroundColor Gray
    }
}

# 1. Stop Official Web UI on port 7788
Stop-PortProcess -Port 7788 -ServiceName "Browser-Use Official Web UI"

# 2. Stop Gradio UI on port 7860
Stop-PortProcess -Port 7860 -ServiceName "Gradio UI"

# 3. Stop Streamlit UI on port 8501
Stop-PortProcess -Port 8501 -ServiceName "Streamlit UI"

# 4. Stop OpenCode on port 4096
Stop-PortProcess -Port 4096 -ServiceName "OpenCode Server"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "All services stopped." -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
