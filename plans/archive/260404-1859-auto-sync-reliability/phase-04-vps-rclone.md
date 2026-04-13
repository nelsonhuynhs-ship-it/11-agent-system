# Phase 4: VPS rclone OneDrive Setup Guide

## Context
- [project-code-data-separation.md](memory) ghi: "VPS: rclone from OneDrive every 15 min" — PENDING
- Data trên VPS hiện phụ thuộc sync-data.yml (GitHub Release) → chỉ có parquet + xlsx
- rclone sẽ sync toàn bộ OneDrive/NelsonData/ → /opt/nelson/data/ realtime

## Overview
- **Priority:** P1
- **Status:** ⬜ TODO
- **Description:** Tạo guide + script để Nelson cài rclone trên VPS, config OneDrive remote, cron 15min

## Key Insights
- rclone hỗ trợ OneDrive (Personal) natively
- Auth flow cần browser → phải authorize trên PC rồi copy config lên VPS
- OneDrive/NelsonData chứa: pricing/, email/, assets/, bot/, erp/
- Sync 1 chiều: OneDrive → VPS (VPS không push ngược)
- Bandwidth: NelsonData ~500MB → 15min sync chỉ transfer diff

## Requirements

### Functional
- rclone sync OneDrive:NelsonData → /opt/nelson/data/ mỗi 15 phút
- Exclude: `*.tmp`, `~$*`, `.~lock.*` (Office temp files)
- Log mỗi lần sync vào /opt/nelson/sync/rclone.log
- Telegram alert nếu sync fail 3 lần liên tiếp

### Non-functional
- Bandwidth efficient (chỉ transfer changed files)
- Không ảnh hưởng existing Docker containers

## Architecture
```
OneDrive (NelsonData/)
    ↓ rclone sync (every 15min via cron)
VPS /opt/nelson/data/
    ├── pricing/    (parquet, rate-tables, mapping)
    ├── email/      (cnee_master, contact_master, rules)
    ├── assets/     (logo, PDF, templates)
    ├── bot/        (carrier_tips)
    └── erp/        (ERP data)
    ↓ mounted into Docker containers
nelson-api + nelson-webapp read from /opt/nelson/data/
```

## Implementation Steps (Manual — Nelson thực hiện trên VPS)

### Step 1: Install rclone on VPS
```bash
ssh root@14.225.207.145
curl https://rclone.org/install.sh | bash
rclone version
```

### Step 2: Authorize OneDrive on PC (có browser)
```bash
# Trên PC Home (có browser):
rclone authorize "onedrive"
# → Browser mở → đăng nhập Microsoft → copy token JSON
```

### Step 3: Configure rclone on VPS
```bash
# Trên VPS:
rclone config
# → New remote → name: onedrive → type: onedrive
# → Paste token từ Step 2
# → Choose: OneDrive Personal
# → Confirm
```

### Step 4: Test sync
```bash
# Dry run first
rclone sync onedrive:NelsonData /opt/nelson/data \
  --exclude "*.tmp" --exclude "~$*" --exclude ".~lock.*" \
  --dry-run --progress

# Real sync
rclone sync onedrive:NelsonData /opt/nelson/data \
  --exclude "*.tmp" --exclude "~$*" --exclude ".~lock.*" \
  --progress
```

### Step 5: Create sync script
```bash
cat > /opt/nelson/sync/rclone-data.sh << 'EOF'
#!/bin/bash
LOG="/opt/nelson/sync/rclone.log"
FAIL_COUNT="/opt/nelson/sync/fail_count"

echo "$(date '+%Y-%m-%d %H:%M') START" >> "$LOG"

if rclone sync onedrive:NelsonData /opt/nelson/data \
  --exclude "*.tmp" --exclude "~$*" --exclude ".~lock.*" \
  --log-file "$LOG" --log-level NOTICE \
  --transfers 4 --checkers 8; then
  echo "0" > "$FAIL_COUNT"
  echo "$(date '+%Y-%m-%d %H:%M') OK" >> "$LOG"
else
  COUNT=$(cat "$FAIL_COUNT" 2>/dev/null || echo 0)
  COUNT=$((COUNT + 1))
  echo "$COUNT" > "$FAIL_COUNT"
  echo "$(date '+%Y-%m-%d %H:%M') FAIL #$COUNT" >> "$LOG"

  # Alert after 3 consecutive failures
  if [ "$COUNT" -ge 3 ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d chat_id="${TELEGRAM_CHAT_ID}" \
      -d text="⚠ rclone sync FAIL $COUNT lần liên tiếp! Check VPS log."
  fi
fi

# Keep log under 1MB
tail -1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
EOF
chmod +x /opt/nelson/sync/rclone-data.sh
```

### Step 6: Setup cron
```bash
mkdir -p /opt/nelson/sync
echo "0" > /opt/nelson/sync/fail_count

# Add to crontab
(crontab -l 2>/dev/null; echo "*/15 * * * * /opt/nelson/sync/rclone-data.sh") | crontab -

# Verify
crontab -l
```

### Step 7: Set env vars for Telegram alert
```bash
# Add to /etc/environment or crontab:
TELEGRAM_BOT_TOKEN=<from GitHub secrets>
TELEGRAM_CHAT_ID=<from GitHub secrets>
```

## Todo
- [ ] Install rclone on VPS
- [ ] Authorize OneDrive from PC Home browser
- [ ] Configure rclone remote on VPS
- [ ] Test dry-run sync
- [ ] Create /opt/nelson/sync/rclone-data.sh
- [ ] Setup cron */15 * * * *
- [ ] Verify first automated sync
- [ ] Confirm Telegram alert works on failure

## Success Criteria
- `rclone sync` runs every 15 min via cron
- /opt/nelson/data/ mirrors OneDrive/NelsonData/
- Telegram alert fires after 3 consecutive failures
- Log rotation keeps rclone.log under 1MB

## Risk Assessment
- **OneDrive token expiry:** rclone auto-refreshes OAuth token, but if refresh fails → manual re-auth needed
- **Bandwidth:** First sync ~500MB, after that chỉ diff → minimal bandwidth
- **Disk space VPS:** NelsonData ~500MB, VPS có đủ space
- **Docker volumes:** Docker compose cần mount /opt/nelson/data/ → check docker-compose.yml volumes

## Relationship to Phase 1
Sau khi rclone hoạt động:
- Phase 1 (sync-data.yml) vẫn cần cho parquet slim (processed version)
- rclone sync raw data (original files)
- Hai hệ thống bổ sung nhau, không conflict
