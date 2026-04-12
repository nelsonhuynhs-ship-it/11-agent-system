# ERP Automation Test Stack

Headless xlwings + pytest test runner for `ERP_Master_v14.xlsm`.
Built 2026-04-11 (Phase 1 — Option B from brainstorm report).

## TL;DR — run all tests

```bat
scripts\run-erp-tests.bat
```

Or directly:

```bat
python -m pytest tests/integration -v
```

Expected output: `11 passed, 3 skipped` in ~12 seconds.

## Why this exists

Before: every ERP design iteration required opening Excel manually, clicking
ribbon buttons, verifying cells by eye. Slow, non-repeatable, blocked Claude
from self-verifying.

After: one command (`run-erp-tests.bat`) drives Excel headlessly, calls VBA
macros via COM, asserts sheet state. Claude can now verify changes without a
human clicker. Stealth-mode preserved (Excel still the UX).

## Architecture

```
pytest
  conftest.py
    excel_app     (session-scoped)  → xlwings.App(visible=False)
    erp_workbook  (function-scoped) → copy OneDrive master → tempdir → open
  tests/integration/
    test_erp_smoke.py        ← 11 non-interactive tests (no MsgBox)
    test_erp_quote_flow.py   ← 3 skipped tests pending P2 MsgBox refactor
```

Master file stays untouched: every test copies
`D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm` into pytest's `tmp_path` and
operates on the copy. Tempdir auto-cleans.

## What's covered (P1)

| Test | Asserts |
|---|---|
| `test_workbook_opens_with_expected_sheets` | Pricing Dry/Reefer + Quotes/Active Jobs/CRM/Markup_Store/PUC_Lookup/RateVersions/ChargeBreakdown present |
| `test_pricing_dry_has_data_rows` | `>=100` rows (floor catches empty refresh) |
| `test_pricing_sheet_header_row_present` | Row 1 non-empty |
| `test_quotes_sheet_accessible` | Quotes sheet opens, header matches |
| `test_autoexpire_on_open_runs_clean` | `ERPv14Core.AutoExpireOnOpen` no error |
| `test_apply_rate_freshness_colors_runs_clean` | `ERPv14Core.ApplyRateFreshnessColors` no error |
| `test_refresh_jobs_summary_runs_clean` | `ERPv14Core.RefreshJobsSummary` no error |
| `test_load_row_to_ribbon_does_not_error` | `ERPv14Ribbon.LoadRowToRibbon(2)` no error |
| `test_core_macros_reachable[*]` | 3 parametrized macro-exists checks |

## What's blocked (P2)

Skipped tests in `test_erp_quote_flow.py`:

| Test | Blocker |
|---|---|
| `test_generate_quote_creates_quotes_sheet_row` | `OnAction_GenerateQuote` ends with `MsgBox` — hangs headless Excel |
| `test_mark_quote_win_promotes_to_active_jobs` | `OnAction_MarkQuoteWin` has 5+ MsgBox calls |
| `test_refresh_rates_reopens_workbook` | `OnAction_RefreshRates` has MsgBox + reopen flow |

### P2 Unblock plan — add test-mode flag to VBA

1. Edit `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas`:
   ```vba
   Public g_TestMode As Boolean  ' set by Python test harness
   ```
2. Wrap every `MsgBox ...` call:
   ```vba
   If Not g_TestMode Then MsgBox "...", vbInformation, "Quote Builder v14"
   ```
3. Re-import `.bas` into `ERP_Master_v14.xlsm`, save.
4. In tests, set flag before calling:
   ```python
   erp_workbook.macro("ERPv14Ribbon.SetTestMode")(True)
   erp_workbook.macro("ERPv14Ribbon.OnAction_GenerateQuote")(None)
   ```
5. Remove `@pytest.mark.skip` decorators.

Effort: ~1-2 hours. Do during P2 logic-extraction phase.

## How to add a new test

1. **Non-interactive macro** (no MsgBox) → drop into `test_erp_smoke.py`:
   ```python
   def test_my_new_macro(erp_workbook):
       erp_workbook.macro("ERPv14Core.MyMacro")()
       ws = erp_workbook.sheets["Pricing Dry"]
       assert ws.range("Z1").value == "expected"
   ```

2. **Business logic** (no Excel dependency) → put under `tests/unit/` and test
   the Python module directly (no fixture needed).

3. **MsgBox-laden macro** → add to `test_erp_quote_flow.py` with skip marker
   until P2 unblock.

## Env overrides

- `ERP_MASTER_XLSM=path/to/other.xlsm` — use alternative master file (for
  snapshot testing of pre-refresh state, or Johnny/Jennie's branches).

## Runner script

`scripts/run-erp-tests.bat` uses anaconda python at
`C:\Users\Nelson\anaconda3\python.exe` and passes `-v`. Args forward:

```bat
scripts\run-erp-tests.bat -k smoke          REM only smoke
scripts\run-erp-tests.bat -k "not skip"     REM skip the skipped
scripts\run-erp-tests.bat --lf              REM rerun last failures
```

## Known issues

1. **Windows RPC noise on teardown** — suppressed via `-p no:faulthandler` in
   `pytest.ini`. Harmless, Excel COM release races Python interpreter exit.
2. **Master xlsm must be CLOSED** before running tests — openpyxl/xlwings
   can't open a file locked by a live Excel session. If you see
   `pywintypes.com_error` at fixture setup, close your Excel first.
3. **OneDrive sync races** — if the file is actively syncing, test may read
   stale version. Pause OneDrive or wait sync complete.

## Phase roadmap

- ✅ **P1 (tonight)** — test skeleton + smoke tests running headless
- ⏳ **P2** — MsgBox refactor + extract HDL/markup/dedup logic to Python
  `ERP/core/*.py`, unit-test with pytest (no Excel dependency)
- ⏳ **P3** — coverage backfill → 80% target on Python modules
- ⏳ **P4** — Task Scheduler cron: `run-erp-tests.bat` on every git pull
