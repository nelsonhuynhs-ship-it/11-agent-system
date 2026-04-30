# Task: Phase 1 — Graph Webhook Subscription

## Context
Plan: 260430-graph-migration-v8
Phase: 1
Invoked by: ck:workflow (Opus orchestrator)
Working dir: D:/NELSON/2. Areas/Engine_test

## Your Task
Implement Phase 1 theo spec tại: `plans/260430-graph-migration-v8/phase-01-graph-webhook-subscription.md`

**Mục tiêu:** Thay thế inbox_scanner.py COM (đã chết 04-27) bằng Graph webhook real-time push notification cho bounce/reply.

## Files to CREATE
1. `email_engine/api/routes/webhook_router.py` — endpoint POST /api/graph/webhook
2. `email_engine/core/graph_subscription_manager.py` — create/renew/delete subscription
3. `email_engine/scripts/graph_webhook_renew.py` — cron daily renew
4. `email_engine/data/graph_subscriptions.db` — SQLite tracking

## Files to MODIFY
1. `email_engine/web_server.py` — mount webhook_router, init subscription on startup
2. `email_engine/scanner/inbox_scanner.py` — REPLACE COM scan với Graph fallback poll (1h interval)

## Success Criteria
- [ ] AC1: POST /api/graph/webhook validation handshake return plainText token within 5s
- [ ] AC2: Subscription tạo successful, ID lưu vào graph_subscriptions.db
- [ ] AC3: Send fake bounce → webhook nhận notification ≤ 5 phút
- [ ] AC4: Reply email → webhook nhận → reply_log entry
- [ ] AC5: Subscription renew OK
- [ ] AC6: ClientState mismatch → reject với log warning
- [ ] AC7: inbox_scanner.py Graph polling fallback work
- [ ] AC8: 0 file SEND/SCAN path import win32com

## Constraints
- Match existing code style
- Do NOT touch: email_engine/senders/, email_engine/core/send_email.py
- Respect CLAUDE.md rules
- Backup files before modify
- KHÔNG dùng --highspeed

## How to verify
Run smoke test commands từ phase spec.
Expected: Tailscale Funnel webhook accessible, Graph subscription active.

## Report back
- List every file modified/created (absolute paths)
- For each AC: pass/fail với evidence
- Any skipped items + reason
