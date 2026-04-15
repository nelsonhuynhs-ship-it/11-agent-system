# VBA Gotchas — ERP v4 Edit Checklist

Quick reference to avoid re-introducing bugs that already cost us time.
Check this list **before** committing any `.bas` / `.xml` ribbon edit.

## 1. `Chr(n)` only works for 0-255 — use `ChrW(n)` for Unicode

Bug we hit: `Mark WIN silently failed` because tracking dots used `Chr(9679)` (●).

```vba
' BAD — raises runtime error, jumps to handler silently
wsJ.Cells(r, c).Value = Chr(8594) & "arrow"

' GOOD
wsJ.Cells(r, c).Value = ChrW(8594) & "arrow"
```

Unicode codes we use: 8594 (→) 9675 (○) 9679 (●) 9680 (◐) 10003 (✓) 8987 (⌛) 128231 (📧).

## 2. Line continuation `& _` + next line starts with `_X` → VBA parses as `__X`

Bug we hit: `Syntax error` on mailto assignment because:

```vba
mailto = "http://..." & _
         _UrlEncode(x)    ' parsed as __UrlEncode — not found!
```

**Rule:** Never put a `_`-prefixed identifier at the start of a continuation line.
Fix: either rename (`UrlEncodeStr`) or reshape (`mailto = ...` on one line, append on next).

## 3. `Application.Run "Module.Sub"` doesn't pass IRibbonControl

Test wrappers need to call `control As IRibbonControl` subs with a real control.
Workaround: write a `Public Sub TestXxx()` wrapper that calls the target sub with `Nothing`, or make the test call the inner logic directly.

## 4. VBE "Break on All Errors" setting ignores `On Error Resume Next`

Registry: `HKCU\Software\Microsoft\VBA\<ver>\Common\DefaultErrorTrapping`
- 0 = Break on All Errors (DANGER — breaks even with handlers)
- 1 = Break in Class Module
- 2 = Break on Unhandled Errors (correct default)

Force via PowerShell:
```powershell
foreach ($v in '6.0','6.5','7.0','7.1') {
    $k = "HKCU:\Software\Microsoft\VBA\$v\Common"
    if (Test-Path $k) { Set-ItemProperty -Path $k -Name DefaultErrorTrapping -Value 2 -Force }
}
```

## 5. `VBComponents.Import` fails mid-way → creates `ModuleName1` duplicate

Bug we hit: ribbon callbacks had 2 copies, conflicting dispatch → VBE break mode.

**Rule:** Always use `install_jobs_automation.py` which uses `CodeModule.AddFromFile` for in-place reload. If Import is used and fails, the auto-cleanup pass scans for `<Name>\d+$` and removes.

## 6. `openpyxl.save()` strips `customUI/customUI14.xml` from .xlsm

Bug we hit: ribbon tabs Pricing/Operations disappeared after every Python script that wrote to the workbook.

**Rule:** every Python helper that edits ERP_Master_v14.xlsm must use:
```python
from ERP.core.ribbon_guard import save_preserving_ribbon
save_preserving_ribbon(wb, erp_file)  # NOT wb.save(erp_file)
```

## 7. `cell.value = None` does NOT clear hyperlinks

Bug we hit: `seed_test_jobs --clear` left mailto URLs as raw text in cells.

```python
cell.value = None
cell.hyperlink = None  # MUST clear separately
cell.ClearComments()   # and comments
```

## 8. Module-level `Public g_State As X` — reset to default on workbook open

Don't assume state persists across sessions. Always check `If Len(s) = 0 Then s = default`.

## 9. InputBox in VBA does not respect `g_TestMode` silent flag

Test automation can't answer an InputBox. Either:
- Test non-interactive path separately
- Inject a test-mode bypass: `If g_TestMode Then qty = 1 Else qty = InputBox(...)`

## 10. Excel caches macro list at workbook open

After `CodeModule.AddFromString`, newly added Subs may not be callable via `Application.Run` until workbook is saved + reopened, OR until Excel recompiles. Prefer adding to source `.bas` + re-import.

## Pre-commit checklist

Run **before** every commit that touches `.bas` / `.xml` / `active_jobs_cols.py`:

```
scripts\verify-erp.bat
```

Must print `[OK] ALL CHECKS PASSED` or investigate before committing.
