#!/bin/bash
# check-gh-token.sh — Verify GH_DEPLOY_TOKEN is valid for sync + deploy
# Usage: bash deploy/check-gh-token.sh
# Or run via: gh workflow run sync-data.yml (tests token implicitly)

REPO="nelsonhuynhs-ship-it/FrieghtBrian"
TAG="data-sync-v1"

echo "=== GH_DEPLOY_TOKEN Health Check ==="

# 1. Check if gh CLI is authenticated
if ! gh auth status &>/dev/null; then
  echo "WARN: gh CLI not authenticated (optional)"
fi

# 2. Try listing release assets (tests token via gh CLI)
echo ""
echo "--- Release Assets (data-sync-v1) ---"
gh release view "$TAG" --repo "$REPO" --json assets --jq '.assets[] | "\(.name) (\(.size) bytes)"' 2>/dev/null || echo "FAIL: Cannot access release. Token may be expired."

# 3. Check token type from GitHub Actions secrets page
echo ""
echo "--- Manual Steps ---"
echo "1. Go to: https://github.com/$REPO/settings/secrets/actions"
echo "2. Check GH_DEPLOY_TOKEN — edit to see type:"
echo "   - github_pat_* = Fine-grained PAT (recommended)"
echo "   - ghp_*        = Classic PAT (OK but broad scope)"
echo "   - gho_*        = OAuth token (SHORT-LIVED — replace ASAP!)"
echo ""
echo "3. If expired, create new:"
echo "   → https://github.com/settings/tokens?type=beta"
echo "   → Name: nelson-freight-deploy"
echo "   → Expiry: 90 days"
echo "   → Repo: $REPO only"
echo "   → Permissions: Contents (Read & Write)"
echo ""
echo "=== Done ==="
