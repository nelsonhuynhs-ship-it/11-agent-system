---
phase: 3
title: "Refactor VBA Ribbon Modules"
status: completed
priority: P1
effort: "4h"
dependencies: [1, 2]
---

# Phase 3: Refactor VBA Ribbon Modules

## Overview
Split `erp-v14-ribbon-callbacks.bas` (1600 lines, 15 ribbon callbacks) into focused feature modules. Each module handles one feature area. Ribbon file becomes thin router — only delegates to feature modules.

## Requirements
- Functional: All 15 ribbon callbacks still work after split
- Non-functional: No logic duplication, no circular references

## Architecture

```
erp-v14-ribbon-callbacks.bas   ← thin router (only Sub OnAction_* wrappers)
basPriceWatch.bas              ← OnAction_PriceWatch + helpers
basReleaseAlerts.bas           ← OnAction_ReleaseAlert + helpers
basTransitTime.bas             ← OnAction_TransitTime + helpers
basWeeklyReport.bas            ← OnAction_WeeklyReport + helpers
basMonthlyReport.bas           ← OnAction_MonthlyReportV4 + helpers
basYmlScan.bas                 ← OnAction_YmlScan + helpers
basFastId.bas                  ← OnAction_FastIdCheck + helpers
basReeferPlug.bas              ← OnAction_ReeferPlug + helpers
basEnrichMonthly.bas           ← OnAction_EnrichMonthly + helpers
basArchive.bas                 ← OnAction_ArchiveJob + helpers
basSyncMilestones.bas          ← Btn_SyncMilestones_OnAction + helpers
basRefreshAll.bas              ← OnAction_RefreshAll (orchestrates all)
basQuoteImage.bas              ← OnAction_QuoteImage + OnAction_QuoteImageBulk
basJobsAutomation.bas          ← Keep from erp-v14-jobs-automation.bas
basCostEngine.bas              ← CostBreakdown.bas (already separate)
basShared.bas                  ← GetConfigValue, WriteLog, m_* state vars
```

## Module Inventory (from scout)

**Current:** `erp-v14-ribbon-callbacks.bas` (1600 lines) contains:
- 15 ribbon button callbacks + 4 combo callbacks
- ALL business logic embedded in each callback
- Module-level state variables scattered throughout

**After split:**
| Module | Callbacks | Est. Lines |
|--------|-----------|-----------|
| `basShared.bas` | — | 150 (state vars, config, logging) |
| `basRefreshAll.bas` | OnAction_RefreshAll | 100 |
| `basQuoteImage.bas` | OnAction_QuoteImage, OnAction_QuoteImageBulk | 250 |
| `basPriceWatch.bas` | OnAction_PriceWatch | 150 |
| `basReleaseAlerts.bas` | OnAction_ReleaseAlert | 120 |
| `basTransitTime.bas` | OnAction_TransitTime | 100 |
| `basWeeklyReport.bas` | OnAction_WeeklyReport | 120 |
| `basMonthlyReport.bas` | OnAction_MonthlyReportV4 | 150 |
| `basYmlScan.bas` | OnAction_YmlScan | 100 |
| `basFastId.bas` | OnAction_FastIdCheck | 80 |
| `basReeferPlug.bas` | OnAction_ReeferPlug | 100 |
| `basEnrichMonthly.bas` | OnAction_EnrichMonthly | 100 |
| `basEnrichEmail.bas` | OnAction_EnrichEmail | 100 |
| `basArchive.bas` | OnAction_ArchiveJob | 100 |
| `basSyncMilestones.bas` | Btn_SyncMilestones_OnAction | 100 |

**Thin ribbon file** (`erp-v14-ribbon-callbacks.bas`): ~200 lines — only `Sub OnAction_*` wrappers that call feature module subs.

## Related Code Files
- Create: 13 new `.bas` files in `ERP/vba-v14-mirror/`
- Modify: `erp-v14-ribbon-callbacks.bas` (rewrite as thin router)
- Also update `ERP_SYSTEM_GUIDE.md` module map

## Implementation Steps

1. **Read full `erp-v14-ribbon-callbacks.bas`** — identify which subs belong to which feature area
2. **Create `basShared.bas`** — extract module-level state variables (`m_Carrier`, `m_POL`, etc.), `GetConfigValue()`, `WriteLog()`, `ribbonUI` reference
3. **Create each feature module** — extract related callback + all its helper subs/functions
4. **Rewrite `erp-v14-ribbon-callbacks.bas`** — replace callback body with `Call <module>.FeatureName(args)`
5. **Verify VBA compiles** — open xlsm, hit `Compile` in VBE (no errors)
6. **Run existing E2E tests** — `python scripts/com-e2e/erp_e2e.py` still passes

## Success Criteria
- [ ] Each ribbon button callback still works (manual smoke test each button)
- [ ] VBA compiles with 0 errors in VBE
- [ ] No callback body exceeds 5 lines in ribbon file
- [ ] `ERP_SYSTEM_GUIDE.md` updated with new module map

## Risk Assessment
- **Risk**: Breaking `g_TestMode` / `g_LastError` state shared across callbacks
- **Mitigation**: Keep test harness vars in `basShared.bas`, accessible from all modules
- **Risk**: Circular `Call` references between modules
- **Mitigation**: `basShared.bas` has no dependencies; feature modules depend only on `basShared.bas`
