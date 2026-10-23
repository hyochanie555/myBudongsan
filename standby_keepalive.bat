@echo off
echo [%date% %time%] Standby KeepAlive triggered (Modern Standby reset) >> "D:\8.Antigravity\myBudongsan\standby_keepalive.log"
timeout /t 15 /nobreak >nul
exit /b 0
