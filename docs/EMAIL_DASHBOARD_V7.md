# Email Dashboard v7 — Master Overview

**Last updated:** 2026-04-23 10:00
**Status:** ✅ VERIFIED LIVE (v7 Schema Migration + Contact Info enrichment + Firmographic data)
**Plan:** `plans/260422-1800-email-dashboard-v6-master/` (naming v6, content v7+)
**Dashboard UI:** `plans/visuals/email-dashboard-v7.html`
**Master Data:** `contact_unified_v7.xlsx` (62 cols, 22,854 CNEE rows, 2,338 SHIPPER rows)

---

## Session 2026-04-23 Shipped (v7 Migration — Contact Info + Firmographic Enrichment ✅)

**Completion:** v7 data migration completed 2026-04-23 (Panjiva contact + revenue integration)

**New in v7:**
- ✅ **Contact Info sheet source** — 22% email coverage from Panjiva shipment-level Contact Info (vs 1–2% buyer-level)
- ✅ **Firmographic enrichment** — Revenue, employees, suppliers, top products from buyer-level Panjiva
- ✅ **Multi-origin tracking** — POL_LIST, ORIGIN_COUNTRIES, MULTI_ORIGIN flag for companies sourcing multiple origins
- ✅ **Tier auto-scoring** — TIER_AUTO_SCORE (HOT/WARM/COLD) computed from revenue + shipments + recency
- ✅ **Decision maker capture** — PIC_NAME + PIC_POSITION from Contact Info sheet
- ✅ **v6 5-col LOCK preserved 100%** — EMAIL_STATUS, SEND_COUNT_EMAIL, LAST_SENT_EMAIL, REPLY_STATUS, TIER (v6 values untouched)

**Data integration:**
- v6 existing: 22,230 CNEE → matched + enriched with Panjiva firmographic
- Panjiva new: 624 new CNEE (found in Contact Info or buyer-level, not in v6)
- v7 result: 22,854 CNEE (22,230 enriched + 624 new)
- SHIPPER sheet: expanded 662 → 2,338 (1,676 new SEA shippers from shipment files)

**Files shipped:**
- `scripts/panjiva_clean_v3.py` (594 LOC) — Contact Info + buyer-level parser
- `scripts/_panjiva_v3_helpers.py` (406 LOC) — Panjiva extraction helpers
- `scripts/migrate-to-unified-v7.py` (538 LOC) — v6→v7 migration + enrichment
- `scripts/_migrate_v7_helpers.py` (387 LOC) — Migration helpers + TIER_AUTO_SCORE logic
- `email_engine/web_server.py` — Updated CNEE_V7 constant + _get_cnee_df fallback chain
- `docs/DATA_FLOW.md` — Updated Layer 4 (41→62 cols), added Layer 4a (Contact Info) + 4b (Firmographic)
- `docs/SYSTEM_STANDARDS.md` Section 1 — v7 file paths + rules 1.3–1.5

**OneDrive cleanup (2026-04-22):**
- Archived to `backups/legacy/` (10 files): v5 + v6 old versions, orphan rules files
- Active in root (10 files): v7 master, v5 fallback, config, mappings, shipment patterns

---

## Session 2026-04-22 23:30 Shipped (Rule Engine + Smart Consolidation ✅)

**Completion:** Rule Engine + Smart Consolidation session finalized 2026-04-22 23:30

**New capabilities:**
- ✅ `rule_engine.resolve_config()` auto-resolves POL + ARB per contact's ORIGIN_COUNTRY
- ✅ Malaysia (7,232 contacts) now route POL=PKG + ARB=port_klang (was HPH)
- ✅ China routes handle NGB variant correctly → `ningbo` key
- ✅ Smart Send UI consolidated: Markup input + Preview modal in 1 widget
- ✅ Master file unified: `contact_unified_v6.xlsx` sheet="CNEE" (22,842 rows)
- ✅ Filelock added: prevent concurrent write corruption
- ✅ Schema adapter: schema-agnostic v5/v6 load with fallback chain

**Files shipped:**
- `email_engine/core/rule_engine.py` (218 LOC)
- `email_engine/core/xlsx_lock.py` (NEW)
- `email_engine/core/cnee_schema_adapter.py` (NEW)
- `email_engine/web_server.py` (_get_cnee_df updated)
- `api/routers/contacts_router.py` (DuckDB fix)
- `plans/visuals/email-dashboard-v6.html` (UI)

**Verification:**
- Unit tests: 29/29 PASS
- Integration tests: 5/5 PASS
- Code review: 9.25/10 (0 critical, 8 minor follow-up)

**See:** `plans/260422-2330-rule-engine-smart-consolidation/plan.md` for full details.

---

## Mục tiêu Platform

Biến email tool từ 1 kênh (Email) thành **multi-channel intelligence-driven outreach platform**:
- **Email** — Optimized với daily rotation engine + anti-spam 5-layer (Phase 1 ✅ LIVE)
- **Prospect Intelligence** — Firmographic + decision maker data from Panjiva (Phase 1 v7 ✅)
- **WhatsApp** — Meta Cloud API direct (sandbox $0 tuần 1 → $20/tháng production, deferred Phase 5)
- **LinkedIn** — Sales Nav hybrid (deferred Phase 6)

Với master data **2-sheet tách riêng CNEE/SHIPPER**, bảo vệ priority customer, auto-harvest decision makers từ auto-reply + Panjiva Contact Info sheet.

**v7 advantage:** 62-col schema includes 21 new firmographic + multi-origin tracking. Enable intelligent segmentation (HOT prospects = high revenue + frequent shipments) + multi-lane rates (companies sourcing multiple origins).

---

## Session 2026-04-22 Shipped (Phase 1 ✅ VERIFIED)

**Batch validation:**
- ✅ Rotation batch ROT_1776868843: 700 emails queued → 700 SENT, 0 FAILED (2026-04-22 22:47–22:52)
- ✅ Bug fix: `queue_to_outlook_worker()` integrated with `auto_rate_builder` (import + function call + lane grouping optimization)
- ✅ Performance: Added 3-tier cache layer (30s/60s/300s TTL) to `/api/rotation/*` endpoints
- ✅ Doc audit: DAILY_ROTATION_ENGINE.md updated with known issues + performance metrics

**Deliverables this session:**
1. Queue integration wired (was LOG-only, now SEND)
2. Rate builder called 1x per lane instead of 700x per batch (24x lane grouping → from 700 calls to 24 calls)
3. Performance caching layer added to rotation API
4. Live batch (700 CNEE) successfully sent and verified

---

## Current State (Phase 1 ✅ COMPLETE)

**Files shipped (Phase 1 + 2026-04-22 fixes):**
- ✅ `scripts/panjiva_clean_v2.py` — Extract 15-col Panjiva raw + split CNEE/SHIPPER
- ✅ `scripts/migrate-to-unified-v6.py` — Merge 5 source file → 2-sheet master
- ✅ `email_engine/core/rotation_engine.py` — Daily 700-email plan builder (3h)
- ✅ `email_engine/core/rotation_helpers.py` — Config/data loaders (200 LOC split)
- ✅ `email_engine/core/typo_shield.py` — Fuzzy domain typo detector (RapidFuzz)
- ✅ `email_engine/core/typo_domains.py` — TOP_DOMAINS ~300 entries
- ✅ `email_engine/core/bounce_harvest_v2.py` — OOO/LEFT auto-detect + replacement extractor
- ✅ `email_engine/core/harvest_patterns.py` — Regex patterns (harvest detection)
- ✅ `email_engine/core/smart_send_window.py` — Timezone-aware send scheduling
- ✅ `email_engine/core/us_holidays.py` — US federal holiday calendar
- ✅ `email_engine/core/vn_holidays.py` — VN holiday calendar (Tết, 30/4, 2/9…)
- ✅ `email_engine/config/rotation_quota.json` — Commodity quota config
- ✅ `docs/SYSTEM_STANDARDS.md` — Section 6.5 Anti-Spam Standards added
- ✅ `docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md` — v6 architecture updated
- ✅ `email_engine/api/routes/rotation_router.py` — Added performance caching (30s/60s/300s TTL)
- ✅ `email_engine/core/rotation_engine.py` — Fixed queue_to_outlook_worker() integration + lane grouping

**Next phases:**
- 🔨 Phase 2 — Typo Shield + Bounce Harvest v2 wired into web_server.py
- ⏳ Phase 3 — Shipper Blacklist system (VN team overlap filter)
- ⏳ Phase 4 — Contacts Tab UI (CRUD + import/rollback)
- ⏳ Phase 5A — WhatsApp SANDBOX free test
- ⏳ Phase 5B — WhatsApp PRODUCTION $20/mo cap
- ⏳ Phase 6 — LinkedIn hybrid integration

---

## Architecture — Email Pipeline v7

```
MASTER DATA (2-sheet v7):
  D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx
  ├─ Sheet "CNEE" — 22,854 rows, active send
  │   Cols: EMAIL, COMMODITY_CATEGORY, TIMEZONE, EMAIL_STATUS,
  │          SEND_COUNT, LAST_SENT_DATE, REPLY_STATUS, TIER (v6 core),
  │          REVENUE_USD, EMPLOYEES, TOP_SUPPLIERS, TOP_PRODUCTS,
  │          PIC_NAME, PIC_POSITION, POL_LIST, ORIGIN_COUNTRIES,
  │          TIER_AUTO_SCORE (v7 new, 21 cols), ... (62 total)
  └─ Sheet "SHIPPER" — 2,338 rows (v6: 662), HOLD until VN blacklist ready
      (Same 62-col v7 schema, different audience)

BACKEND MODULES (email_engine/core/):
  rotation_engine.py          → Daily 700-email plan builder
  rotation_helpers.py         → Config/data loaders
  smart_send_window.py        → Timezone-aware scheduling
  typo_shield.py              → Fuzzy domain typo detect (≥92%→BLOCK, 85-91%→HOLD)
  bounce_harvest_v2.py        → OOO/LEFT detector + replacement extractor
  us_holidays.py + vn_holidays.py → Calendar logic

CONFIG (email_engine/config/):
  rotation_quota.json         → {daily_total: 700, by_commodity: {...}}

WEB SERVER (email_engine/):
  web_server.py               → :8100 FastAPI
    GET  /api/rotation/today     → today's plan JSON
    GET  /api/rotation/progress  → cycle progress + commodity bars
    POST /api/rotation/run-today → start batch send
    POST /api/send              → single email send (old endpoint)

UI (plans/visuals/):
  email-dashboard-v6.html     → 8 tabs:
    1. Quick Send        — batch 50+ manual UI
    2. Priority          — VIP/CUSTOMER tier filter
    3. Inbox             — recent replies + harvest panel
    4. Open Tracker      — read status from Outlook (polling 60s)
    5. Contacts          — 2-sheet browser (CRUD + import/rollback)
    6. WhatsApp          — sandbox/production toggle + templates
    7. LinkedIn          — deferred Phase 6
    8. Settings          — config editor + quota adjust + blacklist builder
```

---

## 5-Layer Anti-Spam Filter

**Applied in order (fail-safe):**

| Layer | Check | Result | Code |
|-------|-------|--------|------|
| 1. EXCLUDED | Customer in `excluded_customers.json` | SKIP + log BLOCKED | `load_excluded_emails()` |
| 2. SUPPRESSED | EMAIL_STATUS = SUPPRESSED/DEAD | SKIP + log SUPPRESSED | filter in `build_daily_plan()` |
| 3. COOLDOWN 7d | LAST_SENT_DATE ≤ today - 7d OR NULL | INCLUDE | enforce in `_get_eligible_candidates()` |
| 4. HARD LIMIT 3/30d | SEND_COUNT < 3 AND sent <3 in last 30d | INCLUDE | check + enforce in filter |
| 5. TYPO SHIELD | Domain fuzzy match via RapidFuzz | BLOCK (≥92%) or HOLD (85-91%) | `typo_shield.check_typo()` |

**Violation logging:**
```
ROTATION: Filtered 57 emails (EXCLUDED), 230 (COOLDOWN), 45 (HARD_LIMIT), 12 (TYPO_BLOCK)
Target: 700 → Actual: 656 (auto-redistribute surplus among commodities)
```

---

## Daily Rotation Logic

**Quota distribution (from config file):**

```json
{
  "daily_total": 700,
  "by_commodity": {
    "FLOORING": 150,
    "FURNITURE_INDOOR": 150,
    "CANDLE": 100,
    "RUBBER": 100,
    "PLASTIC": 100,
    "PLYWOOD": 50,
    "FOOD_AMBIENT": 30,
    "OTHERS": 20
  },
  "cooldown_days": 7,
  "hard_limit_count": 3,
  "hard_limit_window_days": 30
}
```

**Algorithm (rotation_engine.py::build_daily_plan):**

1. Load master CSV (CNEE sheet)
2. Filter 5 layers (EXCLUDED → SUPPRESSED → cooldown → hard limit → typo)
3. Group by COMMODITY_CATEGORY
4. For each commodity, pick top N (sorted SEND_COUNT ASC, LAST_SENT_DATE ASC NULLS FIRST)
5. If commodity has <quota candidates:
   - Calc deficit (e.g., GARMENT wants 50, only 30 eligible)
   - Redistribute deficit to next commodity (cascade)
6. Return JSON: `{ date, target_total, actual_total, by_commodity: {}, redistributed: {}, cycle_info: {} }`

**Example output:**

```json
{
  "date": "2026-04-23",
  "target_total": 700,
  "actual_total": 698,
  "by_commodity": {
    "FLOORING": {
      "quota": 150,
      "picked": 150,
      "candidates_remaining": 3500,
      "emails": ["john@flooring.com", "jane@hardwood.com", ...]
    },
    "GARMENT": {
      "quota": 20,
      "picked": 20,
      "candidates_remaining": 140,
      "emails": [...]
    }
  },
  "redistributed": {
    "APPAREL": 10,  // originally 20, but only 10 new eligible
    "ELECTRONICS": 8
  },
  "cycle_info": {
    "cycle_number": 1,
    "week_in_cycle": 2,
    "weeks_total_estimate": 5.3,
    "total_unsent_remaining": 17740
  }
}
```

---

## Scan Sent Workflow (Auto-Trigger)

**Trigger:** After `POST /api/rotation/run-today` batch completion

**Execution:** `scan-sent-outlook.py`

1. Read Outlook Sent folder (last 14 days)
2. Extract email metadata: FROM, TO, SUBJECT, BODY, DATE_SENT
3. For each sent email:
   - Look up recipient in master CNEE sheet
   - Scan replies to extract:
     - OOO auto-reply → parse return date → set DEFER_UNTIL column
     - LEFT/no longer here → extract replacement contact (position classifier)
     - BOUNCED hard bounce → set EMAIL_STATUS = DEAD
4. Update master file: REPLY_STATUS + EMAIL_STATUS + DEFER_UNTIL
5. Write scan log: `email_engine/logs/scan_sent_2026-04-23_0830.log`
6. Queue replacement candidates → `email_engine/data/replacement_candidates.json` for Nelson review
7. Commit to git: `git add email_engine/logs/scan_sent_*.log && git commit -m "scan: sent audit 2026-04-23"`

---

## Smart Send Window (Timezone-Aware)

**Purpose:** Avoid spam filters + inbox overload

**Target:** Tuesday/Wednesday/Thursday, 9–11h local time (contact's TIMEZONE column)

**Avoid:** Monday <10h, Friday >15h, Sat/Sun, US federal holidays

**URGENT bypass:** Contact['URGENT']==True → send immediately

**Implementation:** `smart_send_window.py::plan_send_time(contact_row, now_utc)`

Returns UTC send time (converted from contact's local timezone).

---

## Typo Shield (RapidFuzz)

**Purpose:** Prevent silent sends to mistyped domains

**Thresholds:**
- ≥92% similarity → auto-BLOCK (log ERROR, skip)
- 85–91% similarity → HOLD (flag for Nelson review)
- <85% similarity → OK (send)

**Domain list:** `email_engine/core/typo_domains.py`
```python
TOP_DOMAINS = [
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "aol.com", "icloud.com", "protonmail.com", ...  # ~300 entries
]
```

**Examples detected:**
- `john@gmail.co` → suggest `john@gmail.com` (BLOCK ≥96%)
- `jane@yaho.com` → suggest `jane@yahoo.com` (HOLD 89%)
- `bob@microsoft.comm` → (BLOCK 94%)

---

## Bounce Harvest v2 (OOO/LEFT Detection)

**Purpose:** Auto-classify auto-reply + extract replacements

**Patterns:** `email_engine/core/harvest_patterns.py`

| Pattern | Action |
|---------|--------|
| "out of office", "out-of-office", "i'm out" | OOO → extract return date |
| "no longer here", "left the company", "not working here" | LEFT → extract replacement contact |
| Hard bounce: "5.1.1 bad recipient" | BOUNCED → set EMAIL_STATUS=DEAD |

**Replacement extraction:**
- Regex EMAIL_RX: `(\w+[\w.%+-]+@[\w.-]+\.\w+)`
- Position classifier: "Pricing" / "Booking" / "Operations" / "Sales" / "General"
- Confidence score: position keywords found = 1.0, generic = 0.7
- Filter: don't suggest contacts same domain as sender (internal)
- Queue: `email_engine/data/replacement_candidates.json`

Example:
```json
{
  "original_email": "john@oldcompany.com",
  "original_position": "PRICING",
  "harvest_date": "2026-04-22T14:30:00Z",
  "candidates": [
    {
      "email": "jane.pricing@newcompany.com",
      "position": "PRICING",
      "confidence": 1.0,
      "context_snippet": "...please contact Jane Smith (jane.pricing@newcompany.com)..."
    }
  ]
}
```

---

## Files & Modules

| File | Purpose | LOC | Status |
|------|---------|-----|--------|
| `scripts/panjiva_clean_v3.py` | Extract Contact Info + buyer-level Panjiva, parse Decision Maker | 594 | ✅ v7 |
| `scripts/_panjiva_v3_helpers.py` | Panjiva extraction utilities | 406 | ✅ v7 |
| `scripts/migrate-to-unified-v7.py` | v6→v7 migration + Panjiva enrichment + TIER_AUTO_SCORE | 538 | ✅ v7 |
| `scripts/_migrate_v7_helpers.py` | Migration + enrichment helpers | 387 | ✅ v7 |
| `scripts/panjiva_clean_v2.py` | Extract 15-col Panjiva + split CNEE/SHIPPER (legacy v6 parser) | 197 | ↪ archived |
| `scripts/migrate-to-unified-v6.py` | Merge 5 files → 2-sheet master (legacy v6 migration) | 199 | ↪ archived |
| `email_engine/core/rotation_engine.py` | Daily 700-email plan builder | 254 | ✅ |
| `email_engine/core/rotation_helpers.py` | Config/data loaders | 203 | ✅ |
| `email_engine/core/typo_shield.py` | Fuzzy domain typo detect | 131 | ✅ |
| `email_engine/core/typo_domains.py` | TOP_DOMAINS ~300 | 52 | ✅ |
| `email_engine/core/bounce_harvest_v2.py` | OOO/LEFT auto-detect | 221 | ✅ |
| `email_engine/core/harvest_patterns.py` | Regex patterns | 184 | ✅ |
| `email_engine/core/smart_send_window.py` | Timezone-aware scheduling | 194 | ✅ |
| `email_engine/core/us_holidays.py` | US federal holiday calendar | 68 | ✅ |
| `email_engine/core/vn_holidays.py` | VN holiday calendar | 125 | ✅ |
| `email_engine/config/rotation_quota.json` | Commodity quota config | — | ✅ |
| `plans/visuals/email-dashboard-v7.html` | 8-tab UI (v7 data binding) | — | 🔨 Updating |
| `docs/SYSTEM_STANDARDS.md` | Section 1 (v7 paths) + 6.5 (anti-spam) | — | ✅ v7 |
| `docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md` | v6 architecture (needs v7 update) | — | ⏳ pending |
| `docs/EMAIL_DASHBOARD_V7.md` | This file (master overview v7) | — | ✅ v7 |
| `docs/DATA_FLOW.md` | Layer 4 schema (41→62 cols v7), Layer 4a Contact Info | — | ✅ v7 |
| `docs/PANJIVA_EXPORT_GUIDE.md` | How to export + import Panjiva files | — | 🔨 NEW |
| `docs/MASTER_V7_SCHEMA.md` | Full 62-col v7 schema reference + lock rules | — | 🔨 NEW |
| `docs/DAILY_ROTATION_ENGINE.md` | Rotation engine specific doc | — | 🔨 Creating |

---

## Success Metrics (v7 Status)

| Metric | Baseline (v4) | Target (v6–7) | Current (v7) |
|--------|-----------|-------------|---------|
| Email open rate | 3.7% | 12–15% | TBD (tracking Phase 5) |
| Send volume/day | 200–300 | 700 weekday | ✅ 700 verified |
| Per-recipient max sends | Uncontrolled | 3/30d hard limit | ✅ enforced |
| Typo silent sends | 345/month | 0 | ✅ 0 (Typo Shield) |
| Pool size (CNEE) | 22,230 | 25–28K clean | ✅ 22,854 (v7) |
| Data files | 7 scattered | 1 master 2-sheet | ✅ 1 unified v7.xlsx |
| Pool size (SHIPPER) | 0 (mixed) | 5–8K separate | ✅ 2,338 v7 |
| Firmographic coverage | 0% | — | ✅ 98% (Panjiva revenue) |
| Decision maker emails | 2% | — | ✅ 22% (Contact Info sheet) |
| Multi-origin tracking | 0% | — | ✅ 624 companies detected |

---

## Known Issues & Resolutions

### Resolved (2026-04-22)
- ✅ Queue integration bug (LOG vs SEND) — fixed, verified with batch ROT_1776868843
- ✅ Import path incorrect — corrected to `from email_engine.core.auto_rate_builder`
- ✅ Rate builder inefficiency (700 calls/batch) — optimized to lane grouping (24 calls for 700 emails)

### Remaining for Phase 2+
None blocking Phase 1. See `plans/260422-1800-email-dashboard-v6-master/` for full implementation details + Phase 2–6 roadmap.

### Performance notes
- Cache hit latency still 1–2s (database lock from concurrent worker threads) — monitor for 2–3 days, then optimize if needed
- Lane grouping reduces rate builder CPU load from O(n) to O(unique lanes)

---

## Related Docs

- [Data Flow — Layer 4 Schema](./DATA_FLOW.md) — v7 CNEE schema (62 cols) + Layer 4a Contact Info + 4b Firmographic
- [PANJIVA_EXPORT_GUIDE.md](./PANJIVA_EXPORT_GUIDE.md) — **NEW** How to export Panjiva files for quarterly v7 refresh
- [MASTER_V7_SCHEMA.md](./MASTER_V7_SCHEMA.md) — **NEW** Full 62-col reference + lock rules + per-column purpose
- [Daily Rotation Engine](./DAILY_ROTATION_ENGINE.md) — Specific module doc
- [Email Pipeline Source of Truth](./EMAIL_PIPELINE_SOURCE_OF_TRUTH.md) — Canonical architecture (needs v7 update)
- [System Standards Section 1](./SYSTEM_STANDARDS.md#section-1--canonical-file-paths) — v7 file paths + rules 1.3–1.5
- [System Standards Section 6.5](./SYSTEM_STANDARDS.md#section-65--email-anti-spam-standards-v6-2026-04-22) — Anti-spam rules
- [Plan: v6 Master](../plans/260422-1800-email-dashboard-v6-master/plan.md) — Full roadmap (applies v7 data layer)
