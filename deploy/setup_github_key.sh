#!/bin/bash
# ═══════════════════════════════════════════
# Nelson — GitHub Deploy Key Setup
# Run on VPS first time only
# ═══════════════════════════════════════════
set -e

echo "=== Nelson Deploy Key Setup ==="
echo ""

# Generate SSH deploy key
if [ -f "/root/.ssh/github_nelson" ]; then
  echo "Key already exists at /root/.ssh/github_nelson"
  echo "Skipping generation."
else
  ssh-keygen -t ed25519 -C "nelson-vps-deploy" -f /root/.ssh/github_nelson -N ""
  echo "Key generated."
fi

# Add SSH config
if ! grep -q "github_nelson" /root/.ssh/config 2>/dev/null; then
  cat >> /root/.ssh/config << 'EOF'

# Nelson GitHub Deploy
Host github.com
  IdentityFile /root/.ssh/github_nelson
  StrictHostKeyChecking no
EOF
  chmod 600 /root/.ssh/config
  echo "SSH config updated."
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  STEP 1: Add PUBLIC key to GitHub"
echo "═══════════════════════════════════════════"
echo ""
echo "Go to: https://github.com/nelsonhuynhs-ship-it/FreightBrian/settings/keys"
echo "Click 'Add deploy key' → Title: 'Nelson VPS'"
echo "Paste this key:"
echo ""
cat /root/.ssh/github_nelson.pub
echo ""
echo ""
echo "═══════════════════════════════════════════"
echo "  STEP 2: Add PRIVATE key to GitHub Secrets"
echo "═══════════════════════════════════════════"
echo ""
echo "Go to: https://github.com/nelsonhuynhs-ship-it/FreightBrian/settings/secrets/actions"
echo "New secret name: VPS_SSH_KEY"
echo "Paste the content below (including BEGIN/END lines):"
echo ""
cat /root/.ssh/github_nelson
echo ""
echo ""
echo "═══════════════════════════════════════════"
echo "  STEP 3: Add Telegram secrets"
echo "═══════════════════════════════════════════"
echo ""
echo "Also add these GitHub Secrets:"
echo "  TELEGRAM_BOT_TOKEN → 8697753100:AAF0HVN0VxK-ilyz_GUdE_JOCSr3D3QCFys"
echo "  TELEGRAM_CHAT_ID   → 5398948978"
echo ""
echo "=== Done! Run setup_vps_full.sh next ==="
