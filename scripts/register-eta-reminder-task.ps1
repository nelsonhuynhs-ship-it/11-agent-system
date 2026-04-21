# register-eta-reminder-task.ps1
# Creates Windows Task Scheduler entry for CNEE ETA-7 daily reminder.
#
# Usage (run as Administrator OR Nelson account):
#   powershell -ExecutionPolicy Bypass -File scripts\register-eta-reminder-task.ps1
#
# What it does:
#   - Runs daily at 08:00 (7:30-18:00 window safe)
#   - C:/Users/Nelson/anaconda3/python -m email_engine.core.cnee_milestone eta-reminder
#   - Runs in context of current user (inherits Outlook COM + env vars)
#   - Task name: NelsonCNEEMilestoneETA7
#   - Logs to: email_engine\core\shipment_brain.log (shared log)
#
# To remove: Unregister-ScheduledTask -TaskName "NelsonCNEEMilestoneETA7" -Confirm:$false

$TaskName = "NelsonCNEEMilestoneETA7"
$PythonExe = "C:\Users\Nelson\anaconda3\python.exe"
$WorkDir   = "D:\NELSON\2. Areas\Engine_test"
$Module    = "-m email_engine.core.cnee_milestone eta-reminder"

# Check python exists
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python not found at: $PythonExe"
    Write-Host "Check CLAUDE.md — Python path is C:/Users/Nelson/anaconda3/python"
    exit 1
}

# Check work dir exists
if (-not (Test-Path $WorkDir)) {
    Write-Error "Working directory not found: $WorkDir"
    exit 1
}

# Remove existing task if present (idempotent)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task: $TaskName"
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Build task components
$action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $Module `
    -WorkingDirectory $WorkDir

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "08:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false

# Register task for current user (no password required)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Nelson Freight: Check ETA-7 Active Jobs daily, compose CNEE arrival notice drafts"

Write-Host ""
Write-Host "Task registered: $TaskName"
Write-Host "Schedule: Daily 08:00"
Write-Host "Command:  $PythonExe $Module"
Write-Host "WorkDir:  $WorkDir"
Write-Host ""
Write-Host "To verify: Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "To run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
