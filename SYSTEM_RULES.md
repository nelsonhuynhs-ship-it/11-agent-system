# System Rules — Nelson Freight ERP

> **Updated:** 16 Mar 2026 | Post-refactor architecture

## Architecture Rules

### Single Source of Truth
- **Parquet dataset** (`Pricing_Engine/data/Cleaned_Master_History.parquet`) is the ONLY source for pricing data
- All clients (ERP, Bot, WebApp) read from Parquet — never from intermediate files
- `MasterFullPricing.xlsx` is an optional output, NOT a data source

### Separation of Concerns
```
Pricing_Engine/  → Data Layer (import, normalize, store)
ERP/             → Operations (refresh, quote, job, CRM, intelligence)
TelegramBot/     → Client (AI assistant)
api/             → Client (FastAPI backend)
webapp/          → Client (Next.js frontend)
```

### ERP Central Hub
- All operational scripts are organized under `ERP/` by business workflow
- New operational code goes into the appropriate `ERP/` subdirectory
- Clients (Bot, API, WebApp) consume ERP data but do NOT contain business logic

## Pricing Rules

### Pipeline
```
Raw carrier files → master_loader_v2.py → Parquet → refresh.py → ERP_Master.xlsm
```

### Formula (DO NOT CHANGE)
```
Selling Price = Base O/F + Global Markup ($J$3) + Carrier Markup + PUC (if SOC)
```

### Container Types
Standard order: `20GP, 40GP, 40HQ, 45HQ, 40NOR, 20RF, 40RF`

## ERP Excel Rules

### Layout Protection
- **Rows 1-8** = LAYOUT — NEVER clear, overwrite, or reformat
- **Row 1:** Header (timestamp, title, PUC dropdowns, Markup)
- **Row 2:** Quick Search (POL, POD, Place), Carrier Markup values
- **Row 3:** Quote Generation button, Global Markup values
- **Row 4-5:** Customer info, Quick preset
- **Row 6:** Spacer
- **Row 7:** Data title
- **Row 8:** Column headers
- **Row 9+:** Data

### Hidden Sheets (managed by refresh.py)
| Sheet | Purpose |
|-------|---------|
| `PUC_Lookup` | Place → PUC costs |
| `BasicCost_Lookup` | Route → cost breakdown (Key, Contract, Group, Breakdown, TotalCharge) |
| `Search_Lists` | POL/POD/Place dropdowns |
| `Markup_Store` | Saved carrier markups |
| `Version` | Pipeline version info |

### VBA Locked Functions
These functions in `QuoteJobWorkflow.bas` MUST NOT be modified without explicit approval:
- `ApplyQuickSearch` — filters Pricing Dashboard
- `GenerateQuote` — creates quote from selected rows
- `MarkQuoteWin` — converts quote to Active Job
- `FindSheet("keyword")` — finds sheets by keyword (NEVER hardcode emoji sheet names)

## Data Refresh Rules

### Daily Workflow
1. Place new carrier files in `Pricing_Engine/data/`
2. Run `python Pricing_Engine/run.py pricing` to update Parquet
3. Run `python ERP/core/refresh.py` to update ERP dashboard
4. **Close ERP_Master.xlsm in Excel before running refresh**

### What refresh.py Does
1. Reads Parquet dataset
2. Imports normalization functions from `Pricing_Engine/scripts/create_master_dashboard.py`
3. Creates Master pivot (Base Ocean Freight, 30-day filter)
4. Creates BasicCost_Lookup (full charge breakdown with TotalCharge)
5. Creates PUC_Lookup table
6. Extracts reference sheets from FAK file
7. Writes everything to ERP_Master.xlsm with formulas

## Module Development Rules

### Adding New ERP Features
1. Create new module in appropriate `ERP/` subdirectory
2. Do NOT modify `ERP/core/refresh.py` unless changing data pipeline
3. Do NOT modify VBA locked functions
4. Add handler in `ERP/core/control.py` if it's a menu item

### Adding Bot Features
1. Create new module in `TelegramBot/`
2. Add handler in `bot_v5.py`
3. Do NOT modify `bot_v5.py` core logic — create separate module

### Client Data Access
- Bot reads Parquet via `query_engine.py`
- Bot reads ERP via `erp_reader.py` (path: `config.py → ERP_FILE`)
- API reads Parquet via `data_access.py`
- NO client should write to Parquet or ERP_Master.xlsm directly

## Legacy Cleanup Status

✅ Phase 6 cleanup completed 2026-03-22.
Archived to `_archive/pre_phase6_snapshot/`
V13 staging active at `ERP/data/ERP_V13_STAGING.xlsm`

**DO NOT add new code to `_archive/` directories.**
