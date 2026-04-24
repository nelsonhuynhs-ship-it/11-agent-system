# VBA Standards — ERP v4

**Status:** Canonical reference (2026-04-15)
**Audience:** AI agents + any contributor editing `.bas` / `.xml` / VBA project files.
**Companion doc:** `vba-gotchas.md` (reactive — documents bugs we hit).
This doc is **proactive** — the standards every module must meet before it ships.

> Nelson's frustration we solve here: "em chỉ fix được lỗi A thì lỗi B lại tiếp tục bị tiếp".
> This doc + the 7/7 `verify-erp.bat` pipeline close that loop.

---

## 1. Pipeline — 7/7 verify-erp gate

`scripts/verify-erp.bat` is the single entry point. Exit 0 = safe to test in Excel.
Every ERP edit (`.bas` / `.xml` / `active_jobs_cols.py`) MUST pass it before commit.

| Step | Script | What it catches |
|------|--------|-----------------|
| 1 | `taskkill EXCEL` | stale Excel locks files |
| 2 | `check_vba_compile.py` | R1–R9 static lint (< 1s) |
| 3 | `check_zip_structure.py` | `customUI14.xml` + `vbaProject.bin` present in xlsm zip |
| 4 | `check_vba_modules.py` | required modules present, no duplicates (`Module1`, `ModuleName1`) |
| 5 | `check_imports.py` | Python core imports (`active_jobs_cols`, `ribbon_guard`, `email_builder`) |
| 6 | `pytest` core | `ribbon_guard + schema + email_builder` tests |
| 7 | `check_vba_live_compile.py` | **headless Excel COM compile** — final gate |

Layer logic:
```
Static lint (step 2) ───── catches known patterns, fast, always runs
                   │
                   ▼
Live compile (step 7) ──── catches anything lint misses
                           (type libs, corrupted VBA project, edge cases)
```

If step 2 catches it, you save ~10s vs waiting for step 7. Both exist because
**neither alone is sufficient** — lint has false negatives on novel patterns,
live compile requires Excel installed + Trust Access ON.

---

## 2. Lint rules (R1–R9) — `check_vba_compile.py`

Every `.bas` file in `D:/OneDrive/NelsonData/erp/*.bas` is scanned.

### R1 — Module-level declarations before procedures
```
Attribute VB_Name = "…"
Option Explicit
' <-- all module-level Const/Private/Public/Dim MUST live here
Private m_State As String

Private Sub First()    ' <-- first procedure
    …
End Sub

' <-- after this line, only procedures allowed. Declarations here raise:
'     "Compile error: Only comments may appear after End Sub…"
```
**Bug we hit (gotcha #11):** `Private m_CurrentMonth As String` on line 655 of
`erp-v14-jobs-automation.bas`.

### R2 — Every Sub/Function has matching End
Simple counter: `^(Public|Private|Friend)?\s*(Sub|Function|Property)` vs `^End (Sub|Function|Property)`.

### R3 — `Chr(n>255)` → use `ChrW(n)`
```vba
' BAD — runtime error on non-ASCII:
Chr(8594)   ' →
' GOOD:
ChrW(8594)
```
**Bug we hit (gotcha #1):** Mark WIN silently failed — `Chr(9679)` (●) raised
runtime error, jumped to handler, no visible effect.

### R4 — Line continuation followed by `_Ident`
```vba
' BAD — parsed as "__UrlEncode" (illegal identifier):
mailto = "http://..." & _
         _UrlEncode(x)
```
**Bug we hit (gotcha #2).** Fix: rename helper or reshape the expression.

### R5 — Identifier must NOT start with underscore
```vba
' BAD — VBA compile error "Syntax error":
Private Function _FormatMonthLabel(iso As String) As String
Private _m_State As String

' GOOD:
Private Function FormatMonthLabel(iso As String) As String
Private m_State As String
```
**Bug we hit (gotcha #12, 2026-04-15):** after fixing R1, Nelson hit another
compile error because helpers were named `_CurrentMonthISO`, `_FormatMonthLabel`,
`_ShiftMonth`. Python convention doesn't carry over to VBA.

### R6 — Identifier must NOT be a VBA reserved keyword
Reserved keywords list (MS-VBAL spec) includes:
`Sub, Function, Property, End, If, Then, Else, Dim, Const, Public, Private,
Friend, Static, Type, Enum, Declare, WithEvents, As, New, Nothing, Null,
Empty, True, False, Me, Set, Let, Get, Call, Do, Loop, For, Each, Next,
While, Wend, Until, Exit, Return, GoTo, On, Error, Resume, Select, Case,
With, Option, Explicit, Base, Compare, Module, Class, Attribute, Implements,
Event, RaiseEvent, Redim, Preserve, Is, Not, And, Or, Xor, Eqv, Imp, Like,
Mod, TypeOf, ByRef, ByVal, Optional, ParamArray, Property, Lib, Alias, Any,
String, Integer, Long, Single, Double, Currency, Date, Boolean, Byte, Variant,
Object, Decimal, LongLong, LongPtr`

False-positive fix (2026-04-15): `IDENT_DECL` regex now skips
`Type|Enum|Declare|WithEvents` in the declaration keyword group, so
`Private Type HdlRule` doesn't flag "Type" as the identifier name.

### R7 — Identifier must NOT contain `.` `!` `@` `&` `$` `#`
These chars are reserved for type suffixes (`x&` = Long, `s$` = String) and
member access (`obj.Member`, `Worksheets!Sheet1`).

### R8 — Every `.bas` module must have `Option Explicit`
Scans first ~40 lines of declaration section. Without it, typos become silent
`Variant/Empty` — caught at runtime not compile, the exact class of bug we
want to eliminate.

### R9 — `Attribute VB_Name = "X"` must match filename stem
**Only enforced when both filename stem and VB_Name are valid VBA idents.**
This skip avoids a false positive on `erp-v14-jobs-automation.bas` (kebab-case
filename, `VB_Name = "ERPv14JobsAutomation"`) — VBA can't have hyphens so the
stem itself isn't a valid identifier. When imported, VBE uses the `VB_Name`
attribute and ignores the filename.

---

## 3. Live compile gate — `check_vba_live_compile.py`

### Why it exists
Static lint only catches patterns we've seen before. Live compile catches
**anything** Excel would refuse at open time:
- Missing/broken type library references
- Corrupted VBA project (happens after crashed Excel)
- Novel syntax errors we haven't encoded as lint rules yet
- Locked project (authorisation failure)

### How it works
1. `win32com.client.DispatchEx("Excel.Application")` — hidden instance
2. `excel.Workbooks.Open(xlsm, UpdateLinks=0, ReadOnly=True)`
3. `excel.VBE.CommandBars.FindControl(Id=578).Execute()` — VBE "Compile VBAProject"
4. Poll `win32gui.EnumWindows` for ~2s for dialog title matching:
   - `"Microsoft Visual Basic for Applications"`
   - `"Microsoft Visual Basic"`
   - `"Compile error"`
5. Enumerate `VBProject.VBComponents`, read `CodeModule.Lines(1, count)` —
   catches locked project (lines unreadable = project failed to compile)
6. Close any surfaced dialogs with `WM_CLOSE` before `Excel.Quit()` — otherwise
   Quit hangs waiting for user input

### Hardening: `_retry_com()`
Excel rejects COM calls with `RPC_E_CALL_REJECTED` (`-2147418111`) or
`RPC_E_SERVERCALL_RETRYLATER` (`-2147417846`) while VBE is mid-compile. Without
retry, the gate fails intermittently.

```python
def _retry_com(fn, retries: int = 8, base_delay: float = 0.25):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as ex:
            msg = str(ex)
            if "rejected by callee" in msg or "-2147418111" in msg or "-2147417846" in msg:
                time.sleep(min(base_delay * (2 ** attempt), 2.0))
                pythoncom.PumpWaitingMessages()
                continue
            raise
```
Backoff: 0.25s → 0.5s → 1s → 2s (capped). 8 attempts = ~8s worst case.
`pythoncom.PumpWaitingMessages()` between retries is critical — without pumping,
Excel never gets a chance to finish what it's busy with.

### Exit codes
- `0` — clean compile (prints `LIVE_COMPILE: OK (N modules compiled via Excel)`)
- `1` — compile error (dialog surfaced OR module unreadable OR VBE.Execute raised)
- `2` — environment error (no pywin32, no Excel, Trust Access off, can't open file)

### Prereqs
- Excel installed (not Excel for Mac / web / 365 online)
- `pywin32` installed: `pip install pywin32`
- "Trust access to VBA project object model" = ON
  (File → Options → Trust Center → Macro Settings → check the box)

---

## 4. Module structure standard

```vba
Attribute VB_Name = "SomeModule"          ' matches filename stem (R9)
Option Explicit                           ' mandatory (R8)

'==============================================================
' MODULE-LEVEL DECLARATIONS (before any Sub/Function — R1)
'==============================================================
Private Const PY_HOME As String = "C:\Users\Nelson\anaconda3\python.exe"
Private Const LOG_PATH As String = "D:\OneDrive\NelsonData\erp\logs\"
Private m_CurrentMonth As String          ' ISO "YYYY-MM"
Private m_TestMode As Boolean

'==============================================================
' PUBLIC API (ribbon callbacks)
'==============================================================
Public Sub OnAction_SomeButton(control As IRibbonControl)
    On Error GoTo EH
    …
    Exit Sub
EH:
    LogError "OnAction_SomeButton", Err.Number, Err.Description
End Sub

'==============================================================
' PRIVATE HELPERS (no leading underscore — R5)
'==============================================================
Private Function FormatMonthLabel(iso As String) As String
    FormatMonthLabel = …
End Function
```

### Naming
- Module: `PascalCase` matching filename stem (`ERPv14JobsAutomation`)
- Public Subs/Functions: `PascalCase` (`OnAction_QuoteImage`, `RefreshAll`)
- Ribbon callbacks: prefix `OnAction_` or `GetEnabled_` or `GetLabel_`
- Private helpers: `PascalCase`, no underscore prefix (`FormatMonthLabel`)
- Module-level vars: `m_camelCase` (`m_CurrentMonth`, `m_TestMode`)
- Constants: `UPPER_SNAKE` (`PY_HOME`, `LOG_PATH`)
- Loop vars: short (`i`, `r`, `c`, `wb`, `ws`)

### Error handling template
```vba
Public Sub ActionX(control As IRibbonControl)
    On Error GoTo EH
    ' happy path
    Exit Sub
EH:
    LogError "ActionX", Err.Number, Err.Description
    MsgBox "ActionX failed: " & Err.Description, vbExclamation
End Sub
```
Never swallow errors with `On Error Resume Next` unless you `Err.Clear` and
check `Err.Number` explicitly. Blanket resume-next hides every bug.

### Chr() vs ChrW()
Use `ChrW` for any char > 255. Our Unicode codes:

| Code | Char | Use |
|------|------|-----|
| 8594 | → | navigation |
| 9675 | ○ | status empty |
| 9679 | ● | status filled |
| 9680 | ◐ | status partial |
| 10003 | ✓ | checkmark |
| 8987 | ⌛ | hourglass / waiting |
| 128231 | 📧 | email |

---

## 5. Ribbon preservation (critical)

`customUI/customUI14.xml` disappears from `.xlsm` if you save with vanilla
`openpyxl.save()`. Every Python helper MUST use:

```python
from ERP.core.ribbon_guard import save_preserving_ribbon
save_preserving_ribbon(wb, erp_file)  # NOT wb.save(erp_file)
```

`check_zip_structure.py` (verify step 3) fails if `customUI14.xml` or
`vbaProject.bin` missing from the xlsm zip. That's your early warning.

---

## 6. Deployment pattern

Live VBA lives on OneDrive, **not** the repo:
`D:/OneDrive/NelsonData/erp/*.bas`

Deployment flow:
1. Edit `.bas` file in OneDrive (it's the source of truth)
2. Run `verify-erp.bat` — must be green
3. Commit the `.bas` changes + test updates
4. `install_jobs_automation.py` reloads modules in-place via
   `CodeModule.AddFromFile` (safer than `Import` which creates `ModuleName1`
   duplicates on partial failure — see gotcha #5)

See `docs/erp-v14-source-of-truth.md` for the full source-of-truth policy.

---

## 7. Adding a new lint rule

When we hit a new class of bug:
1. Reproduce it with a minimal `.bas` snippet
2. Document it in `vba-gotchas.md` (bug → root cause → fix)
3. Add a rule R(N+1) to `check_vba_compile.py` — include:
   - `# R(N+1) — …` comment at top of docstring
   - Pattern match in `check_file()`
   - Test it against a known-bad file AND the full `erp-v14-*.bas` corpus
     (catch false positives before shipping)
4. Update this doc's §2 table
5. Commit all three (gotcha, lint, standards) together

---

## 8. Quick reference

```bash
# Before every commit touching VBA:
scripts\verify-erp.bat

# Just the fast linter (no Excel needed):
python scripts\check_vba_compile.py

# Just the live compile gate (needs Excel + Trust Access):
python scripts\check_vba_live_compile.py "D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"
```

Expected output from step 7 when green:
```
LIVE_COMPILE: OK (5 modules compiled via Excel)
```
