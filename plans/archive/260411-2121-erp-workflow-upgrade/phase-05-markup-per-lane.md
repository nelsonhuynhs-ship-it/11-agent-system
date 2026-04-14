# Phase 5 — Markup Per-Lane Schema

**Priority:** MEDIUM (correctness, not daily friction) | **Status:** PENDING | **Effort:** 2-3h | **Tier:** 2

## Problem

`Markup_Store` sheet is keyed by **Carrier** only. Same carrier on different lanes gets same margin:

**Example:** Nelson sets WC margin for ONE = $150/40HQ, then opens a EC quote for ONE. Ribbon shows $150 (loaded from store). Nelson adjusts to $200 for EC. Saves. Next WC quote for ONE → shows $200 (WC margin silently destroyed).

## Proposed schema

**Current:** `Markup_Store` cols: `Carrier | Mar20GP | Mar40GP | Mar40HC | Mar45HC | Mar40NOR | Mar20RF | Mar40RF`

**New:** `Carrier | Lane | Mar20GP | Mar40GP | Mar40HC | Mar45HC | Mar40NOR | Mar20RF | Mar40RF`

Where `Lane` ∈ {`WC`, `EC`, `GULF`, `*` (default)}. Default row `*` acts as fallback if no lane-specific row found.

**Why lane (not full POL+POD):** 3 lane groups match Nelson's mental model + market behavior. Per-POD would create 50+ rows per carrier — overhead without value.

## Actions

### 5.1 Map POD → Lane helper

Add to `ERPv14Core` module (`erp-v14-quick-wins.bas`):
```vba
Public Function GetLaneFromPOD(pod As String) As String
    ' Maps POD to lane group for markup lookup.
    ' Mirrors the lane map used by forecast/market report.
    Dim p As String: p = UCase(Trim(pod))
    If Len(p) = 0 Then GetLaneFromPOD = "*" : Exit Function

    ' WC ports
    If InStr(p, "LAX") > 0 Or InStr(p, "LGB") > 0 Or InStr(p, "LONG BEACH") > 0 _
        Or InStr(p, "OAK") > 0 Or InStr(p, "OAKLAND") > 0 _
        Or InStr(p, "SEA") > 0 Or InStr(p, "TAC") > 0 Or InStr(p, "TACOMA") > 0 _
        Or InStr(p, "VANCOUVER") > 0 Or InStr(p, "PORTLAND") > 0 Then
        GetLaneFromPOD = "WC": Exit Function
    End If
    ' EC ports
    If InStr(p, "NYC") > 0 Or InStr(p, "NEW YORK") > 0 _
        Or InStr(p, "BOS") > 0 Or InStr(p, "BOSTON") > 0 _
        Or InStr(p, "SAV") > 0 Or InStr(p, "CHS") > 0 Or InStr(p, "CHARLESTON") > 0 _
        Or InStr(p, "BAL") > 0 Or InStr(p, "MIA") > 0 Or InStr(p, "MIAMI") > 0 _
        Or InStr(p, "NORFOLK") > 0 Or InStr(p, "JAX") > 0 Or InStr(p, "JACKSONVILLE") > 0 _
        Or InStr(p, "MONTREAL") > 0 Or InStr(p, "TORONTO") > 0 Or InStr(p, "HALIFAX") > 0 Then
        GetLaneFromPOD = "EC": Exit Function
    End If
    ' GULF ports
    If InStr(p, "HOU") > 0 Or InStr(p, "HOUSTON") > 0 _
        Or InStr(p, "NOLA") > 0 Or InStr(p, "NEW ORLEANS") > 0 _
        Or InStr(p, "MOBILE") > 0 Then
        GetLaneFromPOD = "GULF": Exit Function
    End If

    GetLaneFromPOD = "*"  ' fallback
End Function
```

### 5.2 Update `LoadMarkupForCarrier` to use (carrier, lane) key

File: `erp-v14-ribbon-callbacks.bas:484` (current signature takes only `cn`)

```vba
Private Sub LoadMarkupForCarrier(cn As String)
    m_Mar20GP = 0: m_Mar40GP = 0: m_Mar40HC = 0
    m_Mar45HC = 0: m_Mar40NOR = 0: m_Mar20RF = 0: m_Mar40RF = 0
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ERPv14Core.FindSheet("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Then Exit Sub
    Dim lane As String: lane = ERPv14Core.GetLaneFromPOD(m_POD)

    Dim lastRow As Long: lastRow = wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
    Dim foundExact As Long: foundExact = 0
    Dim foundDefault As Long: foundDefault = 0
    Dim r As Long
    For r = 2 To lastRow
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(cn) Then
            Dim rowLane As String: rowLane = UCase(Trim(wsM.Cells(r, 2).Value))
            If rowLane = lane Then
                foundExact = r
                Exit For
            ElseIf rowLane = "*" Or Len(rowLane) = 0 Then
                foundDefault = r  ' keep searching for exact lane match
            End If
        End If
    Next r

    Dim useRow As Long
    If foundExact > 0 Then
        useRow = foundExact
    ElseIf foundDefault > 0 Then
        useRow = foundDefault
    Else
        Exit Sub
    End If

    ' Columns shifted +1 because Lane inserted at col 2
    m_Mar20GP = ERPv14Core.SL(wsM.Cells(useRow, 3).Value)
    m_Mar40GP = ERPv14Core.SL(wsM.Cells(useRow, 4).Value)
    m_Mar40HC = ERPv14Core.SL(wsM.Cells(useRow, 5).Value)
    m_Mar45HC = ERPv14Core.SL(wsM.Cells(useRow, 6).Value)
    m_Mar40NOR = ERPv14Core.SL(wsM.Cells(useRow, 7).Value)
    m_Mar20RF = ERPv14Core.SL(wsM.Cells(useRow, 8).Value)
    m_Mar40RF = ERPv14Core.SL(wsM.Cells(useRow, 9).Value)
End Sub
```

### 5.3 Update `SaveMarkupForCarrier` correspondingly

Same file:
```vba
Private Sub SaveMarkupForCarrier(cn As String)
    Dim wsM As Worksheet
    On Error Resume Next
    Set wsM = ERPv14Core.FindSheet("Markup_Store")
    On Error GoTo 0
    If wsM Is Nothing Then Exit Sub
    Dim lane As String: lane = ERPv14Core.GetLaneFromPOD(m_POD)

    Dim lastRow As Long: lastRow = wsM.Cells(wsM.Rows.Count, 1).End(xlUp).Row
    Dim r As Long, found As Long: found = 0
    For r = 2 To lastRow
        If UCase(Trim(wsM.Cells(r, 1).Value)) = UCase(cn) _
           And UCase(Trim(wsM.Cells(r, 2).Value)) = lane Then
            found = r
            Exit For
        End If
    Next r
    If found = 0 Then
        found = lastRow + 1
        wsM.Cells(found, 1).Value = cn
        wsM.Cells(found, 2).Value = lane
    End If
    wsM.Cells(found, 3).Value = m_Mar20GP
    wsM.Cells(found, 4).Value = m_Mar40GP
    wsM.Cells(found, 5).Value = m_Mar40HC
    wsM.Cells(found, 6).Value = m_Mar45HC
    wsM.Cells(found, 7).Value = m_Mar40NOR
    wsM.Cells(found, 8).Value = m_Mar20RF
    wsM.Cells(found, 9).Value = m_Mar40RF
End Sub
```

### 5.4 One-shot migration of existing Markup_Store data

Current rows have no Lane column. Migration: shift each row's columns right by 1 and insert `*` in col 2.

Python migration script: `scripts/migrate-markup-store.py`
```python
"""Migrate Markup_Store sheet from v1 (per-carrier) to v2 (per-carrier-lane).

Run ONCE before importing the updated VBA.
"""
import shutil
import sys
from pathlib import Path
import openpyxl

XLSM = Path("D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm")
BACKUP = Path("D:/OneDrive/NelsonData/pricing/_backup/pre-p5-markup-migration/")

def migrate():
    BACKUP.mkdir(parents=True, exist_ok=True)
    shutil.copy2(XLSM, BACKUP / XLSM.name)
    print(f"Backed up to {BACKUP}")

    wb = openpyxl.load_workbook(XLSM, keep_vba=True)
    ws = wb["Markup_Store"]

    # Check if already migrated (col 2 header = 'Lane')
    if ws.cell(1, 2).value == "Lane":
        print("Already migrated (col 2 is Lane). Nothing to do.")
        return

    print(f"Before: {ws.max_row} rows, {ws.max_column} cols")

    # Insert new column at position 2
    ws.insert_cols(2)
    ws.cell(1, 2).value = "Lane"
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, 1).value:
            ws.cell(r, 2).value = "*"  # default lane

    wb.save(XLSM)
    print(f"After: {ws.max_row} rows, {ws.max_column} cols")
    print("Migration done. Re-import updated VBA modules into the xlsm.")

if __name__ == "__main__":
    migrate()
```

### 5.5 Unit test the lane mapper

`tests/unit/test_erp_lane_mapper.py`:
```python
"""Unit test for GetLaneFromPOD — run via xlwings to call the VBA function."""
import pytest

@pytest.mark.parametrize("pod,expected", [
    ("LAX-LGB", "WC"),
    ("LONG BEACH", "WC"),
    ("OAKLAND", "WC"),
    ("VANCOUVER, BC", "WC"),
    ("NEW YORK, NY", "EC"),
    ("BALTIMORE", "EC"),
    ("CHARLESTON", "EC"),
    ("MIAMI", "EC"),
    ("HOUSTON, TX", "GULF"),
    ("NEW ORLEANS", "GULF"),
    ("UNKNOWN_PORT", "*"),
])
def test_lane_mapping(erp_workbook, pod, expected):
    result = erp_workbook.macro("ERPv14Core.GetLaneFromPOD")(pod)
    assert result == expected
```

## Rollout order

1. Backup xlsm + Markup_Store
2. Run `python scripts/migrate-markup-store.py`
3. Verify Lane column present
4. Re-import updated VBA modules
5. Test manually: set WC margin for ONE → switch to EC route → verify margin resets (loads * default or separate EC row)
6. Run pytest regression

## Success criteria
- [ ] Markup_Store has `Lane` column at position 2
- [ ] `GetLaneFromPOD` maps PODs correctly (11 test cases pass)
- [ ] Setting margin for ONE on WC route → saved as (ONE, WC)
- [ ] Switching to EC route for ONE → loads separate (ONE, EC) row or * default
- [ ] Migration idempotent (safe to run twice)
- [ ] Regression green

## Risk
- HIGH — migration touches live ERP file
- Mitigation: backup first (script does), manual verification of Markup_Store after migration before VBA re-import

## Next
→ P6: Architecture docs
