# Task: Phase 4 — Sent Scan Graph Migration

## Context
Plan: 260430-graph-migration-v8
Phase: 4
Invoked by: ck:workflow
Working dir: D:/NELSON/2. Areas/Engine_test

## Your Task
Implement Phase 4 theo spec: `plans/260430-graph-migration-v8/phase-04-sent-scan-graph.md`

**Mục tiêu:** Replace COM scan Outlook Sent folder bằng Graph API messageId verification.

## Files MODIFY
1. `email_engine/api/routes/sent_scan_router.py` — REWRITE endpoints /api/sent-scan/*
2. `email_engine/senders/graph_sender.py` — save messageId vào email_log.csv column graph_msg_id

## New Logic
- GET /api/sent-scan/pending — find emails with graph_msg_id but not verified
- POST /api/sent-scan/verify-batch — verify N emails via Graph /me/messages/{id}
- After send, save messageId to email_log.csv

## Success Criteria
- [ ] AC1: graph_sender.send() return messageId, save vào email_log.csv
- [ ] AC2: /api/sent-scan/pending list emails chưa verified
- [ ] AC3: /api/sent-scan/verify-batch Graph query OK, mark verified
- [ ] AC4: Throttle handle (max 30 req/min)
- [ ] AC5: 0 import win32com trong sent_scan_router.py

## Constraints
- Do NOT touch: email_engine/senders/graph_sender.py logic chỉ append
- Match existing code style
- Backup files before modify

## Report back
- List files modified
- Each AC pass/fail + evidence
