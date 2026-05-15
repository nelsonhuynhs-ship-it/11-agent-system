# 11-Agent System v3.0

ClaudeKit-native 11-agent orchestration system with MiniMax routing, skill preload policy, runtime observability, fake-executor E2E tests, and workflow state machine.

## Architecture

## 11 Core Agents

| # | Agent | Phase | Route | Capability | Tools |
|---|-------|-------|-------|------------|-------|
| 1 | design-finder | 1 | Opus/M2.7 | image+search | Read-only |
| 2 | ux-reviewer | 2 | VLM | vlm | Read-only |
| 3 | code-reviewer | 2 | M2.7 | text | Read-only |
| 4 | security-auditor | 2 | M2.7 | search+text | Read-only |
| 5 | perf-analyzer | 2 | VLM | vlm | Read-only |
| 6 | master-executor | 3 | M2.7 | text | **Write** |
| 7 | test-writer | 4 | M2.7 | text | **Write** |
| 8 | doc-writer | 4 | M2.7 | text | **Write** |
| 9 | tech-debt-tracker | 4 | Opus | text | Read-only |
| 10 | git-commit | 5 | M2.7 | text | Read-only |
| 11 | i18n-checker | — | N/A | — | (Nelson does not use) |

> **Read-only roles**: design-finder, ux-reviewer, code-reviewer, security-auditor, perf-analyzer, tech-debt-tracker, git-commit — deny Edit/Write in tools, use disallowedTools.
> **Write-capable roles**: master-executor, test-writer, doc-writer — allow Edit/Write in tools.

## v3.0 Highlights

- **Claude Code-native frontmatter** for role templates (name, model, effort, maxTurns, memory, isolation, skills[], tools[], disallowedTools[])
- **Explicit skill loading policy** per role with bounded helper skills
- **Runtime snapshot** under agent-system-runtime/ (Git-tracked backup of C:\Users\Nelson\.claude)
- **mm-agent-spawner.sh** routing: text / search / vlm / image
- **log-spawn.py** JSONL + SQLite observability (spawn_start, capability_resolved, fallback_used, spawn_complete, spawn_failed)
- **Harness workflow state machine** (PLAN / SCOUT / REVIEW / EXECUTE / VERIFY / OBSERVE / RETRY / STOP)
- **Fake executor E2E regression suite** — no real model cost during testing
- **127 agent-system tests passing**

## Runtime Snapshot

Files under agent-system-runtime/ are a Git-tracked snapshot of the live runtime at C:\Users\Nelson\.claude:

| File | Live path |
|------|-----------|
| bin/mm-agent-spawner.sh | C:\Users\Nelson\.claude\bin\mm-agent-spawner.sh |
| bin/log-spawn.py | C:\Users\Nelson\.claude\bin\log-spawn.py |
| agents-mm/*.md | C:\Users\Nelson\.claude\agents-mm\*.md |

To restore from snapshot: backup live runtime first, then copy files back to the live paths.

## Verification

```powershell
& "C:\Program Files\Git\bin\bash.exe" -n "C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh"
pytest tests/agent-system -q
```

Expected: 127 passed.

## Skills

```
skills/design-finder/       - Design inspiration
skills/ux-reviewer/        - UX/Accessibility review
skills/code-reviewer/       - Code quality review
skills/security-auditor/    - Security audit
skills/perf-analyzer/       - Performance analysis
skills/master-executor/     - Phase 3 executor
skills/test-writer/          - Test generation
skills/doc-writer/           - Documentation generation
skills/tech-debt-tracker/   - Technical debt tracking
skills/git-commit/            - Commit message generation
```

## Source

Inspired by subagent-driven-development (57.4K installs) from skills.sh
