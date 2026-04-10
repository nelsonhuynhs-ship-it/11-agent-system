# Nelson Freight — Logistics ERP System

> **Last updated:** 16 Mar 2026 | Post-refactor architecture

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    NELSON FREIGHT                         │
│                                                          │
│  ┌──────────────────┐                                    │
│  │  Pricing_Engine   │ ← Single Source of Truth (Parquet) │
│  │  (Data Layer)     │                                    │
│  └──────┬───────────┘                                    │
│         │ reads Parquet                                   │
│         ▼                                                │
│  ┌──────────────────────────────────────────┐            │
│  │  ERP (Operational Hub)                    │            │
│  │  ├── core/         refresh + control      │            │
│  │  ├── quotes/       quote management       │            │
│  │  ├── jobs/         job + shipment ops     │            │
│  │  ├── crm/          customer management    │            │
│  │  ├── intelligence/ analytics + market     │            │
│  │  ├── carrier_rules/ business rules        │            │
│  │  ├── data/         operational data       │            │
│  │  └── vba/          Excel macros           │            │
│  └──────┬───────────────────────────────────┘            │
│         │                                                │
│         ▼                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│  │ Telegram │  │  FastAPI  │  │  WebApp  │               │
│  │   Bot    │  │   API    │  │ (Next.js)│               │
│  └──────────┘  └──────────┘  └──────────┘               │
└──────────────────────────────────────────────────────────┘
```

## Directory Structure

```
Engine_test/
├── Pricing_Engine/         # Data Layer — rate import, Parquet, normalization
├── ERP/                    # Operational Hub — see ERP_SYSTEM_GUIDE.md
│   ├── core/               # Refresh + system control
│   ├── quotes/             # Quote CRUD, image generation
│   ├── jobs/               # Job enrichment, email, tracking
│   ├── crm/                # Customer management
│   ├── intelligence/       # Daily sync, alerts, market reports
│   ├── carrier_rules/      # Weight rules, booking config
│   ├── data/               # ERP_Master.xlsm + all operational data
│   └── vba/                # VBA macro source
├── TelegramBot/            # AI Bot client
├── api/                    # FastAPI backend
├── webapp/                 # Next.js frontend
└── _archive/               # Deprecated scripts (read-only)
```

## Business Workflow

```
Carrier Rate Files (FAK/SCFI/FIX/OCR)
  → Pricing_Engine/scripts/master_loader_v2.py
  → Cleaned_Master_History.parquet (10M+ rows)
  → ERP/core/refresh.py
  → ERP_Master.xlsm (Pricing Dashboard)
  → VBA QuickSearch + GenerateQuote
  → ERP/quotes/ (quote image, CRM sync)
  → ERP/jobs/ (Active Job, email, tracking)
  → ERP/crm/ (customer analytics)
  → ERP/intelligence/ (alerts, reports)
```

## Data Source Rules

| Consumer | Data Source | Access Method |
|----------|-----------|---------------|
| **ERP** | Parquet | `ERP/core/refresh.py` → Excel |
| **Telegram Bot** | Parquet | `query_engine.py` direct read |
| **WebApp** | Parquet | FastAPI DAL |
| **All clients** | Parquet | Single source of truth |

**Rule:** No module should bypass the Pricing Engine. All rate data flows through Parquet.

## Key Files

| File | Purpose |
|------|---------|
| `Pricing_Engine/data/Cleaned_Master_History.parquet` | 10M+ rows — single truth source |
| `ERP/data/ERP_Master.xlsm` | Operational workbook |
| `ERP/core/refresh.py` | Parquet → Excel pipeline (780 lines) |
| `ERP/QuoteJobWorkflow.bas` | VBA macros (39KB) |
| `TelegramBot/bot_v5.py` | AI bot main handler |

## System Stats

- **Parquet:** 10,064,969 rows × 16 columns
- **ERP modules:** 8 subdirectories, 60+ scripts
- **Carriers:** CMA, COSCO, EMC, HPL, MSC, ONE, WHL, YML, ZIM, HMM, MSK, PIL, TSL, ESL, MCK, APL
- **Clients:** 3 (Bot, API, WebApp)

## Legacy Compatibility

The following directories still exist for backward compatibility and will be removed in Phase 6:

- `CRM/` → migrated to `ERP/crm/`
- `Jobs/` → migrated to `ERP/jobs/`
- `Integration/` → migrated to `ERP/intelligence/`
- `market_intelligence/` → migrated to `ERP/intelligence/`
- `ERP/scripts/` → migrated to `ERP/core/`, `ERP/quotes/`, `ERP/jobs/`, `ERP/carrier_rules/`

**Do NOT add new code to legacy directories.** All new development should target the organized `ERP/` subdirectories.
<!-- test deploy v3 -->
