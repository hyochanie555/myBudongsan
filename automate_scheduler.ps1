# Windows Task Scheduler Setup for real estate scraper
$taskName = "MyBudongsan_Scraper_Auto"
$batchPath = Join-Path $PSScriptRoot "실행_budongsan.bat"
$workingDir = $PSScriptRoot

# 0. Windows 전원 설정: 절전 모드 해제 타이머(Wake Timers) 활성화
try {
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d 1 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d 1 2>$null
    # 대기 모드 중 네트워크 연결 유지 (모니터 분리 / 절전 모드에서도 Wi-Fi 유지)
    powercfg /setacvalueindex SCHEME_CURRENT fea3413e-7e05-4911-9a71-700331f1c294 f15576e8-98b7-4186-b944-eafa664402d9 1 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT fea3413e-7e05-4911-9a71-700331f1c294 f15576e8-98b7-4186-b944-eafa664402d9 1 2>$null
    # 배터리 소모 한계(Standby Budget)로 인한 Wi-Fi 차단 및 강제 동면 방지 (0으로 해제)
    powercfg /setacvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 9fe527be-1b70-48da-930d-7bcf17b44990 0 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 9fe527be-1b70-48da-930d-7bcf17b44990 0 2>$null
    # 연결 끊김 대기 모드 및 예비 시간 해제
    powercfg /setdcvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 468fe7e5-1158-46ec-88bc-5b96c9e44fd0 0 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT SUB_NONE 68afb2d9-ee95-47a8-8f50-4115088073b1 0 2>$null
    powercfg /setacvalueindex SCHEME_CURRENT SUB_NONE 68afb2d9-ee95-47a8-8f50-4115088073b1 0 2>$null
    powercfg /setactive SCHEME_CURRENT 2>$null
    Write-Host "[INFO] Windows 절전 해제 타이머, 배터리 긴축 해제 및 대기 중 Wi-Fi 유지 활성화 완료" -ForegroundColor Cyan
} catch {
    # 무시
}

# 1. 트리거 정의 (하루 7회: 05:00, 09:00, 11:00, 13:00, 15:00, 18:00, 21:00)
$times = @("05:00", "09:00", "11:00", "13:00", "15:00", "18:00", "21:00")
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
        -Description "myBudongsan Real Estate Auto Scraper (Daily 7 times: 05:00, 09:00, 11:00, 13:00, 15:00, 18:00, 21:00)" `
        -Force `
        -ErrorAction Stop | Out-Null

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] 스케줄러 등록이 성공적으로 완료되었습니다!" -ForegroundColor Green
    Write-Host " 작업 이름 : $taskName" -ForegroundColor Green
    Write-Host " 실행 시간 : $($times -join ', ') (하루 7회)" -ForegroundColor Green
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
            -Description "myBudongsan Real Estate Auto Scraper (Daily 7 times: 05:00, 09:00, 11:00, 13:00, 15:00, 18:00, 21:00)" `
            -Force `
            -ErrorAction Stop | Out-Null

        Write-Host ""
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host " [SUCCESS] 스케줄러 등록이 완료되었습니다 (기본 모드)!" -ForegroundColor Green
        Write-Host " 작업 이름 : $taskName" -ForegroundColor Green
        Write-Host " 실행 시간 : $($times -join ', ') (하루 7회)" -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] 작업 등록 실패: $($_.Exception.Message)" -ForegroundColor Red
    }
}