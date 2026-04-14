#!/bin/bash
# Setup Git repo + Nginx HTTPS for GoClaw on VPS
# Run: ssh root@14.225.207.145 'bash -s' < deploy/setup-vps-git-nginx.sh

set -e

echo "=== [1/4] Git setup ==="
cd /root/goclaw
if [ -d "goclaw-workspace" ]; then
  echo "goclaw-workspace already exists, pulling latest..."
  cd goclaw-workspace && git pull && cd ..
else
  echo "Cloning FreightBrian..."
  git clone https://github.com/nelsonhuynhs-ship-it/FrieghtBrian.git goclaw-workspace
fi
echo "[OK] Git repo ready at /root/goclaw/goclaw-workspace"

echo ""
echo "=== [2/4] Nginx config for goclaw.pudongprime.vn ==="
cat > /etc/nginx/sites-available/goclaw <<'NGINX'
server {
    listen 80;
    server_name goclaw.pudongprime.vn;

    location / {
        proxy_pass http://127.0.0.1:18790;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
NGINX

# Enable site
ln -sf /etc/nginx/sites-available/goclaw /etc/nginx/sites-enabled/goclaw
nginx -t && systemctl reload nginx
echo "[OK] Nginx HTTP proxy ready for goclaw.pudongprime.vn"

echo ""
echo "=== [3/4] SSL with Certbot ==="
if command -v certbot &> /dev/null; then
  certbot --nginx -d goclaw.pudongprime.vn --non-interactive --agree-tos -m nelsonhuynhs@gmail.com || echo "[WARN] Certbot failed — check DNS A record points to 14.225.207.145"
else
  echo "Installing certbot..."
  apt-get update -qq && apt-get install -y -qq certbot python3-certbot-nginx
  certbot --nginx -d goclaw.pudongprime.vn --non-interactive --agree-tos -m nelsonhuynhs@gmail.com || echo "[WARN] Certbot failed — check DNS A record points to 14.225.207.145"
fi

echo ""
echo "=== [4/4] Verify ==="
echo "Git:   $(ls /root/goclaw/goclaw-workspace/CLAUDE.md 2>/dev/null && echo 'OK' || echo 'MISSING')"
echo "Nginx: $(nginx -t 2>&1 | grep -c 'successful') config(s) OK"
echo ""
echo "DONE! Next: Add DNS A record goclaw.pudongprime.vn -> 14.225.207.145"
