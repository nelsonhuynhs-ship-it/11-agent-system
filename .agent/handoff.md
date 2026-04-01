# Handoff Context — Nelson Freight
# Updated by: Laptop VP at 2026-03-30 11:00
# Read this FIRST when starting a new session on any machine

## Current Sprint
Sprint 12: Bot Intelligence + RAG + Email Pipeline + Auto Quote

---

## Session 2026-03-30 sáng (PC Home, 06:00–07:15)

### 1. GSD Framework Adoption (3 Phases)
- Installed GSD v1.30.0 (57 skills, 18 agents, 5 hooks) → `.agent/`
- Created 7 codebase docs → `.planning/codebase/` (STACK, INTEGRATIONS, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, CONCERNS)
- Created 4 planning artifacts → `.planning/` (PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md)
- GSD_ADOPTION_GUIDE.md (atomic commits, verify-work, milestone cycles)

### 2. FastAPI nelson-flow Endpoints (10 endpoints, all tested 200 OK)
| File | Action | Description |
|------|--------|-------------|
| `api/routers/pricing_router.py` | **NEW** | POST /pricing/check, GET /carriers, GET /ports |
| `api/services/quote_builder.py` | **NEW** | Buying/selling/profit calc + AJ cost breakdown |
| `api/routers/quote_router.py` | **MODIFIED** | Added POST /quotes/build + POST /quotes/{id}/send |
| `api/services/job_service.py` | **NEW** | Job activation + booking email + FAST_JOB_NO |
| `api/routers/job_router.py` | **NEW** | POST /jobs/activate, PATCH /fast-no, POST /booking-email, GET /active |
| `api/app.py` | **MODIFIED** | Mounted 2 new routers (13 total) |

---

## Session 2026-03-26 (Laptop VP — Full Day, committed 2026-03-30)

### Auto-Rate Email System ✅
- **[NEW]** `email_engine/core/auto_rate_builder.py` — query Parquet + build HTML rate table per customer route
- Tested: HPH→USCHI, USSAV — HPL, CMA rates confirmed
- Wired into `run_all.py` option 13 (AUTO QUOTE SEND)
- Added `--auto-rate` mode to `send_email.py` with preview + confirm

### Knowledge Per-Customer Parquet ✅
- **[NEW]** `email_engine/core/knowledge_ingest.py` — 692 .msg + 48 JSON → 587 unique emails → 12 per-customer parquets
- Output: `Pricing_Engine/data/knowledge_db/customer_*.parquet`
- Customers: HML(154), PANDA(113), Nafood(77), PT_FOOD(45), HER_HUI_WOOD(44), SIRI(43), VINARES(39), CREATIVE_LIGHT(35)

### Bot 'Neon' Bug Fix ✅
- `email_analytics.py` paths fixed: hardcoded → relative `BASE_DIR.parent`

### Rate Import Restored ✅
- Backup (10.2M) + new (273K) merged → 6,286,680 rows after dedup

### ShipmentBrain Upgraded ✅
- Dedup: 1,021 duplicates removed. Added `mentee_pic` + org_rules integration.

### Unified Scanner = 4 Jobs ✅
| # | Job                  | Module              | Schedule               |
|---|----------------------|---------------------|------------------------|
| 1 | Mentee Classification| main.py             | 09:00-17:30, every 30m |
| 2 | Pricing Import       | rate_importer.py     | 09:00-17:30, every 30m |
| 3 | Shipment Brain       | shipment_brain.py    | 09:00-17:30, every 30m |
| 4 | Knowledge Ingest     | knowledge_ingest.py  | 09:00-17:30, every 30m |

### Knowledge JSON Cleanup ✅
- ~460 raw JSON files deleted from `Pricing_Engine/data/knowledge/`
- Consolidated into `email_knowledge.parquet` via `build_knowledge_parquet.py`

---

## Session 2026-03-25 (Laptop VP — Full Day)

### N.E.L.S.O.N v2.0 Core (6 commits)
- ORACLE memory layer: conversations + profiles + DAG task queue
- SENTINEL heartbeat: 6 real checks
- Context memory: all routes save to Oracle, 8-turn history in Gemini

### Intelligence Pipeline
- `intelligence/email_intel.py` (221 LOC), `rate_predictor.py` (195 LOC), `rag_engine.py` (225 LOC)
- `TelegramBot/core/logger.py` (78 LOC) — JSON-lines structured logging
- 2 new scheduler jobs: rate_prediction (07:45), email_intel (21:00)

---

## ⚠️ ERP Note — Folders excluded from Git
`.gitignore` excludes: `ERP/core/`, `ERP/crm/`, `ERP/jobs/`, `ERP/quotes/`, `ERP/vba/`, `ERP/data/`, `email_engine/`, `*.xlsm`
Only tracked: `ERP/carrier_rules/` + `ERP/intelligence/`
**Solution:** Copy manually between machines or remove from .gitignore

---

## PC Home — TODO when switching
1. `git pull origin main`
2. Check `.planning/` folder — 12 GSD + codebase docs
3. Check `api/routers/` — 15 routers (3 new: pricing, job, + updated quote)
4. Review email_engine/ changes (local-only on Laptop VP)
5. Test API: `cd api && python -m uvicorn app:app --reload --port 8100`

## Laptop VP — TODO when switching
1. `git pull origin main`
2. Check `.planning/` + GSD agents
3. ERP: Copy `ERP/core/`, `ERP/data/`, `ERP/vba/` from local backup
4. Test bot: send message on Telegram → check AI context quality

## Blocked / Pending
- email_engine/ + ERP/ in .gitignore → code only on local machines
- Rate pipeline NOT fully automated (Windows Task runs data_collector, not rate_importer)
- 77 critical anomalies: threshold tuning needed
- USLAX port mapping fix pending
- VPS deploy: SSH issue blocking /api/reports/monthly

## VPS State (7 Scheduled Jobs)
| Time  | Job                  | Status     |
|-------|----------------------|------------|
| 05:30 | ETL Sync             | ✅ running |
| 06:00 | Rate Expiry Guardian | ✅ running |
| 07:30 | Morning Briefing     | ✅ running |
| 07:45 | Rate Prediction      | ✅ NEW     |
| 08:00 | SENTINEL Heartbeat   | ✅ UPGRADED|
| 08:00 | Anomaly Alerts (cron)| ✅ running |
| 21:00 | Email Intel Scan     | ✅ NEW     |

## Environment Notes
- Laptop VP: SSH GitHub ✅, SSH VPS ✅, Outlook ⚠️ (may need restart)
- PC Home: SSH GitHub ✅, SSH VPS ❓ (need test)
- VPS: bot active, 7 jobs scheduled
- Parquet: ~6.3M rows after dedup, email_knowledge.parquet created
