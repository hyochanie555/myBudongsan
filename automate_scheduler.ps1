# Windows Task Scheduler Setup for real estate scraper
$taskName = "MyBudongsan_Scraper_Auto"
$batchPath = Join-Path $PSScriptRoot "실행_budongsan.bat"
$workingDir = $PSScriptRoot

# 1. Define Triggers (05:07, 09:07, 11:07, 13:07, 15:07, 18:07, 21:07)
$times = @("05:07", "09:07", "11:07", "13:07", "15:07", "18:07", "21:07")
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
    Write-Host "[SUCCESS] Task '$taskName' registered successfully with 8 triggers." -ForegroundColor Green
    Write-Host "Scheduled times: $($times -join ', ')"
} catch {
    Write-Host "[ERROR] Failed to register task. Please run this script as Administrator." -ForegroundColor Red
    Write-Host $_.Exception.Message
}
