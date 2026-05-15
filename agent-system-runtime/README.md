# Agent System Runtime Snapshot — v3

## What Is This

This folder is a **Git-tracked snapshot** of the live 11-agent orchestration runtime at:
```
C:\Users\Nelson\.claude\
  bin/mm-agent-spawner.sh
  bin/log-spawn.py
  agents-mm/*.md
```

The live runtime runs on this machine and is NOT auto-synced. This snapshot is
intentionally committed to the `11-agent-system` repo to preserve a stable version.

## Restore Procedure (if needed)

1. **Backup current runtime FIRST:**
   ```powershell
   Copy-Item -Recurse "$env:USERPROFILE\.claude" "$env:USERPROFILE\.claude-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
   ```

2. **Copy snapshot files to runtime:**
   ```powershell
   Copy-Item "D:\NELSON\2. Areas\Engine_test\agent-system-runtime\bin\mm-agent-spawner.sh" "$env:USERPROFILE\.claude\bin\mm-agent-spawner.sh"
   Copy-Item "D:\NELSON\2. Areas\Engine_test\agent-system-runtime\bin\log-spawn.py" "$env:USERPROFILE\.claude\bin\log-spawn.py"
   Copy-Item "D:\NELSON\2. Areas\Engine_test\agent-system-runtime\agents-mm\*.md" "$env:USERPROFILE\.claude\agents-mm\"
   ```

3. **Verify syntax:**
   ```bash
   bash -n "$USERPROFILE/.claude/bin/mm-agent-spawner.sh"
   pytest "D:\NELSON\2. Areas\Engine_test\tests\agent-system" -q
   ```

## IMPORTANT

- **Do NOT auto-overwrite runtime** unless you have confirmed backup.
- The live runtime at `C:\Users\Nelson\.claude` is the working copy — this snapshot is for
  reproducibility and disaster recovery only.
- To update the snapshot: edit files in `C:\Users\Nelson\.claude`, then re-copy to this folder.

## Contents

| File | Description |
|------|-------------|
| `bin/mm-agent-spawner.sh` | Routing engine for 11 MiniMax sub-agents |
| `bin/log-spawn.py` | SQLite + JSONL observability logger |
| `agents-mm/*.md` | Role templates with Claude Code-native frontmatter |

## Version

- Snapshot: v3
- Committed: 2026-05-15
- Live runtime: `C:\Users\Nelson\.claude`