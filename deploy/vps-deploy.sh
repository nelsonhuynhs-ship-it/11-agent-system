#!/bin/bash
# VPS Deploy Script — Nelson Freight
# Usage: ssh nelson@14.225.207.145 'bash -s' < deploy/vps-deploy.sh
set -e

echo "=== Nelson Freight VPS Deploy ==="
echo "Time: $(date)"

cd /home/nelson

# Pull latest
git pull origin main

# Verify required dirs
REQUIRED="api TelegramBot webapp ERP/intelligence ERP/carrier_rules Pricing_Engine/scripts Pricing_Engine/config"
echo ""
echo "=== Verify directories ==="
for dir in $REQUIRED; do
    if [ -d "$dir" ]; then echo "  ✅ $dir"
    else echo "  ❌ MISSING: $dir"; exit 1; fi
done

# Restart services
echo ""
echo "=== Restarting services ==="
sudo systemctl restart nelson-api
sudo systemctl restart nelson-bot
sudo systemctl restart nelson-webapp3003

# Health check
sleep 5
echo ""
echo "=== Health check ==="
API=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8100/api/health/liveness)
WEBAPP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3003/login)
echo "API: $API"
echo "WebApp: $WEBAPP"

echo ""
free -h
echo "=== Deploy complete ==="
