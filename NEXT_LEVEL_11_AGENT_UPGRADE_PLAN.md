# NEXT LEVEL 11-AGENT UPGRADE PLAN

## Purpose

Upgrade the current 11-agent system from `7/10 runtime-ready` to `9/10 production-grade`.

This plan is for Claude Code to implement with `/ck:cook`.

Current verified baseline:
- `C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh` passes `bash -n`.
- `pytest tests/agent-system -q` passes `68` tests.
- Runtime smoke with fake executors confirms:
  - `--upgrade-image` routes to `mm-image`.
  - `--upgrade-search` routes to `mm-search`.
  - `--upgrade-vlm` routes to `mm-vlm`.
- 11 core `SKILL.md` files have bounded helper skill policies.
- Role templates in `C:/Users/Nelson/.claude/agents-mm/*.md` have capability policy.

Primary remaining gap:
- The system is runtime-ready, but not yet fully Claude Code-native.
- Skill usage is still mostly prompt-instructed, not enforced by subagent frontmatter.
- Observability still mostly logs spawn completion, not actual skill/search/VLM/fallback events.
- Tool boundaries are not strict enough per role.
- Tests cover routing and basic runtime, but not full workflow state transitions.

## Source Ideas To Adapt

Use these as architecture references only. Do not bulk-copy external prompts.

1. Claude Code native subagents
   - Adopt frontmatter fields: `skills`, `tools`, `disallowedTools`, `model`, `effort`, `maxTurns`, `memory`, `isolation`, `hooks`.
   - Source: https://code.claude.com/docs/en/subagents

2. VoltAgent and 0xfurai subagent collections
   - Borrow structure: clear role description, focus areas, approach, quality checklist, output format.
   - Do not install 100+ agents. Keep Nelson's 11-agent architecture.

3. Composio agent-orchestrator
   - Borrow pattern: worktree isolation, branch-per-agent for risky execution, CI/review feedback loop.
   - Do not replace the current spawner with a new orchestrator.

4. LangGraph multi-agent router/handoff
   - Borrow state-machine thinking: explicit phases, structured handoff payload, retry/stop rules.
   - Do not add LangGraph dependency unless explicitly approved later.

5. OpenAI Agents SDK tracing/guardrails
   - Borrow tracing concepts: trace id, spans, handoff events, guardrail checks.
   - Do not add SDK dependency unless explicitly approved later.

## Non-Goals

- Do not create dozens of new agents.
- Do not replace the existing 11-agent workflow.
- Do not edit non-existent `D:/NELSON/2. Areas/Engine_test/.agents/roles`.
- Do not remove MiniMax wrappers.
- Do not run expensive real model calls for tests when fake executor tests are enough.
- Do not commit or push unless Nelson explicitly asks.

## Target Architecture

### 1. Agent Definition Layer

Each subagent should become a Claude Code-native role definition with explicit frontmatter.

Target files:
- `C:/Users/Nelson/.claude/agents-mm/code-reviewer.md`
- `C:/Users/Nelson/.claude/agents-mm/design-finder.md`
- `C:/Users/Nelson/.claude/agents-mm/doc-writer.md`
- `C:/Users/Nelson/.claude/agents-mm/git-commit.md`
- `C:/Users/Nelson/.claude/agents-mm/master-executor.md`
- `C:/Users/Nelson/.claude/agents-mm/perf-analyzer.md`
- `C:/Users/Nelson/.claude/agents-mm/security-auditor.md`
- `C:/Users/Nelson/.claude/agents-mm/tech-debt-tracker.md`
- `C:/Users/Nelson/.claude/agents-mm/test-writer.md`
- `C:/Users/Nelson/.claude/agents-mm/ux-reviewer.md`

Important:
- Keep `PRE_FLIGHT.md` unchanged unless required by tests.
- These files may be used as injected templates by `mm-agent-spawner.sh`, not necessarily native `.claude/agents/` files. Still make them frontmatter-compatible so they can be migrated or mirrored later.

### 2. Runtime Layer

Keep:
- `C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh`
- `C:/Users/Nelson/.claude/bin/mm-claude.sh`
- `C:/Users/Nelson/.claude/bin/mm-search.sh`
- `C:/Users/Nelson/.claude/bin/mm-vlm.sh`
- `C:/Users/Nelson/.claude/bin/mm-image.sh`

Enhance:
- `mm-agent-spawner.sh` emits structured event spans.
- `log-spawn.py` persists event details.
- Tests use fake executor overrides to avoid real model cost.

### 3. Orchestration Layer

Target file:
- `D:/NELSON/2. Areas/Engine_test/harness/harness-config.yaml`

Add explicit workflow state:
- `PLAN`
- `SCOUT`
- `REVIEW`
- `EXECUTE`
- `VERIFY`
- `OBSERVE`
- `RETRY`
- `STOP`

This is a config-level state machine, not a new framework.

### 4. Evaluation Layer

Target folder:
- `D:/NELSON/2. Areas/Engine_test/tests/agent-system/`

Add tests for:
- frontmatter validity
- skill preload mapping
- tool permission boundaries
- maxTurns/effort/isolation policy
- event logging
- fake workflow state transitions
- degraded-mode reporting

## Phase 1 — Claude Code-Native Frontmatter

### Objective

Make each of the 10 role templates frontmatter-compatible and deterministic.

### Required Frontmatter Schema

Each role template should begin with:

```yaml
---
name: <role-name>
description: <one sentence trigger description>
model: inherit
effort: <low|medium|high|xhigh>
maxTurns: <integer>
memory: project
skills:
  - <own-skill>
  - <helper-skill-1>
  - <helper-skill-2>
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - <tools denied for this role>
---
```

Use only fields supported by Claude Code docs.

### Per-Agent Frontmatter Policy

#### design-finder

```yaml
name: design-finder
model: inherit
effort: high
maxTurns: 8
memory: project
skills:
  - design-finder
  - aesthetic
  - ai-multimodal
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
```

Reason:
- Research/design only.
- Must not edit code.
- Search/image routing is handled by spawner flags.

#### ux-reviewer

```yaml
name: ux-reviewer
model: inherit
effort: high
maxTurns: 10
memory: project
skills:
  - ux-reviewer
  - ai-multimodal
  - chrome-devtools
  - web-testing
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
```

Reason:
- Read-only UX/accessibility/visual verification.
- Can run browser/test commands.
- Must not directly patch UI.

#### code-reviewer

```yaml
name: code-reviewer
model: inherit
effort: high
maxTurns: 10
memory: project
skills:
  - code-reviewer
  - scout
  - docs-seeker
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
```

Reason:
- Read-only code review.
- Search/docs only when framework/API uncertainty exists.

#### security-auditor

```yaml
name: security-auditor
model: inherit
effort: xhigh
maxTurns: 12
memory: project
skills:
  - security-auditor
  - security-scan
  - ai-multimodal
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
```

Reason:
- Read-only security review.
- Must use current search for CVE/security claims.

#### perf-analyzer

```yaml
name: perf-analyzer
model: inherit
effort: high
maxTurns: 10
memory: project
skills:
  - perf-analyzer
  - chrome-devtools
  - web-testing
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
```

Reason:
- Read-only performance investigation.
- Can run profiling/test commands.

#### master-executor

```yaml
name: master-executor
model: inherit
effort: high
maxTurns: 18
memory: project
isolation: worktree
skills:
  - master-executor
  - systematic-debugging
  - verification-before-completion
tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
disallowedTools: []
```

Reason:
- Primary code editor.
- Worktree isolation reduces blast radius for large fixes.
- Must verify before completion.

#### test-writer

```yaml
name: test-writer
model: inherit
effort: medium
maxTurns: 14
memory: project
isolation: worktree
skills:
  - test-writer
  - verification-before-completion
  - ck-loop
tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
disallowedTools: []
```

Reason:
- May create tests.
- `ck-loop` only after failing tests or explicit retry loop.

#### doc-writer

```yaml
name: doc-writer
model: inherit
effort: medium
maxTurns: 10
memory: project
skills:
  - doc-writer
  - docs-seeker
  - mermaidjs-v11
tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
disallowedTools: []
```

Reason:
- May update docs.
- Diagrams only when requested or useful.

#### tech-debt-tracker

```yaml
name: tech-debt-tracker
model: inherit
effort: medium
maxTurns: 8
memory: project
skills:
  - tech-debt-tracker
  - sequential-thinking
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
```

Reason:
- Read-only debt analysis.
- Writes only reports if explicitly allowed by workflow.

#### git-commit

```yaml
name: git-commit
model: inherit
effort: low
maxTurns: 6
memory: project
skills:
  - git-commit
tools:
  - Read
  - Grep
  - Glob
  - Bash
disallowedTools:
  - Edit
  - Write
```

Reason:
- Should generate commit messages and inspect diff.
- Must not commit/push unless Nelson explicitly asks.

### Phase 1 Tests

Create or update:
- `tests/agent-system/test_agent_frontmatter.py`

Required assertions:
- Every role template except `PRE_FLIGHT.md` has YAML frontmatter.
- Required fields exist: `name`, `description`, `skills`, `tools`, `maxTurns`, `memory`.
- Read-only roles disallow `Edit` and `Write`.
- `master-executor`, `test-writer`, `doc-writer` allow `Edit` and `Write`.
- `master-executor` and `test-writer` use `isolation: worktree`.
- `security-auditor` has `effort: xhigh`.
- `git-commit` has `maxTurns <= 6`.

## Phase 2 — Skill Preload Enforcement

### Objective

Move from "agent is told to load skill" to "skill is declared in frontmatter and tested".

### Required Mapping

Use this exact mapping:

```yaml
design-finder:
  skills: [design-finder, aesthetic, ai-multimodal]
ux-reviewer:
  skills: [ux-reviewer, ai-multimodal, chrome-devtools, web-testing]
code-reviewer:
  skills: [code-reviewer, scout, docs-seeker]
security-auditor:
  skills: [security-auditor, security-scan, ai-multimodal]
perf-analyzer:
  skills: [perf-analyzer, chrome-devtools, web-testing]
master-executor:
  skills: [master-executor, systematic-debugging, verification-before-completion]
test-writer:
  skills: [test-writer, verification-before-completion, ck-loop]
doc-writer:
  skills: [doc-writer, docs-seeker, mermaidjs-v11]
tech-debt-tracker:
  skills: [tech-debt-tracker, sequential-thinking]
git-commit:
  skills: [git-commit]
```

### Skill Policy Text

Inside each role body, keep a short body policy:

```markdown
## Skill Policy
- Use preloaded skills from frontmatter first.
- Load no more than 2 helper skills beyond the role's own skill unless the user explicitly asks.
- If a needed skill is unavailable, write `NEEDS VERIFICATION: missing skill <name>`.
```

### Phase 2 Tests

Update:
- `tests/agent-system/test_skill_loading_policy.py`
- `tests/agent-system/test_agent_frontmatter.py`

Required assertions:
- Frontmatter `skills` exactly includes own skill.
- Helper count is bounded.
- Existing `D:/NELSON/2. Areas/Engine_test/.agents/skills/<skill>/SKILL.md` exists for every declared project skill when applicable.
- Missing plugin/system skills are allowed only if they are not project-local; log as warning in test output, not failure.

## Phase 3 — Tool Permission Boundaries

### Objective

Stop review agents from accidentally editing code.

### Role Classes

Read-only roles:
- `design-finder`
- `ux-reviewer`
- `code-reviewer`
- `security-auditor`
- `perf-analyzer`
- `tech-debt-tracker`
- `git-commit`

Write-capable roles:
- `master-executor`
- `test-writer`
- `doc-writer`

### Required Policy

Read-only roles:
- Must include `disallowedTools: [Edit, Write]`.
- Must state in body: "Do not modify files. Write findings only."

Write-capable roles:
- Must include explicit "surgical changes only" policy.
- Must include verification requirement.

### Phase 3 Tests

Create:
- `tests/agent-system/test_tool_boundaries.py`

Required assertions:
- Read-only roles cannot use `Edit`/`Write`.
- Write roles explicitly allow `Edit` and `Write`.
- `git-commit` does not allow file edit tools.
- Every role body contains either `Do not modify files` or `Surgical changes`.

## Phase 4 — Runtime Event Spans

### Objective

Make observability real, not just schema-level.

### Event Types

`mm-agent-spawner.sh` must emit these events through `log-spawn.py`:

- `spawn_start`
- `spawn_complete`
- `spawn_failed`
- `fallback_used`
- `degraded_mode`
- `capability_resolved`

Optional future events:
- `skill_loaded`
- `search_used`
- `vlm_used`
- `verification_result`

Do not fake optional future events unless runtime can actually observe them.

### Required `log-spawn.py` Args

Already present:
- `--trace-id`
- `--requested-capability`
- `--resolved-executor`
- `--fallback-executor`
- `--error-class`
- `--query`
- `--source-url`
- `--task-id`

Add if missing:
- `--details-json`

### Event Emission Rules

In `mm-agent-spawner.sh`:

1. After trace ID generation and routing:
   - emit `spawn_start`
   - emit `capability_resolved`

2. When primary executor fails and fallback is used:
   - emit `fallback_used`
   - include original executor and fallback executor in `details_json`

3. When all attempts fail:
   - emit `spawn_failed`
   - emit `degraded_mode` if requested capability failed

4. On success:
   - emit `spawn_complete`

### JSONL Contract

Every JSONL event should include:

```json
{
  "ts": "...",
  "trace_id": "...",
  "task_id": "...",
  "role": "...",
  "event_type": "...",
  "capability": "...",
  "requested_capability": "...",
  "resolved_executor": "...",
  "fallback_executor": "...",
  "duration_sec": 0,
  "status": "...",
  "error_class": "...",
  "details": {}
}
```

### Phase 4 Tests

Update:
- `tests/agent-system/test_observability.py`
- `tests/agent-system/test_runtime_smoke.py`

Required assertions:
- Fake executor successful run writes `spawn_start`, `capability_resolved`, `spawn_complete`.
- Fake primary fail + fallback success writes `fallback_used`.
- Failed run writes `spawn_failed`.
- JSONL contains `trace_id` for all events.
- SQLite `agent_tool_events` contains matching events.
- `details_json` is valid JSON.

## Phase 5 — Workflow State Machine

### Objective

Make the harness explicit enough to prevent orchestration drift.

### Target File

`D:/NELSON/2. Areas/Engine_test/harness/harness-config.yaml`

Add:

```yaml
workflow_state_machine:
  states:
    - PLAN
    - SCOUT
    - REVIEW
    - EXECUTE
    - VERIFY
    - OBSERVE
    - RETRY
    - STOP
  transitions:
    PLAN: [SCOUT, REVIEW, EXECUTE, STOP]
    SCOUT: [REVIEW, PLAN, STOP]
    REVIEW: [EXECUTE, PLAN, STOP]
    EXECUTE: [VERIFY, RETRY, STOP]
    VERIFY: [OBSERVE, RETRY, STOP]
    OBSERVE: [STOP, PLAN]
    RETRY: [EXECUTE, STOP]
    STOP: []
  retry_policy:
    max_retries_per_agent: 1
    max_total_workflow_retries: 3
    require_degraded_mode_marker: true
```

### Handoff Payload

Add required handoff schema:

```yaml
handoff_payload:
  required_fields:
    - trace_id
    - task_id
    - phase
    - role
    - input_files
    - output_report
    - verification_command
    - status
    - needs_verification
```

### Phase 5 Tests

Create:
- `tests/agent-system/test_workflow_state_machine.py`

Required assertions:
- All required states exist.
- No transition points to unknown state.
- `STOP` has no outgoing transitions.
- `RETRY` can only go to `EXECUTE` or `STOP`.
- Handoff payload required fields exist.
- Retry policy has bounded retries.

## Phase 6 — Search/VLM Hardening

### Objective

Ensure search and VLM are triggered by real task conditions.

### Search Policy

Mandatory search triggers:
- CVE/security claims
- current framework behavior
- unknown error
- dependency version policy
- breaking API checks
- vendor/tool recommendation

Required output when search is used:
- source URL
- access date
- claim tied to source

### VLM Policy

Mandatory VLM triggers:
- screenshot
- UI mockup
- visual regression
- flame graph
- PDF/image OCR
- exposed secret image/config screenshot

Required output when VLM is unavailable:
- `NEEDS VERIFICATION: VLM unavailable`

### Phase 6 Tests

Update:
- `tests/agent-system/test_search_policy.py`
- `tests/agent-system/test_vlm_policy.py`

Required assertions:
- All mandatory triggers appear in role templates.
- Search-capable roles state citation requirement.
- VLM-capable roles state degraded-mode requirement.
- `master-executor` requests VLM for UI changes.
- `security-auditor` requests VLM for screenshots/images with secrets/configs.

## Phase 7 — Realistic End-to-End Smoke Suite

### Objective

Prove the 11-agent system can route all roles without real model spend.

### Test File

Create:
- `tests/agent-system/test_e2e_fake_executors.py`

### Fake Executor Contract

Fake executors must:
- accept `--file <prompt_file>`
- write their executor name to a marker file
- copy first lines of prompt into output
- exit 0 or controlled non-zero depending on test

### Required E2E Tests

1. Every supported role routes to expected default executor.
2. `--upgrade-search` overrides any role to search executor.
3. `--upgrade-vlm` overrides any role to VLM executor.
4. `--upgrade-image` only works for image-generation task.
5. Fallback triggers once and then succeeds.
6. Failed fallback writes `NEEDS VERIFICATION`.
7. Each output report contains role template content.
8. Each run produces a trace id.
9. JSONL has matching event trace id.
10. SQLite has matching event trace id.

### Expected Default Routing

```yaml
code-reviewer: mm-claude
master-executor: mm-claude
test-writer: mm-claude
doc-writer: mm-claude
tech-debt-tracker: mm-claude
git-commit: mm-claude
security-auditor: mm-search
design-finder: mm-search
ux-reviewer: mm-vlm
perf-analyzer: mm-vlm
```

## Phase 8 — Scoring Model

### Objective

Quantify whether the system is actually improving.

### Add Scorecard

Create:
- `D:/NELSON/2. Areas/Engine_test/tests/agent-system/agent_system_scorecard.md`

Include:

```markdown
# Agent System Scorecard

## Current Score

| Area | Score | Evidence |
| --- | ---: | --- |
| Runtime routing | /10 | |
| Skill loading | /10 | |
| Tool boundaries | /10 | |
| Search intelligence | /10 | |
| VLM routing | /10 | |
| Observability | /10 | |
| Regression coverage | /10 | |
| Workflow orchestration | /10 | |
| Context discipline | /10 | |
| Failure recovery | /10 | |

## Minimum Bar For 9/10

- Runtime routing >= 9
- Skill loading >= 8
- Tool boundaries >= 9
- Search intelligence >= 8
- VLM routing >= 8
- Observability >= 8
- Regression coverage >= 9
- Workflow orchestration >= 8
- Context discipline >= 8
- Failure recovery >= 8
```

### Add Score Script

Optional but preferred:
- `tests/agent-system/score_agent_system.py`

It should read test/config/template evidence and output a markdown score table.

Do not overengineer. Static score is acceptable for now.

## Verification Commands

Run all:

```powershell
cd "D:\NELSON\2. Areas\Engine_test"

& "C:\Program Files\Git\bin\bash.exe" -n "C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh"

pytest tests/agent-system -q
```

Run fake executor smoke:

```powershell
pytest tests/agent-system/test_e2e_fake_executors.py -q
```

Run targeted policy tests:

```powershell
pytest tests/agent-system/test_agent_frontmatter.py tests/agent-system/test_tool_boundaries.py tests/agent-system/test_workflow_state_machine.py -q
```

## Acceptance Criteria

This upgrade is complete only when:

1. `bash -n` passes.
2. Full `pytest tests/agent-system -q` passes.
3. Fake E2E executor tests prove all default role routes.
4. Fake E2E executor tests prove all upgrade routes.
5. Fake E2E executor tests prove fallback success and degraded failure.
6. Every role template has valid frontmatter.
7. Every role has bounded `skills`.
8. Read-only roles deny `Edit` and `Write`.
9. Write-capable roles allow `Edit` and `Write`.
10. Harness has explicit state machine.
11. Observability emits more than `spawn_complete`.
12. JSONL and SQLite both receive traceable events.
13. Scorecard claims at least `9/10` only if backed by test evidence.

## Rollback Plan

Before editing, back up:
- `C:/Users/Nelson/.claude/agents-mm`
- `C:/Users/Nelson/.claude/bin/mm-agent-spawner.sh`
- `C:/Users/Nelson/.claude/bin/log-spawn.py`
- `D:/NELSON/2. Areas/Engine_test/harness/harness-config.yaml`
- `D:/NELSON/2. Areas/Engine_test/tests/agent-system`

Backup location:
- `C:/Users/Nelson/.claude/agent-backups/<timestamp>-next-level-11-agent`

Rollback:
- Restore only touched files from backup.
- Do not use `git reset --hard`.

## Claude Code Execution Prompt

Use this exact prompt after opening Claude Code in:

`D:\NELSON\2. Areas\Engine_test`

```markdown
/ck:cook

Implement the plan in:
D:\NELSON\2. Areas\Engine_test\NEXT_LEVEL_11_AGENT_UPGRADE_PLAN.md

Goal:
Upgrade the 11-agent system from 7/10 runtime-ready to 9/10 production-grade.

Hard requirements:
- Read the full plan first.
- Back up all touched files before editing.
- Do not edit non-existent `.agents/roles`.
- Do not create new agents beyond the existing 10 role templates plus existing workflow skill.
- Do not run expensive real model calls; use fake executor tests.
- Preserve current working runtime behavior.
- Add frontmatter, tool boundaries, observability events, workflow state machine, and fake E2E tests.
- Run all verification commands from the plan.

Output:
1. Files changed.
2. Backup path.
3. What changed by phase.
4. Test results.
5. Remaining risks.
```

## Final Judgement Target

Current verified level before this plan:
- `7/10`

Expected after this plan:
- `9/10`

What will still prevent `10/10`:
- No real production telemetry dashboard yet.
- No long-horizon benchmark suite with historical tasks.
- No automatic monthly drift audit job yet.
- No real per-token/per-cost accounting per agent.
- No real human approval queue for high-risk actions.

To reach `10/10`, add a later phase for:
- dashboard
- long-horizon benchmark
- monthly drift audit automation
- cost accounting
- approval queue
