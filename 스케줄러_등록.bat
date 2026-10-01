@echo off
chcp 65001 > nul
setlocal

cd /d "%~dp0"

:: Check for admin and elevate
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Requesting Administrator Privileges...
    powershell -NoProfile -Command "Start-Process powershell -ArgumentList '-NoExit -NoProfile -ExecutionPolicy Bypass -File \"\"%~dp0automate_scheduler.ps1\"\"' -WorkingDirectory \"\"%~dp0.\"\" -Verb RunAs"
    exit /b
)

echo ========================================================
echo   [스케줄러 등록] 부동산 스크래퍼 자동 실행 등록
echo ========================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0automate_scheduler.ps1"
echo.
pause
