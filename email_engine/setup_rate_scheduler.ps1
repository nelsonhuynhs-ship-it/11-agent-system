# setup_rate_scheduler.ps1
# Nelson Freight - Rate Parquet Scheduler
# Usage: powershell -ExecutionPolicy Bypass -File "...\email_engine\setup_rate_scheduler.ps1"

$BASE_DIR    = "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test"
$SCRIPT      = "$BASE_DIR\email_engine\core\rate_parquet_updater.py"
$WORK_DIR    = "$BASE_DIR\email_engine"
$INCOMING    = "$BASE_DIR\Pricing_Engine\data\incoming"

# Find python
$PY = (Get-Command python -ErrorAction Stop).Source
$PYW = $PY -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $PYW)) { $PYW = $PY }

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  Nelson Rate Scheduler Setup" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  Python:   $PYW"
Write-Host "  Script:   $SCRIPT"
Write-Host "  WorkDir:  $WORK_DIR"
Write-Host "  Incoming: $INCOMING"
Write-Host ""

if (-not (Test-Path $SCRIPT)) {
    Write-Host "ERROR: Script not found: $SCRIPT" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $INCOMING)) {
    New-Item -ItemType Directory -Path $INCOMING -Force | Out-Null
    Write-Host "  Created incoming folder" -ForegroundColor Green
}

# Remove old tasks
Write-Host "[1/3] Removing old tasks..." -ForegroundColor Yellow
$oldList = @("NelsonRateImporter","NelsonRateImporter_Hourly","EmailEngine_Parquet","EmailEngine_Collector","NelsonUnifiedScanner")
foreach ($name in $oldList) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "  Removed: $name" -ForegroundColor Yellow
    } else {
        Write-Host "  Skip: $name" -ForegroundColor Gray
    }
}

# Shared action + settings
$action = New-ScheduledTaskAction -Execute $PYW -Argument "`"$SCRIPT`"" -WorkingDirectory $WORK_DIR
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 20) -StartWhenAvailable -MultipleInstances IgnoreNew -WakeToRun:$false
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited

# Task 1: Daily 07:30
Write-Host ""
Write-Host "[2/3] Creating NelsonRateImporter - daily 07:30..." -ForegroundColor Yellow
$trigger1 = New-ScheduledTaskTrigger -Daily -At "07:30"
Register-ScheduledTask -TaskName "NelsonRateImporter" -Trigger $trigger1 -Action $action -Settings $settings -Principal $principal -Description "Import FAK rate files vao Parquet daily 07:30" -Force | Out-Null
Write-Host "  OK: NelsonRateImporter - daily 07:30" -ForegroundColor Green

# Task 2: Hourly 08:00 to 18:00 (11 triggers)
Write-Host ""
Write-Host "[3/3] Creating NelsonRateImporter_Hourly - 08:00 to 18:00..." -ForegroundColor Yellow
$t08 = New-ScheduledTaskTrigger -Daily -At "08:00"
$t09 = New-ScheduledTaskTrigger -Daily -At "09:00"
$t10 = New-ScheduledTaskTrigger -Daily -At "10:00"
$t11 = New-ScheduledTaskTrigger -Daily -At "11:00"
$t12 = New-ScheduledTaskTrigger -Daily -At "12:00"
$t13 = New-ScheduledTaskTrigger -Daily -At "13:00"
$t14 = New-ScheduledTaskTrigger -Daily -At "14:00"
$t15 = New-ScheduledTaskTrigger -Daily -At "15:00"
$t16 = New-ScheduledTaskTrigger -Daily -At "16:00"
$t17 = New-ScheduledTaskTrigger -Daily -At "17:00"
$t18 = New-ScheduledTaskTrigger -Daily -At "18:00"
$triggerList = @($t08,$t09,$t10,$t11,$t12,$t13,$t14,$t15,$t16,$t17,$t18)
Register-ScheduledTask -TaskName "NelsonRateImporter_Hourly" -Trigger $triggerList -Action $action -Settings $settings -Principal $principal -Description "Import FAK rate files vao Parquet - kiem tra moi 60 phut" -Force | Out-Null
Write-Host "  OK: NelsonRateImporter_Hourly - 08:00-18:00" -ForegroundColor Green

# Done
Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Verify:"
Write-Host '    Get-ScheduledTask | Where { $_.TaskName -like "Nelson*" } | Select TaskName,State'
Write-Host ""
Write-Host "  Test ngay:"
Write-Host '    Start-ScheduledTask -TaskName "NelsonRateImporter"'
Write-Host ""
Write-Host "  Drop file gia vao:"
Write-Host "    $INCOMING"
Write-Host ""
Write-Host "  Check log:"
Write-Host "    Get-Content `"$BASE_DIR\email_engine\logs\rate_updater.log`" -Tail 20"
