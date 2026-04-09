#!/bin/bash
# ============================================================
#   GoClaw Worktree Helper — VPS
#   Manages git worktrees for GoClaw agents on VPS
#   Location: /opt/nelson/goclaw/worktree-helper.sh
#
#   Usage:
#     ./worktree-helper.sh create <name> [branch]
#     ./worktree-helper.sh list
#     ./worktree-helper.sh remove <name>
#     ./worktree-helper.sh status <name>
#     ./worktree-helper.sh sync
# ============================================================

set -e

GOCLAW_ROOT="/opt/nelson/goclaw"
REPO="$GOCLAW_ROOT/workspace/FreightBrian"
WORKTREES="$GOCLAW_ROOT/worktrees"
LOG="$GOCLAW_ROOT/logs/worktree.log"

log() { echo "$(date '+%H:%M:%S') | $*" | tee -a "$LOG"; }

# Ensure repo exists
if [ ! -d "$REPO/.git" ]; then
  echo "ERROR: Repo not found at $REPO — run goclaw-sync workflow first"
  exit 1
fi

cmd_create() {
  local NAME="$1"
  local BRANCH="${2:-goclaw/$NAME}"
  local WT_PATH="$WORKTREES/$NAME"

  if [ -z "$NAME" ]; then
    echo "Usage: $0 create <name> [branch]"
    exit 1
  fi

  if [ -d "$WT_PATH" ]; then
    echo "Worktree '$NAME' already exists at $WT_PATH"
    exit 1
  fi

  cd "$REPO"
  git fetch origin --prune

  # Create branch if not exists
  if git show-ref --verify --quiet "refs/heads/$BRANCH" 2>/dev/null; then
    git worktree add "$WT_PATH" "$BRANCH"
  elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH" 2>/dev/null; then
    git worktree add "$WT_PATH" -b "$BRANCH" "origin/$BRANCH"
  else
    git worktree add -b "$BRANCH" "$WT_PATH" HEAD
  fi

  log "CREATED worktree '$NAME' → $WT_PATH (branch: $BRANCH)"
  echo ""
  echo "Path: $WT_PATH"
  echo "Branch: $BRANCH"
  echo "Files: $(find "$WT_PATH" -maxdepth 1 -type f | wc -l) root files"
}

cmd_list() {
  cd "$REPO"
  echo "=== GoClaw Worktrees ==="
  echo ""

  git worktree list --porcelain | while IFS= read -r line; do
    case "$line" in
      worktree\ *)
        WT_PATH="${line#worktree }"
        ;;
      branch\ *)
        BRANCH="${line#branch refs/heads/}"
        NAME=$(basename "$WT_PATH")
        if [ "$WT_PATH" = "$REPO" ]; then
          echo "  [main repo] $WT_PATH ($BRANCH)"
        else
          COMMIT=$(cd "$WT_PATH" && git log -1 --pretty='%h %s' 2>/dev/null || echo "?")
          echo "  [$NAME] $WT_PATH"
          echo "    branch: $BRANCH"
          echo "    commit: $COMMIT"
          echo ""
        fi
        ;;
    esac
  done
}

cmd_remove() {
  local NAME="$1"
  local WT_PATH="$WORKTREES/$NAME"

  if [ -z "$NAME" ]; then
    echo "Usage: $0 remove <name>"
    exit 1
  fi

  if [ ! -d "$WT_PATH" ]; then
    echo "Worktree '$NAME' not found at $WT_PATH"
    exit 1
  fi

  cd "$REPO"
  git worktree remove "$WT_PATH" --force 2>/dev/null || rm -rf "$WT_PATH"
  git worktree prune

  log "REMOVED worktree '$NAME'"
  echo "Removed: $NAME"
}

cmd_status() {
  local NAME="$1"
  local WT_PATH="$WORKTREES/$NAME"

  if [ -z "$NAME" ] || [ ! -d "$WT_PATH" ]; then
    echo "Usage: $0 status <name>"
    echo "Worktree not found. Run '$0 list' to see available."
    exit 1
  fi

  cd "$WT_PATH"
  echo "=== Worktree: $NAME ==="
  echo "Path: $WT_PATH"
  echo "Branch: $(git branch --show-current)"
  echo "Commit: $(git log -1 --pretty='%h %s (%cr)')"
  echo ""
  echo "--- Changes ---"
  git status --short
  echo ""
  echo "--- Recent commits ---"
  git log --oneline -5
}

cmd_sync() {
  cd "$REPO"
  git fetch origin --prune
  git checkout main
  git reset --hard origin/main
  log "SYNCED main to $(git rev-parse --short HEAD)"
  echo "Main synced: $(git log -1 --pretty='%h %s')"

  # Update all worktrees
  echo ""
  echo "--- Updating worktrees ---"
  for wt in "$WORKTREES"/*/; do
    [ -d "$wt" ] || continue
    NAME=$(basename "$wt")
    cd "$wt"
    BRANCH=$(git branch --show-current)
    echo "  $NAME ($BRANCH): merging main..."
    git merge main --no-edit 2>/dev/null && echo "    OK" || echo "    CONFLICT — manual resolve needed"
  done
}

# Route commands
case "${1:-help}" in
  create) cmd_create "$2" "$3" ;;
  list)   cmd_list ;;
  remove) cmd_remove "$2" ;;
  status) cmd_status "$2" ;;
  sync)   cmd_sync ;;
  *)
    echo "GoClaw Worktree Helper"
    echo ""
    echo "Usage:"
    echo "  $0 create <name> [branch]  — Create new worktree"
    echo "  $0 list                    — List all worktrees"
    echo "  $0 remove <name>           — Remove worktree"
    echo "  $0 status <name>           — Show worktree status"
    echo "  $0 sync                    — Sync main + update worktrees"
    echo ""
    echo "Examples:"
    echo "  $0 create ui-review"
    echo "  $0 create fix-api goclaw/fix-api"
    echo "  $0 status ui-review"
    ;;
esac
