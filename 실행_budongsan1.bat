@echo off
chcp 65001 > nul
setlocal

set "CURRENT_DIR=%~dp0"
set "PATH=C:\Program Files\Git\cmd;%PATH%"

cd /d "%CURRENT_DIR%."
if errorlevel 1 (
    echo [ERROR] Failed to change directory to: %CURRENT_DIR%
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   [RUN] Starting Real Estate Scraper (local_scraper.py)...
echo ========================================================
python "%CURRENT_DIR%local_scraper.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Scraper failed with error.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   [SYNC] Syncing with GitHub...
echo ========================================================
git add -A

git diff --cached --quiet
if %errorlevel%==0 (
    echo [INFO] No changes detected. Skipping commit and push.
    echo [DONE] Finished.
    pause
    exit /b 0
)

for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"`) do set "NOW=%%i"
git commit -m "Auto update: %NOW% (local scraper)"

echo.
echo [INFO] Pushing changes to GitHub...
git pull --rebase origin main
git push origin main
if errorlevel 1 (
    echo.
    echo [ERROR] Git push failed. Please check internet connection or GitHub authentication.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   [SUCCESS] Scraping and GitHub Sync completed!
echo ========================================================
pause
exit /b 0