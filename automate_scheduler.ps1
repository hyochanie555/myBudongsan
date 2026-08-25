# Windows Task Scheduler Setup for real estate scraper
$taskName = "MyBudongsan_Scraper_Auto"
$batchPath = Join-Path $PSScriptRoot "실행_budongsan.bat"
$workingDir = $PSScriptRoot

# 0. Windows 전원 설정: 절전 모드 해제 타이머(Wake Timers) 활성화
try {
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d 1 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d 1 2>$null
    powercfg /setactive SCHEME_CURRENT 2>$null
    Write-Host "[INFO] Windows 절전 모드 해제 타이머(Wake Timers) 활성화 확인 완료" -ForegroundColor Cyan
} catch {
    # 무시
}

# 1. 트리거 정의 (하루 5회: 07:00, 11:00, 15:00, 18:00, 21:00)
$times = @("07:00", "11:00", "15:00", "18:00", "21:00")
$triggers = foreach ($time in $times) {
    New-ScheduledTaskTrigger -Daily -At $time
}

# 2. 실행 동작 정의
$action = New-ScheduledTaskAction -Execute $batchPath -WorkingDirectory $workingDir

# 3. 상세 설정 정의
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

# 4. 작업 등록
try {
    # 기존 작업이 있으면 제거 후 등록
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask `
        -TaskName $taskName `
        -Trigger $triggers `
        -Action $action `
        -Settings $settings `
        -Description "myBudongsan Real Estate Auto Scraper (Daily 5 times: 07:00, 11:00, 15:00, 18:00, 21:00)" `
        -Force `
        -ErrorAction Stop | Out-Null

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] 스케줄러 등록이 성공적으로 완료되었습니다!" -ForegroundColor Green
    Write-Host " 작업 이름 : $taskName" -ForegroundColor Green
    Write-Host " 실행 시간 : $($times -join ', ') (하루 5회)" -ForegroundColor Green
    Write-Host " 절전 모드 : 절전 모드에서 컴퓨터 깨우기(WakeToRun) 활성화됨" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] 작업 등록 실패: $($_.Exception.Message)" -ForegroundColor Red
}