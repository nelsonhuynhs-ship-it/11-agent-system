# NELSON SYSTEM MAP — 2026-03-22

> Auto-generated system scan. READ-ONLY report — nothing was modified.
> Scan time: 22:44 → 22:50 (Mar 22, 2026)

---

## 1. Folder Structure Overview

```
D:\NELSON\2. Areas\PricingSystem\Engine_test\
├── ERP\                          # Excel-based ERP system
│   ├── core\                     # Python build + refresh scripts (5 files)
│   ├── carrier_rules\            # JSON booking/weight rules
│   ├── crm\                      # CRM dashboard
│   ├── data\                     # ERP_Master.xlsm + staging files
│   ├── intelligence\             # 12 Python modules (alerts, tracking, reports)
│   ├── jobs\                     # Job enrichment + email builder
│   ├── quotes\                   # Quote CRUD + image gen
│   ├── vba\                      # 8 VBA modules (.bas files)
│   └── ERP_SYSTEM_GUIDE.md
│
├── Pricing_Engine\               # Rate data pipeline
│   ├── config\                   # nmi_config.json
│   ├── data\                     # Parquet (10.2M rows) + PUC + custeam
│   │   └── custeam\              # 24 rows parsed space data + JSON
│   ├── models\                   # EMPTY (capacity_risk, price_trend, training)
│   ├── scripts\                  # master_loader_v2 etc.
│   ├── reports\
│   ├── OCR_Engine\, OCR_Input\, OCR_Output\
│   ├── rate_importer.py          # 41 KB — Outlook → Parquet pipeline
│   ├── rate_monitor.py           # NEW — NMI Rate Anomaly Detector
│   ├── parquet_auditor.py        # 27 KB
│   ├── puc_importer.py           # 14 KB
│   ├── clean_parquet.py          # 6 KB
│   ├── run.py                    # CLI entry
│   ├── setup_scheduler.py        # Windows Task Scheduler
│   ├── setup_v13_sheets.py       # Sheet header setup
│   └── test_v13_ribbon.py        # ERP V13 tests
│
├── TelegramBot\                  # Bot v5 system (32 files)
│   ├── bot_v5.py                 # 82 KB — Main bot handlers
│   ├── ai_chat.py                # Gemini AI integration
│   ├── ai_pricing.py             # AI pricing recommendations
│   ├── ai_risk_engine.py         # Risk assessment
│   ├── ai_sales_intel.py         # Sales intelligence
│   ├── auto_email_booking.py     # Auto booking emails
│   ├── bot_menu.py               # Menu system
│   ├── customer_intelligence.py  # Customer analysis
│   ├── customer_profiles.py      # HML/SIRI/PANDA profiles
│   ├── dashboard_builder.py      # PNG chart builder
│   ├── data_lake.py              # Data aggregation
│   ├── database.py               # SQLite management  
│   ├── email_analytics.py        # Email analysis
│   ├── erp_reader.py             # ERP read-only access
│   ├── erp_writer.py             # Quote→Job conversion
│   ├── etl_sync.py               # ETL sync
│   ├── freetime_formatter.py     # Freetime output
│   ├── hpl_commands.py           # HPL API commands
│   ├── intelligence_features.py  # 32 KB — 10 intelligence features
│   ├── kpi_store.py              # KPI + Forecast + Pipeline
│   ├── markup_engine.py          # Pricing markup
│   ├── nl_query_agent.py         # Natural language queries
│   ├── query_engine.py           # Parquet query
│   ├── query_parser.py           # Query parsing
│   ├── quote_formatter.py        # Quote formatting
│   ├── rate_expiry_guardian.py    # Rate expiry alerts
│   ├── rate_limiter.py           # API rate limiting
│   ├── win_loss_analyzer.py      # Win/loss analysis
│   ├── carrier_tips.json         # Advisory notes
│   ├── config.py                 # Bot config
│   ├── requirements.txt
│   ├── start_bot.bat
│   └── data\                     # freight_bot.db (SQLite)
│
├── email_engine\                 # Email intelligence system
│   ├── core\                     # 18 Python modules (described below)
│   ├── data\                     # 11 data files (customer, shipper, rules)
│   ├── ingest\                   # Email ingestion
│   ├── outlook\                  # Outlook integration
│   ├── data_panjiva\             # Panjiva trade data
│   ├── logs\                     # shipments.db (SQLite)
│   ├── assets\
│   ├── backup\
│   ├── _archive\, _backup\
│   ├── run_all.py                # Main runner
│   ├── test_pipeline.py          # Pipeline tests
│   ├── backup.pst                # 7.5 GB PST archive
│   └── setup_*.ps1               # Task scheduler scripts
│
├── api\                          # FastAPI backend
│   ├── app.py                    # Main FastAPI app
│   ├── config.py                 # API config
│   ├── data_access.py            # 22 KB data layer
│   ├── email_event_engine.py     # 20 KB event processing
│   ├── email_scanner.py          # 19 KB scanner
│   ├── erp_api_bridge.py         # ERP bridge
│   ├── event_bus.py              # Event bus
│   ├── quote_intelligence.py     # 15 KB quote AI
│   ├── quote_store.py            # 16 KB quote storage
│   ├── routers\                  # 11 API routers
│   ├── services\                 # notification.py
│   ├── middleware\
│   ├── workers\
│   └── database\
│
├── webapp\                       # Next.js 16 frontend
│   ├── src\app\                  # 8 pages (below)
│   ├── src\components\layout\    # Sidebar.tsx, Topbar.tsx
│   ├── src\lib\
│   └── package.json              # Next.js 16 + React 19 + Tailwind v4
│
├── assets\                       # Shared assets
├── _archive\                     # Archived code
└── .agent\                       # AI agent system
    ├── memory\                   # 6 files (context, backlog, logs, DBs)
    ├── agents\                   # CTO multi-agent system
    ├── workflows\                # 10+ workflow definitions
    ├── skills\                   # 50 skills (listed below)
    └── miniapp\                  # Telegram Mini App prototype
```

---

## 2. WebApp — Pages Built So Far

**Stack:** Next.js 16.1.6 | React 19.2.3 | Tailwind CSS v4 | Recharts 3.8 | TypeScript 5

### Pages (8 total)

| Route | File | Purpose |
|---|---|---|
| `/` | `app/page.tsx` | Root landing (redirect to dashboard) |
| `/dashboard` | `app/dashboard/page.tsx` | Main dashboard overview |
| `/dashboard/pricing` | `app/dashboard/pricing/page.tsx` | Rate pricing view |
| `/dashboard/quotes` | `app/dashboard/quotes/page.tsx` | Quotes management |
| `/dashboard/customers` | `app/dashboard/customers/page.tsx` | Customer CRM view |
| `/dashboard/shipments` | `app/dashboard/shipments/page.tsx` | Shipment tracking |
| `/dashboard/ai` | `app/dashboard/ai/page.tsx` | AI intelligence panel |
| `/dashboard/team` | `app/dashboard/team/page.tsx` | Team management |

### Components

| Component | Size | Purpose |
|---|---|---|
| `Sidebar.tsx` | 7.2 KB | Navigation sidebar |
| `Topbar.tsx` | 2.4 KB | Top navigation bar |

### Status
- ⚠️ Has `.next/` build dir → was built at least once
- ⚠️ No API connection config visible in `src/lib/`
- ⚠️ Only 2 layout components — needs more UI components

---

## 3. API — FastAPI Backend

### Routers (11 total)

| Router | Size | Purpose |
|---|---|---|
| `rate_router.py` | 17 KB | Rate queries and comparisons |
| `erp_router.py` | 15 KB | ERP data access |
| `hpl_router.py` | 8 KB | HPL carrier API integration |
| `health_router.py` | 5 KB | System health checks |
| `dashboard_router.py` | 5 KB | Dashboard data aggregation |
| `intelligence_router.py` | 4 KB | Intelligence queries |
| `quote_router.py` | 5 KB | Quote management |
| `email_router.py` | 3 KB | Email integration |
| `worker_router.py` | 3 KB | Background worker control |
| `shipment_router.py` | 2 KB | Shipment tracking |
| `auth_router.py` | 2 KB | Authentication |

### Core Services

| File | Size | Purpose |
|---|---|---|
| `data_access.py` | 22 KB | Data layer / Parquet queries |
| `email_event_engine.py` | 20 KB | Email event processing |
| `email_scanner.py` | 19 KB | Outlook email scanning |
| `quote_store.py` | 16 KB | Quote persistence |
| `quote_intelligence.py` | 15 KB | Quote AI analysis |
| `erp_api_bridge.py` | 9 KB | ERP ↔ API bridge |
| `event_bus.py` | 8 KB | Event-driven architecture |
| `notification.py` | 5 KB | Notification service |

---

## 4. Email Engine — Current Capability

### Python Modules (18 in `core/`)

| Module | Size | Purpose |
|---|---|---|
| `send_email.py` | 33 KB | Email sending (SMTP) |
| `process_reply.py` | 30 KB | Reply processing & classification |
| `data_collector.py` | 28 KB | Data collection from emails |
| `read_email1.py` | 28 KB | Email reading engine |
| `pst_importer.py` | 26 KB | PST archive import |
| `sequence_engine.py` | 26 KB | Email sequence automation |
| `main.py` | 24 KB | Main orchestrator |
| `scan_outlook_folders.py` | 23 KB | Outlook folder scanning |
| `shipment_brain.py` | 22 KB | Shipment intelligence |
| `generate_dashboard.py` | 19 KB | Dashboard generation |
| `follow_up_engine.py` | 14 KB | Follow-up automation |
| `email_parser.py` | 13 KB | Email parsing |
| `nelson_briefing.py` | 10 KB | Daily briefing builder |
| `email_engine.py` | 7 KB | Core email engine |
| `replacement_outreach.py` | 7 KB | Replacement customer outreach |
| `ops_briefing.py` | 6 KB | Operations briefing |
| `reply_analyzer.py` | 3 KB | Reply intent analysis |
| `notify.py` | 2 KB | Notification helper |

### SQLite Database: `shipments.db`

| Table | Rows | Key Columns |
|---|---|---|
| **email_events** | **6,163** | received_at, sender, customer_name, route, pol, pod, carrier, intent |
| **shipments** | 41 | shipment_key, hbl, bkg, current_stage, carrier, etd |
| **sales_replies** | 48 | customer_name, intent, next_action, urgency |
| **nelson_alerts** | 31 | alert_type, risk_level, alert_reason |
| **customers** | 0 | (schema only — not populated) |
| **email_maybe_review** | 0 | (schema only — not populated) |

### Data Files (11)

| File | Purpose |
|---|---|
| `customer_final.xlsx` | Customer master |
| `contact_master.xlsx` | Contact database |
| `cnee_master.xlsx` | Consignee master |
| `shipper_master.xlsx` | Shipper master |
| `Port_Code_Mapping_Final.xlsx` | Port code mapping |
| `customer_rules.json` | Customer-specific rules |
| `rules.json` / `rules.yaml` | Processing rules |
| `shipment_patterns.yaml` | Pattern matching |
| `config.xlsx` | Config parameters |
| `data.xlsx` | Working data |
| `replacement_leads.xlsx` | Replacement leads |

### Email Engine Status
- **PST Archive:** 7.5 GB (`backup.pst`) imported → 6,163 events
- **Sending:** `send_email.py` (33 KB) — SMTP-based
- **Templates:** Embedded in `send_email.py` and `auto_email_booking.py`
- **Triggers:** `run_all.py` orchestrates, `setup_brain_scheduler.ps1` for scheduling
- **Sequences:** `sequence_engine.py` (26 KB) — multi-step email campaigns
- **Intelligence:** `shipment_brain.py` + `nelson_briefing.py` for smart analysis

---

## 5. Skills — Full List (50 total)

### Nelson Custom Skills (16)

| # | Skill | Purpose |
|---|---|---|
| 1 | `auto-test-loop` | Automated test-fix-retry loop |
| 2 | `bot-v5-dev` | Telegram Bot v5 development |
| 3 | `brainstorm-upgrade` | System brainstorming & upgrade planning |
| 4 | `cleanup-after-task` | Post-task temp file cleanup |
| 5 | `data-pipeline` | Parquet/SQLite/PostgreSQL data management |
| 6 | `email-intelligence` | 10 Email Intelligence Features master |
| 7 | `erp-master` | ERP_Master.xlsm rules & operations |
| 8 | `freight-ops` | Logistics & freight core operations |
| 9 | `nelson-system-audit` | Architecture audit system |
| 10 | `system-review` | System self-evaluation |
| 11 | `webapp-scalable` | WebApp 1,000-user architecture |
| 12 | `webapp-testing` | WebApp Playwright testing |
| 13 | `next-best-practices` | Next.js best practices |
| 14 | `systematic-debugging` | 4-phase debugging methodology |
| 15 | `test-driven-development` | TDD workflow |
| 16 | `verification-before-completion` | Evidence-first verification |

### Third-Party / Vercel Skills (26)

| # | Skill | Purpose |
|---|---|---|
| 17 | `vercel-agent-browser` | Browser automation CLI |
| 18 | `vercel-ai-elements` | AI chat interface components |
| 19 | `vercel-ai-sdk` | AI SDK (generateText, streamText, tools) |
| 20 | `vercel-autoship` | Changeset-based releases |
| 21 | `vercel-building-components` | UI component building guide |
| 22 | `vercel-cli` | Vercel CLI deployment |
| 23 | `vercel-composition-patterns` | React composition patterns |
| 24 | `vercel-deploy` | Vercel deployment |
| 25 | `vercel-find-skills` | Skill discovery |
| 26 | `vercel-json-render-core` | JSON→UI schema |
| 27 | `vercel-json-render-react` | JSON→React renderer |
| 28 | `vercel-json-render-react-native` | JSON→React Native renderer |
| 29 | `vercel-json-render-remotion` | JSON→Video renderer |
| 30 | `vercel-next-cache-components` | Next.js 16 cache/PPR |
| 31 | `vercel-next-upgrade` | Next.js upgrade migration |
| 32 | `vercel-react-best-practices` | React perf optimization |
| 33 | `vercel-react-native-skills` | React Native/Expo |
| 34 | `vercel-remotion-best-practices` | Video creation |
| 35 | `vercel-streamdown` | Streaming markdown renderer |
| 36 | `vercel-turborepo` | Monorepo build system |
| 37 | `vercel-web-design-guidelines` | UI/UX review |
| 38 | `vercel-workflow` | Durable workflow DevKit |

### General Skills (8)

| # | Skill | Purpose |
|---|---|---|
| 39 | `algorithmic-art` | Generative art with p5.js |
| 40 | `brand-guidelines` | Anthropic brand styling |
| 41 | `canvas-design` | Visual art/poster creation |
| 42 | `claude-api` | Claude API / Anthropic SDK |
| 43 | `docx` | Word document creation/editing |
| 44 | `frontend-design` | Production-grade frontend UI |
| 45 | `internal-comms` | Internal communications |
| 46 | `mcp-builder` | MCP server building |
| 47 |  `pptx` | PowerPoint creation/editing |
| 48 | `ui-ux-pro-max` | UI/UX design intelligence |
| 49 | `web-artifacts-builder` | Complex HTML artifacts |
| 50 | `xlsx` | Spreadsheet operations |

---

## 6. Pricing Engine — What Exists

### Python Files (11)

| File | Size | Purpose |
|---|---|---|
| `rate_importer.py` | 41 KB | Outlook→Parquet rate import pipeline |
| `parquet_auditor.py` | 27 KB | Parquet data quality audit |
| `rate_monitor.py` | **NEW** | NMI Rate Anomaly Detector (built today) |
| `test_v13_ribbon.py` | 18 KB | ERP V13 test suite |
| `puc_importer.py` | 14 KB | PUC (inland cost) import |
| `run.py` | 8 KB | CLI entry point |
| `setup_scheduler.py` | 7 KB | Windows Task Scheduler setup |
| `clean_parquet.py` | 6 KB | Parquet cleaning |
| `setup_v13_sheets.py` | 5 KB | Sheet header setup |

### Models Directory (ALL EMPTY)

| Subfolder | Contents | ML Files |
|---|---|---|
| `capacity_risk/` | EMPTY | None |
| `price_trend/` | EMPTY | None |
| `training/` | EMPTY | None |

### Parquet Data

| File | Rows | Carriers | PODs |
|---|---|---|---|
| `Cleaned_Master_History.parquet` | **10,237,866** | 20 | 145 |
| `custeam_history.parquet` | 24 | 8 | N/A |
| + 4 backup parquets | — | — | — |

---

## 7. VBA Modules — List (8 total)

| # | Module | VB_Name | Purpose |
|---|---|---|---|
| 1 | `QuoteBuilder_ERP.bas` | QuoteBuilder | Ribbon callbacks, QuickSearch, GenerateQuote, MarkQuoteWin/Lost |
| 2 | `QuoteJobWorkflow.bas` | — | Quote-Job workflow macros v9, dynamic markup |
| 3 | `BookingEmail.bas` | BookingEmail | Booking email template engine |
| 4 | `CostBreakdown.bas` | CostBreakdown | Cost breakdown engine |
| 5 | `MonthlyReport.bas` | MonthlyReport | Monthly report export |
| 6 | `CRM_Sheet.bas` | CRM_Sheet | Customer SOP lookup module |
| 7 | `SheetEvent_PricingDashboard.bas` | — | Sheet event code for Pricing Dashboard |
| 8 | `Sheet_PricingHandler.bas` | — | Sheet event handler (pasted into sheet module) |

---

## 8. ERP Intelligence Modules (12 files)

| Module | Size | Purpose |
|---|---|---|
| `tracking_manager.py` | 20 KB | Container/BL tracking |
| `weekly_report.py` | 14 KB | Weekly market report |
| `spot_cache.py` | 12 KB | Spot rate caching |
| `price_alerts.py` | 11 KB | Price change alerts |
| `market_history.py` | 7 KB | Historical market data |
| `profit_calculator.py` | 7 KB | Profit/cost analysis |
| `quote_matcher.py` | 6 KB | Quote matching |
| `sailing_schedule.py` | 6 KB | Vessel schedule |
| `product_update.py` | 6 KB | Product update parsing |
| `market_brief.py` | 6 KB | Market brief generator |
| `daily_sync.py` | 5 KB | Daily data sync |
| `hpl_auth.py` | 4 KB | HPL API authentication |

---

## 9. Memory State — Key Facts

### Active Context (`05_active_context.md`)
- **ERP Build:** V13 Ribbon = ✅ LIVE
- **Staging:** ERP_V13_STAGING.xlsm = ⏳ Needs rebuild
- **Last session:** 2026-03-22 22:14

### Backlog (`backlog.md`)
**P1:** Rebuild staging, test Quote→WIN→ActiveJobs pipeline, fix CRM 43 cols
**P2:** Bot v5 modules, WebApp Sprint 13-14, rate importer automation
**P3:** Email Engine v1.1, NL interface, multi-user auth

### Lessons Learned (2 entries)
1. Active Jobs header is ROW 7, not ROW 1
2. CRM 43 cols verified

### Session Log
- 717 lines, mostly from CTO agent system (2026-03-22)
- Contains Telegram Mini App prototype code (embedded in log)
- Multiple encoding errors logged (`charmap` codec issues)

### Memory Database Files
- `task_board.db` — 94 KB (CTO agent task tracking)
- `mailbox.db` — 20 KB (inter-agent messaging)

---

## 10. Gaps — What's Missing or Incomplete

### 🔴 Critical Gaps

| # | Gap | Impact |
|---|---|---|
| 1 | **ML Models = EMPTY** | No price prediction, no capacity risk model. All 3 dirs scaffolding only |
| 2 | **ERP Staging needs rebuild** | Can't test full Quote→WIN→Job pipeline |
| 3 | **customers table = 0 rows** | Email engine customer DB not populated |

### 🟡 Important Gaps

| # | Gap | Impact |
|---|---|---|
| 4 | **WebApp has no API connection** | 8 pages exist but no data fetching visible in `src/lib/` |
| 5 | **Only 2 UI components** | Sidebar + Topbar — needs charts, tables, cards |
| 6 | **Product_update docs = 0** | Only 3 weeks parsed (W06-08). Need more for Space Risk model |
| 7 | **No `monitor.py`** | No centralized daily monitoring script |
| 8 | **Session log = messy** | 717 lines with embedded code (Mini App HTML/CSS/JS dump) |
| 9 | **Bot freight_bot.db mostly empty** | Only price_snapshots (1,091) has data |
| 10 | **No auth system** | API `auth_router.py` is only 2 KB — likely stub |

### 🟢 Ready but Not Connected

| # | Item | Status |
|---|---|---|
| 11 | `rate_monitor.py` | ✅ Built, tested, needs ERP data + Telegram env |
| 12 | Email intelligence features | 32 KB module exists, needs activation |
| 13 | HPL API integration | Auth + commands exist, needs live testing |
| 14 | ERP intelligence (12 modules) | Built, but no scheduler connects them |

---

## Summary Stats

| Component | Count |
|---|---|
| **Top-level directories** | 9 |
| **WebApp pages** | 8 |
| **API routers** | 11 |
| **Email Engine modules** | 18 |
| **TelegramBot files** | 32 |
| **VBA modules** | 8 |
| **ERP intelligence modules** | 12 |
| **Skills installed** | 50 |
| **Memory files** | 6 |
| **Parquet rows** | 10,237,866 |
| **Email events** | 6,163 |
| **ML models** | 0 |
| **Workflows defined** | 10+ |
