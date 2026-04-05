@echo off
title MyBudongsan Scraper - Local Sync
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "sync_listings.ps1"

echo.
echo Sync Complete.
echo Going to sleep mode in 10 seconds... (Press CTRL+C to cancel)
timeout /t 10 /nobreak
rundll32.exe powrprof.dll,SetSuspendState 0,1,0