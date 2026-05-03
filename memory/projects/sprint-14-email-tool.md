# Project: Email Automation — v7 (CURRENT)
Last updated: 2026-04-29 (refreshed from git log + plans/archive)

## ⚠️ Anti-stale Note
Source of truth: this file + `git log` + `plans/archive/`. Glossary descriptions are HISTORICAL planning text — DO NOT rely on glossary for status.

## Current Stack (v7 SHIPPED 2026-04-24)
- Email pipeline: **Graph API only** (Outlook COM DEPRECATED — see "DEPRECATED" section)
- Daily rotation engine: 700 emails/weekday auto-scheduled
- Master schema: 2-sheet master (CNEE + SHIPPER), unified v7
- Dashboard: **localhost:8231 FastAPI + HTML local-only** — KHÔNG webapp/cloud (Sếp catch 2026-04-29: parquet sync cloud quá chậm). Frontend = HTML static + Tkinter GUI views.
- Rate engine: Rate Table v2 dual POL HPH+HCM + 10 POD cross-sell + IPI/RIPI gateway
- ⚠️ **DO NOT propose** webapp / Next.js / Supabase / Vercel cho email dashboard. Local-only đã chốt.

## Completed (✅ — DO NOT RE-SUGGEST)

### v7 Era (Apr 22-28)
- ✅ **v7 SHIPPED** 2026-04-24 (commit superseding v6 archive)
- ✅ Contact Info sheet parser + contact_unified_v7 wired to web_server (Apr 23)
- ✅ Panjiva buyer-level cleaner + migrate to unified v7 (Apr 23)
- ✅ Data flow SOT + validator for 6-layer pipeline (Apr 23)
- ✅ Scanner v7 stability fix + carrier auto-reply + 10 lanes + rule engine normalize (Apr 24)
- ✅ Dashboard Session Progress + Smart Send + Loading paren fix (Apr 24)
- ✅ rclone VPS check v7 master (replaces removed cnee_master.xlsx) (Apr 23)
- ✅ Rate Table v2 dual POL HPH+HCM + 10 POD cross-sell (Apr 25)
- ✅ Smart Quote Img + filter restore + burst-session detection (Apr 28)

### v6 Era (Apr 21-22) — superseded by v7
- ✅ Smart Send UI consolidation + preview modal (Apr 22)
- ✅ Rule engine + master file wire (v5→v6) + filelock (Apr 22)
- ✅ Dashboard Contacts tab + rotation progress widgets (Apr 22)
- ✅ Daily rotation engine — 700 emails/weekday (Apr 22)
- ✅ Phase 2.5 safety net + scan-sent 14d auto-block (Apr 22)
- ✅ Typo shield + bounce harvest + smart send window (Apr 22)
- ✅ 2-sheet master CNEE + SHIPPER migration (Apr 22)
- ✅ Bounce Fix v2 Class 46 ReportItem + unified feed + cooldown (Apr 21)
- ✅ CNEE Milestone Notify MVP v2 + VBA Sync button (Apr 21)

### Earlier
- ✅ S13 Rate & Send API
- ✅ S14A Dashboard v2 (FastAPI + HTML, localhost:8231) — GitHub b42646b, 896a1b2
- ✅ AI Model (XGBoost, 21 corridors, walk-forward)
- ✅ Market Intelligence badge + dynamic intro (URGENT/COMPETITIVE/STABLE)
- ✅ DuckDB 28x faster + Exp +2 day buffer
- ✅ 48h cooldown + email signature from config.xlsx
- ✅ Desktop shortcut (1-click launch)

## DEPRECATED — DO NOT USE / DO NOT SUGGEST

### Outlook COM
- **Status**: DEPRECATED entirely. Pipeline 100% Graph API.
- **Send path**: `email_engine/senders/graph_sender.py` is THE sender.
- **Scanner/Bounce**: also Graph API (delegated Mail.Read + Mail.Send permissions).
- **Legacy imports**: 5 files still `import win32com` but those imports are dead/unused branches:
  - `api/email_scanner.py`, `email_engine/api/routes/rotation_router.py`
  - `email_engine/core/bounce_handler.py`, `email_engine/core/cnee_milestone.py`
  - `email_engine/core/knowledge_ingest.py`
- **DO NOT propose** "migrate to Graph API" — already done. If COM import shows up in critique → propose REMOVAL of dead import, not migration.

### v3/v4/v5/v6 Plans
- All superseded. Archive locations:
  - `plans/archive/260414-email-automation-v3/`
  - `plans/archive/email-v4-v5-superseded-by-v6/`
  - `plans/archive/completed-2026-04/`
- Glossary still mentions S14B/C/D — those plans superseded by v3 → which itself superseded by v6 → which superseded by v7. Skip all.

## Active Work
Currently no active sprint plan. Next sprint TBD by Sếp.

## Key Decisions (current as of v7)
- Pipeline: 100% Graph API (no COM)
- Master schema: unified v7 with 2-sheet (CNEE + SHIPPER)
- Send rate: 700 emails/weekday via daily rotation engine
- Local dashboard at localhost:8231 (FastAPI + HTML)
- VPS sync via rclone, master file is v7 unified

## What Critique/Brainstorm SHOULD Verify (potential real gaps)
Before proposing, MUST cross-check `git log --since="14 days"` + `plans/archive/`:
- Active Jobs v4 (10 features planned per old plan — Sếp confirm status before suggest)
- Bot v5 production deployment (laptop-only — Sếp confirm if VPS deploy done)
- DuckDB archival policy (no current TTL evidence in git log — verify)
- Test coverage email_engine/core (currently 0% — verified via grep)

For any other suggestion: cross-check shipped signals first. If shipped → SKIP, never re-suggest.

## Sources Used to Build This
- git log Apr 20-28 inclusive (30+ commits parsed)
- plans/archive/ directory listing
- email_engine/senders/graph_sender.py existence verified
- All commit hashes verifiable via `git show <hash>`
