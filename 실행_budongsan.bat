@echo off
chcp 65001 > nul
setlocal

set "CURRENT_DIR=%~dp0"
set "PATH=%LOCALAPPDATA%\Python\bin;%LOCALAPPDATA%\Microsoft\WindowsApps;C:\Program Files\Git\cmd;%PATH%"

cd /d "%CURRENT_DIR%."
if errorlevel 1 (
    echo [ERROR] Failed to change directory to: %CURRENT_DIR%
    exit /b 1
)

if not exist "data" mkdir "data"
set "LOG_FILE=%CURRENT_DIR%data\last_run.log"

for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do set "NOW=%%i"
echo ======================================================== >> "%LOG_FILE%"
echo [RUN] Scraper started at %NOW% >> "%LOG_FILE%"

echo [RUN] Starting Real Estate Scraper...
python "%CURRENT_DIR%local_scraper.py" >> "%LOG_FILE%" 2>&1
if errorlevel 1 (
    echo [ERROR] Scraper failed at %NOW% >> "%LOG_FILE%"
    echo [ERROR] Scraper failed. Check data\last_run.log
    exit /b 1
)

echo [SYNC] Syncing with GitHub...
git add -A >> "%LOG_FILE%" 2>&1

git diff --cached --quiet
if %errorlevel%==0 (
    echo [INFO] No changes detected. >> "%LOG_FILE%"
    echo [INFO] No changes detected.
    exit /b 0
)

for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do set "NOW=%%i"
git commit -m "Auto-update listings: %NOW% (Local Scraper)" >> "%LOG_FILE%" 2>&1
git push origin main >> "%LOG_FILE%" 2>&1

echo [SUCCESS] Scraping and GitHub sync finished at %NOW% >> "%LOG_FILE%"
echo [SUCCESS] Scraping and GitHub sync finished successfully!
exit /b 0

