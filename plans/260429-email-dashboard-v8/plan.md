---
title: Email Dashboard V8 — Toàn diện reliability + error detection + tab upgrade
slug: 260429-email-dashboard-v8
date: 2026-04-29
status: pending (Sprint 1 đang ship)
priority: P0
estimated_effort: 5 sprint × 1-3 ngày = 8-12 ngày M2.7 total
owner: Opus brain (planner) + M2.7 (executor)
blockedBy: []
related:
  - 260429-graph-send-reliability/ (Sprint 1, đang ship tối nay)
  - memory/projects/sprint-14-email-tool.md (v7 state)
---

# Email Dashboard V8 — Master Plan

## Mission

V7 → V8: nâng dashboard từ "ship được nhưng silent fail" → "production-grade reliable + observable". 5 sprint phased, KHÔNG webapp/cloud (Sếp chốt local-only).

## Hiện trạng V7 — Audit verified

### ✅ Có rồi
- 6 Tkinter GUI views: `dashboard/auto_rate/send/scan/history/settings`
- 120 API endpoints local FastAPI port 8231
- Bounce infrastructure: `bounce_handler.py` (171 dòng) + `scanner/` (5 files) + `sent_scan_router.py`
- Graph sender: `graph_sender.py` (155 dòng)
- email_log.csv: 17,359 rows tracked
- Daily rotation 700 emails/weekday
- Master file v7 unified (22,854 rows + firmographic)

### ❌ Gaps verified (từ audit hôm nay)
1. **Send default = COM** (web_server.py:44) → silent fail. **Sprint 1 fix tối nay.**
2. **Email log thiếu verify columns**: chỉ có `timestamp, email, subject, campaign_id, status, reply_timestamp, cycle_id`. Thiếu `backend, graph_msg_id, verified, bounce_at, bounce_reason`.
3. **Bounce scanner đang dùng Outlook COM** (`inbox_scanner.py: Walk Outlook Inbox`). COM đã shutdown 04/27 → bounce detection KHÔNG hoạt động.
4. **Dashboard KHÔNG có failed/error tab** — Sếp không biết email nào lỗi.
5. **`auto_rate_view.py` 1264 dòng** — God object, hard to test/maintain.
6. **`web_server.py` 4152 dòng** — cần split.
7. **Test coverage 15%** (9 test / 61 core file).
8. **2 TODO lâu năm**: `cnee_milestone.py:44` (weekly digest), `main.py:412` (attachment extract).

## ⚓ Keep/Drop Matrix (Sếp confirm 2026-04-29)

**GIỮ NGUYÊN — không đụng:**
- 9 view web dashboard: Quick Send, Priority, Inbox, Insights, AI Model, Alerts, Open Tracker, Follow-up Queue, Settings
- Backend ẩn: daily rotation 700/weekday, sent scan, bounce KB, CNEE memory, suppression, WhatsApp integration, Panjiva pipeline, Smart draft AI, Send-time AI

**BỎ — chỉ web, drop desktop:**
- `email_engine/gui/views/*` (6 file Tkinter): dashboard_view, auto_rate_view (1264 dòng), send_view, scan_view, history_view, settings_view
- → Gap #5 (auto_rate_view god object) AUTO-RESOLVED bằng delete, không cần refactor
- → Cần check `app.py` import nào còn ref Tkinter trước delete

**Ref:** `~/.claude/projects/.../memory/project_email_v8_keep_drop_matrix.md`

## 5 Sprint Phased

### Sprint 1 — Graph Send Reliability (URGENT, tối nay 1-2h)
**Plan riêng:** [`260429-graph-send-reliability/plan.md`](../260429-graph-send-reliability/plan.md)

Fix:
- Default backend → graph
- Verify mechanism: poll Sent folder lấy graph_msg_id
- Dashboard badge ✅/⚠️/❌
- Log columns thêm: `backend, graph_msg_id, verified`

→ **Đang ship tối nay**.

### Sprint 2 — Error Detection Complete (1-2 ngày)

**Goal:** Sếp biết được email nào lỗi/bounce + lý do.

**Phase 2.1 — Bounce scanner migrate COM → Graph API:**
- `email_engine/scanner/inbox_scanner.py` thay `Walk Outlook Inbox` bằng `/me/messages?$filter=...`
- `bounce_handler.scan_bounces()` đọc Graph inbox, classify NDR pattern
- Auto-tag `processed_category` qua Graph categories API

**Phase 2.2 — Email log schema upgrade:**
- Append columns: `backend, graph_msg_id, verified, bounce_at, bounce_reason, retry_count, status_v2`
- Migration script: backfill existing 17,359 rows (status=SENT → status_v2=delivered)
- Backward compat: old reader code vẫn work (column add only)

**Phase 2.3 — Failed/Error tab mới trong dashboard:**
- Tkinter view `error_view.py` — hiển thị 3 categories: silent_fail, bounce, throttled
- Filter by date + recipient + bounce_reason
- Action button: "Retry" (re-queue), "Mark resolved", "Add to blacklist"
- Web HTML mirror tại `/api/errors` (Sếp xem điện thoại)

**Phase 2.4 — Auto-retry queue cho failed sends:**
- SQLite `~/.claude/email_retry_queue.db` (separate từ agent-failures.db)
- Schema: `id, original_send_ts, recipient, subject, html_body, retry_count, last_error, status (pending/retry/abandoned)`
- Cron 5 phút: pop pending, retry với exponential backoff (1m, 5m, 30m, 2h, abandon)
- Update email_log.csv + display dashboard

**Sprint 2 AC:**
- Bounce detection chạy qua Graph (no COM)
- Email log có 7 column mới, backfilled
- Dashboard có Error tab với action buttons
- 1 test send failed → tự retry sau 1 phút → log hiển thị retry_count=1

**Effort:** ~1.5-2 ngày M2.7.

### Sprint 3 — Tab Quality Audit + Upgrade (2-3 ngày)

**Đánh giá 6 tab hiện tại** (Sếp yêu cầu):

| Tab | Lines | Đánh giá hiện tại | Action V8 |
|---|---|---|---|
| `dashboard_view.py` | 272 | OK basic | Thêm KPI live: send rate, bounce rate, success% 24h |
| `auto_rate_view.py` | **1264** | God object | Split thành 4 module: rate_table, rate_compare, rate_pickup, rate_settings |
| `send_view.py` | 335 | OK | Add inline preview verify badge (từ Sprint 1) |
| `scan_view.py` | 298 | OK | Wire bounce results từ Graph scanner (Sprint 2) |
| `history_view.py` | 178 | Quá ít chức năng | Add filter advanced: date range, status, bounce-only, customer |
| `settings_view.py` | 217 | OK | Cleanup deprecated COM settings, add Graph token status |

**Phase 3.1 — Dashboard KPI Tab:**
- Live counter: emails sent today / quota / success rate
- Mini chart: hourly send histogram + bounce overlay
- Health indicator: Graph token expiry, queue size, last error

**Phase 3.2 — Auto Rate Refactor:**
- Split `auto_rate_view.py` 1264 → 4 file <400 lines mỗi cái
- Extract data layer (rate_data.py) khỏi view layer
- Add unit test cho rate filter logic

**Phase 3.3 — History Tab Advanced Filter:**
- Date picker (single date, range, last 7d/30d preset)
- Multi-select status filter
- Search by email/customer name
- Export filtered rows → CSV

**Phase 3.4 — Settings polish:**
- Remove deprecated COM toggle
- Add Graph token status badge (valid/expired/refresh-needed)
- Clear cache button

**Sprint 3 AC:**
- 6 tabs sau upgrade pass smoke test (no regression)
- `auto_rate_view.py` split thành 4 file <400 dòng mỗi cái
- Dashboard KPI tab live update mỗi 30s
- History tab filter combo work

**Effort:** ~2-3 ngày M2.7.

### Sprint 4 — Data Cleanup Pipeline (1-2 ngày)

**Goal:** Master file 22,854 rows clean, bounce-aware, deduped.

**Research từ web (em sẽ làm Phase 4.1):**
- Email list hygiene best practices (Mailgun/SendGrid/Postmark guides)
- SPF/DKIM/DMARC setup verification
- Domain reputation services (Talos, Sender Score, Postmaster Tools)
- Bounce classification taxonomy (hard vs soft, retry policy)

**Phase 4.1 — Research + design:**
- Web search 5 best-in-class email cleaning workflows
- Compare against Nelson current pipeline
- Propose specific add-ons (vd domain blacklist auto-update từ Spamhaus)

**Phase 4.2 — Master file dedup:**
- Detect duplicate emails (case-insensitive, normalized)
- Merge duplicate rows preserving best history
- Output report: X duplicates removed, Y rows preserved

**Phase 4.3 — Bounce-marked email archive:**
- Move hard bounces → `archive_blacklist.xlsx`
- Soft bounces ≥3 lần → cũng blacklist
- Whitelist re-inclusion mechanism

**Phase 4.4 — Domain reputation tracker:**
- Track per-domain success rate
- Auto-pause sends to domains <50% success rate (last 14d)
- Manual override + alert dashboard

**Sprint 4 AC:**
- Master file dedup report generated
- ≥X hard bounces moved to archive (X = count thực)
- Per-domain reputation table query <100ms
- Auto-pause threshold rule active

**Effort:** ~1-2 ngày M2.7.

### Sprint 5 — V8 Polish (defer 1 tuần)

**Phase 5.1 — Test coverage 15% → 50%:**
- Add test cho graph_sender, send pipeline, bounce_handler, rotation_engine
- Integration test: send 5 emails → verify all 5 in Sent folder

**Phase 5.2 — web_server.py 4152 dòng split:**
- Identify route groups → 4-6 router modules
- Extract data layer (cnee_loader.py) khỏi server
- Backward compat: same endpoints, same behavior

**Phase 5.3 — API documentation:**
- OpenAPI spec generate auto (FastAPI native)
- Group endpoints by tag (send/scan/rate/history/admin)
- Mount Swagger UI tại `/docs` local

**Phase 5.4 — Implement 2 TODO lâu năm:**
- `cnee_milestone.py:44` — weekly Telegram digest
- `main.py:412` — attachment extraction

**Sprint 5 AC:**
- Test coverage ≥50% verified by `pytest --cov`
- web_server.py <2000 dòng
- `/docs` Swagger UI accessible
- 2 TODO closed

**Effort:** ~3-4 ngày M2.7.

## Acceptance Criteria — V8 Toàn diện

| Tier | Definition | Verify |
|---|---|---|
| **Reliability** | 0 silent fail trong 7 ngày | Email log query: count(status="SENT" but graph_msg_id=null) = 0 |
| **Observability** | Sếp biết email nào lỗi <5 phút sau khi xảy ra | Error tab có entry trong 5 phút sau bounce |
| **Quality** | Test coverage ≥50%, no file >2000 dòng | pytest --cov + wc -l |
| **Performance** | Send rate vẫn ≥700/weekday | Daily rotation engine log |
| **Maintainability** | God objects split (auto_rate, web_server) | Lines count |
| **Data hygiene** | Hard bounces archived, dedup'd master | Master file row count + archive count |

## Sequence + Schedule

```
TỐI NAY:  Sprint 1 (graph-send-reliability) — 1-2h
NGÀY 1-2: Sprint 2 (error detection complete) — 1.5-2 ngày
NGÀY 3-5: Sprint 3 (tab quality + auto_rate refactor) — 2-3 ngày
NGÀY 6-7: Sprint 4 (data cleanup + research) — 1-2 ngày
DEFER:    Sprint 5 (polish) — 3-4 ngày sau khi 1-4 stable

TOTAL: ~8-12 ngày M2.7 active work
```

## Risk Register

| Risk | Mitigation |
|---|---|
| Graph API rate limit (30/min Exchange Online) | Pacing đã có ở graph_sender.py:96 (28/min) |
| Sent folder sync lag >30s | verify_in_sent_folder polling 30s với exponential backoff. Cron 5min recheck. |
| Migration backfill email_log.csv 17K rows fail mid-way | Atomic write to .tmp + rename. Backup .bak trước. |
| auto_rate_view split break UI | Phase 3.2 force smoke test 5 user flow trước commit |
| Domain reputation rule false-positive (block legit domain) | Manual override + dashboard alert |
| Test coverage push break existing tests | pytest --cov check old + new together |

## Sprint 1 Status

✅ Plan ready: [`260429-graph-send-reliability/plan.md`](../260429-graph-send-reliability/plan.md)
🔄 Đang ship via M2.7 terminal

## Next Step

Sau khi Sprint 1 GREEN tối nay:
1. Sếp test thử bấm Send 5 email → verify dashboard ✅ + msg_id
2. Em viết phase file chi tiết Sprint 2 (error detection)
3. Sếp paste prompt cho M2.7 ship Sprint 2

KHÔNG plan blind toàn bộ 5 sprint cùng lúc — phased delivery để Sếp pivot scope nếu cần.
