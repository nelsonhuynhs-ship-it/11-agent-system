# Phase 1 — Sheet Activate Event + Cascade Search

**Priority:** HIGH (daily pain) | **Status:** PENDING | **Effort:** 2-3h | **Tier:** 1

## Context

Nelson's #1 pain: switching `Pricing Dry` ↔ `Pricing Reefer` tab does NOT refresh the ribbon. He has to click a data cell after every tab switch. Plus search combo (Carrier) doesn't narrow POL/POD dropdowns.

## Root causes (verified against live v14 VBA)

1. `erp-v14-ribbon-callbacks.bas:429` `LoadRowToRibbon` only wired via `Worksheet_SelectionChange` event — no `Workbook_SheetActivate` hook
2. `OnChange_Search*` handlers (`erp-v14-ribbon-callbacks.bas:185-340`) each write to row 1 independently, no cross-combo awareness
3. Row 1 search text persists when user switches sheets (e.g., Carrier=ONE leftover on Reefer tab)

## Actions

### 1.1 Add `Workbook_SheetActivate` event
Add to `ThisWorkbook` VBA module (manual paste via VBE — no .bas file):
```vba
Private Sub Workbook_SheetActivate(ByVal Sh As Object)
    On Error Resume Next
    ' Only react when entering a pricing sheet
    If InStr(1, Sh.Name, "Pricing", vbTextCompare) = 0 Then Exit Sub

    ' Clear any stale row 1 search placeholders from previous sheet
    ERPv14Core.ClearAllSearchPlaceholders Sh

    ' Reload ribbon from active cell if it points at a data row
    Dim r As Long: r = ActiveCell.Row
    If r >= DATA_START_ROW Then
        Call ERPv14Ribbon.LoadRowToRibbon(r)
    Else
        ' No row selected — clear ribbon state
        Call ERPv14Ribbon.ClearRibbonState
    End If

    ' Re-apply preset if active (DRY_ONLY / REEFER_ONLY / SHOW_ALL)
    Call ERPv14Preset.RefreshActivePreset
    On Error GoTo 0
End Sub
```

### 1.2 Add helpers in `erp-v14-quick-wins.bas` (ERPv14Core module)
```vba
' Clear all 6 search placeholders (Carrier/POL/POD/Place/Exp/Note) on row 1
Public Sub ClearAllSearchPlaceholders(ws As Worksheet)
    Dim cols As Variant
    cols = Array(1, 2, 3, 4, 5, 6)  ' adjust to match actual search columns
    Dim i As Long
    For i = LBound(cols) To UBound(cols)
        On Error Resume Next
        ws.Cells(1, cols(i)).Value = GetPlaceholder(CInt(cols(i)))
        On Error GoTo 0
    Next i
    ' Clear AutoFilter
    If ws.AutoFilterMode Then ws.AutoFilterMode = False
End Sub
```

### 1.3 Add `ClearRibbonState` in `erp-v14-ribbon-callbacks.bas`
```vba
Public Sub ClearRibbonState()
    m_POL = "": m_POD = "": m_Place = "": m_Carrier = ""
    m_Eff = "": m_Exp = "": m_Note = "": m_Source = ""
    m_Buy20GP = 0: m_Buy40GP = 0: m_Buy40HC = 0: m_Buy45HC = 0
    m_Buy40NOR = 0: m_Buy20RF = 0: m_Buy40RF = 0
    m_Mar20GP = 0: m_Mar40GP = 0: m_Mar40HC = 0: m_Mar45HC = 0
    m_Mar40NOR = 0: m_Mar20RF = 0: m_Mar40RF = 0
    m_PUC20 = 0: m_PUC40 = 0: m_PUC40HC = 0
    m_Customer = ""
    m_IsSOC = False: m_SourceRow = 0
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
End Sub
```

### 1.4 Cascade search combos
Modify each `OnChange_Search*` in `erp-v14-ribbon-callbacks.bas:185-340` to rebuild sibling combo item lists after filter applied:

```vba
Public Sub OnChange_SearchCarrier(control As IRibbonControl, text As String)
    Dim ws As Worksheet: Set ws = ERPv14Core.GetActivePricingSheet()
    If ws Is Nothing Then Exit Sub
    ws.Cells(1, COL_CARRIER).Value = IIf(text = "", GetPlaceholder(COL_CARRIER), text)
    Call ERPv14Core.ApplyQuickSearch(ws)
    ' CASCADE: force other combos to re-read their item lists from visible rows only
    If Not ribbonUI Is Nothing Then
        ribbonUI.InvalidateControl "cbSearchPOL"
        ribbonUI.InvalidateControl "cbSearchPOD"
        ribbonUI.InvalidateControl "cbSearchPlace"
    End If
End Sub
```

### 1.5 Modify `GetItemLabel_POL` / `GetItemLabel_POD` / `GetItemLabel_Place` to read from filtered visible rows only
In `erp-v14-ribbon-callbacks.bas:208`, `236`, `264`:
```vba
Public Sub GetItemLabel_POL(control As IRibbonControl, index As Long, ByRef label As Variant)
    ' Build list from currently visible rows only (respects AutoFilter)
    label = ERPv14Core.GetUniqueVisibleValues(COL_POL)(index)
End Sub
```

Add helper in `ERPv14Core`:
```vba
Public Function GetUniqueVisibleValues(col As Long) As Collection
    ' Returns unique non-empty values from column `col`, visible rows only
    Dim c As New Collection
    Dim ws As Worksheet: Set ws = GetActivePricingSheet()
    Dim r As Long, lastRow As Long, v As String
    lastRow = ws.Cells(ws.Rows.Count, col).End(xlUp).Row
    For r = DATA_START_ROW To lastRow
        If ws.Rows(r).Hidden = False Then
            v = SS(ws.Cells(r, col).Value)
            If Len(v) > 0 Then
                On Error Resume Next
                c.Add v, v  ' key-based dedup
                On Error GoTo 0
            End If
        End If
    Next r
    Set GetUniqueVisibleValues = c
End Function
```

### 1.6 Import changes into live xlsm
```
1. Open ERP_Master_v14.xlsm in VBE (Alt+F11)
2. In ThisWorkbook module, paste Workbook_SheetActivate
3. Re-import updated erp-v14-ribbon-callbacks.bas + erp-v14-quick-wins.bas
4. Save As .xlsm
```

## Verification

```bash
# 1. Run integration test — should still pass 11/3 (P1 doesn't touch MsgBox blockers)
scripts\run-erp-tests.bat

# 2. Manual smoke:
# a. Open ERP_Master_v14.xlsm
# b. On Pricing Dry, click any row → ribbon shows buy prices for that row
# c. Click Pricing Reefer tab → ribbon AUTO-refreshes to whatever row is active
# d. Type "ONE" in Carrier combo → POL dropdown now shows only POLs with ONE rates
# e. Click Pricing Dry tab → row 1 search placeholders reset, AutoFilter cleared
```

## Success criteria
- [ ] Sheet activate event fires on tab click
- [ ] Ribbon state refreshes automatically on sheet switch
- [ ] Cascade filter: POL dropdown narrows after Carrier typed
- [ ] Row 1 search resets on sheet switch
- [ ] Regression: 11/3 pytest still green

## Risk
- MED — VBA event hooks can cause infinite loops if not guarded. `On Error Resume Next` + `Application.EnableEvents = False` around internal calls recommended.

## Next
→ P2: MsgBox refactor to unblock quote flow tests
