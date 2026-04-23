#!/bin/bash
# pre-commit hook — validate data contracts + check docs staleness
#
# Install (run once from repo root):
#   cp scripts/pre-commit.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# To bypass in emergency (not recommended):
#   git commit --no-verify -m "..."

set -e

PYTHON="python"

# Detect Anaconda python on Windows if available
if command -v "C:/Users/Nelson/anaconda3/python" &>/dev/null; then
    PYTHON="C:/Users/Nelson/anaconda3/python"
fi

# 1. Contract validation — BLOCKS commit if schema drift detected
echo "[pre-commit] Running data contract validation..."
"$PYTHON" scripts/validate-data-contracts.py

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "[pre-commit] BLOCKED: data contract validation failed."
    echo "             Fix the issues above before committing."
    echo "             To skip (emergency only): git commit --no-verify"
    exit 1
fi

echo "[pre-commit] Contracts OK."

# 2. Docs staleness — WARNS only, does not block commit
echo "[pre-commit] Checking docs staleness..."
"$PYTHON" scripts/check-docs-staleness.py

echo "[pre-commit] Done — proceeding with commit."
exit 0
