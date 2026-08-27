@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

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

echo [NET] Waiting for network connection...
for /L %%w in (1,1,10) do (
    ping -n 1 github.com > nul 2>&1
    if !errorlevel!==0 (
        echo [NET] Network is online. >> "%LOG_FILE%"
        goto :NET_READY
    )
    timeout /t 2 /nobreak > nul
)
echo [WARN] Network ping check timed out. Proceeding anyway... >> "%LOG_FILE%"

:NET_READY
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

set PUSH_OK=0
for /L %%A in (1,1,3) do (
    if !PUSH_OK!==0 (
        echo [SYNC] Attempt %%A: Pushing to GitHub... >> "%LOG_FILE%"
        git push origin main >> "%LOG_FILE%" 2>&1
        if !errorlevel!==0 (
            set PUSH_OK=1
        ) else (
            echo [WARN] Git push attempt %%A failed. Retrying in 3s... >> "%LOG_FILE%"
            timeout /t 3 /nobreak > nul
        )
    )
)

if !PUSH_OK!==1 (
    echo [SUCCESS] Scraping and GitHub sync finished at %NOW% >> "%LOG_FILE%"
    echo [SUCCESS] Scraping and GitHub sync finished successfully!
    exit /b 0
) else (
    echo [ERROR] Git push failed after 3 attempts at %NOW% >> "%LOG_FILE%"
    echo [ERROR] Git push failed. Check network or credentials.
    exit /b 1
)

