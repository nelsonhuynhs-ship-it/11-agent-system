---
name: GoClaw Worktree Manager
description: Manage git worktrees on VPS for isolated code work — create, list, switch, sync, and cleanup worktrees
---

## Instructions

You are a GoClaw agent with access to git worktrees on VPS. Worktrees let you work on code in isolation without affecting the main branch or other agents' work.

### Paths

| Item | Path |
|------|------|
| Main repo | `/opt/nelson/goclaw/workspace/FreightBrian` |
| Worktrees | `/opt/nelson/goclaw/worktrees/<name>/` |
| Deploy code (read-only) | `/opt/nelson/code` |
| Helper script | `/opt/nelson/goclaw/wt` |
| Logs | `/opt/nelson/goclaw/logs/` |
| Plans | `/opt/nelson/goclaw/plans/` |

### Quick Commands

```bash
# Create new worktree for a task
wt create ui-review

# Create with specific branch
wt create fix-api goclaw/fix-api

# List all worktrees
wt list

# Check status of a worktree
wt status ui-review

# Sync main branch + update all worktrees
wt sync

# Remove when done
wt remove ui-review
```

### Workflow

1. **Start task** → `wt create <task-name>`
2. **Work in worktree** → `cd /opt/nelson/goclaw/worktrees/<task-name>/`
3. **Edit files** → make changes, test
4. **Commit** → `git add . && git commit -m "feat: description"`
5. **Push branch** → `git push origin goclaw/<task-name>`
6. **Done** → `wt remove <task-name>` (or keep for review)

### Rules

- NEVER work directly in main repo (`/opt/nelson/goclaw/workspace/FreightBrian`)
- ALWAYS create a worktree for any code changes
- Use descriptive names: `ui-review`, `fix-rate-api`, `build-dashboard`
- Commit with conventional format: `feat:`, `fix:`, `refactor:`, `docs:`
- Run `wt sync` before starting new work to get latest code
- DO NOT touch `/opt/nelson/code` — that's the live deploy copy

### Reading Code (No Changes)

If you only need to READ code (review, understand, answer questions):
- Use main repo directly: `cat /opt/nelson/goclaw/workspace/FreightBrian/api/routers/email_rate_router.py`
- No worktree needed for read-only tasks

### Project Structure

```
FreightBrian/
├── api/              — FastAPI backend (port 8100)
│   ├── routers/      — API endpoints
│   └── data_access.py — DAL layer (DuckDB)
├── webapp/           — Next.js frontend (port 3003)
│   └── src/app/      — App Router pages
├── email_engine/     — Email sending system
├── shared/           — Shared utilities (paths, config)
├── tools/goclaw/     — GoClaw tools and scripts
├── db/               — DuckDB engine
└── deploy/           — Deploy scripts
```
