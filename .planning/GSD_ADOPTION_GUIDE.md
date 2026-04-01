# GSD Workflow Adoption Guide — Nelson Freight

> Last updated: 2026-03-30

## 1. Atomic Commit Convention

### Before (Old Way)
```bash
git add .
git commit -m "feat: update bot and api"
git push
```

### After (GSD Way)
```bash
# Each task = 1 focused commit
git add TelegramBot/anomaly_alerts.py
git commit -m "feat(phase-3): wire anomaly detector to telegram alerts"

git add api/middleware/jwt_guard.py
git commit -m "feat(phase-2): add JWT middleware for route protection"

git push
```

### Commit Format
```
<type>(<scope>): <description>

Types: feat, fix, chore, docs, refactor, test
Scope: phase-N, module name, or component
```

### Benefits
- Git bisect finds exact failing change
- Each commit independently revertable
- Clear history for AI context in future sessions

---

## 2. Verify-Work Integration

### Available Commands (via GSD skills)
```
/gsd:verify-work [N]     # Verify phase N deliverables
/gsd:audit-uat            # Audit user acceptance testing
/gsd:audit-milestone      # Audit entire milestone
```

### Workflow
1. Complete a phase → run `/gsd:verify-work N`
2. GSD extracts testable deliverables from the plan
3. Walks through each test case with Sếp
4. If fails → auto-generates fix plans
5. If passes → mark phase complete, move to next

### Integration with Existing System
- Existing `/verification-before-completion` skill → still active
- GSD verify is **complementary** — adds structured UAT
- Both can coexist: use Nelson skill for quick checks, GSD for formal verification

---

## 3. Milestone Cycle Workflow

### Starting a New Milestone
```
/gsd:new-milestone "Sprint 13"
```
This will:
1. Ask what you want to build next
2. Research the domain (optional)
3. Create scoped REQUIREMENTS.md
4. Create phased ROADMAP.md
5. Reset STATE.md for new cycle

### Full Cycle
```
/gsd:new-milestone         # Define what's next
/gsd:discuss-phase 5       # Capture preferences for Phase 5
/gsd:plan-phase 5          # Research + create task plans
/gsd:execute-phase 5       # Build it (wave execution)
/gsd:verify-work 5         # Confirm it works
/gsd:ship 5                # Git PR + deploy

/gsd:complete-milestone    # Archive + tag release
/gsd:new-milestone         # Start next cycle
```

### Integration with Existing Workflows
| GSD Command | Nelson Equivalent | Status |
|------------|-------------------|--------|
| `/gsd:new-milestone` | `/sprint-planning` | Both coexist |
| `/gsd:discuss-phase` | Chat tự do | GSD adds structure |
| `/gsd:plan-phase` | Manual task list | GSD adds research + XML plans |
| `/gsd:execute-phase` | Manual coding | GSD adds wave execution |
| `/gsd:verify-work` | `/verification-before-completion` | Both coexist |
| `/gsd:ship` | `/feature-deploy` | Both coexist |
| `/gsd:complete-milestone` | `/end-of-sprint` | Both coexist |

### Quick Tasks (No Full Planning)
```
/gsd:quick "Fix rate limiter bug on API"
```
Skips research + plan checking. Still gets atomic commits + state tracking.

---

## 4. Session Management

### Start of Session
```
/gsd:resume-work            # GSD checks STATE.md, tells you where you left off
```
Or use existing Nelson workflow:
```
/new-session                 # Reads memory files
```

### End of Session
```
/gsd:pause-work              # Saves progress to STATE.md
/end-of-sprint               # Nelson memory update (keep using this too)
```

### Health Check
```
/gsd:health                  # Check .planning/ integrity
/gsd:health --repair         # Auto-fix issues
```

---

## 5. Available GSD Commands (Quick Reference)

### Core
| Command | Purpose |
|---------|---------|
| `/gsd:help` | Show all commands |
| `/gsd:progress` | Show current milestone progress |
| `/gsd:next` | Auto-detect next step |
| `/gsd:quick` | Quick task (no full planning) |
| `/gsd:fast` | Fastest mode |
| `/gsd:stats` | Show usage statistics |

### Planning
| Command | Purpose |
|---------|---------|
| `/gsd:map-codebase` | Re-scan codebase (7 docs) |
| `/gsd:new-milestone` | Start new sprint cycle |
| `/gsd:discuss-phase N` | Discuss feature preferences |
| `/gsd:plan-phase N` | Create task plans with research |
| `/gsd:add-phase` | Add a phase to roadmap |
| `/gsd:add-backlog` | Add to backlog |

### Execution
| Command | Purpose |
|---------|---------|
| `/gsd:execute-phase N` | Build phase (wave execution) |
| `/gsd:verify-work N` | Verify phase deliverables |
| `/gsd:ship N` | PR + deploy |
| `/gsd:debug` | Structured debugging |

### Utilities
| Command | Purpose |
|---------|---------|
| `/gsd:settings` | Configure GSD options |
| `/gsd:health` | Check .planning/ integrity |
| `/gsd:review` | Code review |
| `/gsd:pause-work` | Save progress |
| `/gsd:resume-work` | Resume from STATE.md |
