# Phase 6 — Architecture Docs + Deprecation READMEs

**Priority:** LOW (documentation) | **Status:** PENDING | **Effort:** 30 min | **Tier:** 3

## Why this phase exists

Audit C was misled because it read legacy v13 files in the repo (`ERP/vba/*.bas`, `ERP/core/refresh.py`) instead of live v14 (`erp-v14-*.bas` on OneDrive, `refresh-v14.py`). Every new contributor will hit the same trap. Fix: README stubs pointing at truth.

## Actions

### 6.1 Create `ERP/vba/README.md`

```markdown
# ERP VBA — LEGACY v13 (DO NOT EDIT)

These .bas files are v13 code kept for git history only. **The live ERP uses v14**.

## Live v14 source of truth

```
D:/OneDrive/NelsonData/erp/
├── erp-v14-quick-wins.bas         ← ERPv14Core module
├── erp-v14-ribbon-callbacks.bas   ← ERPv14Ribbon module
├── erp-v14-preset-dryreefer.bas   ← ERPv14Preset module
├── CostBreakdown.bas              ← shared HDL rules
└── CustomUI_v14.xml               ← ribbon definition
```

## Why v14 lives on OneDrive, not repo

- **Stealth mode** — Nelson uses Excel at office. Coworkers don't see a webapp.
  Keeping the .bas files on OneDrive means Excel refresh/rebuild workflow
  doesn't touch git.
- **Fast iteration** — VBA edits can be tested without git commit cycle.
- **Backup** — OneDrive version history is the safety net.

## When working on v14

1. Edit the .bas files on OneDrive directly
2. Open `ERP_Master_v14.xlsm` in VBE → re-import modules
3. Save as .xlsm
4. Run `scripts\run-erp-tests.bat` for regression
5. Legacy files in this directory: IGNORE

## If you're an AI agent

DO NOT read files from this directory when auditing v14 code.
Read from `D:/OneDrive/NelsonData/erp/` instead.
See `docs/erp-v14-source-of-truth.md` for the full map.
```

### 6.2 Create `ERP/core/README.md`

```markdown
# ERP Core — Mixed v13/v14 (READ WHICH IS LIVE)

| File | Status | Replacement |
|---|---|---|
| `refresh.py` | DEPRECATED v13 | `D:/OneDrive/NelsonData/erp/refresh-v14.py` |
| `build_erp_v13_ribbon.py` | DEPRECATED v13 | `refresh-v14.py` + manual VBA import |
| `control.py` | Check usage | — |
| `customui_utils.py` | Shared — keep | — |

## Why refresh.py is dead

- Missing Eff filter → loads 197K stale rows (5+ years old) as if active
- No 15d→30d→90d fallback cascade
- Doesn't split Pricing Dry / Pricing Reefer
- v14 `refresh-v14.py` on OneDrive is the authoritative implementation

Calling `ERP.core.refresh.refresh_data()` now raises `RuntimeError`. See
`docs/erp-v14-source-of-truth.md` §refresh.
```

### 6.3 Create `docs/erp-v14-source-of-truth.md`

Full map of v14 live files, who reads what, deprecation graveyard, onboarding checklist.

```markdown
# ERP v14 Source of Truth

**Last updated:** 2026-04-11 | **Owners:** Nelson

This document is the authoritative map of where ERP v14 lives. If you're an
AI agent or a new contributor auditing / modifying ERP v14, start here.

## Live v14 files (OneDrive)

All under `D:/OneDrive/NelsonData/erp/`:

| File | Role | Lines | Module name |
|---|---|---|---|
| `ERP_Master_v14.xlsm` | Main workbook — 11 sheets | — | — |
| `erp-v14-quick-wins.bas` | Core helpers | ~290 | `ERPv14Core` |
| `erp-v14-ribbon-callbacks.bas` | Ribbon state + all button handlers | ~1550 | `ERPv14Ribbon` |
| `erp-v14-preset-dryreefer.bas` | Dry/Reefer column preset | ~120 | `ERPv14Preset` |
| `CostBreakdown.bas` | HDL rules per carrier | ~280 | `CostBreakdown` |
| `CustomUI_v14.xml` | Ribbon XML (2 tabs: Pricing + Operations) | ~250 | — |
| `refresh-v14.py` | Parquet → xlsm refresh (Eff+Exp filter, 15→30→90 fallback) | ~430 | — |
| `customui_utils.py` | CustomUI inject helper | ~100 | — |

## v14 sheets in ERP_Master_v14.xlsm

| Sheet | Role | Writer |
|---|---|---|
| `Pricing Dry` | Data: POL/POD/Carrier/20GP/40GP/40HC/45HC/40NOR buy prices | `refresh-v14.py` |
| `Pricing Reefer` | Data: POL/POD/Carrier/20RF/40RF buy prices | `refresh-v14.py` |
| `Quotes` | Quote rows (QuoteID, customer, margin, status) | `OnAction_GenerateQuote` |
| `Active Jobs` | Jobs promoted from WIN quotes | `OnAction_MarkQuoteWin` |
| `CRM` | Customer list | Human + `ERP/crm/*.py` |
| `Markup_Store` | Per-(carrier, lane) margin | `SaveMarkupForCarrier` |
| `PUC_Lookup` | PUC charges by Place | `refresh-v14.py` |
| `InvoiceLog` | Billing log | Human + `ERP/jobs/*.py` |
| `ChargeBreakdown` | Line-item charges per route | `refresh-v14.py` |
| `RateVersions` | FAK/SCFI/PUC version labels | `refresh-v14.py` |
| `_QuoteImg` | Temp sheet for quote image capture | `OnAction_QuoteImage` (auto-deleted) |

## Deprecated files (repo — DO NOT USE)

| Path | Replaced by | Status |
|---|---|---|
| `ERP/vba/QuoteBuilder_ERP.bas` | `erp-v14-ribbon-callbacks.bas` | Legacy v13 |
| `ERP/vba/QuoteJobWorkflow.bas` | `erp-v14-ribbon-callbacks.bas` | Legacy v13 |
| `ERP/vba/Sheet_PricingHandler.bas` | Sheet1 event in `ERP_Master_v14.xlsm` | Legacy v13 |
| `ERP/vba/SheetEvent_PricingDashboard.bas` | `ThisWorkbook_SheetActivate` (P1) | Legacy v13 |
| `ERP/vba/CRM_Sheet.bas` | Pending — may extract to v14 | Legacy v13 |
| `ERP/vba/BookingEmail.bas` | `ERP/jobs/email_builder.py` | Moved to Python |
| `ERP/vba/MonthlyReport.bas` | TBD | Legacy v13 |
| `ERP/core/refresh.py` | `refresh-v14.py` | Raises RuntimeError |
| `ERP/core/build_erp_v13_ribbon.py` | `refresh-v14.py` + VBE import | v13 builder, unused |

## Refresh flow

```
Outlook email (Harry Duong)
  ↓
rate_importer.py → OneDrive/pricing/incoming/
  ↓
master_loader_v2.py → Cleaned_Master_History.parquet
  ↓
refresh-v14.py (Eff+Exp filter, 15d→30d→90d cascade)
  ↓
ERP_Master_v14.xlsm (Pricing Dry + Pricing Reefer + ChargeBreakdown + RateVersions)
  ↓
User clicks cell → ribbon auto-loads → quote → win/loss → job
```

## Audit checklist (for AI agents)

When asked to "audit v14" or "evaluate ERP workflow":

1. ✅ Read `D:/OneDrive/NelsonData/erp/erp-v14-*.bas` — NOT `ERP/vba/*.bas`
2. ✅ Read `refresh-v14.py` — NOT `ERP/core/refresh.py`
3. ✅ Read `CustomUI_v14.xml` — NOT `CustomUI_ERP.xml` if it exists
4. ✅ Open `ERP_Master_v14.xlsm` via xlwings to see live sheet structure
5. ❌ DO NOT trust claims from reading the repo `ERP/` legacy files
6. ❌ DO NOT modify files in `ERP/vba/` or `ERP/core/refresh.py` — they're dead code

## Related plans

- `plans/260411-2121-erp-workflow-upgrade/` (this plan)
- `plans/260411-2019-rate-pipeline-reorg/` (rate pipeline upstream)
- `plans/reports/audit-260411-rate-import-pipeline.md` (upstream audit)

## Related docs

- `docs/erp-automation-test-stack.md` — test stack usage
- `docs/rate-pipeline-contract.md` — upstream folder contract
```

### 6.4 Add pointer to `CLAUDE.md`

Append to the "System Overview" or "Architecture" section:
```markdown
## ERP v14 Source of Truth

See `docs/erp-v14-source-of-truth.md` — AI agents and new contributors MUST
read this before auditing or modifying ERP v14. Live v14 lives on OneDrive,
not in the repo.
```

## Verification

```bash
# 1. README files exist
ls ERP/vba/README.md ERP/core/README.md docs/erp-v14-source-of-truth.md

# 2. CLAUDE.md references the source-of-truth doc
grep -l "erp-v14-source-of-truth" CLAUDE.md

# 3. grep for anyone still referencing legacy paths
grep -rn "ERP.core.refresh\|ERP/vba/QuoteBuilder" --include="*.py" --include="*.md"
```

## Success criteria
- [ ] `ERP/vba/README.md` created, points at OneDrive
- [ ] `ERP/core/README.md` created, lists deprecated files
- [ ] `docs/erp-v14-source-of-truth.md` created with full map
- [ ] `CLAUDE.md` links the source-of-truth doc
- [ ] Grep for legacy references returns only README/docs mentions

## Risk
- ZERO — documentation only

## Closing

With P6 done, the entire plan is complete:
- P1 — Sheet activate + cascade search ✅
- P2 — MsgBox refactor ✅ (unblocked test stack 14/0)
- P3 — Quote flow quick wins ✅
- P4 — Parquet 45'HQ + legacy kill ✅
- P5 — Markup per-lane ✅
- P6 — Docs ✅

Run full regression:
```bash
scripts\run-erp-tests.bat
# Expected: 14 passed, 0 skipped (was 11/3 pre-P2)
pytest tests/unit -v
# Expected: all green including new unit tests from P4+P5
```

If green → Phase 2 from memory (API-first migration) becomes feasible with
all this cleanup done. Defer that to a new sprint.
