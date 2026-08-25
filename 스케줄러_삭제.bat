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

echo ========================================================
echo   [스케줄러 삭제] 부동산 스크래퍼 자동 실행 작업 제거
echo ========================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command "Unregister-ScheduledTask -TaskName 'MyBudongsan_Scraper_Auto' -Confirm:$false -ErrorAction Continue; Write-Host '[SUCCESS] MyBudongsan_Scraper_Auto 작업이 삭제되었습니다.' -ForegroundColor Green"
echo.
pause
