# ERP v14 Source of Truth

**Last updated:** 2026-04-11 | **Owner:** Nelson

This document is the authoritative map of where ERP v14 lives. If you're an
AI agent or a new contributor auditing / modifying ERP v14, **start here**.

---

## Live v14 files (OneDrive)

All under `D:/OneDrive/NelsonData/erp/`:

| File | Role | ~Lines | Module name |
|---|---|---|---|
| `ERP_Master_v14.xlsm` | Main workbook — 11 sheets | — | — |
| `erp-v14-quick-wins.bas` | Core helpers (cascade search, formatting, utilities) | 290 | `ERPv14Core` |
| `erp-v14-ribbon-callbacks.bas` | Ribbon state + all button handlers | 1550 | `ERPv14Ribbon` |
| `erp-v14-preset-dryreefer.bas` | Dry/Reefer column preset switcher | 120 | `ERPv14Preset` |
| `CostBreakdown.bas` | HDL rules per carrier (shared charge logic) | 280 | `CostBreakdown` |
| `CustomUI_v14.xml` | Ribbon XML — 2 tabs (Pricing + Operations) | 250 | — |
| `refresh-v14.py` | Parquet → xlsm refresh (Eff+Exp filter, 15→30→90 fallback) | 430 | — |
| `customui_utils.py` | CustomUI inject helper | 100 | — |

---

## v14 sheets in `ERP_Master_v14.xlsm`

| Sheet | Role | Writer |
|---|---|---|
| `Pricing Dry` | POL/POD/Carrier/20GP/40GP/40HC/45HC/40NOR buy prices | `refresh-v14.py` |
| `Pricing Reefer` | POL/POD/Carrier/20RF/40RF buy prices | `refresh-v14.py` |
| `Quotes` | Quote rows (QuoteID, customer, margin, status) | `OnAction_GenerateQuote` (VBA) |
| `Active Jobs` | Jobs promoted from WIN quotes | `OnAction_MarkQuoteWin` (VBA) |
| `CRM` | Customer list | Human + `ERP/crm/*.py` |
| `Markup_Store` | Per-`(carrier, lane)` margin cache | `SaveMarkupForCarrier` (VBA) |
| `PUC_Lookup` | PUC charges by Place | `refresh-v14.py` |
| `InvoiceLog` | Billing log | Human + `ERP/jobs/*.py` |
| `ChargeBreakdown` | Line-item charges per route | `refresh-v14.py` |
| `RateVersions` | FAK/SCFI/PUC version labels | `refresh-v14.py` |
| `_QuoteImg` | Temp sheet for quote image capture | `OnAction_QuoteImage` (auto-deleted) |

---

## Deprecated files (repo — DO NOT USE)

These are legacy v13 files kept only for git history. Do not read them when
auditing v14. Do not edit them.

| Path | Replaced by | Status |
|---|---|---|
| `ERP/vba/QuoteBuilder_ERP.bas` | `erp-v14-ribbon-callbacks.bas` | Legacy v13 |
| `ERP/vba/QuoteJobWorkflow.bas` | `erp-v14-ribbon-callbacks.bas` | Legacy v13 |
| `ERP/vba/Sheet_PricingHandler.bas` | Sheet1 event in `ERP_Master_v14.xlsm` | Legacy v13 |
| `ERP/vba/SheetEvent_PricingDashboard.bas` | `ThisWorkbook_SheetActivate` (P1) | Legacy v13 |
| `ERP/vba/CRM_Sheet.bas` | Pending — may extract to v14 | Legacy v13 |
| `ERP/vba/BookingEmail.bas` | `ERP/jobs/email_builder.py` | Moved to Python |
| `ERP/vba/MonthlyReport.bas` | TBD | Legacy v13 |
| `ERP/core/refresh.py` | `refresh-v14.py` | Raises `RuntimeError` |
| `ERP/core/build_erp_v13_ribbon.py` | `refresh-v14.py` + manual VBE import | v13 builder, unused |

---

## Refresh flow

```
Outlook email (Harry Duong — carrier rate updates)
  │
  ▼
rate_importer.py
  │   → OneDrive/pricing/incoming/
  ▼
master_loader_v2.py
  │   → Cleaned_Master_History.parquet   (~6.6M rows)
  ▼
refresh-v14.py
  │   • Eff + Exp filter
  │   • 15d → 30d → 90d cascade
  │   • split Dry / Reefer
  ▼
ERP_Master_v14.xlsm
  │   • Pricing Dry
  │   • Pricing Reefer
  │   • ChargeBreakdown
  │   • RateVersions
  │   • PUC_Lookup
  ▼
User clicks cell
  │   → ribbon auto-loads (ERPv14Ribbon)
  ▼
Quote (Quotes sheet) → Win/Loss → Active Jobs → InvoiceLog
```

---

## Audit checklist (for AI agents)

When asked to **"audit v14"** or **"evaluate ERP workflow"**:

1. Read `D:/OneDrive/NelsonData/erp/erp-v14-*.bas` — NOT `ERP/vba/*.bas`
2. Read `refresh-v14.py` — NOT `ERP/core/refresh.py`
3. Read `CustomUI_v14.xml` — NOT `ERP/vba/CustomUI_ERP.xml`
4. Open `ERP_Master_v14.xlsm` via xlwings to inspect live sheet structure
5. DO NOT trust claims derived from reading the repo `ERP/` legacy files
6. DO NOT modify files in `ERP/vba/` or `ERP/core/refresh.py` — they're dead code

**Case study:** Tonight's audit (2026-04-11) got confused reading legacy v13
files in `ERP/vba/` and wrote claims that didn't match the live v14 workbook.
See `plans/reports/brainstorm-260411-2121-erp-workflow-upgrade-synthesis.md`
for the full cautionary tale. Don't repeat it.

---

## Related plans

- `plans/260411-2121-erp-workflow-upgrade/` — this plan (P1–P6)
- `plans/260411-2019-rate-pipeline-reorg/` — upstream rate pipeline reorg
- `plans/reports/audit-260411-rate-import-pipeline.md` — upstream pipeline audit

## Related docs

- `docs/erp-automation-test-stack.md` — ERP test stack usage
- `docs/rate-pipeline-contract.md` — upstream folder contract
- `docs/market-report-4c-system.md` — market report pipeline
