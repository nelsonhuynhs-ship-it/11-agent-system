# register-si-alert-task.ps1
# Creates Windows Task Scheduler entry for daily 48h SI cutoff Telegram alert.
#
# Usage (run as Nelson account — no admin required, Interactive logon):
#   powershell -ExecutionPolicy Bypass -File scripts\register-si-alert-task.ps1
#
# What it does:
#   - Runs daily at 08:05 (5min after NelsonCNEEMilestoneETA7 at 08:00)
#   - python scripts\si-48h-alert.py
#   - Runs in context of current user (inherits env vars BOT_TOKEN + ADMIN_CHAT_ID)
#   - Task name: NelsonSI48hAlert
#
# To test manually: Start-ScheduledTask -TaskName "NelsonSI48hAlert"
# To remove:        Unregister-ScheduledTask -TaskName "NelsonSI48hAlert" -Confirm:$false
# Dry-run test:     python scripts\si-48h-alert.py --test

$TaskName  = "NelsonSI48hAlert"
$PythonExe = "C:\Users\Nelson\anaconda3\python.exe"
$WorkDir   = "D:\NELSON\2. Areas\Engine_test"
$Script    = "scripts\si-48h-alert.py"

# Validate paths before registering
if (-not (Test-Path $PythonExe)) {
    Write-Error "Python not found at: $PythonExe"
    Write-Host "Check CLAUDE.md — Python path is C:/Users/Nelson/anaconda3/python.exe"
    exit 1
}

if (-not (Test-Path $WorkDir)) {
    Write-Error "Working directory not found: $WorkDir"
    exit 1
}

if (-not (Test-Path (Join-Path $WorkDir $Script))) {
    Write-Error "Script not found: $WorkDir\$Script"
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
    -Argument $Script `
    -WorkingDirectory $WorkDir

$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At "08:05AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# Register for current user (no password required — Interactive logon)
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
    -Description "Nelson Freight: 48h SI cutoff warning via Telegram (BOT_TOKEN + ADMIN_CHAT_ID required)"

Write-Host ""
Write-Host "Task registered: $TaskName"
Write-Host "Schedule:  Daily 08:05"
Write-Host "Command:   $PythonExe $Script"
Write-Host "WorkDir:   $WorkDir"
Write-Host ""
Write-Host "IMPORTANT: Ensure these env vars are set for user $env:USERNAME:"
Write-Host "  BOT_TOKEN      (Telegram bot token)"
Write-Host "  ADMIN_CHAT_ID  (Nelson's Telegram chat ID from @userinfobot)"
Write-Host ""
Write-Host "To verify:      Get-ScheduledTask -TaskName '$TaskName'"
Write-Host "To run now:     Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To dry-run:     python scripts\si-48h-alert.py --test"
Write-Host "To remove:      Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
