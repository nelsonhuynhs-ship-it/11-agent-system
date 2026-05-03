# 11-Agent Harness System

## Overview

Harness system để orchestrate 11-agent workflow qua Telegram group chat với 2 bots:
- `@claude_bot` (Commander/Opus) — planning, orchestration
- `@nelson_freight_bot` (Executor/M2.7) — execution

## Architecture

```
Human (1:1 session) → Plan → Telegram Group → Commander → Executor → 11-Agent Chain
                                              ↓
                                        Harness Controller
                                              ↓
                    ┌────────────────────────┼────────────────────────┐
                    ↓                        ↓                        ↓
              design-finder            code-reviewer           master-executor
              ux-reviewer              security-auditor        test-writer
              perf-analyzer            doc-writer              tech-debt-tracker
                                                                  git-commit
```

## Components

### 1. BAT Files (Hardened)
- `D:/NELSON/2. Areas/START_COMMANDER_OPUS.bat` — Commander bot launcher
- `D:/NELSON/2. Areas/START_EXECUTOR_MINIMAX.bat` — Executor bot launcher

Features:
- Log rotation (10MB max)
- Max restart counter (prevent infinite loops)
- Env file validation
- Consecutive failure tracking

### 2. Harness Controller
- `harness/harness_controller.py` — Python orchestration engine

Capabilities:
- Context injection
- State machine
- Phase routing
- Validation per phase
- Retry engine (exponential backoff)
- Report generation

### 3. Validators
- `harness/validators/*.yaml` — Validation rules per phase

Each validator defines:
- Pass/fail criteria
- Retry behavior
- Fail actions (notify, escalate, block)

## Files Structure

```
Engine_test/harness/
├── harness-config.yaml          # Main configuration
├── harness_controller.py       # Orchestration engine
└── validators/
    ├── design-finder.yaml
    ├── ux-reviewer.yaml
    ├── code-reviewer.yaml
    ├── security-auditor.yaml
    ├── perf-analyzer.yaml
    ├── master-executor.yaml
    ├── test-writer.yaml
    ├── doc-writer.yaml
    ├── tech-debt-tracker.yaml
    └── git-commit.yaml
```

## Workflow

1. **Human** (Nelson) brainstorm + approve plan trong 1:1 session với Claude Code
2. **Plan** được delegate vào Telegram group
3. **Commander** (@claude_bot) nhận plan, inject context
4. **Executor** (@nelson_freight_bot) chạy 11-agent chain
5. **Harness Controller** validate từng phase
6. **Report** được gửi về group sau khi hoàn thành
7. **Human** nhận notification + full report

## Delegation Pattern

### From Commander to Executor (in Telegram group):

```
@nelson_freight_bot: /delegate task="fix bug #123" phases=code-reviewer,master-executor,test-writer
```

### Harness Controller reads plan and routes:

```python
# Phase routing via mm-delegate-phase.sh
bash ~/.claude/bin/mm-delegate-phase.sh <plan-file> <workflow> <phase-name>
```

## Running

### Start Commander Bot
```batch
D:\NELSON\2. Areas\START_COMMANDER_OPUS.bat
```

### Start Executor Bot
```batch
D:\NELSON\2. Areas\START_EXECUTOR_MINIMAX.bat
```

### Run Harness Controller (manual)
```bash
cd D:/NELSON/2. Areas/Engine_test
python harness/harness_controller.py "fix bug #123"
```

## Validation Rules

| Phase | Validator | Pass Criteria | Fail Action |
|-------|-----------|---------------|-------------|
| design-finder | design-finder.yaml | output exists, not empty | retry, skip |
| ux-reviewer | ux-reviewer.yaml | issues list, severity | retry, proceed |
| code-reviewer | code-reviewer.yaml | findings, fixes | retry, escalate |
| security-auditor | security-auditor.yaml | severity summary, fixes | retry, **BLOCK** |
| perf-analyzer | perf-analyzer.yaml | bottlenecks, recs | retry, proceed |
| master-executor | master-executor.yaml | files modified | retry, escalate |
| test-writer | test-writer.yaml | tests pass | retry, **BLOCK** |
| doc-writer | doc-writer.yaml | docs updated | retry, proceed |
| tech-debt-tracker | tech-debt-tracker.yaml | debt items | retry, proceed |
| git-commit | git-commit.yaml | commit created | retry, preserve |

## Security Features

- **Log rotation**: 10MB max per log file
- **Max restart**: 10 attempts, then exit
- **Env validation**: API key format check
- **Consecutive fail tracking**: Notify after 3 fails
- **Isolation**: Separate USERPROFILE per bot

## Next Steps

1. ✅ BAT files hardened
2. ✅ Harness Controller built
3. ✅ Validators created per phase
4. 🔲 Test Telegram group delegation (manual test required)
5. 🔲 Add Telegram bot command parsing in Executor
6. 🔲 Setup webhook for Commander → Executor communication