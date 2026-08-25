@echo off
chcp 65001 > nul
setlocal

set "CURRENT_DIR=%~dp0"
set "PATH=C:\Program Files\Git\cmd;%PATH%"

cd /d "%CURRENT_DIR%."
if errorlevel 1 (
    echo [ERROR] Failed to change directory to: %CURRENT_DIR%
    exit /b 1
)

echo [RUN] Starting Real Estate Scraper...
python "%CURRENT_DIR%local_scraper.py"
if errorlevel 1 (
    echo [ERROR] Scraper failed.
    exit /b 1
)

echo [SYNC] Syncing with GitHub...
git add data/results.json data/history.json data/last_run.txt

git diff --cached --quiet
if %errorlevel%==0 (
    echo [INFO] No changes detected.
    exit /b 0
)

for /f "usebackq tokens=*" %%i in (powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'") do set "NOW=%%i"
git commit -m "Auto-update listings: %NOW% (Local Scraper)"
git pull --rebase origin main
git push origin main

echo [SUCCESS] Scraping and GitHub sync finished successfully!
exit /b 0
