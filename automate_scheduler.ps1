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

# 1. 트리거 정의 (하루 6회: 07:00, 11:00, 13:00, 15:00, 18:00, 21:00)
$times = @("07:00", "11:00", "13:00", "15:00", "18:00", "21:00")
$triggers = foreach ($time in $times) {
    New-ScheduledTaskTrigger -Daily -At $time
}

# 2. 실행 동작 정의
$action = New-ScheduledTaskAction -Execute $batchPath -WorkingDirectory $workingDir

# 3. 상세 설정 정의 (절전모드/화면꺼짐/배터리 상태에서도 백그라운드 즉시 실행)
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -Priority 4 `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

# 4. 실행 주체 설정 (S4U 모드 지원)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

# 5. 작업 등록
try {
    # 기존 작업 제거 후 등록
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask `
        -TaskName $taskName `
        -Trigger $triggers `
        -Action $action `
        -Settings $settings `
        -Principal $principal `
        -Description "myBudongsan Real Estate Auto Scraper (Daily 6 times: 07:00, 11:00, 13:00, 15:00, 18:00, 21:00)" `
        -Force `
        -ErrorAction Stop | Out-Null

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] 스케줄러 등록이 성공적으로 완료되었습니다!" -ForegroundColor Green
    Write-Host " 작업 이름 : $taskName" -ForegroundColor Green
    Write-Host " 실행 시간 : $($times -join ', ') (하루 6회)" -ForegroundColor Green
    Write-Host " 절전 모드 : 화면 꺼짐/절전 모드에서도 백그라운드 실행(S4U/WakeToRun)" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} catch {
    # 관리자 권한 없는 경우 기본 Principal로 재시도
    try {
        Register-ScheduledTask `
            -TaskName $taskName `
            -Trigger $triggers `
            -Action $action `
            -Settings $settings `
            -Description "myBudongsan Real Estate Auto Scraper (Daily 6 times: 07:00, 11:00, 13:00, 15:00, 18:00, 21:00)" `
            -Force `
            -ErrorAction Stop | Out-Null

        Write-Host ""
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host " [SUCCESS] 스케줄러 등록이 완료되었습니다 (기본 모드)!" -ForegroundColor Green
        Write-Host " 작업 이름 : $taskName" -ForegroundColor Green
        Write-Host " 실행 시간 : $($times -join ', ') (하루 6회)" -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] 작업 등록 실패: $($_.Exception.Message)" -ForegroundColor Red
    }
}