# Windows Task Scheduler Setup for real estate scraper
$taskName = "MyBudongsan_Scraper_Auto"

$projectDir = "D:\8.Antigravity\myBudongsan"
$batchPath = Join-Path $projectDir "실행_budongsan.bat"
$workingDir = $projectDir

# 0. Windows Power Settings (AC: 모니터/전원 연결 시 절전 해제 및 상시 연결, DC: 배터리 소모 최소화)
try {
    # RTC Wake timers (절전 모드 해제 타이머 허용)
    powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d 1 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT SUB_SLEEP bd3b718a-0680-4d9d-8ab2-e1d2b4ac806d 1 2>$null
    # Connectivity in Standby (대기 모드 네트워크 연결: AC는 활성화, DC는 배터리 절약을 위해 비활성화)
    powercfg /setacvalueindex SCHEME_CURRENT fea3413e-7e05-4911-9a71-700331f1c294 f15576e8-98b7-4186-b944-eafa664402d9 1 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT fea3413e-7e05-4911-9a71-700331f1c294 f15576e8-98b7-4186-b944-eafa664402d9 0 2>$null
    # Standby Budget Percent (AC: 무제한 0, DC: 기본값 5%로 배터리 과소모 방지)
    powercfg /setacvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 9fe527be-1b70-48da-930d-7bcf17b44990 0 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 9fe527be-1b70-48da-930d-7bcf17b44990 5 2>$null
    # Standby Budget Grace Period (AC: 0, DC: 900초 기본값)
    powercfg /setacvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 60c07fe1-0556-45cf-9903-d56e32210242 0 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 60c07fe1-0556-45cf-9903-d56e32210242 900 2>$null
    # User Presence Prediction (AC: 0, DC: 1)
    powercfg /setacvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 82011705-fb95-4d46-8d35-4042b1d20def 0 2>$null
    powercfg /setdcvalueindex SCHEME_CURRENT 8619b916-e004-4dd8-9b66-dae86f806698 82011705-fb95-4d46-8d35-4042b1d20def 1 2>$null
    # Disconnected Standby Mode: 0 (Normal)
    powercfg /setdcvalueindex SCHEME_CURRENT SUB_NONE 68afb2d9-ee95-47a8-8f50-4115088073b1 0 2>$null
    powercfg /setacvalueindex SCHEME_CURRENT SUB_NONE 68afb2d9-ee95-47a8-8f50-4115088073b1 0 2>$null
    powercfg /setactive SCHEME_CURRENT 2>$null
    Write-Host "[INFO] Windows Power Settings Applied Successfully." -ForegroundColor Cyan
} catch {
}

# 1. Triggers (Daily 7 times)
$times = @("05:00", "09:00", "11:00", "13:00", "15:00", "18:00", "21:00")
$triggers = foreach ($time in $times) {
    New-ScheduledTaskTrigger -Daily -At $time
}

# 2. Action
$action = New-ScheduledTaskAction -Execute $batchPath -WorkingDirectory $workingDir

# 3. Settings
$settings = New-ScheduledTaskSettingsSet `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -Priority 4 `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew

# 4. Principal (S4U Mode)
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType S4U -RunLevel Highest

# 5. Register Task
try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask `
        -TaskName $taskName `
        -Trigger $triggers `
        -Action $action `
        -Settings $settings `
        -Principal $principal `
        -Description "myBudongsan Real Estate Auto Scraper" `
        -Force `
        -ErrorAction Stop | Out-Null

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] Scheduled Task registered successfully!" -ForegroundColor Green
    Write-Host " Task Name   : $taskName" -ForegroundColor Green
    Write-Host " Run User    : $currentUser (S4U Mode / Highest Privilege)" -ForegroundColor Green
    Write-Host " Schedule    : $($times -join ', ') (7 times daily)" -ForegroundColor Green
    Write-Host " Background  : Runs in background even when screen is off" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Red
    Write-Host " [ERROR] Administrator privileges required for S4U mode!" -ForegroundColor Red
    Write-Host " Error Details: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "==========================================================" -ForegroundColor Red
}
