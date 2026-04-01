# ============================================
#   NELSON FREIGHT -- COWORK AUTO DEPLOY
#   Trigger: Cowork/Claude gọi script này
#   Flow: git commit+push → VPS tự pull → restart
#   Usage: powershell -ExecutionPolicy Bypass -File cowork_deploy.ps1
#          powershell -ExecutionPolicy Bypass -File cowork_deploy.ps1 -ApiOnly
#          powershell -ExecutionPolicy Bypass -File cowork_deploy.ps1 -WebOnly
#          powershell -ExecutionPolicy Bypass -File cowork_deploy.ps1 -Message "S14A: fix rate fallback"
# ============================================

param(
    [string]$Message = "",       # Custom commit message
    [switch]$ApiOnly,            # Chỉ restart API
    [switch]$WebOnly,            # Chỉ rebuild + restart WebApp
    [switch]$NoRestart,          # Push code thôi, không restart VPS
    [switch]$DryRun              # Simulate only, không thực sự deploy
)

$ErrorActionPreference = "Stop"

$REPO_PATH   = "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test"
$SSH_KEY     = "C:\Users\ADMIN\.ssh\id_nelson_vps_new"
$VPS_HOST    = "root@14.225.207.145"
$VPS_SCRIPT  = "/home/nelson/deploy.sh"
$LOG_FILE    = "$REPO_PATH\deploy\deploy_log.txt"

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

# ── Header ────────────────────────────────
Write-Log "============================================" "Cyan"
Write-Log "  NELSON FREIGHT COWORK DEPLOY" "Cyan"
Write-Log "  $(Get-Date)" "Cyan"
if ($DryRun) { Write-Log "  *** DRY RUN MODE ***" "Yellow" }
Write-Log "============================================" "Cyan"

# ── Step 1: Git status check ──────────────
Write-Log ""
Write-Log "[1/4] Checking git status..." "Yellow"
Set-Location $REPO_PATH

$status = git status --porcelain 2>&1
if ($status) {
    Write-Log "Changes detected:" "White"
    $status | ForEach-Object { Write-Log "  $_" "Gray" }

    # Build commit message
    if ($Message -eq "") {
        $date = Get-Date -Format "yyyy-MM-dd HH:mm"
        $Message = "deploy: auto $date"
    }

    if (-not $DryRun) {
        git add -A
        git commit -m $Message
        if ($LASTEXITCODE -ne 0) { Exit-Error "git commit failed" }
        Write-Log "[OK] Committed: $Message" "Green"
    } else {
        Write-Log "[DRY] Would commit: $Message" "Yellow"
    }
} else {
    Write-Log "[OK] No local changes -- using latest commit" "Green"
}

# ── Step 2: Git push ──────────────────────
Write-Log ""
Write-Log "[2/4] Pushing to GitHub..." "Yellow"

if (-not $DryRun) {
    git push origin main 2>&1
    if ($LASTEXITCODE -ne 0) { Exit-Error "git push failed -- check GitHub auth" }
    Write-Log "[OK] GitHub push done" "Green"
} else {
    Write-Log "[DRY] Would push to GitHub" "Yellow"
}

# ── Step 3: VPS Deploy ────────────────────
if ($NoRestart) {
    Write-Log ""
    Write-Log "[3/4] Skipping VPS restart (--NoRestart)" "Yellow"
} else {
    Write-Log ""
    Write-Log "[3/4] Deploying to VPS..." "Yellow"

    # Build VPS command based on flags
    if ($ApiOnly) {
        $vpsCmd = "cd /home/nelson && git pull origin main && systemctl restart nelson-api && sleep 3 && systemctl is-active nelson-api"
        Write-Log "Mode: API only restart" "Gray"
    } elseif ($WebOnly) {
        $vpsCmd = "cd /home/nelson && git pull origin main && cd webapp && npm run build && systemctl restart nelson-webapp3003 && sleep 3 && systemctl is-active nelson-webapp3003"
        Write-Log "Mode: WebApp rebuild + restart" "Gray"
    } else {
        # Full deploy -- dùng deploy.sh trên VPS
        $vpsCmd = "bash $VPS_SCRIPT"
        Write-Log "Mode: Full deploy (API + WebApp)" "Gray"
    }

    if (-not $DryRun) {
        $sshResult = ssh -i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=30 $VPS_HOST $vpsCmd 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Log "SSH output: $sshResult" "Red"
            Exit-Error "VPS deploy failed"
        }
        Write-Log $sshResult "Gray"
        Write-Log "[OK] VPS deploy done" "Green"
    } else {
        Write-Log "[DRY] Would SSH to $VPS_HOST and run: $vpsCmd" "Yellow"
    }
}

# ── Step 4: Health check ──────────────────
Write-Log ""
Write-Log "[4/4] Health check..." "Yellow"

if (-not $DryRun -and -not $NoRestart) {
    Start-Sleep -Seconds 5

    # Check API
    try {
        $apiResp = Invoke-WebRequest -Uri "http://14.225.207.145:8100/api/health/liveness" -TimeoutSec 10 -UseBasicParsing
        Write-Log "[OK] API: HTTP $($apiResp.StatusCode)" "Green"
    } catch {
        Write-Log "[WARN] API health check failed: $_" "Yellow"
    }

    # Check WebApp
    try {
        $webResp = Invoke-WebRequest -Uri "http://14.225.207.145:3003/login" -TimeoutSec 10 -UseBasicParsing
        Write-Log "[OK] WebApp: HTTP $($webResp.StatusCode)" "Green"
    } catch {
        Write-Log "[WARN] WebApp health check failed: $_" "Yellow"
    }
} else {
    Write-Log "[SKIP] Health check skipped" "Gray"
}

# ── Done ──────────────────────────────────
Write-Log ""
Write-Log "============================================" "Cyan"
Write-Log "  DEPLOY COMPLETE!" "Green"
Write-Log "  API:    http://14.225.207.145:8100" "Cyan"
Write-Log "  WebApp: http://14.225.207.145:3003" "Cyan"
Write-Log "  Domain: https://nelsonfreight.pro.vn" "Cyan"
Write-Log "============================================" "Cyan"
