@echo off
chcp 65001 > nul

REM ===============================
REM 설정
REM ===============================
set PROJECT_DIR=D:\Git\myBudongsan
set PYTHON_EXE=python
set SCRIPT_NAME=serverless_scraper.py

REM ===============================
REM 프로젝트 폴더로 이동
REM ===============================
cd /d %PROJECT_DIR%

echo.
echo ==============================
echo [1/3] Running scraper...
echo ==============================
%PYTHON_EXE% %SCRIPT_NAME%

IF ERRORLEVEL 1 (
    echo [ERROR] Python script failed. Aborting git push.
    pause
    exit /b 1
)

echo.
echo ==============================
echo [2/3] Git add & commit...
echo ==============================

git status

git add .
git commit -m "Auto update from company PC"

REM ===============================
REM Git push
REM ===============================
echo.
echo ==============================
echo [3/3] Git push...
echo ==============================

git push

IF ERRORLEVEL 1 (
    echo [ERROR] Git push failed.
    pause
    exit /b 1
)

echo.
echo ✅ ALL DONE! Successfully pushed to GitHub.
pause
