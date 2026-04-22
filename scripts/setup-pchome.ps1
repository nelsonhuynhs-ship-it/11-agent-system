# ════════════════════════════════════════════════════════════════
# Setup PC Home — FreightBrian clone + full environment
# Run: right-click → "Run with PowerShell"
# Or:  powershell -ExecutionPolicy Bypass -File setup-pchome.ps1
# ════════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"
$REPO_URL = "git@github.com:nelsonhuynhs-ship-it/FrieghtBrian.git"
$TARGET_DIR = "D:\NELSON\2. Areas\Engine_test"
$PARENT_DIR = "D:\NELSON\2. Areas"

Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host " NELSON FREIGHT — PC HOME SETUP" -ForegroundColor Cyan
Write-Host "===========================================`n" -ForegroundColor Cyan

# ────────────────────────────────────────────────────────────
# STEP 1 — Check prerequisites
# ────────────────────────────────────────────────────────────
Write-Host "[1/9] Checking prerequisites..." -ForegroundColor Yellow

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

$checks = @{
    "git"    = "Git not installed. Install: https://git-scm.com/download/win"
    "python" = "Python not installed. Install anaconda or python.org"
    "ssh"    = "SSH client missing. Windows 10+ has it built-in, enable in Optional Features"
}

$missing = @()
foreach ($cmd in $checks.Keys) {
    if (Test-Command $cmd) {
        Write-Host "  OK $cmd" -ForegroundColor Green
    } else {
        Write-Host "  X  $cmd — $($checks[$cmd])" -ForegroundColor Red
        $missing += $cmd
    }
}

if ($missing.Count -gt 0) {
    Write-Host "`nInstall missing tools first, then re-run this script." -ForegroundColor Red
    exit 1
}

# ────────────────────────────────────────────────────────────
# STEP 2 — Verify SSH to GitHub
# ────────────────────────────────────────────────────────────
Write-Host "`n[2/9] Testing SSH to GitHub..." -ForegroundColor Yellow
$sshTest = ssh -T -o BatchMode=yes -o StrictHostKeyChecking=no git@github.com 2>&1
if ($sshTest -match "successfully authenticated") {
    Write-Host "  OK SSH authenticated" -ForegroundColor Green
} else {
    Write-Host "  X  SSH not configured. Generate key:" -ForegroundColor Red
    Write-Host "     ssh-keygen -t ed25519 -C pchome@nelson" -ForegroundColor Yellow
    Write-Host "     Then add public key to GitHub Settings → SSH Keys" -ForegroundColor Yellow
    Write-Host "     Re-run this script after done." -ForegroundColor Yellow
    exit 1
}

# ────────────────────────────────────────────────────────────
# STEP 3 — Clone or pull repo
# ────────────────────────────────────────────────────────────
Write-Host "`n[3/9] Cloning FreightBrian repo..." -ForegroundColor Yellow

if (-not (Test-Path $PARENT_DIR)) {
    New-Item -ItemType Directory -Path $PARENT_DIR -Force | Out-Null
}

if (Test-Path $TARGET_DIR\.git) {
    Write-Host "  Repo exists — pulling latest..." -ForegroundColor Cyan
    Set-Location $TARGET_DIR
    git pull origin main
} else {
    Set-Location $PARENT_DIR
    git clone $REPO_URL Engine_test
    Set-Location $TARGET_DIR
}

$commit = git log --oneline -1
Write-Host "  OK Latest: $commit" -ForegroundColor Green

# ────────────────────────────────────────────────────────────
# STEP 4 — Install Python dependencies
# ────────────────────────────────────────────────────────────
Write-Host "`n[4/9] Installing Python packages..." -ForegroundColor Yellow

$pkgs = @(
    "pandas", "openpyxl", "fastapi", "uvicorn", "filelock",
    "holidays", "rapidfuzz", "pywin32", "python-dateutil",
    "pydantic", "xlrd", "duckdb", "apscheduler", "requests",
    "python-dotenv"
)
pip install $pkgs --quiet --disable-pip-version-check
Write-Host "  OK Dependencies installed" -ForegroundColor Green

# ────────────────────────────────────────────────────────────
# STEP 5 — Set environment variables
# ────────────────────────────────────────────────────────────
Write-Host "`n[5/9] Setting Windows environment variables..." -ForegroundColor Yellow

$envVars = @{
    "BOT_TOKEN"       = "8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys"
    "ADMIN_CHAT_ID"   = "5398948978"
    "NELSON_MACHINE"  = "pc-home"
}

foreach ($key in $envVars.Keys) {
    [System.Environment]::SetEnvironmentVariable($key, $envVars[$key], "User")
    Write-Host "  OK $key set" -ForegroundColor Green
}

# ────────────────────────────────────────────────────────────
# STEP 6 — Check OneDrive sync
# ────────────────────────────────────────────────────────────
Write-Host "`n[6/9] Checking OneDrive sync..." -ForegroundColor Yellow

$onedriveFiles = @{
    "Contacts v6" = "D:\OneDrive\NelsonData\email\contact_unified_v6.xlsx"
    "Pricing master" = "D:\OneDrive\NelsonData\pricing\Cleaned_Master_History.parquet"
}

$missingData = $false
foreach ($name in $onedriveFiles.Keys) {
    $path = $onedriveFiles[$name]
    if (Test-Path $path) {
        $size = [math]::Round((Get-Item $path).Length / 1MB, 1)
        Write-Host "  OK $name (${size}MB)" -ForegroundColor Green
    } else {
        Write-Host "  !  $name missing — wait for OneDrive sync" -ForegroundColor Yellow
        $missingData = $true
    }
}

if ($missingData) {
    Write-Host "  Open OneDrive app, sign in, wait 10-30 min for full sync." -ForegroundColor Yellow
}

# ────────────────────────────────────────────────────────────
# STEP 7 — Copy .env files (manual guidance)
# ────────────────────────────────────────────────────────────
Write-Host "`n[7/9] Secrets (.env files)..." -ForegroundColor Yellow

$envFiles = @(
    "$TARGET_DIR\email_engine\.env",
    "$TARGET_DIR\api\.env"
)

$envMissing = @()
foreach ($ef in $envFiles) {
    if (Test-Path $ef) {
        Write-Host "  OK $(Split-Path $ef -Leaf)" -ForegroundColor Green
    } else {
        Write-Host "  !  Missing: $ef" -ForegroundColor Yellow
        $envMissing += $ef
    }
}

if ($envMissing.Count -gt 0) {
    Write-Host "`n  Copy .env files from Laptop VP manually:" -ForegroundColor Yellow
    Write-Host "  1. Laptop: zip email_engine/.env + api/.env → upload OneDrive private folder" -ForegroundColor White
    Write-Host "  2. PC Home: download zip → extract to above paths" -ForegroundColor White
}

# ────────────────────────────────────────────────────────────
# STEP 8 — Desktop shortcut
# ────────────────────────────────────────────────────────────
Write-Host "`n[8/9] Creating Desktop shortcut..." -ForegroundColor Yellow

$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Nelson Email Dashboard.lnk"
$wshell = New-Object -ComObject WScript.Shell
$shortcut = $wshell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "$TARGET_DIR\email_engine\start-dashboard-v4.bat"
$shortcut.WorkingDirectory = "$TARGET_DIR\email_engine"
$shortcut.Description = "Nelson Email Dashboard v6"
$shortcut.Save()
Write-Host "  OK Shortcut created" -ForegroundColor Green

# ────────────────────────────────────────────────────────────
# STEP 9 — Task Scheduler (REGISTER BUT DISABLED)
# ────────────────────────────────────────────────────────────
Write-Host "`n[9/9] Task Scheduler..." -ForegroundColor Yellow
Write-Host "  ! Skipping auto-register." -ForegroundColor Yellow
Write-Host "  Laptop VP is still primary. Register this PC only when switching:" -ForegroundColor Cyan
Write-Host "    schtasks /Create /TN NelsonEmailRotation /TR ..." -ForegroundColor Gray

# ────────────────────────────────────────────────────────────
# SUMMARY
# ────────────────────────────────────────────────────────────
Write-Host "`n===========================================" -ForegroundColor Cyan
Write-Host " SETUP COMPLETE" -ForegroundColor Green
Write-Host "===========================================`n" -ForegroundColor Cyan

Write-Host "Next steps:" -ForegroundColor Yellow
if ($envMissing.Count -gt 0) {
    Write-Host "  1. Copy .env files from Laptop VP (see Step 7 above)" -ForegroundColor White
}
if ($missingData) {
    Write-Host "  2. Wait for OneDrive sync to finish" -ForegroundColor White
}
Write-Host "  3. Close + reopen PowerShell (reload env vars)" -ForegroundColor White
Write-Host "  4. Test: cd '$TARGET_DIR\email_engine'" -ForegroundColor White
Write-Host "     python web_server.py" -ForegroundColor White
Write-Host "     Browser: http://localhost:8100/api/send-stats" -ForegroundColor White
Write-Host "     Expected: total=22842`n" -ForegroundColor White

Write-Host "Full guide: docs/SETUP_PC_HOME.md" -ForegroundColor Gray
