# Project: Sprint 14 — Email Tool Upgrade
Last updated: 2026-04-01

## Mục tiêu
Transform Rate & Send từ "công cụ gửi email đơn giản" thành **Email Intelligence Platform**.

## Phases

### ✅ S13 (Done)
- Rate & Send API: `email_rate_router.py`
- WebApp UI: `dashboard/rate-send/page.tsx`
- Campaign CNEE tab: bulk send 50, filters, stats

### 🔨 S14A — Fix Core Rate Query (IN PROGRESS, 2026-04-01)
**Problem:** Preview "No rates found" vì data stale > 30 ngày
**Fix:**
1. Smart fallback: 30d → 60d → 90d tự động
2. Rate freshness badge per-row: "3d ago" / "9d ago ⚠️"
3. POD mapping debug: show "USLGB → Long Beach (mapped)" trong response
**Files:** `api/routers/email_rate_router.py`
**Effort:** ~5h | **Risk:** Low

### ⏳ S14B — Email History + Follow-up Dashboard
**What:**
- `/api/email-rate/history` endpoint đọc email_log.csv
- New page: `dashboard/email-history/page.tsx`
- Follow-up Alert Panel (badge đỏ trên sidebar)
- SEQ_STEP auto-increment khi gửi
**Files:** router + 2 new tsx files
**Effort:** ~12h | **Risk:** Medium

### ⏳ S14C — Rate Intelligence
**What:**
- Price delta: so sánh giá lần này vs lần trước gửi cho khách
- Per-campaign default markup (config trong cnee_master)
- Rate Health widget trên Overview dashboard
**Files:** router + overview page
**Effort:** ~9h | **Risk:** Low-Medium

### ⏳ S14D — Bulk Send Intelligence
**What:**
- Pre-send validation gate (filter stale rates, cooldown check)
- Real-time progress (SSE hoặc polling)
- Cooldown logic per CNEE (default 7 ngày)
**Files:** router (bulk endpoint refactor)
**Effort:** ~11h | **Risk:** Medium

## Data Schema (cnee_master.xlsx)
Columns hiện có:
- EMAIL, COMPANY, CNEE_PIC, POL, DESTINATION, CARRIER
- TOTAL_SHIPMENT, CAMPAIGN_ID, EMAIL_QUALITY_SCORE, KB_STATUS
- ALREADY_SENT, LAST_SENT_DATE, SEQ_STEP, SEQ_LAST_SENT, SEQ_STATUS, SOURCE

Columns cần thêm (S14B+D):
- DEFAULT_MARKUP (per campaign)
- COOLDOWN_DAYS (default 7)

## Key Metrics (current)
- 5,316 total prospects
- 4,198 already sent (ALREADY_SENT=Y)
- 1,118 not sent (target)
- 585 rows in email_log.csv
- SEQ_STEP = 0 for ALL prospects (sequence not yet activated)
- 5 follow-up alerts in followup_alerts.csv
