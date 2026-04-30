---
phase: 1
title: Graph Webhook Subscription — Real-time Bounce/Reply
effort_mm: 6-8h
depends: []
blocks: [phase-03]
---

# Phase 1 — Graph Webhook Subscription

## Goal

Replace polling `inbox_scanner.py` (đang chết COM) bằng Microsoft Graph webhook push notification real-time cho 2 events:
- **Bounce/NDR**: NDR email vào Inbox → push → parse → update bounce KB + suppression
- **Reply**: Customer reply → push → match conversationId → save vào reply_log

## Files Create / Modify

### CREATE
- `email_engine/api/routes/webhook_router.py` — endpoint `POST /api/graph/webhook` xử lý notification
- `email_engine/core/graph_subscription_manager.py` — create/renew/delete subscription
- `email_engine/scripts/graph_webhook_renew.py` — cron daily renew expired subscriptions
- `email_engine/data/graph_subscriptions.db` — SQLite track active subscriptions (id, expirationDateTime, resource)

### MODIFY
- `email_engine/web_server.py` — mount webhook_router, init subscription on app startup
- `email_engine/scanner/inbox_scanner.py` — REPLACE COM scan với Graph fallback poll (1h interval, dùng khi webhook lag)

## Microsoft Graph Spec

**Subscription resource:**
```json
POST https://graph.microsoft.com/v1.0/subscriptions
{
  "changeType": "created",
  "notificationUrl": "https://laptop-no6f8ibp.tail82dc4e.ts.net/api/graph/webhook",
  "resource": "me/mailFolders('inbox')/messages",
  "expirationDateTime": "2026-05-03T18:00:00Z",
  "clientState": "<random secret string for verify>"
}
```

**Notification payload (Graph POST tới webhook URL):**
```json
{
  "value": [{
    "subscriptionId": "...",
    "changeType": "created",
    "resource": "users/.../messages/<message-id>",
    "clientState": "<must match>"
  }]
}
```

**Validation handshake:** Khi tạo subscription, Graph POST tới webhook URL với query `?validationToken=xxx` → endpoint phải return plain text `validationToken` trong vòng 10s.

## Webhook Handler Logic (pseudo)

```python
@app.post("/api/graph/webhook")
async def graph_webhook(req: Request):
    # 1. Validation handshake (initial subscription create)
    token = req.query_params.get("validationToken")
    if token:
        return PlainTextResponse(content=token, status_code=200)

    # 2. Process notifications
    body = await req.json()
    for notif in body.get("value", []):
        # 3. Verify clientState match
        if notif.get("clientState") != EXPECTED_STATE:
            log.warning("Webhook clientState mismatch — possible spoof")
            continue

        # 4. Fetch message detail
        msg_id = notif["resource"].split("/")[-1]
        msg = graph_client.get(f"/me/messages/{msg_id}")

        # 5. Classify
        if is_ndr(msg):  # check headers + subject pattern
            handle_bounce(msg)  # → feed B3 BounceKB + suppression
        elif msg.conversationId in tracked_conversations:
            handle_reply(msg)  # → feed reply_log + Insights view

    return Response(status_code=202)
```

## NDR Detection (chuẩn RFC 3464)

```python
def is_ndr(msg) -> bool:
    # Check 1: headers
    headers = {h["name"]: h["value"] for h in msg.get("internetMessageHeaders", [])}
    if headers.get("Auto-Submitted") == "auto-replied":
        return True
    if "X-Failed-Recipients" in headers:
        return True
    if headers.get("Content-Type", "").startswith("multipart/report"):
        return True
    # Check 2: from postmaster/mailer-daemon
    sender = msg.get("from", {}).get("emailAddress", {}).get("address", "").lower()
    if any(s in sender for s in ["postmaster", "mailer-daemon", "mail-daemon"]):
        return True
    # Check 3: subject regex (fallback)
    subject = msg.get("subject", "").lower()
    if any(kw in subject for kw in ["undeliverable", "delivery status", "returned mail", "failure notice"]):
        return True
    return False
```

## Subscription Lifecycle

- **Create**: on app startup, call `subscription_manager.ensure_active()` → check DB, create if none, save id+expiration
- **Renew**: daily cron `graph_webhook_renew.py` — `PATCH /subscriptions/{id}` extend expiration +3 days
- **Delete on shutdown**: graceful handler

## Acceptance Criteria

- [ ] AC1: `POST /api/graph/webhook` validation handshake return plainText token within 5s
- [ ] AC2: Subscription tạo successful, ID lưu vào graph_subscriptions.db
- [ ] AC3: Send 1 fake bounce (gửi tới invalid address) → webhook nhận notification ≤ 5 phút → bounce_handler invoked
- [ ] AC4: Send 1 reply email từ test account → webhook nhận → reply_log entry
- [ ] AC5: Subscription expire test (set short expiration) → renew cron extend OK
- [ ] AC6: ClientState mismatch → reject với log warning, KHÔNG process
- [ ] AC7: Fallback poll 1h interval (nếu webhook lag) work — `inbox_scanner.py` rewrite Graph polling
- [ ] AC8: 0 file SEND/SCAN path import win32com sau phase này

## Smoke Test

```bash
# After deploy:
curl -X POST https://laptop-no6f8ibp.tail82dc4e.ts.net/api/graph/webhook \
  -H "Content-Type: application/json" \
  -d '{"value":[{"clientState":"test-spoof"}]}'
# Expect: 202 + log warning clientState mismatch

# Real test:
# Send to invalid@nowhere-domain-12345.com
# Wait 2-5 min
# Check: tail email_engine/logs/bounce_log.csv
```

## Rollback

```bash
# Disable subscription:
DELETE /subscriptions/{id}
# Restore inbox_scanner.py COM version từ git
git checkout v7-graph-fix-stable-20260429 -- email_engine/scanner/inbox_scanner.py
```

## Done When

- [ ] All 8 AC pass
- [ ] Webhook stable 24h không miss notification
- [ ] B3 BounceKB feed work (xem phase-03)
- [ ] Subscription DB có entry, renew cron schedule
