# Phase 3 — Quote Flow Quick Wins

**Priority:** MEDIUM | **Status:** PENDING | **Effort:** 2h | **Tier:** 1
**Depends on:** P2 (needs unblocked quote flow tests for regression safety)

## Scope — 4 quick wins

1. **Quote Image multi-row bug** — select 4 rows, get only 2 (from memory)
2. **Customer validation** — red-flag typo not in CRM sheet
3. **Margin "apply default" button** — skip 7-field retype
4. **PUC lookup fuzzy match** — stop failing on "HO CHI MINH CITY" vs "HOCHIM"

## Action 3.1 — Quote Image multi-row fix

File: `erp-v14-ribbon-callbacks.bas:1526` `OnAction_QuoteImage`

**Bug hypothesis (from memory):** `Selection.Cells` enumerates all cells in contiguous selection, but multi-row select behaves inconsistently. Fix: use `Selection.Columns(1).Cells` to enumerate the first column's cells = one cell per row.

```vba
' BEFORE (pseudo, verify actual code)
For Each c In Selection.Cells
    ' process row c.Row

' AFTER
Dim firstCol As Range
Set firstCol = Intersect(Selection.EntireRow, Selection.Parent.Columns(Selection.Column))
For Each c In firstCol.Cells
    ' process row c.Row
```

**Also fix cleanup:**
```vba
' End of OnAction_QuoteImage — always delete _QuoteImg sheet even on error
On Error Resume Next
Application.DisplayAlerts = False
ThisWorkbook.Sheets("_QuoteImg").Delete
Application.DisplayAlerts = True
On Error GoTo 0
```

## Action 3.2 — Customer validation

File: `erp-v14-ribbon-callbacks.bas:670` `OnChange_Customer`

```vba
Public Sub OnChange_Customer(control As IRibbonControl, text As String)
    m_Customer = Trim(text)
    If Len(m_Customer) = 0 Then Exit Sub

    ' Verify against CRM sheet
    Dim wsCRM As Worksheet
    Set wsCRM = ERPv14Core.FindSheet("CRM")
    If wsCRM Is Nothing Then Exit Sub

    Dim found As Boolean: found = False
    Dim lastRow As Long: lastRow = wsCRM.Cells(wsCRM.Rows.Count, 1).End(xlUp).Row
    Dim r As Long
    For r = 2 To lastRow
        If UCase(Trim(wsCRM.Cells(r, 1).Value)) = UCase(m_Customer) Then
            found = True
            Exit For
        End If
    Next r

    If Not found Then
        ' Silent warning via status bar — don't block Nelson's typing
        Application.StatusBar = "⚠ Customer '" & m_Customer & "' not in CRM. Press Add to register."
        m_CustomerValid = False
    Else
        Application.StatusBar = False
        m_CustomerValid = True
    End If
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
End Sub
```

Add module var `Public m_CustomerValid As Boolean`.

**Don't block quote generation** — Nelson may enter new customer. Just warn.

## Action 3.3 — Margin "Apply Default" button

Add ribbon control to `CustomUI_v14.xml`:
```xml
<button id="btnApplyDefaultMargin"
        label="Apply Default"
        imageMso="FormatPainter"
        onAction="OnAction_ApplyDefaultMargin"
        screentip="Load last saved margin for this carrier"/>
```

Handler in `erp-v14-ribbon-callbacks.bas`:
```vba
Public Sub OnAction_ApplyDefaultMargin(control As IRibbonControl)
    If Len(m_Carrier) = 0 Then
        MsgBox "Click a data row first to pick carrier.", vbExclamation
        Exit Sub
    End If
    LoadMarkupForCarrier m_Carrier  ' existing helper
    Call SaveMarkupForCarrier(m_Carrier)  ' persist to store
    If Not ribbonUI Is Nothing Then ribbonUI.Invalidate
    Application.StatusBar = "Applied default margin for " & m_Carrier
End Sub
```

This effectively re-loads existing carrier margin from `Markup_Store` with 1 click instead of 7 edits.

## Action 3.4 — PUC fuzzy match

File: `erp-v14-ribbon-callbacks.bas:533` `LookupPUC`

Read current implementation first, then:
```vba
Private Sub LookupPUC(placeName As String)
    m_PUC20 = 0: m_PUC40 = 0: m_PUC40HC = 0
    If Len(placeName) = 0 Then Exit Sub
    Dim wsP As Worksheet: Set wsP = ERPv14Core.FindSheet("PUC_Lookup")
    If wsP Is Nothing Then Exit Sub

    Dim lastRow As Long: lastRow = wsP.Cells(wsP.Rows.Count, 1).End(xlUp).Row
    Dim r As Long, target As String, row_place As String
    target = UCase(Trim(placeName))

    ' Pass 1: exact match
    For r = 2 To lastRow
        row_place = UCase(Trim(wsP.Cells(r, 1).Value))
        If row_place = target Then
            m_PUC20 = ERPv14Core.SL(wsP.Cells(r, 2).Value)
            m_PUC40 = ERPv14Core.SL(wsP.Cells(r, 3).Value)
            m_PUC40HC = ERPv14Core.SL(wsP.Cells(r, 4).Value)
            Exit Sub
        End If
    Next r

    ' Pass 2: contains (either direction)
    For r = 2 To lastRow
        row_place = UCase(Trim(wsP.Cells(r, 1).Value))
        If Len(row_place) >= 5 And (InStr(target, row_place) > 0 Or InStr(row_place, target) > 0) Then
            m_PUC20 = ERPv14Core.SL(wsP.Cells(r, 2).Value)
            m_PUC40 = ERPv14Core.SL(wsP.Cells(r, 3).Value)
            m_PUC40HC = ERPv14Core.SL(wsP.Cells(r, 4).Value)
            Debug.Print "[PUC fuzzy] " & placeName & " → " & wsP.Cells(r, 1).Value
            Exit Sub
        End If
    Next r

    ' No match — log
    Debug.Print "[PUC] No match for: " & placeName
End Sub
```

## Verification

```bash
# Regression
scripts\run-erp-tests.bat

# Expected: 14 passed / 0 skipped (P2 already unlocked those)
```

**Manual smoke for each fix:**
1. Quote Image: open Pricing Dry, select 4 rows, click Quote Image → clipboard should contain all 4 rows (not 2)
2. Customer: type "GARBAGE_TYPO" in Customer combo → status bar shows warning
3. Apply Default: click row → click "Apply Default" → margin fields show saved values
4. PUC: pick SOC row with "HO CHI MINH CITY" place → PUC_Lookup has "HOCHIM" → values loaded

## Success criteria
- [ ] Quote Image multi-row works (4 rows in, 4 rows out)
- [ ] _QuoteImg sheet auto-cleans on error path
- [ ] Customer typo shows status bar warning (doesn't block generation)
- [ ] Apply Default margin = 1 click = 7 margin fields populated
- [ ] PUC matches "HO CHI MINH CITY" even when PUC_Lookup has "HOCHIM" or vice versa
- [ ] Regression green

## Risk
- LOW — each fix is self-contained
- `m_CustomerValid` field new — make sure serialization via `SaveMarkupForCarrier` isn't affected (shouldn't be)

## Next
→ P4: Python refresh layer (parquet 45'HQ)
