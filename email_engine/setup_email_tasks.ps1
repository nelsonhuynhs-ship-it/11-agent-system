# setup_email_tasks.ps1
# Nelson Freight - Tao lai NelsonEmailScan + NelsonEmailBriefing tro C:
# Usage: powershell -ExecutionPolicy Bypass -File "...\email_engine\setup_email_tasks.ps1"

$BASE    = "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test"
$EMAILS  = "$BASE\email_engine"
$SCAN    = "$EMAILS\core\outlook_scanner.py"
$BRIEF   = "$EMAILS\core\nelson_briefing.py"

$PY  = (Get-Command python -ErrorAction Stop).Source
$PYW = $PY -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $PYW)) { $PYW = $PY }

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  Nelson Email Tasks Setup" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  Python:  $PYW"
Write-Host "  Scan:    $SCAN"
Write-Host "  Brief:   $BRIEF"
Write-Host ""

if (-not (Test-Path $SCAN))  { Write-Host "ERROR: $SCAN not found"  -ForegroundColor Red; exit 1 }
if (-not (Test-Path $BRIEF)) { Write-Host "ERROR: $BRIEF not found" -ForegroundColor Red; exit 1 }
Write-Host "  Scripts found" -ForegroundColor Green

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -WakeToRun:$false

$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited

# Remove neu cu con
foreach ($n in @("NelsonEmailScan","NelsonEmailBriefing")) {
    if (Get-ScheduledTask -TaskName $n -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $n -Confirm:$false
        Write-Host "  Removed old: $n" -ForegroundColor Yellow
    }
}

# TASK 1: NelsonEmailScan - moi 30 phut, 08:00-17:30
Write-Host ""
Write-Host "[1/2] Creating NelsonEmailScan (every 30 min, 08:00-17:30)..." -ForegroundColor Yellow

$action1 = New-ScheduledTaskAction -Execute $PYW -Argument "`"$SCAN`"" -WorkingDirectory $EMAILS

$t0800 = New-ScheduledTaskTrigger -Daily -At "08:00"
$t0830 = New-ScheduledTaskTrigger -Daily -At "08:30"
$t0900 = New-ScheduledTaskTrigger -Daily -At "09:00"
$t0930 = New-ScheduledTaskTrigger -Daily -At "09:30"
$t1000 = New-ScheduledTaskTrigger -Daily -At "10:00"
$t1030 = New-ScheduledTaskTrigger -Daily -At "10:30"
$t1100 = New-ScheduledTaskTrigger -Daily -At "11:00"
$t1130 = New-ScheduledTaskTrigger -Daily -At "11:30"
$t1200 = New-ScheduledTaskTrigger -Daily -At "12:00"
$t1230 = New-ScheduledTaskTrigger -Daily -At "12:30"
$t1300 = New-ScheduledTaskTrigger -Daily -At "13:00"
$t1330 = New-ScheduledTaskTrigger -Daily -At "13:30"
$t1400 = New-ScheduledTaskTrigger -Daily -At "14:00"
$t1430 = New-ScheduledTaskTrigger -Daily -At "14:30"
$t1500 = New-ScheduledTaskTrigger -Daily -At "15:00"
$t1530 = New-ScheduledTaskTrigger -Daily -At "15:30"
$t1600 = New-ScheduledTaskTrigger -Daily -At "16:00"
$t1630 = New-ScheduledTaskTrigger -Daily -At "16:30"
$t1700 = New-ScheduledTaskTrigger -Daily -At "17:00"
$t1730 = New-ScheduledTaskTrigger -Daily -At "17:30"

$scanTriggers = @($t0800,$t0830,$t0900,$t0930,$t1000,$t1030,$t1100,$t1130,
                  $t1200,$t1230,$t1300,$t1330,$t1400,$t1430,$t1500,$t1530,
                  $t1600,$t1630,$t1700,$t1730)

Register-ScheduledTask -TaskName "NelsonEmailScan" `
    -Trigger $scanTriggers -Action $action1 -Settings $settings `
    -Principal $principal `
    -Description "Nelson Email Scan: mentee classify + rate import + shipment brain. Every 30min 08:00-17:30. Path: $BASE" `
    -Force | Out-Null

Write-Host "  OK: NelsonEmailScan - 20 triggers (08:00-17:30 x30min)" -ForegroundColor Green

# TASK 2: NelsonEmailBriefing - 07:45 hang ngay
Write-Host ""
Write-Host "[2/2] Creating NelsonEmailBriefing (daily 07:45)..." -ForegroundColor Yellow

$action2  = New-ScheduledTaskAction -Execute $PYW -Argument "`"$BRIEF`"" -WorkingDirectory $EMAILS
$trigger2 = New-ScheduledTaskTrigger -Daily -At "07:45"

Register-ScheduledTask -TaskName "NelsonEmailBriefing" `
    -Trigger $trigger2 -Action $action2 -Settings $settings `
    -Principal $principal `
    -Description "Nelson Daily Briefing: Excel dashboard sang 07:45. Path: $BASE" `
    -Force | Out-Null

Write-Host "  OK: NelsonEmailBriefing - daily 07:45" -ForegroundColor Green

# Summary
Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  All Nelson tasks:"
Get-ScheduledTask | Where-Object { $_.TaskName -like "Nelson*" } | Select-Object TaskName, State | Format-Table -AutoSize
Write-Host ""
Write-Host "  Test ngay:"
Write-Host '    Start-ScheduledTask -TaskName "NelsonEmailScan"'
Write-Host '    Start-ScheduledTask -TaskName "NelsonEmailBriefing"'
