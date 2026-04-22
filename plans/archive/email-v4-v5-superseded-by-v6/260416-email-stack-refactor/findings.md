# Findings — Email Stack Audit 2026-04-16

## Inventory (4 flow chồng chéo)

| # | Flow | File | Lines | Storage | Status |
|---|------|------|-------|---------|--------|
| 1 | Direct Outlook COM | `email_engine/web_server.py:160 _do_send()` | 90 | In-memory `SEND_PROGRESS` | Active |
| 2 | JSON Queue | `api/routers/email_rate_router.py:1544-1639` | 95 | `email_engine/data/email_queue.json` | Deprecated 2026-04-08 (chưa xóa) |
| 3 | PostgreSQL Queue | `api/routers/email_queue_router.py` | 248 | PostgreSQL `email_queue` table | Clean code, không ai dùng |
| 4 | Outlook COM Worker | `email_engine/outlook_queue_worker.py` | 92 | — (polls #2) | Standalone script |

**Total code:** ~525 dòng cho 1 tính năng "gửi email". Có thể gộp còn ~200 dòng.

## Bugs Identified

### Bug 1 — Worker poll sai endpoint
`outlook_queue_worker.py:45` → `/api/email-rate/queue/pending` (JSON queue #2)
PG queue #3 dùng `/api/email/queue/pending` (prefix khác, không có `-rate`)
→ Worker luôn thấy queue rỗng dù PG có job.

### Bug 2 — Dashboard v4 local không qua queue
`web_server.py:842 v4_bulk_send()` → `background_tasks.add_task(_do_send, ...)` → Outlook COM trực tiếp.
KHÔNG enqueue. Worker chạy cũng không thấy job (vì web_server.py không có queue table).

### Bug 3 — Fail silent
`_do_send` catch Exception → nhồi vào `SEND_PROGRESS[cid]['errors']` nhưng dashboard v4 chỉ call `bulk-send` rồi **không poll `/api/send-status/{id}`** → user không biết fail.

### Bug 4 — Hai batch script cùng tồn tại
- `email_engine/start-dashboard.bat` (cũ, cho v3)
- `email_engine/start-dashboard-v4.bat` (mới, cho v4)
→ confusing, nên xóa .bat cũ.

## Endpoints Analysis

### web_server.py (local :8100) — 32 endpoints
- Email send: `/api/send`, `/api/email-rate/campaign/bulk-send`
- Email status: `/api/send-status/{campaign_id}` ← dashboard chưa poll
- History: `/api/history`, `/api/history/stats`, `/api/data/email-log`
- Contacts/Config: `/api/campaigns`, `/api/contacts`, `/api/config`
- Queue: ❌ KHÔNG CÓ endpoint nào

### email_rate_router.py (VPS :8100) — ~40 endpoints
- Queue #2 (JSON): `/queue/add`, `/queue/pending`, `/queue/mark-sent`, `/queue/mark-failed`, `/queue/history`
- Campaign: `/campaign/prospects`, `/campaign/send`, `/campaign/bulk-send`
- Stats: `/campaign/stats`, `/follow-up-queue` (mới thêm 2026-04-15)

### email_queue_router.py (VPS :8100) — 6 endpoints
- PG Queue #3: `/queue`, `/queue/pending`, `/queue/{id}/complete`, `/queue/{id}/fail`, `/queue/status`, `/queue/reset-stuck`
- Feature rich: atomic lock, retry logic, stuck detection

## Cái gì thuận tiện
- Cooldown 48h + suppression list trong `_do_send` ✅
- CSV log đầy đủ field timestamp/campaign/pol/dest ✅
- PG queue code clean (retry, lock, stuck) ✅
- Dashboard v4 CORS `null` cho file:// ✅
- 7 endpoints đã wired ✅

## Cái gì chưa thuận tiện
- Không biết flow nào active khi bấm Send
- Worker chạy nhưng không làm gì (poll wrong endpoint)
- `_do_send` fail = user không biết
- Dashboard v4 không có queue status panel
- 4 flow → maintenance nightmare
- Dead code deprecated chưa xóa

## Skill Match
- `backend-development` — FastAPI endpoints, SQLite schema
- `debugging` — trace flow, verify endpoints
- `databases` — SQLite design

## Open Questions (cần Nelson quyết)
1. Giữ PG queue (#3) cho VPS automation, hay xóa luôn?
2. Worker: minimized window hay Windows service?
3. Flow A ưu tiên trước, hay gộp cả 2 flow trong sprint này?
