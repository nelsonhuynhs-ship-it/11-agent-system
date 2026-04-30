---
title: Graph Send Reliability — Fix silent fail + verify mechanism
slug: 260429-graph-send-reliability
date: 2026-04-29
status: pending
priority: P0 URGENT
estimated_effort: 3-5h M2.7 (Tier 1 expanded — 10 file)
owner: M2.7 master-executor
blockedBy: []
related:
  - email_engine/web_server.py:44 (EMAIL_SEND_BACKEND default)
  - email_engine/senders/graph_sender.py:107 (send_html_via_graph)
---

# Graph Send Reliability — URGENT Fix

## Pain (Sếp catch 2026-04-29 evening)

Bấm Send trên dashboard → email **không gửi thực sự** (silent fail). Yêu cầu:
1. Fix root cause silent fail
2. Hệ thống PHẢI có verify mechanism — biết được email đã thực sự gửi qua Graph API

## Root Cause Verified

**File:** `email_engine/web_server.py:44`
```python
EMAIL_SEND_BACKEND = os.environ.get("EMAIL_SEND_BACKEND", "outlook").strip().lower()
```

→ Default = `"outlook"`. Khi env var KHÔNG set:
- `_send_email_html()` line 53: check `EMAIL_SEND_BACKEND == "graph"` → FALSE
- Fallback Outlook COM line 60: `outlook_app.CreateItem(0)`
- COM worker đã shutdown từ 2026-04-27 23:23 (verified worker_err.log không update 2 ngày)
- Nếu `outlook_app=None` → `RuntimeError("Outlook COM dispatch missing")` line 59
- Nếu callsite catch silently → email "Sent" nhưng KHÔNG đi đâu

**4 callsites bị ảnh hưởng** (verified `web_server.py:864, 978, 1302` + line 47):
- Smart Send flow
- send_emails endpoint
- Bulk send batch
- Manual send trigger

## Fix — 4 step ship tối nay

### Step 1 — Flip default backend (5 phút)
**File:** `email_engine/web_server.py:44`

**OLD:**
```python
EMAIL_SEND_BACKEND = os.environ.get("EMAIL_SEND_BACKEND", "outlook").strip().lower()
```

**NEW:**
```python
EMAIL_SEND_BACKEND = os.environ.get("EMAIL_SEND_BACKEND", "graph").strip().lower()
```

→ Default flip từ COM → Graph. Sếp bấm Send → đi Graph mặc định.

### Step 2 — Hard fail nếu COM dispatch missing (10 phút)
**File:** `email_engine/web_server.py:47-64`

Update `_send_email_html` để LOG VISIBLE warning + return verifiable result:

```python
def _send_email_html(to: str, subject: str, html_body: str, outlook_app=None) -> dict:
    """Backend-agnostic email send. Returns verification dict.

    Returns:
        {
          "ok": bool,
          "backend": "graph" | "outlook",
          "graph_msg_id": str | None,   # message-id from Sent folder if backend=graph
          "sent_at": ISO timestamp,
          "to": str,
          "subject": str,
        }
    Raises on hard failure.
    """
    sent_at = datetime.now().isoformat()
    if EMAIL_SEND_BACKEND == "graph":
        from email_engine.senders import send_html_via_graph, verify_in_sent_folder
        send_html_via_graph(to=to, subject=subject, html_body=html_body)
        # Verify: read back from Sent folder within 30s window
        msg_id = verify_in_sent_folder(to=to, subject=subject, since=sent_at)
        return {
            "ok": True,
            "backend": "graph",
            "graph_msg_id": msg_id,
            "sent_at": sent_at,
            "to": to,
            "subject": subject,
        }
    # Outlook COM fallback
    if outlook_app is None:
        log.error(f"[SEND-FAIL] backend=outlook but COM dispatch missing for {to}")
        raise RuntimeError(f"Outlook COM dispatch missing — set EMAIL_SEND_BACKEND=graph")
    m = outlook_app.CreateItem(0)
    m.To = to
    m.Subject = subject
    m.HTMLBody = html_body
    m.Send()
    return {"ok": True, "backend": "outlook", "graph_msg_id": None, "sent_at": sent_at, "to": to, "subject": subject}
```

### Step 3 — Add verify_in_sent_folder() Graph API read-back (30 phút)
**File mới:** `email_engine/senders/graph_sender.py` (append to existing file)

```python
GRAPH_SENT_FOLDER = "https://graph.microsoft.com/v1.0/me/mailFolders/sentitems/messages"

def verify_in_sent_folder(to: str, subject: str, since: str, max_wait_sec: int = 30) -> str | None:
    """Poll Sent folder for matching message. Returns Graph message-id or None.

    Microsoft /sendMail returns 202 but no message-id. To verify actual delivery,
    poll Sent folder filtered by recipient + subject + receivedDateTime.

    Args:
        to: recipient email
        subject: exact subject string
        since: ISO timestamp lower bound
        max_wait_sec: total polling budget (default 30s)
    """
    import time
    token = get_token()
    deadline = time.time() + max_wait_sec
    poll_intervals = [2, 3, 5, 5, 10]  # progressive backoff

    for delay in poll_intervals:
        if time.time() >= deadline:
            break
        time.sleep(delay)
        # Filter: $filter=toRecipients/any(r:r/emailAddress/address eq 'to')
        # and subject eq 'subject' and sentDateTime ge since
        params = {
            "$filter": (
                f"sentDateTime ge {since}Z "
                f"and subject eq '{subject.replace(chr(39), chr(39)*2)}'"
            ),
            "$select": "id,sentDateTime,toRecipients",
            "$top": 5,
            "$orderby": "sentDateTime desc",
        }
        try:
            r = requests.get(
                GRAPH_SENT_FOLDER,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=10,
            )
            if r.status_code != 200:
                continue
            messages = r.json().get("value", [])
            for msg in messages:
                recipients = msg.get("toRecipients", [])
                if any(rcpt["emailAddress"]["address"].lower() == to.lower() for rcpt in recipients):
                    return msg["id"]
        except Exception as e:
            log.debug(f"verify_in_sent_folder poll failed: {e}")
            continue
    return None
```

Add to `email_engine/senders/__init__.py`:
```python
from .graph_sender import send_html_via_graph, verify_in_sent_folder
```

### Step 4 — Surface verify result trong dashboard (15 phút)

**File:** `email_engine/web_server.py` — `send_emails` endpoint (line 905-940 area)

Update để log + display:
```python
# After _send_email_html call:
result = _send_email_html(to=to_addr, subject=subj, html_body=html_body, outlook_app=outlook)
log.info(f"[SEND-OK] backend={result['backend']} to={to_addr} msg_id={result['graph_msg_id']} sent_at={result['sent_at']}")
# Append to email_log.csv with verify column
log_row = {
    "ts": result["sent_at"],
    "to": to_addr,
    "subject": subj,
    "backend": result["backend"],
    "graph_msg_id": result["graph_msg_id"] or "",
    "verified": "yes" if result["graph_msg_id"] else "pending",
}
# csv writer append
```

Dashboard query: `email_log.csv` rows last 10 → display column "Verified" với badge:
- ✅ Green: backend=graph + msg_id non-empty
- ⚠️ Amber: backend=graph + msg_id null (đã 202 nhưng read-back không tìm thấy — Sent folder lag)
- ❌ Red: backend=outlook hoặc raise

## Acceptance Criteria

| AC | Test | Pass |
|---|---|---|
| AC1 | Default backend = graph | `grep EMAIL_SEND_BACKEND web_server.py:44` show `"graph"` |
| AC2 | Send 1 email → 202 + return dict | Test send to test address → result["ok"]=True, result["backend"]="graph" |
| AC3 | Verify từ Sent folder | result["graph_msg_id"] non-null trong 30s |
| AC4 | Hard fail khi outlook+no_dispatch | `EMAIL_SEND_BACKEND=outlook` + outlook_app=None → RuntimeError visible (không silent) |
| AC5 | Log có verify info | email_log.csv mới có column `backend`, `graph_msg_id`, `verified` |
| AC6 | Dashboard display badge | Sent items list hiện ✅/⚠️/❌ tương ứng |
| AC7 | Live test 5 emails | 5 sends thực → 5 ✅ trong dashboard, KHÔNG silent fail |
| AC8 | Backward compat | Set `EMAIL_SEND_BACKEND=outlook` + outlook_app dispatch → vẫn work (cho dev testing) |

## Smoke Test (Sếp verify)

```
1. Restart web_server.py
2. Bấm Send 1 test email tới chính mình
3. Trong 30s: dashboard phải hiển thị ✅ + msg_id
4. Mở Outlook Sent folder → email phải có
5. Mở web_server.log → có dòng [SEND-OK] backend=graph msg_id=AAMkA...
```

## ⚠️ TIER 1 EXPANSION (Sếp confirm 2026-04-29 — rip COM toàn SEND path)

**Lý do mở rộng:** Memory `reference_email_graph_only.md` chốt graph-only. Plan cũ chỉ fix `web_server.py:44` = half-fix. Smart Send 700/day vẫn silent fail vì `rotation_router.py:841` default `backend="outlook"`.

### Files thêm vào scope (Tier 1 SEND path — 8 file total)

| # | File | Action | Why |
|---|---|---|---|
| 1 | `email_engine/web_server.py:44 + 47-103` | Flip default + verify dict (Step 1-2 plan cũ) | Manual send + Smart Send confirm |
| 2 | `email_engine/api/routes/rotation_router.py:828-851` | Flip `backend="outlook"` → `"graph"` line 841. Bypass queue, gọi thẳng `send_html_via_graph` | **Smart Send 700/day root cause** |
| 3 | `email_engine/core/rotation_engine.py:queue_to_outlook_worker` | Add `if backend=="graph"` branch — KHÔNG enqueue, send synchronous Graph với pacing 28/min | Core daily rotation logic |
| 4 | `email_engine/outlook_queue_worker.py` | **DELETE entire file** | Memory chốt — worker COM dead 04/27, không còn ai start |
| 5 | `email_engine/core/send_email.py` (1122 dòng) | Scan: nếu là wrapper COM-only → DELETE. Nếu có shared logic → migrate Graph | Helper send |
| 6 | `email_engine/core/main.py` (696 dòng) | Scan: nếu legacy CLI entry-point chưa ai dùng → DELETE. Nếu có hàm utils dùng nơi khác → strip COM blocks | Legacy pipeline |
| 7 | `email_engine/core/sequence_engine.py` (674 dòng) | Migrate sequence/follow-up send sang Graph | Follow-up Queue view dependency |
| 8 | `email_engine/ingest/batch_send_outlook.py` (262 dòng) | Migrate hoặc DELETE nếu replaceable bởi rotation_router Graph branch | Batch send |
| 9 | `email_engine/core/cnee_milestone.py:603-652` | Migrate Draft creation (TODO #8) sang Graph `/me/messages` POST | Weekly digest |

### Tier 2 (NOT in this sprint — Sprint 2 plan)
Scan/Read path: `scanner/inbox_scanner.py`, `core/bounce_handler.py`, `core/process_reply.py`, `core/reply_detector.py`, `core/scan_outlook_folders.py`, `core/read_email1.py`, `core/shipment_brain.py`, `core/nelson_customer_sort.py`

### Tier 3 (KEEP — offline tools, không send path)
- `email_engine/core/pst_importer.py` — Sếp chạy 1 lần import historical PST
- `email_engine/core/knowledge_ingest.py` — `.msg` parser offline

### Acceptance Criteria — bổ sung (AC9-AC12)

| AC | Test | Pass |
|---|---|---|
| AC9 | Smart Send 700/day đi Graph | `grep "EMAIL_SEND_BACKEND" rotation_router.py:841` show `"graph"`. Bấm Smart Send → 1 batch → row mới trong email_log.csv có `backend=graph` |
| AC10 | Queue worker vắng mặt | `outlook_queue_worker.py` deleted. `python -c "import email_engine.outlook_queue_worker"` → ModuleNotFoundError |
| AC11 | Sequence Follow-up Queue ship Graph | View Follow-up Queue click "Send" → email log row có `backend=graph` |
| AC12 | Toàn email_engine không còn `import win32com` ở SEND path | `grep -rn "import win32com" email_engine/{web_server,api,core/{rotation_engine,send_email,main,sequence_engine,cnee_milestone},ingest}` → 0 match (Tier 3 PST/MSG OK giữ) |

## Files Touched (10 file — Tier 1 expanded)

- `email_engine/web_server.py` (Step 1-4 cũ)
- `email_engine/senders/graph_sender.py` (Append verify_in_sent_folder)
- `email_engine/senders/__init__.py` (Export)
- `email_engine/api/routes/rotation_router.py` (Step 5: line 841 default + bypass queue)
- `email_engine/core/rotation_engine.py` (Step 6: Graph branch trong `queue_to_outlook_worker`)
- `email_engine/outlook_queue_worker.py` (Step 7: **DELETE**)
- `email_engine/core/send_email.py` (Step 8: scan, delete or migrate)
- `email_engine/core/main.py` (Step 9: scan, delete or strip)
- `email_engine/core/sequence_engine.py` (Step 10: migrate Graph)
- `email_engine/ingest/batch_send_outlook.py` (Step 11: migrate or delete)
- `email_engine/core/cnee_milestone.py:603-652` (Step 12: migrate Draft Graph)

## Files Touched — ORIGINAL 3 file (Step 1-4 plan cũ giữ nguyên)

- `email_engine/web_server.py` (Edit: line 44 + line 47-64 + send_emails block)
- `email_engine/senders/graph_sender.py` (Append verify_in_sent_folder function)
- `email_engine/senders/__init__.py` (Export verify_in_sent_folder)

## Backup Plan

Backup 3 files trước edit:
```bash
cp email_engine/web_server.py email_engine/web_server.py.bak.20260429-graph
cp email_engine/senders/graph_sender.py email_engine/senders/graph_sender.py.bak.20260429-graph
cp email_engine/senders/__init__.py email_engine/senders/__init__.py.bak.20260429-graph
```

Rollback: `cp .bak.20260429-graph` ngược lại.

## Risk + Mitigation

| Risk | Mitigation |
|---|---|
| Sent folder read-back lag >30s | Set `verified=pending` không fail. Cron 5min recheck. |
| Graph 429 rate limit (cap 30/min) | graph_sender.py:96 đã có pacing 28/min |
| Token expired mid-send | get_token() có retry msal silent acquire. Nếu fail → raise visible. |
| Subject special chars break $filter | Escape single quote line `subject.replace(chr(39), chr(39)*2)` |
| Email_log.csv schema change break dashboard read | Column add backward compat (old columns + new) |

## Lệnh Sếp paste cho M2.7 (T1 hoặc terminal mới)

```
/cook

Đọc plan: D:/NELSON/2. Areas/Engine_test/plans/260429-graph-send-reliability/plan.md

Execute 4 step (URGENT — ship tối nay):
1. Flip default backend "outlook" → "graph" (web_server.py:44)
2. Update _send_email_html return verify dict + visible error log
3. Add verify_in_sent_folder() vào graph_sender.py (Sent folder read-back)
4. Update send_emails endpoint log + email_log.csv schema (add backend, graph_msg_id, verified columns)

CONSTRAINTS:
- Backup 3 file trước (.bak.20260429-graph)
- Verify 8 AC mechanical
- KHÔNG --highspeed
- KHÔNG đụng plan archive

Verify smoke test 5 emails. Ghi reports/CHECKPOINT-graph-send.md.
Tự /ck:debug nếu fail.
```

## Success Definition (Sếp accept)

1. AC1-AC7 pass
2. Sếp test bấm Send 1 email → trong 30s thấy ✅ + msg_id trong dashboard
3. Mở Outlook Sent folder → email tồn tại
4. KHÔNG có "silent fail" report nào trong 24h tới (Sếp test 5-10 sends)
