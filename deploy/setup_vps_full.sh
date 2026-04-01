#!/bin/bash
# ═══════════════════════════════════════════════════════
# Nelson VPS Full Setup
# VPS: 14.225.207.145 (Ubuntu 24.04)
# Ports: Bot(none) Dashboard(8100) WebApp(3002)
# DO NOT use ports 3000/3001 — reserved for TraSuaPOS
# ═══════════════════════════════════════════════════════
set -e

echo "========================================="
echo "  N.E.L.S.O.N — VPS Full Setup"
echo "  IP: 14.225.207.145"
echo "  Ports: Dashboard=8100, WebApp=3002"
echo "  SAFE: 3000/3001 untouched (TraSuaPOS)"
echo "========================================="
echo ""

# ── System packages ──────────────────────────────────
echo "[1/8] Installing system packages..."
apt update -q
apt install -y python3 python3-pip python3-venv git rsync curl

# ── Node.js 20 for WebApp ───────────────────────────
echo "[2/8] Installing Node.js 20 + PM2..."
if ! command -v node &> /dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt install -y nodejs
fi
npm install -g pm2

# ── Directory structure ──────────────────────────────
echo "[3/8] Creating directory structure..."
mkdir -p /opt/nelson/{data,logs,memory,backup}

# ── Python virtual environment ───────────────────────
echo "[4/8] Setting up Python venv..."
if [ ! -d "/opt/nelson/venv" ]; then
  python3 -m venv /opt/nelson/venv
fi
/opt/nelson/venv/bin/pip install --upgrade pip -q

# ── Clone or update repo ────────────────────────────
echo "[5/8] Cloning/updating repo..."
if [ ! -d "/opt/nelson/.git" ]; then
  cd /opt
  git clone git@github.com:nelsonhuynhs-ship-it/FreightBrian.git nelson
  echo "  Repo cloned"
else
  cd /opt/nelson
  git pull origin main
  echo "  Repo updated"
fi

# ── Install Python deps ─────────────────────────────
echo "[6/8] Installing Python dependencies..."
/opt/nelson/venv/bin/pip install -r /opt/nelson/requirements_vps.txt -q

# ── Build WebApp ─────────────────────────────────────
echo "[7/8] Setting up WebApp..."
if [ -d "/opt/nelson/webapp" ]; then
  cd /opt/nelson/webapp
  npm install --silent
  npm run build
  pm2 delete nelson-webapp 2>/dev/null || true
  pm2 start npm --name nelson-webapp -- start -- -p 3002
  pm2 save
  pm2 startup systemd -u root --hp /root 2>/dev/null | tail -1 | bash 2>/dev/null || true
  echo "  WebApp running on port 3002"
  cd /opt/nelson
fi

# ── Systemd services ────────────────────────────────
echo "[8/8] Creating systemd services..."

# Nelson Bot v5
cat > /etc/systemd/system/nelson-bot.service << 'SVCEOF'
[Unit]
Description=Nelson Freight Bot v5
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/nelson/TelegramBot
EnvironmentFile=/opt/nelson/.env
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONUTF8=1
ExecStart=/opt/nelson/venv/bin/python bot_v5.py
Restart=always
RestartSec=15
StandardOutput=append:/opt/nelson/logs/bot.log
StandardError=append:/opt/nelson/logs/bot_error.log

[Install]
WantedBy=multi-user.target
SVCEOF

# Dashboard API (port 8100)
cat > /etc/systemd/system/nelson-dashboard.service << 'SVCEOF'
[Unit]
Description=Nelson Dashboard API
After=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/nelson/.agent/agents
EnvironmentFile=/opt/nelson/.env
Environment=PYTHONUTF8=1
ExecStart=/opt/nelson/venv/bin/uvicorn dashboard_api:app --host 0.0.0.0 --port 8100 --workers 2
Restart=always
RestartSec=5
StandardOutput=append:/opt/nelson/logs/dashboard.log
StandardError=append:/opt/nelson/logs/dashboard_error.log

[Install]
WantedBy=multi-user.target
SVCEOF

# ── Cron jobs ────────────────────────────────────────
cat > /etc/cron.d/nelson << 'CRONEOF'
SHELL=/bin/bash
PATH=/opt/nelson/venv/bin:/usr/bin:/bin
PYTHONUTF8=1

# Morning briefing (Email Engine mode: briefing)
0 7 * * * root cd /opt/nelson/email_engine && /opt/nelson/venv/bin/python run_all.py briefing >> /opt/nelson/logs/email_briefing.log 2>&1

# Email scan (mode: scan — safe, no send)
30 8 * * * root cd /opt/nelson/email_engine && /opt/nelson/venv/bin/python run_all.py scan >> /opt/nelson/logs/email_scan.log 2>&1

# Rate monitor — Monday
0 9 * * 1 root cd /opt/nelson && /opt/nelson/venv/bin/python Pricing_Engine/rate_monitor.py --check >> /opt/nelson/logs/rate_monitor.log 2>&1

# Rate monitor — Tue-Fri
0 9 * * 2-5 root cd /opt/nelson && /opt/nelson/venv/bin/python Pricing_Engine/rate_monitor.py --check >> /opt/nelson/logs/rate_monitor.log 2>&1

# Log rotation — weekly
0 2 * * 0 root find /opt/nelson/logs -name "*.log" -size +10M -exec truncate -s 1M {} \;
CRONEOF

# ── Enable and start ────────────────────────────────
systemctl daemon-reload
systemctl enable nelson-bot nelson-dashboard
systemctl start nelson-bot nelson-dashboard

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "  Bot:       $(systemctl is-active nelson-bot)"
echo "  Dashboard: $(systemctl is-active nelson-dashboard) → http://14.225.207.145:8100"
echo "  WebApp:    → http://14.225.207.145:3002"
echo ""
echo "  Next steps:"
echo "  1. cp /opt/nelson/deploy/.env.template /opt/nelson/.env"
echo "  2. nano /opt/nelson/.env  (fill TELEGRAM_CHAT_ID)"
echo "  3. systemctl restart nelson-bot nelson-dashboard"
echo "  4. Test: curl http://localhost:8100/agent/health"
echo ""
