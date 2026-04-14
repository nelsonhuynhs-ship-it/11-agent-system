# Phase 2 — MsgBox Refactor + g_TestMode Flag ⭐ UNBLOCKER

**Priority:** HIGH (blocks test coverage) | **Status:** PENDING | **Effort:** 2-3h | **Tier:** 1

## Why this is critical

1. 32 `MsgBox` calls in `erp-v14-ribbon-callbacks.bas` break Nelson's flow — every click → modal popup → click → continue
2. They also BLOCK the ERP test stack (tonight's Task A). Three tests in `tests/integration/test_erp_quote_flow.py` are `@pytest.mark.skip(reason="MsgBox")` — this phase unblocks them
3. After this phase: `pytest tests/integration` goes from `11 passed / 3 skipped` to `14 passed / 0 skipped`

## Strategy

Introduce a single global flag `g_TestMode` that:
- When `False` (default, production) → every MsgBox fires normally
- When `True` (headless test) → success/info MsgBox silenced, errors logged to `Debug.Print`

**Do NOT silence error prompts in production** — only convert success/info to status bar.

## Actions

### 2.1 Add `g_TestMode` module variable
Top of `erp-v14-ribbon-callbacks.bas`:
```vba
' Test harness flag — set True from xlwings before calling OnAction_*
' to bypass MsgBox prompts that would block headless Excel.
Public g_TestMode As Boolean
```

### 2.2 Add helper procs
```vba
' Wrapper: replaces MsgBox for success/info when in test mode
Private Function MsgBoxOrSilent(prompt As String, _
                                 Optional buttons As VbMsgBoxStyle = vbInformation, _
                                 Optional title As String = "ERP v14") As VbMsgBoxResult
    If g_TestMode Then
        Debug.Print "[silenced] " & title & ": " & prompt
        MsgBoxOrSilent = vbOK
        Exit Function
    End If
    MsgBoxOrSilent = MsgBox(prompt, buttons, title)
End Function

Public Sub SetTestMode(enabled As Boolean)
    g_TestMode = enabled
End Sub
```

### 2.3 Convert the 15 success/info MsgBox calls
Target the `vbInformation` / success prompts in the hot path. **Keep** the `vbExclamation` / error prompts unchanged.

**Replace in GenerateQuote (`erp-v14-ribbon-callbacks.bas:866`):**
```vba
' BEFORE
MsgBox "Quote " & qid & " created! ..."

' AFTER
Call MsgBoxOrSilent("Quote " & qid & " created! ...", vbInformation, "Quote Builder v14")
```

**Similarly replace success prompts in:**
- `OnAction_MarkQuoteWin` — win confirmation + "Job created" message
- `OnAction_MarkQuoteLost:1283` — "Quote marked as LOST"
- `OnAction_RefreshRates:1458` — "Refresh complete" message
- `OnAction_CheckAutoLost` — "N quotes auto-expired"
- `OnAction_JobsSummary` — summary popup
- `OnAction_QuoteImage` — "Copied to clipboard" success

**Leave unchanged (critical validations Nelson needs to see):**
- `GenerateQuote:769` "Please enter Customer name!" (vbExclamation)
- `GenerateQuote:773` "Please click a data row first!" (vbExclamation)
- `MarkQuoteWin:905/909/915` validation errors
- Any `vbExclamation` / `vbCritical` / error dialogs

### 2.4 Also convert "nice-to-have" confirmation prompts
Optionally convert `Application.StatusBar = "..."` for non-blocking info:
```vba
' For long-running operations (RefreshRates, QuoteImage)
Application.StatusBar = "Generating quote image..."
' ... do work ...
Application.StatusBar = False
```

### 2.5 Update `tests/integration/test_erp_quote_flow.py` to use the flag
```python
# Remove skip markers from all 3 tests
# Set test mode before exercising quote flow
def test_generate_quote_creates_quotes_sheet_row(erp_workbook):
    erp_workbook.macro("ERPv14Ribbon.SetTestMode")(True)
    try:
        ws_dash = erp_workbook.sheets["Pricing Dry"]
        ws_dash.activate()
        ws_dash.range("A2").select()
        erp_workbook.macro("ERPv14Ribbon.LoadRowToRibbon")(2)
        erp_workbook.macro("ERPv14Ribbon.OnChange_Customer")(None, "TEST_CUSTOMER")
        erp_workbook.macro("ERPv14Ribbon.OnAction_GenerateQuote")(None)

        ws_q = erp_workbook.sheets["Quotes"]
        # Assert new row written at col 3 (Customer), col 36 (Status)
        last_row = ws_q.range("A" + str(ws_q.cells.last_cell.row)).end("up").row
        assert ws_q.range(f"C{last_row}").value == "TEST_CUSTOMER"
        assert ws_q.range(f"AJ{last_row}").value == "PENDING"
    finally:
        erp_workbook.macro("ERPv14Ribbon.SetTestMode")(False)
```

Similar pattern for `test_mark_quote_win_promotes_to_active_jobs` and `test_refresh_rates_reopens_workbook`.

## Import + verify

```bash
# 1. Edit erp-v14-ribbon-callbacks.bas with changes
# 2. Open ERP_Master_v14.xlsm in VBE → re-import the .bas
# 3. Save As .xlsm
# 4. Run test
scripts\run-erp-tests.bat -v

# Expected:
# tests/integration/test_erp_quote_flow.py::test_generate_quote_creates_quotes_sheet_row PASSED
# tests/integration/test_erp_quote_flow.py::test_mark_quote_win_promotes_to_active_jobs PASSED
# tests/integration/test_erp_quote_flow.py::test_refresh_rates_reopens_workbook PASSED
# ...
# 14 passed, 0 skipped
```

## Success criteria
- [ ] `g_TestMode` flag exists, togglable via `SetTestMode(True/False)`
- [ ] `MsgBoxOrSilent` helper in place
- [ ] 15 info/success prompts converted (list each with file:line in commit message)
- [ ] Error prompts unchanged in production
- [ ] 3 previously-skipped tests now PASSING
- [ ] `pytest tests/integration` → `14 passed, 0 skipped`

## Risk
- LOW in production (silencing only applies when flag = True, default False)
- MED in test stack (if a test forgets to reset flag, next test may silently accept errors)
  → mitigation: `try / finally SetTestMode(False)` in every test body

## Next
→ P3 quote flow quick wins (now tested by unblocked quote flow tests)
