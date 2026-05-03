# 11-Agent System v2.0

ClaudeKit 11-agent workflow orchestration with MiniMax M2.7 auto-delegation.

## Architecture



## 11 Core Agents

| # | Agent | Phase | Route | Purpose |
|---|-------|-------|-------|---------|
| 1 | design-finder | 1 | Opus | UI/UX design inspiration |
| 2 | ux-reviewer | 2 | Opus | UX/Accessibility audit |
| 3 | code-reviewer | 2 | Opus | Logic, TypeScript, patterns |
| 4 | security-auditor | 2 | Opus | Security vulnerabilities |
| 5 | perf-analyzer | 2 | Opus | Performance, bundle size |
| 6 | master-executor | 3 | M2.7 | Apply fixes from reports |
| 7 | test-writer | 4 | M2.7 | Generate tests |
| 8 | doc-writer | 4 | M2.7 | Generate documentation |
| 9 | tech-debt-tracker | 4 | Opus | Prioritize technical debt |
| 10 | git-commit | 5 | M2.7 | Conventional commit message |
| 11 | i18n-checker | — | N/A | (Nelson does not use) |

## v2.0 Improvements

- **Two-Stage Review Cycle**: Spec Compliance then Code Quality
- **Fresh Context Isolation**: Anti-pattern rules prevent subagent pollution
- **Model Selection by Complexity**: M2.7 for mechanical, Opus for judgment
- **Status Escalation Rules**: Max 3 retries, clear escalation path
- **Mandatory Final Whole-Implementation Review**: Before commit

## Automation Agents

### autopilot (NEW)
Autonomous pipeline agent. Runs 11-agent workflow **without human confirmation**.
- Self-healing on failure (3x retry then escalate)
- Auto-proceed when phase complete
- Only blocks on: security, 3x failure, user data affected

### monitor (NEW)
Observability agent. Track agent performance metrics.
- Execution time per agent
- Success/error rates
- Token usage tracking
- Health alerts

## Installation

```bash
git clone https://github.com/nelsonhuynhs-ship-it/11-agent-system.git
cd 11-agent-system
./install.sh
```

## Skills

skills/design-finder/       - Design inspiration
skills/ux-reviewer/        - UX/Accessibility review
skills/code-reviewer/       - Code quality review
skills/security-auditor/    - Security audit
skills/perf-analyzer/       - Performance analysis
skills/master-executor/     - Phase 3 executor
skills/test-writer/         - Test generation
skills/doc-writer/          - Documentation generation
skills/tech-debt-tracker/  - Technical debt tracking
skills/git-commit/           - Commit message generation
skills/i18n-checker/       - Internationalization (not used)
skills/autopilot/           - Autonomous pipeline (NEW)
skills/monitor/             - Observability (NEW)

## Rules

rules/orchestration-protocol.md - Status escalation + max iterations

## Reports

reports/11-agent-code-review-report.md   - Review findings
reports/11-agent-execution-report.md     - Implementation report

## Source

Inspired by subagent-driven-development (57.4K installs) from skills.sh

