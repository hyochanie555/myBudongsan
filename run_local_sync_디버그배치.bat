@echo off
title MyBudongsan Scraper - Local Sync
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "sync_listings.ps1"

echo.
echo Sync Complete. Press any key to close this window...
pause