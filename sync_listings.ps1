# Real Estate Scraper & Sync Script
# Run this script to update data and push to GitHub Pages

Write-Host "[INFO] Starting Real Estate Scraper..." -ForegroundColor Cyan

# 1. Run Scraper
# Using the python from the backend venv if available, otherwise global python
$pythonPath = "..\backend\venv\Scripts\python.exe"
if (-Not (Test-Path $pythonPath)) {
    $pythonPath = "python"
}

& $pythonPath local_scraper.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Scraper failed. Skipping Sync." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "[SUCCESS] Scraper finished successfully." -ForegroundColor Green

# 2. Git Sync
Write-Host "[INFO] Syncing to GitHub..." -ForegroundColor Cyan

# Ensure we are in a git repo
if (-Not (Test-Path .git)) {
    Write-Host "[WARNING] Not a git repository. Skipping push." -ForegroundColor Yellow
    exit 0
}

git add data/results.json data/history.json
$currentTime = Get-Date -Format "yyyy-MM-dd HH:mm"
git commit -m "Auto-update listings: $currentTime (Local Run)"

# 3. Push to GitHub
git push

# Check for push success
if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] Sync complete! Check the dashboard on your phone." -ForegroundColor Magenta
} else {
    Write-Host "[WARNING] Git push failed. Check your credentials or internet." -ForegroundColor Yellow
}

Write-Host ""
Write-Host ">>> ALL DONE!" -ForegroundColor Green
Read-Host "Press Enter to close..."
