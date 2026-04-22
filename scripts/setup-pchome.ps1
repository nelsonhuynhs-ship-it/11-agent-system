# ════════════════════════════════════════════════════════════════
# Setup PC Home — FreightBrian clone + full environment (v2)
# Run: right-click → "Run with PowerShell"
# ════════════════════════════════════════════════════════════════

$REPO_URL    = "git@github.com:nelsonhuynhs-ship-it/FrieghtBrian.git"
$TARGET_DIR  = "D:\NELSON\2. Areas\Engine_test"
$PARENT_DIR  = "D:\NELSON\2. Areas"
$LOG_FILE    = "$env:USERPROFILE\Desktop\setup-pchome.log"

# Logging helper — ghi ra file + console
function Write-Log($msg, $color = "White") {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Add-Content -Path $LOG_FILE -Value $line
    Write-Host $msg -ForegroundColor $color
}

# ⚠ Luôn pause ở cuối, dù success hay fail
function Wait-Before-Exit {
    Write-Host ""
    Write-Host "───────────────────────────────────────────" -ForegroundColor Cyan
    Write-Host " Log saved: $LOG_FILE" -ForegroundColor Gray
    Write-Host "───────────────────────────────────────────" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "Press ENTER to close this window"
}

# Bắt tất cả exception để pause trước khi tắt
trap {
    Write-Log "`n✗ UNEXPECTED ERROR: $($_.Exception.Message)" "Red"
    Write-Log "  Line: $($_.InvocationInfo.ScriptLineNumber)" "Red"
    Write-Log "  Stack: $($_.ScriptStackTrace)" "Gray"
    Wait-Before-Exit
    exit 1
}

# Clear log file
"Setup PC Home — started $(Get-Date)" | Out-File -FilePath $LOG_FILE -Force

Write-Log "`n===========================================" "Cyan"
Write-Log " NELSON FREIGHT — PC HOME SETUP v2" "Cyan"
Write-Log "===========================================`n" "Cyan"

# ════════════════════════════════════════════════
# STEP 1 — Prerequisites
# ════════════════════════════════════════════════
Write-Log "[1/9] Checking prerequisites..." "Yellow"

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

$checks = @{
    "git"    = "Git missing. Install: https://git-scm.com/download/win"
    "python" = "Python missing. Install: anaconda.com or python.org"
    "ssh"    = "SSH missing. Enable Windows Optional Feature: OpenSSH Client"
}

$missing = @()
foreach ($cmd in $checks.Keys) {
    if (Test-Command $cmd) {
        Write-Log "  OK $cmd" "Green"
    } else {
        Write-Log "  X  $cmd — $($checks[$cmd])" "Red"
        $missing += $cmd
    }
}

if ($missing.Count -gt 0) {
    Write-Log "`nInstall missing tools, then re-run this script." "Red"
    Wait-Before-Exit
    exit 1
}

# ════════════════════════════════════════════════
# STEP 2 — Verify SSH to GitHub (parse improved)
# ════════════════════════════════════════════════
Write-Log "`n[2/9] Testing SSH to GitHub..." "Yellow"

$sshKeyPath = "$env:USERPROFILE\.ssh\id_ed25519"
$sshKeyPathAlt = "$env:USERPROFILE\.ssh\id_rsa"
$sshKeyPathPchome = "$env:USERPROFILE\.ssh\id_pchome"

$hasKey = (Test-Path $sshKeyPath) -or (Test-Path $sshKeyPathAlt) -or (Test-Path $sshKeyPathPchome)

if (-not $hasKey) {
    Write-Log "  ! No SSH key found. Generating new one..." "Yellow"
    $email = Read-Host "  Enter your GitHub email (e.g., nelsonhuynhs@gmail.com)"
    if (-not $email) { $email = "pchome@nelson" }
    ssh-keygen -t ed25519 -C $email -f $sshKeyPath -N '""'
    Write-Log "  OK Key generated at $sshKeyPath" "Green"
    Write-Log "`n  ══════════════════════════════════════" "Cyan"
    Write-Log "  COPY THIS PUBLIC KEY to GitHub:" "Yellow"
    Write-Log "  https://github.com/settings/keys → New SSH key" "Yellow"
    Write-Log "  ══════════════════════════════════════`n" "Cyan"
    Get-Content "$sshKeyPath.pub" | Write-Host -ForegroundColor Green
    Write-Log "`n  Copy key → GitHub → paste → Save" "Yellow"
    Read-Host "`n  Press ENTER after you added key to GitHub"
}

# Test SSH — parse flexible
Write-Log "  Testing GitHub connection..." "Cyan"
$sshTest = ssh -T -o BatchMode=yes -o StrictHostKeyChecking=no git@github.com 2>&1 | Out-String
Write-Log "  SSH response: $sshTest" "Gray"

if ($sshTest -match "successfully authenticated" -or $sshTest -match "Hi .+!") {
    Write-Log "  OK SSH authenticated" "Green"
} else {
    Write-Log "  X  SSH test failed." "Red"
    Write-Log "  Possible causes:" "Yellow"
    Write-Log "    - Public key not added to GitHub yet" "Yellow"
    Write-Log "    - Firewall blocking port 22 (try: ssh -p 443 -T git@ssh.github.com)" "Yellow"
    Wait-Before-Exit
    exit 1
}

# ════════════════════════════════════════════════
# STEP 3 — Clone or pull repo
# ════════════════════════════════════════════════
Write-Log "`n[3/9] Cloning FreightBrian repo..." "Yellow"

if (-not (Test-Path $PARENT_DIR)) {
    New-Item -ItemType Directory -Path $PARENT_DIR -Force | Out-Null
    Write-Log "  Created parent dir: $PARENT_DIR" "Gray"
}

if (Test-Path "$TARGET_DIR\.git") {
    Write-Log "  Repo exists — pulling latest..." "Cyan"
    Set-Location $TARGET_DIR
    git pull origin main 2>&1 | Out-String | Write-Log
} else {
    Set-Location $PARENT_DIR
    Write-Log "  Cloning fresh..." "Cyan"
    git clone $REPO_URL Engine_test 2>&1 | Out-String | Write-Log
    Set-Location $TARGET_DIR
}

$commit = git log --oneline -1
Write-Log "  OK Latest commit: $commit" "Green"

# ════════════════════════════════════════════════
# STEP 4 — Install Python dependencies
# ════════════════════════════════════════════════
Write-Log "`n[4/9] Installing Python packages..." "Yellow"

$pkgs = @(
    "pandas", "openpyxl", "fastapi", "uvicorn", "filelock",
    "holidays", "rapidfuzz", "pywin32", "python-dateutil",
    "pydantic", "xlrd", "duckdb", "apscheduler", "requests",
    "python-dotenv"
)
Write-Log "  Installing: $($pkgs -join ', ')" "Gray"
pip install $pkgs --quiet --disable-pip-version-check 2>&1 | Out-String | Write-Log
Write-Log "  OK Dependencies installed" "Green"

# ════════════════════════════════════════════════
# STEP 5 — Environment variables
# ════════════════════════════════════════════════
Write-Log "`n[5/9] Setting environment variables..." "Yellow"

$envVars = @{
    "BOT_TOKEN"       = "8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys"
    "ADMIN_CHAT_ID"   = "5398948978"
    "NELSON_MACHINE"  = "pc-home"
}

foreach ($key in $envVars.Keys) {
    [System.Environment]::SetEnvironmentVariable($key, $envVars[$key], "User")
    Write-Log "  OK $key set" "Green"
}

# ════════════════════════════════════════════════
# STEP 6 — OneDrive check
# ════════════════════════════════════════════════
Write-Log "`n[6/9] Checking OneDrive sync..." "Yellow"

$onedriveFiles = @{
    "Contacts v6"    = "D:\OneDrive\NelsonData\email\contact_unified_v6.xlsx"
    "Pricing master" = "D:\OneDrive\NelsonData\pricing\Cleaned_Master_History.parquet"
}

foreach ($name in $onedriveFiles.Keys) {
    $path = $onedriveFiles[$name]
    if (Test-Path $path) {
        $size = [math]::Round((Get-Item $path).Length / 1MB, 1)
        Write-Log "  OK $name (${size}MB)" "Green"
    } else {
        Write-Log "  !  $name not synced yet" "Yellow"
        Write-Log "     Path: $path" "Gray"
    }
}

# ════════════════════════════════════════════════
# STEP 7 — .env secrets (manual)
# ════════════════════════════════════════════════
Write-Log "`n[7/9] Checking .env secrets..." "Yellow"

$envFiles = @(
    "$TARGET_DIR\email_engine\.env",
    "$TARGET_DIR\api\.env"
)

$envMissing = @()
foreach ($ef in $envFiles) {
    if (Test-Path $ef) {
        Write-Log "  OK $(Split-Path $ef -Leaf)" "Green"
    } else {
        Write-Log "  !  Missing: $ef" "Yellow"
        $envMissing += $ef
    }
}

if ($envMissing.Count -gt 0) {
    Write-Log "`n  Copy .env from Laptop VP manually (Telegram/USB/OneDrive)" "Yellow"
}

# ════════════════════════════════════════════════
# STEP 8 — Desktop shortcut
# ════════════════════════════════════════════════
Write-Log "`n[8/9] Creating Desktop shortcut..." "Yellow"

try {
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath "Nelson Email Dashboard.lnk"
    $wshell = New-Object -ComObject WScript.Shell
    $shortcut = $wshell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = "$TARGET_DIR\email_engine\start-dashboard-v4.bat"
    $shortcut.WorkingDirectory = "$TARGET_DIR\email_engine"
    $shortcut.Description = "Nelson Email Dashboard v6"
    $shortcut.Save()
    Write-Log "  OK Shortcut created at $shortcutPath" "Green"
} catch {
    Write-Log "  !  Shortcut creation failed: $_" "Yellow"
    Write-Log "     Create manually later" "Gray"
}

# ════════════════════════════════════════════════
# STEP 9 — Task Scheduler (SKIP by default)
# ════════════════════════════════════════════════
Write-Log "`n[9/9] Task Scheduler..." "Yellow"
Write-Log "  ! Skipping auto-register (Laptop VP still primary)" "Yellow"
Write-Log "  When switching PC Home → primary, run:" "Cyan"
Write-Log "    schtasks /Create /TN NelsonEmailRotation ``" "Gray"
Write-Log "      /TR 'D:\NELSON\2. Areas\Engine_test\scripts\daily-rotation-trigger.bat' ``" "Gray"
Write-Log "      /SC DAILY /ST 08:00 /RU Nelson" "Gray"

# ════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════
Write-Log "`n===========================================" "Cyan"
Write-Log " SETUP COMPLETE" "Green"
Write-Log "===========================================`n" "Cyan"

Write-Log "Next steps:" "Yellow"
if ($envMissing.Count -gt 0) {
    Write-Log "  1. Copy .env files from Laptop VP" "White"
}
Write-Log "  2. Close + reopen PowerShell (reload env vars)" "White"
Write-Log "  3. Test run:" "White"
Write-Log "     cd '$TARGET_DIR\email_engine'" "Gray"
Write-Log "     python web_server.py" "Gray"
Write-Log "     Open: http://localhost:8100/api/send-stats" "Gray"
Write-Log "     Expected: total=22842`n" "Gray"

Wait-Before-Exit
