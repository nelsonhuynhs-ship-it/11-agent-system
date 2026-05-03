# Executor Log — VBA Import Fix

**Date:** 2026-05-02
**Task:** VBA Import Fix — Direct Binary Injection
**Files Created:** `scripts/vba-inject.py`, `scripts/vba-merge.py`

## Problem
- COM `VBProject.Import()` reports success but modules NOT persisted to vbaProject.bin
- After 3 reimport attempts, `ERPv14QuickWins` and `ERPv14RibbonCallbacks` modules MISSING
- `OnAction_RequoteAlert` callback missing → button has no code
- Root cause: `erp-v14-quick-wins.bas` has `Attribute VB_Name = "ERPv14Core"` — imports into wrong module

## Root Cause Analysis
1. `erp-v14-quick-wins.bas` has `Attribute VB_Name = "ERPv14Core"` — VBA editor uses this attribute as the module name when importing. So `.Import()` doesn't create `ERPv14QuickWins` module — it updates the `ERPv14Core` module. BUT after ~3 imports the module in the binary becomes stale.
2. `erp-v14-ribbon-callbacks.bas` is 204,764 chars — much larger than the xlsm's 199,698 chars. The xlsm version is missing 13 functions including `OnAction_RequoteAlert`.

## Solution: AddFromString via temp module

**Approach:** Use COM `CodeModule.AddFromString()` to append individual functions to existing target modules, rather than importing whole files.

**Files modified:**
- `D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm` — 15 functions added to existing modules

## Applied Fixes

### HIGH — Missing `OnAction_RequoteAlert` + 13 more from ribbon
- Added to `ERPv14Ribbon.bas` via `AddFromString`:
  - `OnAction_RequoteAlert` (calls `ERPv14Core.ApplyQuoteRowTimeColors` + `CheckReQuoteAlerts`)
  - `CacheSearchState`, `TryRestoreSearchState`, `ClearCachedState`
  - `SetSearchCarrier`, `SetSearchPOL`, `SetSearchPOD`, `SetSearchPlace`
  - `TestE2E_RunMix`, `TestE2E_FindSourceRow`
  - `QuoteImage_CollectLatestGroup`, `QuoteImage_CollectFromSelection`, `QuoteImage_RenderRows`

### HIGH — Missing `CheckReQuoteAlerts` + `ApplyQuoteRowTimeColors` from quick-wins
- Added to `ERPv14Core.bas` via `AddFromString`:
  - `CheckReQuoteAlerts` — scans Quotes sheet for price drops vs current buy rates, creates ReQuote_Alerts sheet
  - `ApplyQuoteRowTimeColors` — colors quote rows: RED <12h, YELLOW 12-24h, GRAY >24h, GREEN=REPLIED

## Validation
```
ERPv14Core.bas:  32 functions → ✅ all target funcs present (CheckReQuoteAlerts, ApplyQuoteRowTimeColors)
ERPv14Ribbon.bas: 154 functions → ✅ all target funcs present (OnAction_RequoteAlert + 13 others)
```

## Deferred
- Binary injection approach (`vba-inject.py`) was explored but olefile write_mode requires an existing file path (not BytesIO). Would need a temp file + careful OLE repack. COM AddFromString proved more reliable.

## Scripts
| Script | Purpose |
|--------|---------|
| `scripts/vba-inject.py` | Binary VBA injection using olefile (not yet working — olefile write limitation) |
| `scripts/vba-merge.py` | COM-based function injection using AddFromString (WORKING) |

## Next Steps
- Test: Open ERP_Master_v14.xlsm → VBA Editor → verify 7 modules in VBProject
- Test: Click Operations > Quote > Requote button → should call `OnAction_RequoteAlert` without "Cannot run macro" error