# Windows Task Scheduler Setup for real estate scraper
$taskName = "MyBudongsan_Scraper_Auto"
$batchPath = "d:\8. Antigravity\myBudongsan\run_local_sync.bat"
$workingDir = "d:\8. Antigravity\myBudongsan"

# 1. Define Triggers (6:00, 11:00, 14:00, 17:00, 21:00)
$times = @("06:00", "11:00", "14:00", "17:00", "21:00")
$triggers = foreach ($time in $times) {
    New-ScheduledTaskTrigger -Daily -At $time
}

# 2. Define Action
$action = New-ScheduledTaskAction -Execute $batchPath -WorkingDirectory $workingDir

# 3. Define Settings
$settings = New-ScheduledTaskSettingsSet -WakeToRun -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

# 4. Register Task
try {
    Register-ScheduledTask -TaskName $taskName -Trigger $triggers -Action $action -Settings $settings -Force -ErrorAction Stop
    Write-Host "[SUCCESS] Task '$taskName' registered successfully with 5 triggers." -ForegroundColor Green
    Write-Host "Scheduled times: $($times -join ', ')"
} catch {
    Write-Host "[ERROR] Failed to register task. Please run this script as Administrator." -ForegroundColor Red
    Write-Host $_.Exception.Message
}
