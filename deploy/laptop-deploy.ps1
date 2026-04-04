# ============================================
#   NELSON FREIGHT -- LAPTOP VP AUTO DEPLOY
#   Machine: LAPTOP-NO6F8IBP (Nelson)
#   SSH: ~/.ssh/id_ed25519 → nelson@14.225.207.145
#   Usage:
#     powershell -ExecutionPolicy Bypass -File deploy\laptop-deploy.ps1
#     powershell -ExecutionPolicy Bypass -File deploy\laptop-deploy.ps1 -ApiOnly
#     powershell -ExecutionPolicy Bypass -File deploy\laptop-deploy.ps1 -WebOnly
#     powershell -ExecutionPolicy Bypass -File deploy\laptop-deploy.ps1 -Message "feat: xyz"
# ============================================

param(
    [string]$Message = "",
    [switch]$ApiOnly,
    [switch]$WebOnly,
    [switch]$NoRestart,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ── AUTO-DETECT REPO PATH ──
$REPO_PATH = $PSScriptRoot | Split-Path -Parent
$SSH_KEY   = "$env:USERPROFILE\.ssh\id_ed25519"
$VPS_HOST  = "nelson-vps"
$LOG_FILE  = "$REPO_PATH\deploy\deploy_log.txt"

function Write-Log {
    param([string]$msg, [string]$color = "White")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $msg"
    Write-Host $line -ForegroundColor $color
    Add-Content -Path $LOG_FILE -Value $line -ErrorAction SilentlyContinue
}

function Exit-Error {
    param([string]$msg)
    Write-Log "ERROR: $msg" "Red"
    Write-Log "=== DEPLOY FAILED ===" "Red"
    exit 1
}

# ── Header ──
Write-Log "============================================" "Cyan"
Write-Log "  NELSON FREIGHT DEPLOY" "Cyan"
Write-Log "  Machine: $env:COMPUTERNAME" "Cyan"
Write-Log "  $(Get-Date)" "Cyan"
if ($DryRun) { Write-Log "  *** DRY RUN MODE ***" "Yellow" }
Write-Log "============================================" "Cyan"

# ── Step 1: Git commit + push ──
Write-Log ""
Write-Log "[1/4] Checking git status..." "Yellow"
Set-Location $REPO_PATH

$status = git status --porcelain 2>&1
if ($status) {
    Write-Log "Changes detected:" "White"
    $status | ForEach-Object { Write-Log "  $_" "Gray" }

    if ($Message -eq "") {
        $Message = "deploy: auto-deploy from $env:COMPUTERNAME $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    }

    if (-not $DryRun) {
        git add -A 2>&1 | Out-Null
        git commit -m $Message 2>&1 | Out-Null
        Write-Log "Committed: $Message" "Green"
    } else {
        Write-Log "[DRY] Would commit: $Message" "Yellow"
    }
} else {
    Write-Log "No local changes" "Gray"
}

# ── Step 2: Push ──
Write-Log ""
Write-Log "[2/4] Pushing to GitHub..." "Yellow"
if (-not $DryRun) {
    $pushResult = git push origin main 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Push output: $pushResult" "Gray"
        Exit-Error "Git push failed"
    }
    Write-Log "Pushed to origin/main" "Green"
} else {
    Write-Log "[DRY] Would push to origin/main" "Yellow"
}

# ── Step 3: SSH test ──
Write-Log ""
Write-Log "[3/4] Connecting to VPS..." "Yellow"

$sshTest = ssh -o ConnectTimeout=10 $VPS_HOST "echo SSH_OK" 2>&1
if ($sshTest -notmatch "SSH_OK") {
    Exit-Error "SSH connection failed: $sshTest`nRun: ssh nelson-vps 'echo test' to debug"
}
Write-Log "SSH connection OK" "Green"

# ── Step 4: Deploy on VPS ──
Write-Log ""
Write-Log "[4/4] Deploying on VPS..." "Yellow"

if ($ApiOnly) {
    $cmd = "cd /opt/nelson/code && git pull origin main 2>&1 && sudo systemctl restart nelson-api && echo 'API_RESTARTED'"
    $expect = "API_RESTARTED"
} elseif ($WebOnly) {
    $cmd = "cd /opt/nelson/code && git pull origin main 2>&1 && cd webapp && npm run build 2>&1 && sudo systemctl restart nelson-webapp3003 && echo 'WEBAPP_REBUILT'"
    $expect = "WEBAPP_REBUILT"
} elseif ($NoRestart) {
    $cmd = "cd /opt/nelson/code && git pull origin main 2>&1 && echo 'CODE_PULLED'"
    $expect = "CODE_PULLED"
} else {
    $cmd = "cd /opt/nelson/code && git pull origin main 2>&1 && sudo systemctl restart nelson-api && echo 'API_OK' && cd webapp && npm run build 2>&1 && sudo systemctl restart nelson-webapp3003 && echo 'DEPLOY_COMPLETE'"
    $expect = "DEPLOY_COMPLETE"
}

if ($DryRun) {
    Write-Log "[DRY] Would run on VPS: $cmd" "Yellow"
    Write-Log "=== DRY RUN COMPLETE ===" "Cyan"
    exit 0
}

$output = ssh $VPS_HOST $cmd 2>&1
$outputStr = $output -join "`n"

# Show last 10 lines
$lines = $outputStr -split "`n"
$tail = if ($lines.Count -gt 10) { $lines[-10..-1] } else { $lines }
$tail | ForEach-Object { Write-Log "  VPS: $_" "Gray" }

if ($outputStr -match $expect) {
    Write-Log ""
    Write-Log "=== DEPLOY SUCCESS ===" "Green"
    Write-Log "VPS: API port 8100 | WebApp port 3003" "Cyan"

    # Health check
    try {
        $health = ssh $VPS_HOST "curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/api/health" 2>&1
        Write-Log "API health: HTTP $health" $(if ($health -eq "200") { "Green" } else { "Yellow" })
    } catch {
        Write-Log "Health check skipped" "Gray"
    }
} else {
    Exit-Error "Deploy may have failed. Check VPS logs."
}
