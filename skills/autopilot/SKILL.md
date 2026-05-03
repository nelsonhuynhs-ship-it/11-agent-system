---
name: ck:autopilot
description: "Autonomous pipeline agent. Runs 11-agent workflow without human confirmation. Self-heals on failure, auto-escalates on blocker."
argument-hint: "[task description or plan path]"
metadata:
  author: nelson-freight
  version: "1.0.0"
---

# Autopilot Agent

Agent chay 11-agent workflow KHONG CAN human confirm. Tu quyet khi nao next phase, tu heal khi fail.

## KHI NAO DUNG

- Task ro rang, khong can review tung buoc
- User noi "chay tu dong", "autonomous", "khong hoi"
- Sau khi plan da duoc approve

## WORKFLOW AUTOPILOT

1. Nhan task/plan
2. Chay Phase 1 (design-finder)
3. Auto-proceed -> Phase 2 (parallel reviews)
4. Auto-proceed -> Phase 3 (master-executor)
5. Auto-proceed -> Phase 4 (test-writer, doc-writer, tech-debt-tracker)
6. Auto-proceed -> Phase 5 (git-commit)
7. Report ket qua

## SELF-HEALING RULES

| Tinh huong | Hanh dong |
|-----------|----------|
| Agent fail | Retry voi M2.7 fallback |
| 2 lan fail | Thu approach khac |
| 3 lan fail | Escalate len user |
| Blocked by context | Provide context, retry |
| Timeout | Skip optional steps, proceed |

## DECISION RULES

**Tu proceed khi:**
- Previous phase DONE hoac DONE_WITH_CONCERNS
- No BLOCKED status
- Results meet threshold (>60% success criteria)

**Escalate khi:**
- SECURITY issues
- BLOCKED status sau 3 retries
- User data affected
- Scope creep detected

## AUTONOMOUS MODE

Khi invoke voi --auto flag:
/ck:autopilot "fix bug X" --auto

Khong hoi confirm giua cac phase. Chi report khi:
- Blocked
- Done
- Can decision (2+ options)

## INTEGRATION VOI 11-AGENT

Autopilot sits above workflow:
- User -> Autopilot -> Workflow orchestration
- Autopilot handles timing + self-healing
- Workflow handles actual agent execution
