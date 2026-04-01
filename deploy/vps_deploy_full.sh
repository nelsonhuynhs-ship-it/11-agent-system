#!/bin/bash
# ============================================
#   NELSON FREIGHT — VPS DEPLOY SCRIPT
#   Chạy trên VPS: bash /home/nelson/deploy.sh
#   Được gọi bởi cowork_deploy.ps1 qua SSH
# ============================================
set -e

echo ""
echo "============================================"
echo "  NELSON FREIGHT VPS DEPLOY"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

REPO="/home/nelson"
API_SERVICE="nelson-api"
WEB_SERVICE="nelson-webapp3003"

cd $REPO

# ── Step 1: Git pull ─────────────────────
echo ""
echo "[1/4] Git pull..."
git pull origin main
echo "[OK] Code updated"

# ── Step 2: Copy files if needed ─────────
echo ""
echo "[2/4] Syncing files..."

# Copy API router (S14A fix)
if [ -f "Engine_test/api/routers/email_rate_router.py" ]; then
    cp Engine_test/api/routers/email_rate_router.py api/routers/email_rate_router.py
    echo "  ✅ email_rate_router.py synced"
fi

echo "[OK] Files synced"

# ── Step 3: Restart services ─────────────
echo ""
echo "[3/4] Restarting services..."

systemctl restart $API_SERVICE
sleep 2
API_STATUS=$(systemctl is-active $API_SERVICE)
echo "  nelson-api: $API_STATUS"

# Chỉ rebuild webapp nếu có thay đổi Next.js
if git diff HEAD~1 HEAD --name-only 2>/dev/null | grep -q "^webapp/"; then
    echo "  WebApp changes detected — rebuilding..."
    cd /home/nelson/webapp
    npm run build
    cd $REPO
    systemctl restart $WEB_SERVICE
    sleep 3
    WEB_STATUS=$(systemctl is-active $WEB_SERVICE)
    echo "  nelson-webapp3003: $WEB_STATUS (rebuilt)"
else
    systemctl restart $WEB_SERVICE
    sleep 2
    WEB_STATUS=$(systemctl is-active $WEB_SERVICE)
    echo "  nelson-webapp3003: $WEB_STATUS (restarted, no rebuild)"
fi

# ── Step 4: Health check ─────────────────
echo ""
echo "[4/4] Health check..."

API_HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8100/api/health/liveness 2>/dev/null || echo "000")
WEB_HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3003/login 2>/dev/null || echo "000")

echo "  API:    HTTP $API_HTTP"
echo "  WebApp: HTTP $WEB_HTTP"

# Memory usage
echo ""
echo "  Memory: $(free -h | grep Mem | awk '{print $3"/"$2}')"

if [ "$API_HTTP" = "200" ] || [ "$API_HTTP" = "307" ]; then
    echo ""
    echo "============================================"
    echo "  ✅ DEPLOY COMPLETE"
    echo "  API:    http://14.225.207.145:8100"
    echo "  WebApp: http://14.225.207.145:3003"
    echo "============================================"
else
    echo ""
    echo "  ⚠ WARNING: API returned HTTP $API_HTTP"
    echo "  Check: journalctl -u nelson-api -n 20"
    exit 1
fi
