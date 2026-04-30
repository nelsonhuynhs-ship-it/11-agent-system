# Task: Phase 2 — Smart Send Preview Migration

## Context
Plan: 260430-graph-migration-v8
Phase: 2
Invoked by: ck:workflow
Working dir: D:/NELSON/2. Areas/Engine_test

## Your Task
Implement Phase 2 theo spec: `plans/260430-graph-migration-v8/phase-02-smart-send-preview-graph.md`

**Mục tiêu:** Replace Outlook desktop COM dispatch bằng Graph draft API + local HTML preview.

## Files CREATE
1. `email_engine/api/routes/smart_send_router.py` — endpoints POST /api/smart-send/preview + /api/smart-send/confirm

## Files MODIFY
1. `email_engine/web_server.py` — mount smart_send_router
2. `plans/visuals/email-dashboard.html` — rewrite JS smartSendFlow()

## Success Criteria
- [ ] AC1: Click Smart Send → preview tab ≤ 3s
- [ ] AC2: Preview đúng VIP đầu tiên
- [ ] AC3: 2 nút Confirm + Cancel
- [ ] AC4: Cancel → DELETE draft
- [ ] AC5: Confirm → emails sent + log đầy đủ
- [ ] AC6: 0 COM dispatch trong smart send path
- [ ] AC7: 0 ImportError nếu Outlook desktop tắt

## Constraints
- Recommend Option B (local HTML render) — KISS
- Do NOT touch: senders/graph_sender.py
- Match existing code style
- Backup files before modify

## Report back
- List files created/modified
- Each AC pass/fail + evidence
