---
phase: 3
title: Bounce KB DSN Parser RFC 3464
effort_mm: 3h
depends: [phase-01]
blocks: []
---

# Phase 3 — Bounce KB Migration

## Goal

Replace COM-based bounce parsing trong `core/bounce_handler.py` bằng RFC 3464 DSN (Delivery Status Notification) parser. Feed từ Phase 1 webhook.

## Why Phase 3 needs Phase 1

- Phase 1 webhook detect NDR → trigger `handle_bounce(msg)`
- `handle_bounce` cần parse Graph message body để extract: failed recipient, action (failed/delayed/relayed/delivered), status code (5.x.x hard, 4.x.x soft), diagnostic
- Old `bounce_handler.py` parse từ Outlook MailItem COM object → khác format

## Files Modify

- `email_engine/core/bounce_handler.py` — REWRITE:
  - Bỏ `import win32com`
  - Input: Graph message JSON (từ webhook)
  - Output: structured bounce record vào `data/bounce_kb.db`

## DSN Format (RFC 3464 chuẩn)

NDR email là `Content-Type: multipart/report; report-type=delivery-status`. Body parts:
1. **text/plain** — human-readable explanation
2. **message/delivery-status** — machine-readable per-recipient status:
   ```
   Reporting-MTA: dns; mail.example.com
   
   Final-Recipient: rfc822; failed@invalid-domain.xyz
   Action: failed
   Status: 5.1.1
   Diagnostic-Code: smtp; 550 5.1.1 User unknown
   ```
3. **message/rfc822** — original message headers

## Parser Logic (pseudo)

```python
def parse_dsn_from_graph_msg(msg: dict) -> list[dict]:
    """Parse Graph message NDR → list of bounce records."""
    bounces = []
    body = msg.get("body", {}).get("content", "")
    
    # Split multipart (Graph trả raw body if NDR)
    if "message/delivery-status" not in body:
        return _fallback_subject_parse(msg)  # Fallback regex on subject
    
    delivery_status = _extract_part(body, "message/delivery-status")
    
    for recipient_block in delivery_status.split("\n\n"):
        rec = {}
        for line in recipient_block.splitlines():
            if line.startswith("Final-Recipient:"):
                rec["email"] = line.split(";")[-1].strip().lower()
            elif line.startswith("Action:"):
                rec["action"] = line.split(":")[-1].strip()  # failed/delayed/relayed/delivered
            elif line.startswith("Status:"):
                rec["status_code"] = line.split(":")[-1].strip()  # e.g. 5.1.1
            elif line.startswith("Diagnostic-Code:"):
                rec["reason"] = line.split(":", 2)[-1].strip()
        
        if rec.get("email"):
            rec["bounce_class"] = _classify(rec.get("status_code", ""))
            rec["received_at"] = msg.get("receivedDateTime")
            bounces.append(rec)
    
    return bounces


def _classify(status: str) -> str:
    """5.x.x = hard, 4.x.x = soft."""
    if not status: return "unknown"
    first = status.split(".")[0]
    return {"5": "hard", "4": "soft", "2": "delivered"}.get(first, "unknown")
```

## Auto-Suppression Hook

Hard bounce (5.x.x) → auto add vào suppression list:

```python
def handle_bounce(graph_msg):
    bounces = parse_dsn_from_graph_msg(graph_msg)
    for b in bounces:
        # 1. Save to bounce_kb
        bounce_kb.insert(b)
        # 2. If hard bounce → suppression
        if b["bounce_class"] == "hard":
            suppression_list.add(
                email=b["email"],
                reason=f"hard_bounce: {b.get('reason', 'no diag')}",
                source="dsn_auto"
            )
            log.info(f"Auto-suppressed {b['email']} after hard bounce")
        # 3. Soft bounce → counter, suppress sau 3 lần
        elif b["bounce_class"] == "soft":
            count = bounce_kb.get_soft_count(b["email"])
            if count >= 3:
                suppression_list.add(b["email"], reason="3 soft bounces", source="dsn_auto")
```

## Acceptance Criteria

- [ ] AC1: Parse 5 sample NDR thật (Sếp gửi lưu mẫu) → extract đúng email + status_code + action
- [ ] AC2: Hard bounce 5.1.1 → auto-suppress ngay
- [ ] AC3: Soft bounce 4.x.x → counter +1, suppress sau 3 lần
- [ ] AC4: Fallback subject parse khi DSN không phải multipart/report
- [ ] AC5: KHÔNG còn `import win32com` trong bounce_handler.py
- [ ] AC6: bounce_kb.db schema migrate: thêm columns `action`, `status_code`, `bounce_class`, `source`

## Done When

- [ ] All 6 AC pass
- [ ] Test với 5 NDR thật từ history
- [ ] Auto-suppression hook ghi log đầy đủ
