#!/usr/bin/env bash
# install-pre-commit-hook.sh — Install git pre-commit hook that runs validate-system.py
# Run once: bash scripts/install-pre-commit-hook.sh

set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "Not in a git repository — skipping hook install"
    exit 0
fi

HOOK_FILE="$REPO_ROOT/.git/hooks/pre-commit"
cat > "$HOOK_FILE" << 'EOF'
#!/usr/bin/env bash
# Auto-installed by scripts/install-pre-commit-hook.sh — validates SYSTEM_STANDARDS rules
echo "[pre-commit] Validating SYSTEM_STANDARDS..."
python "$(git rev-parse --show-toplevel)/scripts/validate-system.py" || {
    echo ""
    echo "[pre-commit] FAILED — fix violations above or commit with --no-verify (NOT recommended)"
    exit 1
}
echo "[pre-commit] OK — all rules pass"
EOF

chmod +x "$HOOK_FILE"
echo "Installed pre-commit hook at: $HOOK_FILE"
echo "It will run scripts/validate-system.py before every commit."
