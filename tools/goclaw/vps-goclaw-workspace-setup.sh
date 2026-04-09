#!/bin/bash
# ============================================================
#   GoClaw Workspace Setup — Run ONCE on VPS
#   Sets up directory structure + worktree helper + symlinks
#   so GoClaw agents can read code and work with worktrees
#
#   Usage: bash vps-goclaw-workspace-setup.sh
# ============================================================

set -e

echo "=== GoClaw Workspace Setup ==="
echo "VPS: $(hostname) | $(date '+%H:%M %d/%m/%Y')"

GOCLAW_ROOT="/opt/nelson/goclaw"
WORKSPACE="$GOCLAW_ROOT/workspace"
WORKTREES="$GOCLAW_ROOT/worktrees"
REPO="$WORKSPACE/FreightBrian"

# 1. Create directory structure
echo ""
echo "--- Creating directories ---"
mkdir -p "$WORKSPACE" "$WORKTREES" "$GOCLAW_ROOT/logs" "$GOCLAW_ROOT/plans" "$GOCLAW_ROOT/skills"
echo "[OK] Directory structure"

# 2. Clone repo if not exists
echo ""
echo "--- Setting up repo ---"
if [ ! -d "$REPO/.git" ]; then
  echo "Cloning repo (first time)..."
  if [ -d "/opt/nelson/code/.git" ]; then
    # Clone from local deploy copy (faster)
    git clone /opt/nelson/code "$REPO"
    cd "$REPO"
    git remote set-url origin "$(cd /opt/nelson/code && git remote get-url origin)"
  else
    echo "ERROR: /opt/nelson/code not found. Run deploy workflow first."
    exit 1
  fi
else
  cd "$REPO"
  git fetch origin --prune
  git reset --hard origin/main
fi
echo "[OK] Repo: $(git log -1 --pretty='%h %s')"

# 3. Install worktree helper
echo ""
echo "--- Installing worktree helper ---"
HELPER_SRC="$REPO/tools/goclaw/vps-worktree-helper.sh"
HELPER_DST="$GOCLAW_ROOT/worktree-helper.sh"

if [ -f "$HELPER_SRC" ]; then
  cp "$HELPER_SRC" "$HELPER_DST"
  chmod +x "$HELPER_DST"
  echo "[OK] Helper installed: $HELPER_DST"
else
  echo "[WARN] Helper not in repo yet — will be installed on next sync"
fi

# 4. Create convenience symlinks
echo ""
echo "--- Creating symlinks ---"

# Link plans directory
ln -sfn "$GOCLAW_ROOT/plans" "$WORKSPACE/plans" 2>/dev/null || true

# Link to main deploy code (read-only reference)
ln -sfn /opt/nelson/code "$GOCLAW_ROOT/deploy-code" 2>/dev/null || true

echo "[OK] Symlinks"

# 5. Create GoClaw exec wrapper for worktrees
cat > "$GOCLAW_ROOT/wt" << 'WRAPPER'
#!/bin/bash
# Quick alias: wt create|list|remove|status|sync
/opt/nelson/goclaw/worktree-helper.sh "$@"
WRAPPER
chmod +x "$GOCLAW_ROOT/wt"
echo "[OK] Quick command: $GOCLAW_ROOT/wt"

# 6. Add to PATH hint
echo ""
echo "--- PATH setup ---"
if ! grep -q "goclaw" /etc/profile.d/nelson.sh 2>/dev/null; then
  cat >> /etc/profile.d/nelson.sh << 'EOF'
# GoClaw workspace
export GOCLAW_ROOT="/opt/nelson/goclaw"
export GOCLAW_REPO="$GOCLAW_ROOT/workspace/FreightBrian"
export PATH="$GOCLAW_ROOT:$PATH"
EOF
  echo "[OK] Added GOCLAW_ROOT + wt to PATH"
else
  echo "[OK] PATH already configured"
fi

# 7. Summary
echo ""
echo "========================================="
echo "  GoClaw Workspace Ready!"
echo "========================================="
echo ""
echo "  Root:       $GOCLAW_ROOT"
echo "  Repo:       $REPO"
echo "  Worktrees:  $WORKTREES"
echo "  Helper:     $GOCLAW_ROOT/wt"
echo ""
echo "  Commands:"
echo "    wt create <name>     — New worktree"
echo "    wt list              — List all"
echo "    wt status <name>     — Check status"
echo "    wt sync              — Pull latest + update all"
echo "    wt remove <name>     — Cleanup"
echo ""
echo "  GitHub Actions: goclaw-sync workflow"
echo "  auto-syncs on every push to main"
echo ""
echo "========================================="
