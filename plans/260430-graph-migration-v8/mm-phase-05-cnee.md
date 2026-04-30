# Task: Phase 5 — CNEE Draft Graph Migration

## Context
Plan: 260430-graph-migration-v8
Phase: 5
Invoked by: ck:workflow
Working dir: D:/NELSON/2. Areas/Engine_test

## Your Task
Implement Phase 5 theo spec: `plans/260430-graph-migration-v8/phase-05-cnee-draft-graph.md`

**Mục tiêu:** Replace COM draft creation trong cnee_milestone.py bằng Graph POST /me/messages (isDraft=true).

## Files MODIFY
1. `email_engine/core/cnee_milestone.py` — line 603-652:
   - Bỏ import win32com
   - Replace outlook.CreateItem(0) + .Save() bằng Graph create draft
2. Check line 44 for weekly digest pattern — migrate if same

## New Logic
- POST /me/messages với isDraft=true
- Support attachments (base64)
- Return draft_id

## Success Criteria
- [ ] AC1: Draft xuất hiện trong web Outlook Drafts folder
- [ ] AC2: Attachment work (PDF rate sheet)
- [ ] AC3: 0 import win32com trong cnee_milestone.py
- [ ] AC4: Backward compat — function signature giữ nguyên

## Constraints
- Do NOT change function signature (callers must not break)
- Match existing code style
- Backup files before modify

## Report back
- List files modified
- Each AC pass/fail + evidence
