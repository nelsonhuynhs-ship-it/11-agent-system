# Email Pipeline — Source of Truth

**Last updated:** 2026-04-22 23:00
**Status:** 🔒 AUTHORITATIVE — DO NOT bypass
**Version:** v6.1 (verified 2026-04-22 — Rotation Engine queue integration tested live)

---

## ONE sentence

**Email send = `email_engine/web_server.py` (local PC) → 5-filter anti-spam layer → Smart Send Window → Outlook COM desktop.**
Không có API VPS, không có webapp Next.js trong chuỗi gửi email. Master data = 2-sheet unified v6.

---

## Allowed path (only one) — v6 Architecture

```
┌─ Nelson click [SEND] / Daily Rotation ─┐
│  web browser:                           │
│  - Quick Send (batch 50+)               │
│  - Daily Rotation 08:00 auto            │
│  → plans/visuals/email-dashboard-v6.   │
│    html (local browser)                 │
└───────────┬─────────────────────────────┘
            │ HTTP (localhost:8100)
            ▼
┌─────────────────────────────────────────────────┐
│ email_engine/web_server.py  (local PC)          │
│   GET  /api/rate-preview                        │
│   POST /api/send                                │
│   GET  /api/rotation/today                      │
│   POST /api/rotation/run-today                  │
│                                                 │
│ → Filter chain (5 layers):                      │
│   1. EXCLUDED list check                        │
│   2. SUPPRESSED status check                    │
│   3. Cooldown 7d enforcement                    │
│   4. Hard limit 3/30d check                     │
│   5. Typo Shield (RapidFuzz domain)             │
│                                                 │
│ → auto_rate_builder.                           │
│     build_rate_table_for_customer()             │
│ → smart_send_window.                           │
│     plan_send_time(contact, tz)                │
│ → outlook.CreateItem().Send()                  │
│ → _log_send() → email_log.csv                  │
│ → Update SEND_COUNT + LAST_SENT_DATE           │
└─────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ Scan Sent (auto-trigger after    │
│ batch completion via webhook)    │
│                                  │
│ scan-sent-outlook.py:            │
│   → Read Outlook Sent (14d)      │
│   → bounce_harvest_v2.py         │
│      (OOO/LEFT detect)           │
│   → Update EMAIL_STATUS +        │
│      REPLY_STATUS                │
│   → Queue replacements           │
└──────────────────────────────────┘
```

**Data flow (daily rotation scenario):**

```
Master file: contact_unified_v6.xlsx (CNEE sheet)
           ↓
   rotation_engine.py::build_daily_plan()
   (reads config/rotation_quota.json)
           ↓
   Filter 5 layers + sort by SEND_COUNT ASC
           ↓
   Returns JSON: { date, target, by_commodity }
           ↓
   Dashboard shows progress bars per commodity
           ↓
   Nelson clicks "Start today's batch"
           ↓
   POST /api/rotation/run-today
           ↓
   web_server loop: for each email in plan
     → smart_send_window.plan_send_time()
     → outlook.CreateItem().Send()
     → Update master: SEND_COUNT+1, LAST_SENT_DATE=today
           ↓
   After batch: scan-sent-outlook.py runs auto
   (webhook trigger or Task Scheduler)
           ↓
   Next day: build_daily_plan() skips 7d cooldown
   emails → new cohort picked
```

**Data sources (v6):**
- Master contact data → `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx` (CNEE sheet)
- Excluded customers → `email_engine/data/excluded_customers.json` (Nelson manual + scanner auto)
- Rotation quota → `email_engine/config/rotation_quota.json`
- Daily plans → `email_engine/data/daily_plans/YYYY-MM-DD.json` (archive)
- Replacement candidates → `email_engine/data/replacement_candidates.json` (harvest queue)
- Rates → `Pricing_Engine/data/Cleaned_Master_History.parquet` (OneDrive, via DuckDB)
- Port map → `email_engine/data/Port_Code_Mapping_Final.xlsx`
- ARB rates → `email_engine/data/arb_rates.yaml`
- Log → `email_engine/logs/email_log.csv`
- Sent scan log → `email_engine/logs/scan_sent_YYYY-MM-DD_HHMM.log`

---

## FORBIDDEN paths (all removed 2026-04-17)

These were deleted. **Do NOT recreate them.**

### Backend
| File | Status |
|------|--------|
| `api/routers/email_rate_router.py` | ❌ DELETED |
| `api/routers/email_queue_router.py` | ❌ DELETED |
| `api/routers/auto_quote_router.py` | ❌ DELETED |
| `api/pipeline/queue_manager.py` | ❌ DELETED |

### Webapp (Next.js)
| File | Status |
|------|--------|
| `webapp/src/app/dashboard/rate-send/` | ❌ DELETED |
| `webapp/src/app/dashboard/email-campaign/` | ❌ DELETED |
| `webapp/src/app/dashboard/email-log/` | ❌ DELETED |
| `webapp/src/lib/api.ts` → `emailRateApi`, `campaignApi` | ❌ REMOVED |
| `webapp/src/hooks/useApi.ts` → email/campaign hooks | ❌ REMOVED |
| `webapp/src/lib/schemas.ts` → email/campaign zod | ❌ REMOVED |

**Kept (different purpose — NOT email send):**
- `api/routers/email_router.py` — Email Event Engine (scan Outlook inbox, alerts, timeline). Uses `email_worker.py`, `email_scanner.py`, `email_event_engine.py`. This is READ, not SEND.

---

## Why this matters (incident log)

**2026-04-17** — Nelson phát hiện code được apply vào `email_rate_router.py` + webapp `rate-send` page thay vì `web_server.py`. Hai path khác nhau → edit sai path = không thấy kết quả trên thực tế. Root cause: nhiều router tên giống nhau, tài liệu phân tán, không có source of truth rõ ràng.

**Fix:** Xoá toàn bộ deprecated path. Chỉ còn 1 path = `web_server.py`. File này là source of truth duy nhất.

---

## Checklist trước khi thêm email endpoint

Nếu ai đó (người/AI) định thêm endpoint email:

- [ ] Endpoint có nằm trong `email_engine/web_server.py` không? → **Nếu không, STOP.**
- [ ] Có gửi qua Outlook COM local không? → **Nếu không, STOP.** (SMTP không dùng)
- [ ] Có thêm vào `api/` hoặc `webapp/`? → **Tuyệt đối KHÔNG.**
- [ ] File có tên chứa `email_*_router.py`, `email-rate/*`, `email-campaign/*`, `email-log/*`? → **Dấu hiệu recreate path chết. Review lại.**

---

## ⚠ Orphan files (cần dọn lần sau)

Các file sau ĐANG gọi `http://14.225.207.145:8100/api/email-rate/*` (VPS API đã chết 2026-04-17):

- `email_engine/outlook_send_agent.py` — poll agent (cũ — web_server.py đã inline Outlook send, không cần agent)
- `email_engine/ingest/send_with_rates.py` — API_BASE hard-code VPS
- `email_engine/run_outlook_agent.bat` — launcher cho agent dead
- `email_engine/tests/test_integration.py` — test chạy sẽ 404

**Action:** Hoặc (a) xoá nếu không dùng, (b) update API_BASE → `http://localhost:8100` (web_server.py local).

---

## Future extensions

Khi cần thêm tính năng email (bulk send, template engine, scanner…):
- Code thêm vào `email_engine/` (core, intelligence, scanner) modules
- Expose qua `web_server.py` endpoints
- UI dùng `plans/visuals/email-dashboard-v4.html` (hoặc file HTML local khác)

**KHÔNG** dùng FastAPI main app (`api/`) hoặc Next.js webapp (`webapp/`).

---

## References
- Phase 07 plan: `plans/260416-email-nelson-solo-platform/phase-07-vps-cleanup.md`
- North Star: `memory/nelson-slogan-and-focus.md`
- Outlook constraint: `memory/project-email-outlook-com-constraint.md`
- Stack audit (pre-cleanup): `memory/project-email-stack-audit.md`
