---
name: erp-governance
description: Governance + regression prevention for Nelson Freight ERP v4. MUST auto-activate on any edit to ERP/, erp-v14-*.bas, CustomUI_v14.xml, or Active Jobs-related tasks. Loads ERP_STANDARDS.md + feature-checklist.md + vba-gotchas.md and enforces pre-flight checks.
---

# ERP Governance

You are editing Nelson Freight's ERP v4 system. **Read and enforce the three governance docs before any change.**

## When this skill triggers

Auto-load on any of:
- User asks to edit `ERP/*`, `erp-v14-*.bas`, `CustomUI_v14.xml`, `ERP_Master_v14.xlsm`
- User says "add feature", "new button", "thêm tính năng", "mark WIN", "ribbon"
- User reports bug in Excel workbook or ribbon
- User asks about Active Jobs layout, tracking dots, mailto links
- Task involves Python helpers under `ERP/jobs/` or `ERP/intelligence/` or `ERP/core/`

## Mandatory pre-flight (every session)

Before editing ANY file under the ERP umbrella, read these three docs:

1. **`docs/ERP_STANDARDS.md`** — architecture, code, test, deploy, change standards
2. **`docs/feature-checklist.md`** — 15 questions to answer before writing code
3. **`docs/vba-gotchas.md`** — 10 traps already discovered (Chr vs ChrW, line continuation, Break on All Errors, etc.)

Load them with the Read tool. Don't skim — cite specific section numbers when writing code.

## Required actions

### On feature request
1. Open `docs/feature-checklist.md`
2. Answer Q1-Q15 explicitly in your response (or in a plan file)
3. Only then write code

### On bug fix
1. Open `docs/vba-gotchas.md`
2. Check if bug matches any of the 10 known traps
3. If yes → apply fix from gotchas
4. If no → add new entry to gotchas after fix

### On any code change to ERP
1. Before commit: run `scripts/verify-erp.bat`
2. Must exit 0
3. If fails → fix + re-run, never ignore

### On schema change (Active Jobs cols)
Dangerous. Follow `docs/ERP_STANDARDS.md` §4.4 full protocol:
- Update `ERP/core/active_jobs_cols.py` first
- Run `ERP/core/migrate_active_jobs_v4.py`
- Audit all Python helpers + tests + VBA
- Backup xlsm with timestamp
- Test suite must be 0-failed

## Source-of-truth files (NEVER hardcode)

| What | Where |
|---|---|
| Active Jobs col positions | `ERP/core/active_jobs_cols.py` (COL dict) |
| VBA ribbon callbacks | `D:/OneDrive/NelsonData/erp/erp-v14-jobs-automation.bas` |
| VBA core ribbon | `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` |
| Ribbon XML | `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` |
| Booking email rules | `ERP/carrier_rules/booking_rules.json` |
| Commission rules | `ERP/data/commissions_rules.yaml` |
| Reefer plug rules | `ERP/data/reefer_freetime.yaml` |
| Live workbook | `D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm` |

## Non-negotiable rules

1. **Every openpyxl save on ERP_Master_v14.xlsm MUST use `save_preserving_ribbon()`** from `ERP.core.ribbon_guard`. Never bare `wb.save(path)`. Else customUI gets stripped, Nelson loses ribbon tabs.

2. **Every Python helper COL reference MUST import from `ERP.core.active_jobs_cols`**. No `ws.cell(r, 5)` — use `ws.cell(r, COL["ETD"])`.

3. **Every VBA ribbon handler MUST have error handler** (`On Error GoTo ErrHandler`). Ribbon click errors bubble up = Excel break mode = bad UX.

4. **Unicode chars (>255) MUST use `ChrW()` not `Chr()`** in VBA. Chr(8594) throws runtime error silently.

5. **Line continuation `& _` followed by `_X` identifier** = parse as `__X`. Either rename or restructure.

6. **Pre-commit MUST run `scripts/verify-erp.bat`** and get exit 0.

7. **Every bug fix MUST add regression test** that would have caught it.

8. **Schema changes require backup first** — `cp ERP_Master_v14.xlsm ERP_Master_v14_BACKUP_YYYYMMDD_HHMM.xlsm`

## Quick references

### Python helper skeleton

```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))
from active_jobs_cols import COL, HDR_ROW, DATA_START
from ribbon_guard import save_preserving_ribbon
import openpyxl
import argparse

def do_work(erp_file: str) -> int:
    wb = openpyxl.load_workbook(erp_file, keep_vba=True)
    ws = wb["Active Jobs"]
    for r in range(DATA_START, ws.max_row + 1):
        if not ws.cell(r, COL["CRM_ID"]).value:
            continue
        # work here ...
    save_preserving_ribbon(wb, erp_file)  # NEVER wb.save()
    wb.close()
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--erp", default=r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm")
    args = ap.parse_args()
    return do_work(args.erp)

if __name__ == "__main__":
    sys.exit(main())
```

### VBA ribbon handler skeleton

```vba
Public Sub OnAction_NewButton(control As IRibbonControl)
    On Error GoTo ErrHandler

    If MsgBox("Description of what happens. Continue?", _
              vbYesNo + vbQuestion, "New Button") = vbNo Then Exit Sub

    Dim script As String: script = FindScript("ERP\jobs\new_helper.py")
    If script = "" Then
        MsgBox "new_helper.py not found", vbExclamation, "New Button"
        Exit Sub
    End If

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "new_button_log.txt"

    Call EnsureFileClosedThenReopen(fullPath, "New Button")
    Dim rc As Long: rc = RunPythonHidden(script, "--erp """ & fullPath & """", logFile)
    Call ReopenWorkbook(fullPath)

    If rc <> 0 Then
        MsgBox "Failed: " & ReadLog(logFile, 15), vbExclamation, "New Button"
        Exit Sub
    End If
    Call MsgBoxOrSilent("Done." & vbCrLf & ReadLog(logFile, 10), vbInformation, "New Button")
    Exit Sub

ErrHandler:
    Application.Visible = True
    MsgBox "Error: " & Err.Description, vbCritical, "New Button"
End Sub
```

### Test skeleton

```python
# tests/test_new_feature.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ERP" / "core"))
from active_jobs_cols import COL

def test_happy_path(seeded_erp):
    # seeded_erp fixture provides copy of ERP_Master_v14.xlsm with 7 seed rows
    import openpyxl
    wb = openpyxl.load_workbook(seeded_erp, keep_vba=True)
    ws = wb["Active Jobs"]
    # test assertion using COL — never hardcoded ints
    assert ws.cell(8, COL["CRM_ID"]).value == "NAFOODS"
    wb.close()

def test_edge_empty_sheet(erp_copy):
    # verify graceful handling of empty Active Jobs
    ...

def test_error_missing_input(tmp_path):
    # verify error path returns non-zero exit, doesn't crash
    ...
```

## Output format

When triggered, begin your response with:

```
[erp-governance] Loaded: ERP_STANDARDS.md (§N), feature-checklist.md, vba-gotchas.md (#X)
[erp-governance] Pre-flight: answered Q1-Q15 / consulted gotchas
[erp-governance] Source-of-truth: using COL from active_jobs_cols.py
```

Then proceed with the user's task.

## Escalation

If user asks to skip any standard ("just do it quickly"), respond:
> Standards prevent regressions. Which specific step do you want to skip, and what's the trade-off you accept? (cite ERP_STANDARDS.md section)

Never skip without explicit user acknowledgment of risk.
