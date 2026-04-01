#!/bin/bash
# Quick handoff update — run at end of each session
# Usage: bash scripts/handoff-update.sh "summary of what you did"

HANDOFF=".agent/handoff.md"
MACHINE=$(hostname)
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
SUMMARY="$1"

if [ -z "$SUMMARY" ]; then
    echo "Usage: bash scripts/handoff-update.sh \"what you did this session\""
    exit 1
fi

echo ""
echo "=== Updating handoff context ==="
echo "Machine: $MACHINE"
echo "Time: $TIMESTAMP"
echo "Summary: $SUMMARY"

git add "$HANDOFF"
git commit -m "handoff: $MACHINE -- $SUMMARY"
git push origin main

echo "=== Handoff pushed. Other machines can git pull to see context. ==="
