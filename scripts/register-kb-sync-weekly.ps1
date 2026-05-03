# register-kb-sync-weekly.ps1
# Registers Windows Task Scheduler job for weekly disposable domain sync
# Runs every Monday at 06:30 local time.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\register-kb-sync-weekly.ps1

$TaskName = "NelsonKBSyncDisposableWeekly"
$Python   = "C:\Users\Nelson\anaconda3\python.exe"
$Script   = "D:\NELSON\2. Areas\Engine_test\scripts\run-kb-sync-disposable-weekly.py"
$LogFile  = "D:\NELSON\2. Areas\Engine_test\email_engine\logs\kb-sync.log"
$WorkDir  = "D:\NELSON\2. Areas\Engine_test"

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

$Action  = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$Script`" >> `"$LogFile`" 2>&1" `
    -WorkingDirectory $WorkDir

$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Monday `
    -At "06:30"

$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Weekly refresh of disposable email domain list from GitHub (Bounce KB Sprint 1 v3)" `
    -Force

Write-Host ""
Write-Host "Task registered: $TaskName"
Write-Host "Schedule: Every Monday 06:30"
Write-Host "Script: $Script"
Write-Host "Log: $LogFile"
Write-Host ""
Write-Host "To verify: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "To run now: Start-ScheduledTask -TaskName '$TaskName'"
