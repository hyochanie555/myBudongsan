@echo off
chcp 65001 > nul
setlocal

:: 관리자 권한 확인 및 자동 상승 실행
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 관리자 권한을 요청합니다...
    powershell -Command "Start-Process cmd -ArgumentList '/c "%~f0"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo ========================================================
echo   [스케줄러 등록] 부동산 스크래퍼 자동 실행 등록
echo ========================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0automate_scheduler.ps1"
echo.
pause
