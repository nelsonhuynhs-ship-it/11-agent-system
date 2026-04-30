# Task: Phase 6 — Sequence Engine Cleanup

## Context
Plan: 260430-graph-migration-v8
Phase: 6
Invoked by: ck:workflow
Working dir: D:/NELSON/2. Areas/Engine_test

## Your Task
Implement Phase 6 theo spec: `plans/260430-graph-migration-v8/phase-06-sequence-engine-cleanup.md`

**Mục tiêu:** Xoá hoàn toàn conditional COM block trong follow-up sequence path.

## Files MODIFY
1. `email_engine/web_server.py:1311` — xoá block `if EMAIL_SEND_BACKEND == "outlook":`
2. `email_engine/core/sequence_engine.py` — bỏ import win32com + xóa COM dispatch path

## Diff Expected
BEFORE: web_server.py có conditional `if EMAIL_SEND_BACKEND == "outlook":` với win32com
AFTER: Chỉ Graph path, không COM fallback

## Success Criteria
- [ ] AC1: grep "EMAIL_SEND_BACKEND.*outlook" → 0 match
- [ ] AC2: grep "import win32com" sequence_engine.py → 0
- [ ] AC3: Follow-up send vẫn work qua Graph (smoke test 3)
- [ ] AC4: bash syntax + python compile check pass

## Constraints
- This is simple cleanup — grep + edit
- Match existing code style
- Backup files before modify

## Report back
- List files modified
- Each AC pass/fail + evidence
