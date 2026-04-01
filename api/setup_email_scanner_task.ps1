# setup_email_scanner_task.ps1
# ============================================================
# Creates a Windows Task Scheduler job to auto-scan Outlook
# emails every 30 minutes and sync with the Shipment Tracker.
# ============================================================
#
# Usage:
#   Run as Administrator:
#   powershell -ExecutionPolicy Bypass -File setup_email_scanner_task.ps1
#
# What it does:
#   1. Scans Outlook folders (TEAM SUNNY / customer subfolders)
#   2. Exports structured JSON dataset → api/email_data/outlook_dataset.json
#   3. Syncs email events → shipment_state.json
#
# Schedule: Every 30 minutes between 7:30 AM - 6:00 PM (Mon-Fri)
# ============================================================

$ErrorActionPreference = "Stop"

# ─── Config ───────────────────────────────────────────────────
$TaskName        = "NelsonFreight_EmailScanner"
$TaskDescription = "Auto-scan Outlook emails for shipment tracking | Nelson Freight System"
$PythonPath      = "python"  # Use system Python
$ScriptDir       = "D:\NELSON\2. Areas\PricingSystem\Engine_test\api"
$ScanScript      = Join-Path $ScriptDir "email_scanner.py"
$SyncScript      = Join-Path $ScriptDir "email_event_engine.py"
$LogFile         = Join-Path $ScriptDir "email_data\task_scheduler.log"

# ─── Verify files exist ──────────────────────────────────────
if (!(Test-Path $ScanScript)) {
    Write-Error "email_scanner.py not found at: $ScanScript"
    exit 1
}
if (!(Test-Path $SyncScript)) {
    Write-Error "email_event_engine.py not found at: $SyncScript"
    exit 1
}

# ─── Build the action ────────────────────────────────────────
# Run scan (--quick for scheduled runs) then sync
$ActionScript = @"
cd /d "$ScriptDir"
echo [%date% %time%] Starting scheduled email scan >> "$LogFile"
python email_scanner.py --quick >> "$LogFile" 2>&1
echo [%date% %time%] Running event sync >> "$LogFile"
python email_event_engine.py >> "$LogFile" 2>&1
echo [%date% %time%] Done >> "$LogFile"
echo. >> "$LogFile"
"@

# Write the batch file
$BatchFile = Join-Path $ScriptDir "email_data\run_email_scan.bat"
$ActionScript | Set-Content -Path $BatchFile -Encoding ASCII

Write-Host "Created batch file: $BatchFile" -ForegroundColor Green

# ─── Create scheduled task ───────────────────────────────────
try {
    # Remove existing task if any
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed existing task: $TaskName" -ForegroundColor Yellow
    }

    # Trigger: every 30 minutes
    $Trigger = New-ScheduledTaskTrigger `
        -Once `
        -At (Get-Date -Hour 7 -Minute 30 -Second 0) `
        -RepetitionInterval (New-TimeSpan -Minutes 30) `
        -RepetitionDuration (New-TimeSpan -Hours 10 -Minutes 30)

    # Action: run the batch file
    $Action = New-ScheduledTaskAction `
        -Execute "cmd.exe" `
        -Argument "/c `"$BatchFile`"" `
        -WorkingDirectory $ScriptDir

    # Settings
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -RunOnlyIfNetworkAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

    # Register
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $TaskDescription `
        -Trigger $Trigger `
        -Action $Action `
        -Settings $Settings `
        -RunLevel Limited

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host "  Task Scheduler Job Created Successfully!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Task Name : $TaskName"
    Write-Host "  Schedule  : Every 30 minutes (7:30 AM - 6:00 PM)"
    Write-Host "  Action    : Scan Outlook + Sync Shipment State"
    Write-Host "  Log File  : $LogFile"
    Write-Host ""
    Write-Host "  To run now:  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
    Write-Host "  To remove:   Unregister-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
    Write-Host ""

} catch {
    Write-Error "Failed to create scheduled task: $_"
    Write-Host ""
    Write-Host "Try running as Administrator, or manually create via Task Scheduler:" -ForegroundColor Yellow
    Write-Host "  Program: cmd.exe"
    Write-Host "  Arguments: /c `"$BatchFile`""
    Write-Host "  Start in: $ScriptDir"
    Write-Host "  Trigger: Every 30 minutes"
}
