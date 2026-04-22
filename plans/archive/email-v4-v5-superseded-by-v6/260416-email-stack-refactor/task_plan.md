# Task Plan — Email Stack Refactor (Local-Only)

**Created:** 2026-04-16
**Decision made:** 2026-04-16 — Nelson approves **kill VPS email**, keep VPS rate query for GoClaw bot
**Trigger:** 4 flow chồng chéo + dashboard v4 fail silent + trải nghiệm WebApp Next.js chậm
**Status:** 📋 READY TO START — chờ Nelson ok từng phase

## 🎯 Nelson's Decisions (2026-04-16)

| Quyết định | Chọn |
|-----------|------|
| Email stack | **LOCAL-ONLY** — kill VPS email hoàn toàn |
| Rate query API trên VPS | **GIỮ** — cho GoClaw bot Telegram query rate từ xa |
| Parquet sync VPS (rclone) | **GIỮ** — vẫn cần cho rate query endpoint |
| WebApp Next.js email page | **KILL** — redirect hoặc remove |
| Dashboard v4 local | **KEEP** — flow chính sau refactor |

## 🏗️ Target Architecture

### LOCAL (Laptop VP / PC Home) — Email stack ở đây
```
Browser (dashboard-v4.html file://)
  ↓ localhost:8100
web_server.py (FastAPI)
  ├─ /api/campaigns, /contacts, /rate-preview  (local Parquet)
  ├─ /api/email-rate/campaign/bulk-send  → ENQUEUE vào SQLite
  ├─ /api/email-rate/queue/pending       → worker poll
  ├─ /api/email-rate/queue/mark-sent/{id}
  ├─ /api/email-rate/queue/mark-failed/{id}
  └─ /api/email-rate/queue/status        → dashboard poll progress

email_engine/data/outlook_queue.db (SQLite, WAL mode)
  ↑
outlook_queue_worker.py (poll localhost:8100 mỗi 30s)
  → Outlook COM Dispatch + Send
  → retry 3x on fail
```

### VPS (14.225.207.145:8100) — giữ các router này
- ✅ `rate_router.py` — query Parquet
- ✅ `latest_rates_router.py` — latest rates
- ✅ `pricing_router.py` — pricing calc
- ✅ `auto_quote_router.py` — auto quote flow
- ✅ `intelligence_router.py` — market intel (public)
- ✅ `customer_check_router.py` — customer lookup
- ✅ `erp_router.py`, `hpl_router.py`, `sync_router.py`
- ✅ `dashboard_router.py`, `job_router.py`, `shipment_router.py`
- ✅ `data_router.py`, `health_router.py`, `worker_router.py`, `auth_router.py`

### VPS — XÓA các router này
- ❌ `email_rate_router.py` (1,639 dòng) — toàn email, xóa luôn
- ❌ `email_queue_router.py` (248 dòng) — PG queue, không cần
- ❌ `email_router.py` (check xem còn dùng không)

### VPS Database — XÓA table
- ❌ `email_queue` table trong PostgreSQL

### WebApp Next.js — XÓA/redirect page
- ❌ `webapp/src/app/dashboard/rate-send/` → redirect tới README về dashboard v4

## 📅 Phases

### Phase A — Cleanup VPS (2-3h, medium risk)

#### A1 — Audit Dependency ✅ DONE (2026-04-16)

**Frontend depend:**
- `webapp/src/app/dashboard/rate-send/page.tsx` → uses `/api/email-rate/customers`, `/config`, `/preview`, `/send`
- `webapp/src/app/dashboard/email-campaign/page.tsx` → uses `/api/email-rate/campaign/*`
- `webapp/src/app/dashboard/email-log/page.tsx` → uses email-rate history
- `webapp/src/lib/api.ts` (15+ methods)
- `webapp/src/hooks/useApi.ts` (React Query hooks)

**Backend depend:**
- `api/app.py:55,152,154` — imports 2 routers
- `api/routers/email_rate_router.py` — 1,639 dòng
- `api/routers/email_queue_router.py` — 248 dòng
- `api/pipeline/queue_manager.py` — ⚠ auto-campaign scheduler nightly 8pm-6am, rate limit 100/h, dùng PG queue
- `api/pipeline/template_engine.py` (implied import in queue_manager) — cần check
- `api/pipeline/blacklist.py` (implied import) — cần check
- `api/database/migrations/003_email_platform.sql` — creates email_queue table
- `api/tests/test_health.py` — asserts email endpoints
- `deploy/vps_deploy_full.sh` — health check email-rate

#### A2 — Nelson's Decisions (2026-04-16)
- ✅ Xóa cả 3 WebApp pages (rate-send + email-campaign + email-log)
- ✅ Kill `email_rate_router.py` + `email_queue_router.py`
- ⚠ Re-evaluate `queue_manager.py`: auto-campaign scheduler có ai trigger không? Nếu không → kill. Nếu có GoClaw/cron trigger → migrate logic sang local hoặc rewrite.
- ✅ DROP TABLE `email_queue` (sau backup `pg_dump`)

#### A3-A6 Tasks
- [ ] A3: Delete 3 WebApp pages + remove email-rate methods trong `api/ts` + `useApi.ts`
- [ ] A4: Comment out imports + includes trong `api/app.py` (lines 55, 152, 154)
- [ ] A5: Audit `api/pipeline/queue_manager.py` + `template_engine.py` + `blacklist.py` — decide kill hay migrate local
- [ ] A6: Remove `email_rate_router.py` + `email_queue_router.py` + kill-related migrations
- [ ] A7: Update `api/tests/test_health.py` + `deploy/vps_deploy_full.sh` health checks
- [ ] A8: Backup + DROP TABLE email_queue trên PG
- [ ] A9: Deploy VPS, verify kept endpoints (rate, intelligence, erp) còn hoạt động
- [ ] A10: Test GoClaw bot Telegram vẫn query rate OK qua VPS API

### Phase B — Local Stack (2-3h)
- [ ] B1: `email_engine/queue_store.py` — SQLite queue module (~80 dòng)
  - Schema: id, to_email, subject, html_body, cc, status, attempts, error_message, created_at, sent_at
  - Functions: `enqueue(jobs)`, `fetch_pending(limit)`, `mark_sent(id)`, `mark_failed(id, err)`, `get_stats()`, `reset_stuck()`
- [ ] B2: `email_engine/web_server.py` — thay `_do_send` background task bằng enqueue
  - Thêm `POST /api/email-rate/queue/enqueue` (direct enqueue for worker testing)
  - Sửa `POST /api/email-rate/campaign/bulk-send` → build HTML body, enqueue vào SQLite
  - Thêm `GET /api/email-rate/queue/pending` → `queue_store.fetch_pending()`
  - Thêm `POST /api/email-rate/queue/mark-sent/{id}` và `mark-failed/{id}`
  - Thêm `GET /api/email-rate/queue/status` → stats cho dashboard
- [ ] B3: `email_engine/outlook_queue_worker.py` — retarget localhost, retry
  - Default API: `http://localhost:8100`
  - Retry: 3 attempts với exponential backoff
  - Better logging: in ra `[SENT]`, `[RETRY]`, `[FAIL]`, `[EMPTY]`
- [ ] B4: `email_engine/start-dashboard-v4.bat` — start thêm worker
  - Start web_server.py minimized
  - Start outlook_queue_worker.py --loop 30 minimized
  - Open dashboard
- [ ] B5: `plans/visuals/email-dashboard-v4.html` — add Queue Status panel
  - Poll `/queue/status` mỗi 5s khi có active campaign
  - Show: Pending / Sent / Failed counters + progress bar

### Phase C — Cleanup + Verify (30 phút)
- [ ] C1: Xóa `email_engine/data/email_queue.json` nếu còn (file JSON queue cũ)
- [ ] C2: Xóa `email_engine/start-dashboard.bat` (script v3 cũ)
- [ ] C3: Test E2E: gửi 3 email thật qua dashboard → thấy hiện trong Outlook Sent
- [ ] C4: Update `memory/project-email-stack-audit.md` → mark "RESOLVED"
- [ ] C5: Commit + push (KHÔNG deploy VPS lúc này, chỉ local)

### Phase D — VPS deploy (sau khi local ổn)
- [ ] D1: Deploy Phase A changes lên VPS qua GitHub Actions
- [ ] D2: Verify GoClaw bot vẫn query rate OK qua VPS API
- [ ] D3: Monitor 24h: VPS logs có error nào không

## 🎯 Acceptance Criteria

- [ ] Bấm Send trên dashboard → thấy job trong `outlook_queue.db` ngay
- [ ] Worker pop job → Outlook COM gửi thành công → log vào `email_log.csv`
- [ ] Dashboard show progress real-time (Pending: 48 → 25 → 0, Sent: 2 → 25 → 50)
- [ ] Fail 1 email → queue retry 3 lần trước khi mark `failed`
- [ ] Outlook tắt giữa chừng → worker báo error rõ, không crash, đợi Outlook mở lại
- [ ] VPS không còn endpoint email nào (verify qua `curl /api/email-rate/campaign/prospects` → 404)
- [ ] GoClaw bot vẫn query rate được (verify qua Telegram `/rate HPH USLAX`)
- [ ] Dashboard v4 không còn gọi VPS cho email (devtools Network tab chỉ thấy localhost)

## ⚠️ Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| WebApp hoặc feature nào khác đang depend email_rate/* | Phase A1 audit kỹ trước, grep toàn codebase |
| Drop `email_queue` table mất data lịch sử queued | Backup `pg_dump email_queue > backup.sql` trước |
| Outlook COM prompt security khi Send() | Trust Center → Programmatic Access → Never Warn (1 lần setup) |
| Worker crash giữa batch | `reset_stuck()` function + dashboard button "Reset stuck jobs" |
| SQLite lock nếu worker + web_server write cùng lúc | WAL mode enabled (đã dùng ở chỗ khác) |

## 📚 References

- Memory: `project-email-stack-audit.md` — full audit of 4 flows
- Memory: `project-email-outlook-com-constraint.md` — why local-only
- Memory: `feedback-stealth-excel.md` — Nelson stealth mode rationale
- Previous plan: `plans/260415-email-dashboard-v4-build/` — Phase 3 completed dashboard wiring
- Session log: `project-session-20260408c.md` — PG queue bugs (sẽ bị deprecate)
