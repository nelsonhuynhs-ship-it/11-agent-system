#!/bin/bash
# check_data_freshness.sh — Alert if Parquet data is stale (> 72h)
# Runs via crontab every 6 hours
# 0 */6 * * * /home/nelson/scripts/check_data_freshness.sh >> /home/nelson/logs/freshness.log 2>&1

set -e

# Load env vars
if [ -f /home/nelson/.env ]; then
  source /home/nelson/.env
fi

# Check file age
PARQUET="/home/nelson/Pricing_Engine/data/Cleaned_Master_History.parquet"

if [ ! -f "$PARQUET" ]; then
  echo "[$(date)] ERROR: Parquet file not found at $PARQUET"
  exit 1
fi

# Calculate age in hours
MOD_EPOCH=$(stat -c %Y "$PARQUET")
NOW_EPOCH=$(date +%s)
AGE_SECONDS=$((NOW_EPOCH - MOD_EPOCH))
AGE_HOURS=$((AGE_SECONDS / 3600))

echo "[$(date)] Parquet age: ${AGE_HOURS}h"

# Alert if stale (> 72 hours) — DISABLED 2026-04-26, log only
if [ "$AGE_HOURS" -gt 72 ]; then
  echo "[$(date)] STALE: data ${AGE_HOURS}h old (telegram alert disabled)"
fi
