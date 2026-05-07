$UI_PORT = "3000"
if (Test-Path ".env") {
    $line = Get-Content .env | Where-Object { $_ -match "^UI_PORT=" }
    if ($line) { $UI_PORT = ($line -replace "^UI_PORT=", "").Trim() }
}

Write-Host "Stopping any existing containers..."
docker compose down 2>$null

# Check if port is still in use by another process
$portLines = netstat -ano | Select-String ":$UI_PORT\s" | Where-Object { $_ -match "ABH.REN|LISTEN" }
if ($portLines) {
    $blockingPid = ($portLines[0] -split '\s+')[-1]
    $processName = (Get-Process -Id $blockingPid -ErrorAction SilentlyContinue).Name

    Write-Host ""
    Write-Host "ERROR: Port $UI_PORT is already in use — cannot start UI container." -ForegroundColor Red
    if ($processName) {
        Write-Host "  Blocking process: $processName (PID $blockingPid)" -ForegroundColor Yellow
    } else {
        Write-Host "  Blocking PID: $blockingPid" -ForegroundColor Yellow
    }
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "  1. Kill the blocking process (if safe):"
    Write-Host "       Stop-Process -Id $blockingPid -Force"
    Write-Host "       .\start.ps1"
    Write-Host ""
    Write-Host "  2. Use a different port — edit UI_PORT in .env, then re-run .\start.ps1"
    Write-Host ""
    Write-Host "  3. If this is a Hyper-V/WinNAT port reservation (run as Admin):"
    Write-Host "       net stop winnat"
    Write-Host "       .\start.ps1"
    Write-Host "       net start winnat"
    exit 1
}

Write-Host "Starting AI Factory (UI on port $UI_PORT)..."
docker compose up -d
