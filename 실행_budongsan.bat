@echo off
chcp 65001 > nul
setlocal

if not "%minimized%"=="1" (
    set minimized=1
    start /min cmd /c "%~f0"
    exit /b
)
REM ==============================
REM 설정
REM ==============================
set "REPO_DIR=D:\Git\myBudongsan"
set "PYTHON_EXE=python"
set "SCRIPT=local_scraper.py"

REM Git 경로 보정 (where git 결과 반영)
set "PATH=C:\Program Files\Git\cmd;%PATH%"

REM ==============================
REM 1) 저장소 폴더로 이동
REM ==============================
cd /d "%REPO_DIR%"
if errorlevel 1 (
  echo [ERROR] 폴더로 이동 실패: %REPO_DIR%
  exit /b 1
)

REM ==============================
REM 2) 파이썬 스크래퍼 실행
REM ==============================
echo.
echo ===== Running scraper =====
%PYTHON_EXE% "%SCRIPT%"
if errorlevel 1 (
  echo [ERROR] 스크래퍼 실행 실패. Push 중단.
  exit /b 1
)

REM ==============================
REM 3) Git Add / Commit (변경 없으면 스킵)
REM ==============================
echo.
echo ===== Git add/commit =====
git add -A

git diff --cached --quiet
if %errorlevel%==0 (
  echo [INFO] 변경사항이 없어 커밋/푸시를 생략합니다.
  exit /b 0
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format ''yyyy-MM-dd HH:mm:ss''"') do set "NOW=%%i"
git commit -m "Auto update: %NOW% (company)"

REM ==============================
REM 4) Push
REM ==============================
echo.
echo ===== Git push =====
git push
if errorlevel 1 (
  echo [ERROR] git push 실패 (인증/네트워크 확인 필요)
  exit /b 1
)

echo.
echo ✅ DONE! GitHub로 push 완료.
exit /b 0
``