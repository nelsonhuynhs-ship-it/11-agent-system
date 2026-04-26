#!/bin/bash
# =========================================================
# vps-rclone-setup.sh — Setup rclone OneDrive → VPS sync
# =========================================================
# Đây là CON ĐƯỜNG DUY NHẤT để data từ PC → VPS
# Data KHÔNG đi qua GitHub — chỉ OneDrive → rclone → VPS
#
# CÁCH DÙNG (3 bước):
#
#   BƯỚC 1 — Trên PC Home (có browser):
#     choco install rclone    (hoặc download từ rclone.org)
#     rclone authorize "onedrive"
#     → Browser mở → login Microsoft → copy TOÀN BỘ token JSON
#
#   BƯỚC 2 — SSH vào VPS:
#     ssh root@14.225.207.145
#     curl -O https://raw.githubusercontent.com/nelsonhuynhs-ship-it/FrieghtBrian/main/deploy/vps-rclone-setup.sh
#     bash vps-rclone-setup.sh
#     → Khi hỏi token: paste token từ Bước 1
#
#   BƯỚC 3 — Verify:
#     tail -f /opt/nelson/sync/rclone.log
#     ls -la /opt/nelson/data/pricing/
#     ls -la /opt/nelson/data/email/
#
# KẾT QUẢ: Mỗi 15 phút, OneDrive/NelsonData tự sync → VPS
#           Docker container đọc /opt/nelson/data (readonly mount)
#           API + WebApp tự thấy data mới, KHÔNG cần restart
# =========================================================

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║   Nelson VPS rclone OneDrive Setup           ║"
echo "║   OneDrive/NelsonData → /opt/nelson/data     ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Install rclone ──────────────────────────────────
if ! command -v rclone &>/dev/null; then
  echo "[1/7] Installing rclone..."
  curl -s https://rclone.org/install.sh | bash
  echo "  Installed: $(rclone version | head -1)"
else
  echo "[1/7] rclone OK: $(rclone version | head -1)"
fi

# ── Step 2: Create directory structure ──────────────────────
echo "[2/7] Creating directories..."
mkdir -p /opt/nelson/sync
mkdir -p /opt/nelson/data/{pricing,email,assets,bot,erp}
mkdir -p /opt/nelson/data/pricing/{rate-tables,mapping}
mkdir -p /opt/nelson/data/email/panjiva
echo "  /opt/nelson/data/ structure created"

# ── Step 3: Configure OneDrive remote ──────────────────────
if rclone listremotes 2>/dev/null | grep -q "^onedrive:"; then
  echo "[3/7] OneDrive remote already configured"
else
  echo "[3/7] Configuring OneDrive remote..."
  echo ""
  echo "  ┌─────────────────────────────────────────────┐"
  echo "  │  BẠN CẦN TOKEN TỪ PC HOME TRƯỚC!            │"
  echo "  │                                              │"
  echo "  │  Trên PC Home chạy:                          │"
  echo "  │    rclone authorize \"onedrive\"               │"
  echo "  │                                              │"
  echo "  │  Browser mở → login Microsoft account        │"
  echo "  │  Copy TOÀN BỘ JSON token (bắt đầu bằng {)   │"
  echo "  └─────────────────────────────────────────────┘"
  echo ""
  echo "  Bây giờ chạy: rclone config"
  echo "  Chọn: n (New remote) → name: onedrive → type: onedrive"
  echo "  Khi hỏi token → paste token JSON từ PC Home"
  echo "  Chọn: onedrive (Personal)"
  echo ""
  read -p "  Bấm Enter để mở rclone config..." _
  rclone config
fi

# ── Step 4: Verify connection ──────────────────────────────
echo "[4/7] Testing OneDrive connection..."
echo "  Listing onedrive:NelsonData..."
if rclone lsd onedrive:NelsonData 2>/dev/null; then
  echo "  OK: OneDrive NelsonData accessible"
  echo ""
  echo "  Folders found:"
  rclone lsd onedrive:NelsonData 2>/dev/null | awk '{print "    " $NF}'
else
  echo ""
  echo "  FAIL: Cannot access onedrive:NelsonData"
  echo "  Troubleshoot:"
  echo "    1. rclone config show    — check remote exists"
  echo "    2. rclone lsd onedrive:  — check root access"
  echo "    3. Make sure OneDrive folder is named exactly 'NelsonData'"
  exit 1
fi

# ── Step 5: Check critical files exist on OneDrive ─────────
echo "[5/7] Checking critical files on OneDrive..."
CRITICAL_OK=true

for f in "pricing/Cleaned_Master_History.parquet" \
         "email/contact_unified_v7.xlsx"; do
  if rclone ls "onedrive:NelsonData/$f" &>/dev/null; then
    SIZE=$(rclone ls "onedrive:NelsonData/$f" 2>/dev/null | awk '{print $1}')
    echo "  OK: $f ($(numfmt --to=iec $SIZE 2>/dev/null || echo "${SIZE} bytes"))"
  else
    echo "  MISSING: $f"
    CRITICAL_OK=false
  fi
done

if [ "$CRITICAL_OK" = false ]; then
  echo ""
  echo "  WARNING: Some critical files missing on OneDrive."
  echo "  Sync will still work, but API may not function correctly."
  echo "  Make sure OneDrive/NelsonData has:"
  echo "    pricing/Cleaned_Master_History.parquet"
  echo "    email/contact_unified_v7.xlsx"
  read -p "  Continue anyway? (y/n) " CONTINUE
  [ "$CONTINUE" != "y" ] && exit 1
fi

# ── Step 6: Create sync script ─────────────────────────────
echo "[6/7] Creating sync script..."

cat > /opt/nelson/sync/rclone-data.sh << 'SYNCSCRIPT'
#!/bin/bash
# ═══════════════════════════════════════════════════════════
# rclone-data.sh — Sync OneDrive/NelsonData → /opt/nelson/data
# Runs every 15 min via cron. Telegram alerts disabled 2026-04-26.
# ═══════════════════════════════════════════════════════════

LOG="/opt/nelson/sync/rclone.log"
FAIL_COUNT_FILE="/opt/nelson/sync/fail_count"
LAST_SUCCESS_FILE="/opt/nelson/sync/last_success"

log_msg() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

log_msg "START sync"

# ── Run rclone sync ────────────────────────────────────────
if rclone sync onedrive:NelsonData /opt/nelson/data \
  --exclude "*.tmp" \
  --exclude "~\$*" \
  --exclude ".~lock.*" \
  --exclude "*.lnk" \
  --exclude "Thumbs.db" \
  --exclude ".DS_Store" \
  --log-file "$LOG" \
  --log-level NOTICE \
  --transfers 4 \
  --checkers 8 \
  --timeout 180s \
  --retries 3 \
  --retries-sleep 10s \
  --low-level-retries 5; then

  echo "0" > "$FAIL_COUNT_FILE"
  date '+%Y-%m-%d %H:%M' > "$LAST_SUCCESS_FILE"
  log_msg "OK sync complete"

  PARQUET="/opt/nelson/data/pricing/Cleaned_Master_History.parquet"
  CNEE="/opt/nelson/data/email/contact_unified_v7.xlsx"
  [ ! -f "$PARQUET" ] && log_msg "WARN: parquet missing after sync"
  [ ! -f "$CNEE" ] && log_msg "WARN: contact_unified_v7 missing after sync"
else
  COUNT=$(cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0)
  COUNT=$((COUNT + 1))
  echo "$COUNT" > "$FAIL_COUNT_FILE"
  log_msg "FAIL #$COUNT"
fi

# ── Log rotation (keep under 1MB) ─────────────────────────
if [ -f "$LOG" ]; then
  LOG_SIZE=$(wc -c < "$LOG" 2>/dev/null || echo 0)
  if [ "$LOG_SIZE" -gt 1048576 ]; then
    tail -500 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
    log_msg "Log rotated (was ${LOG_SIZE} bytes)"
  fi
fi
SYNCSCRIPT

chmod +x /opt/nelson/sync/rclone-data.sh
echo "  Created /opt/nelson/sync/rclone-data.sh"

# ── Create .env for Telegram ───────────────────────────────
if [ ! -f /opt/nelson/sync/.env ]; then
  cat > /opt/nelson/sync/.env << 'ENVFILE'
# Telegram credentials for sync alerts
# Get from GitHub repo secrets or bot settings
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
ENVFILE
  echo ""
  echo "  IMPORTANT: Fill /opt/nelson/sync/.env with Telegram credentials!"
  echo "  nano /opt/nelson/sync/.env"
else
  echo "  /opt/nelson/sync/.env already exists"
fi

# Init state files
echo "0" > /opt/nelson/sync/fail_count
date '+%Y-%m-%d %H:%M' > /opt/nelson/sync/last_success

# ── Step 7: Setup cron ─────────────────────────────────────
echo "[7/7] Setting up cron..."
CRON_LINE="*/15 * * * * /opt/nelson/sync/rclone-data.sh"

if crontab -l 2>/dev/null | grep -q "rclone-data.sh"; then
  echo "  Cron already exists"
else
  (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
  echo "  Cron added: every 15 min"
fi

# ── First sync (dry-run) ──────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   DRY RUN — Preview what will sync           ║"
echo "╚══════════════════════════════════════════════╝"
rclone sync onedrive:NelsonData /opt/nelson/data \
  --exclude "*.tmp" --exclude "~\$*" --exclude ".~lock.*" --exclude "*.lnk" \
  --dry-run --progress 2>&1 | tail -20

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   Setup Complete!                             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  FILES:"
echo "    Sync script : /opt/nelson/sync/rclone-data.sh"
echo "    Config      : /opt/nelson/sync/.env"
echo "    Log         : /opt/nelson/sync/rclone.log"
echo "    State       : /opt/nelson/sync/{fail_count,last_success}"
echo ""
echo "  COMMANDS:"
echo "    Run sync now     : /opt/nelson/sync/rclone-data.sh"
echo "    Monitor log      : tail -f /opt/nelson/sync/rclone.log"
echo "    Check cron       : crontab -l"
echo "    Check data       : ls -la /opt/nelson/data/pricing/"
echo "    Re-authorize     : rclone config reconnect onedrive:"
echo ""
echo "  FLOW:"
echo "    PC save to OneDrive/NelsonData/"
echo "      → rclone sync every 15min"
echo "      → /opt/nelson/data/"
echo "      → Docker reads /data (readonly mount)"
echo "      → API + WebApp shows new data"
echo "      → NO restart needed"
echo ""
echo "  NEXT: Fill Telegram credentials:"
echo "    nano /opt/nelson/sync/.env"
echo ""
echo "  Then run first REAL sync:"
echo "    /opt/nelson/sync/rclone-data.sh"
