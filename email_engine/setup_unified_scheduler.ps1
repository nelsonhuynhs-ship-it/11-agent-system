# setup_unified_scheduler.ps1
# ============================================================
# Registers ONE unified task that replaces 3 separate tasks:
#   EmailEngine_TeamSunny + ShipmentBrain_Scan + NelsonRateImporter
#   → NelsonUnifiedScanner (every 30 min, 08:00-17:30)
#
# Keeps existing tasks untouched:
#   EmailEngine_Briefing   (daily 07:45)
#   EmailEngine_Collector  (every 60 min)
#   EmailEngine_Parquet    (weekly Sun 06:00)
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File setup_unified_scheduler.ps1
# ============================================================

$PythonExe = (Get-Command python -ErrorAction Stop).Source
$PythonW   = $PythonExe -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $PythonW)) {
    Write-Host "  pythonw.exe not found, using python.exe" -ForegroundColor Yellow
    $PythonW = $PythonExe
}

$BaseDir    = Split-Path -Parent $PSScriptRoot
$ScriptPath = Join-Path $PSScriptRoot "core\outlook_scanner.py"
$TaskName   = "NelsonUnifiedScanner"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Nelson Unified Scanner — Scheduler Setup"         -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Python  : $PythonW"
Write-Host "  Script  : $ScriptPath"
Write-Host "  WorkDir : $PSScriptRoot"
Write-Host ""

if (-not (Test-Path $ScriptPath)) {
    Write-Host "  ERROR: outlook_scanner.py not found!" -ForegroundColor Red
    exit 1
}

# ── Remove old separate tasks (optional, only if they exist) ─────────────────
$oldTasks = @("EmailEngine_TeamSunny", "ShipmentBrain_Scan")
foreach ($old in $oldTasks) {
    $existing = Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Removing old task: $old ..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $old -Confirm:$false
    }
}

# ── Register unified task: every 30 min, 08:00-17:30 ─────────────────────────
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "  Removing existing: $TaskName ..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create triggers: every 30 min from 08:00 to 17:30
$triggers = @()
$current  = [datetime]::Today.AddHours(8)
$endTime  = [datetime]::Today.AddHours(17).AddMinutes(30)
while ($current -le $endTime) {
    $triggers += New-ScheduledTaskTrigger -Daily -At $current.ToString("HH:mm")
    $current   = $current.AddMinutes(30)
}

$action = New-ScheduledTaskAction `
    -Execute  $PythonW `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $PSScriptRoot

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit  (New-TimeSpan -Minutes 15) `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -WakeToRun:$false

$principal = New-ScheduledTaskPrincipal `
    -UserId   ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName    $TaskName `
    -Trigger     $triggers `
    -Action      $action `
    -Settings    $settings `
    -Principal   $principal `
    -Description "Nelson Unified Scanner: Mentee + Pricing + Shipment Brain (every 30 min)" `
    -Force | Out-Null

Write-Host "  OK: $TaskName registered" -ForegroundColor Green

# ── Also fix ShipmentBrain_Brief if stale ─────────────────────────────────────
$briefTask = Get-ScheduledTask -TaskName "ShipmentBrain_Brief" -ErrorAction SilentlyContinue
if ($briefTask) {
    Write-Host "  ShipmentBrain_Brief: keeping (daily ops briefing)" -ForegroundColor Gray
}

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  NEW:"
Write-Host "    $TaskName — every 30 min, 08:00-17:30"
Write-Host "    Runs: outlook_scanner.py (Mentee + Pricing + ShipmentBrain)"
Write-Host ""
Write-Host "  KEPT:"
Write-Host "    EmailEngine_Briefing  — daily 07:45"
Write-Host "    EmailEngine_Collector — every 60 min"
Write-Host "    EmailEngine_Parquet   — weekly Sun 06:00"
Write-Host ""
Write-Host "  Verify:"
Write-Host "    Get-ScheduledTask | Where { `$_.TaskName -like 'Nelson*' -or `$_.TaskName -like 'Email*' -or `$_.TaskName -like 'Shipment*' }"
Write-Host ""
Write-Host "  Test now:"
Write-Host "    Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "  Manual run:"
Write-Host "    python `"$ScriptPath`" --dry-run"
