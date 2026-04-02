# ERP System Guide — Nelson Freight

> **Updated:** 16 Mar 2026 | Post-refactor architecture

## ERP = Central Operational Hub

The ERP directory is the **single place** to find all operational workflows. Everything from pricing refresh to job tracking to market intelligence lives here.

## Module Map

### `ERP/core/` — System Core
| File | Purpose |
|------|---------|
| `refresh.py` | Reads Parquet → writes ERP_Master.xlsm (780 lines, merged from 3 legacy scripts) |
| `control.py` | CLI menu — orchestrates all ERP operations |

### `ERP/quotes/` — Quote Management
| File | Purpose |
|------|---------|
| `manager.py` | Quote CRUD, sync CRM↔ERP, WIN→Job workflow |
| `image_generator.py` | Generate quote PNG with pricing + wharfage + trends |
| `crm_quote_manager.py` | CRM-specific quote pipeline management |
| `output/` | Generated quote image files |

### `ERP/jobs/` — Job & Shipment Operations
| File | Purpose |
|------|---------|
| `enrichment.py` | Enrich Active Jobs with cost breakdown + email links |
| `email_builder.py` | Build booking email subject/body/mailto links |
| `create_from_quote.py` | Create job from won quote (standalone) |
| `eta_alerts.py` | ETA alert system for shipments |
| `delay_tracker.py` | Record and track shipment delays |
| `carrier_performance.py` | Carrier performance analysis and reports |
| `analyze_shipments.py` | Shipment data analysis |

### `ERP/crm/` — Customer Management
| File | Purpose |
|------|---------|
| `master.py` | Create and manage CRM_Master.xlsx |
| `dashboard.py` | CRM dashboard with charts |
| `visual_dashboard.py` | Visual CRM dashboard |
| `add_dashboard.py` | Add dashboard sheets to CRM workbook |
| `relationships.py` | Customer relationship and cross-sell analysis |
| `sample_data.py` | Load sample CRM data |

### `ERP/intelligence/` — Analytics & Market Intelligence
| File | Purpose |
|------|---------|
| `daily_sync.py` | Daily orchestration: match quotes + analyze profit + alerts |
| `price_alerts.py` | Price change detection and alerting |
| `profit_calculator.py` | Quote profitability analysis |
| `quote_matcher.py` | Match CRM quotes with current pricing |
| `market_brief.py` | Market brief generator |
| `market_history.py` | Historical trend analysis |
| `weekly_report.py` | Weekly report builder |
| `product_update.py` | Carrier product update parser |
| `sailing_schedule.py` | Sailing schedule data |

### `ERP/carrier_rules/` — Carrier Business Rules
| File | Purpose |
|------|---------|
| `builder.py` | Generate carrier-specific rule JSON files |
| `booking_rules.json` | Booking email template configuration |
| `weight_rules/*.json` | Per-carrier weight limitations (COSCO, YML, ZIM, HPL, MSC, HMM, EMC, MSK, ONE) |

### `ERP/data/` — Operational Data Files
| File | Source |
|------|--------|
| `ERP_Master.xlsm` | Main ERP workbook (original) |
| `CRM_Master.xlsx` | Customer data (migrated from CRM/) |
| `Quote_History.xlsx` | Quote log (migrated from CRM/) |
| `Jobs_Master.xlsx` | Job records (migrated from Jobs/) |
| `Shipments.xlsx` | Shipment history (migrated from Jobs/) |
| `Carrier_Performance_Report.xlsx` | Carrier reports (migrated from Jobs/) |
| `market_history.json` | Market data (migrated from market_intelligence/) |

### `ERP/vba/` — VBA Macro Source
| File | Purpose |
|------|---------|
| `QuoteJobWorkflow.bas` | Core macros: QuickSearch, GenerateQuote, MarkQuoteWin, FindSheet |
| `SheetEvent_PricingDashboard.bas` | Sheet-level event handlers |

## VBA Locked Functions (DO NOT MODIFY)

- `ApplyQuickSearch` — filters Pricing Dashboard
- `GenerateQuote` — creates quote from selected rows
- `MarkQuoteWin` — converts quote to Active Job
- `FindSheet` — finds sheets by keyword (not hardcoded emoji names)

## ERP Layout Rules

- **Rows 1-8** in Pricing Dashboard = LAYOUT — do NOT clear, overwrite, or reformat
- **Pricing formula:** `Base + Global($J$3) + CarrierMarkup + PUC` — do NOT change structure
- **Hidden sheets:** PUC_Lookup, BasicCost_Lookup, Search_Lists, Markup_Store, Version

## Running ERP Operations

```bash
# Refresh pricing data
python ERP/core/refresh.py

# System control menu
python ERP/core/control.py

# Quote management
python ERP/quotes/manager.py

# Enrich active jobs
python ERP/jobs/enrichment.py

# Daily intelligence sync
python ERP/intelligence/daily_sync.py
```
