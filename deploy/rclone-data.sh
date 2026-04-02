#!/bin/bash
# ══════════════════════════════════════════════════════════════
# rclone-data.sh — Sync OneDrive data to VPS /opt/nelson/data
# ══════════════════════════════════════════════════════════════
# Cron: */15 * * * * /opt/nelson/sync/rclone-data.sh >> /opt/nelson/local/logs/rclone.log 2>&1
#
# Setup (one-time on VPS):
#   1. Install rclone: curl https://rclone.org/install.sh | sudo bash
#   2. Configure OneDrive: rclone config  (choose "onedrive" remote)
#   3. Copy this script: cp deploy/rclone-data.sh /opt/nelson/sync/
#   4. Add cron: crontab -e → */15 * * * * /opt/nelson/sync/rclone-data.sh >> /opt/nelson/local/logs/rclone.log 2>&1

set -euo pipefail

REMOTE="onedrive"
DATA_DIR="/opt/nelson/data"
LOG_PREFIX="[rclone $(date '+%Y-%m-%d %H:%M')]"

echo "$LOG_PREFIX Starting data sync..."

# Pricing data (parquet + mapping)
rclone sync "$REMOTE:NelsonData/pricing" "$DATA_DIR/pricing" \
    --transfers 4 --checkers 8 --log-level NOTICE

# Email data (masters + config)
rclone sync "$REMOTE:NelsonData/email" "$DATA_DIR/email" \
    --transfers 4 --checkers 8 --log-level NOTICE

# Assets (PDF, logo, template)
rclone sync "$REMOTE:NelsonData/assets" "$DATA_DIR/assets" \
    --transfers 2 --log-level NOTICE

# Bot data
rclone sync "$REMOTE:NelsonData/bot" "$DATA_DIR/bot" \
    --transfers 2 --log-level NOTICE

echo "$LOG_PREFIX Sync complete."
