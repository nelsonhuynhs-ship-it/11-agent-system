---
phase: 4
title: Sent Scan Migration — Graph messageId Verify
effort_mm: 2h
depends: []
blocks: []
---

# Phase 4 — Sent Scan Migration

## Goal

Replace COM scan Outlook Sent folder bằng Graph API messageId verification. Khi gửi email qua Graph → response trả về `id` → query `/me/messages/{id}` xác nhận message exists trong Sent folder.

## Files Modify

- `email_engine/api/routes/sent_scan_router.py` — REWRITE endpoints `/api/sent-scan/*`
- `email_engine/senders/graph_sender.py` — sau khi send, save `messageId` vào `email_log.csv` column `graph_msg_id` (memory `email_v8_audit_20260429` gap #2)

## New Logic (pseudo)

```python
@router.get("/api/sent-scan/pending")
def sent_scan_pending():
    """Find sent emails có graph_msg_id nhưng chưa verify."""
    rows = csv_read(LOG_FILE, where="status='SENT' AND verified IS NULL")
    return {"count": len(rows), "items": rows[:50]}

@router.post("/api/sent-scan/verify-batch")
def verify_batch(req: VerifyRequest):
    """Verify N email exist trong Sent folder qua Graph."""
    verified = 0
    failed = []
    for msg_id in req.message_ids:
        try:
            resp = graph_client.get(f"/me/messages/{msg_id}", select="id,parentFolderId,sentDateTime")
            if resp.get("parentFolderId") == SENT_FOLDER_ID:
                csv_update(LOG_FILE, msg_id=msg_id, set={"verified": resp["sentDateTime"]})
                verified += 1
            else:
                failed.append({"id": msg_id, "reason": f"in folder {resp.get('parentFolderId')}"})
        except GraphNotFound:
            failed.append({"id": msg_id, "reason": "message not found"})
    return {"verified": verified, "failed": failed}
```

## Acceptance Criteria

- [ ] AC1: graph_sender.send() return `messageId`, save vào email_log.csv
- [ ] AC2: `/api/sent-scan/pending` list emails chưa verified
- [ ] AC3: `/api/sent-scan/verify-batch` Graph query OK, mark verified
- [ ] AC4: Throttle handle (max 30 req/min)
- [ ] AC5: KHÔNG còn `import win32com` trong sent_scan_router.py

## Done When

- [ ] 5 AC pass
- [ ] Test 50 emails verify cycle hoàn tất
