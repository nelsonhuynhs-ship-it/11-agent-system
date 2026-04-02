' ============================================================
'  Sheet Event Handler for Pricing Dashboard
'  Paste into the SHEET MODULE of "Pricing Dashboard"
'  (NOT a standard module — must be the sheet module)
'  How: Alt+F11 > double-click "Sheet1 (Pricing Dashboard)"
'       in Project Explorer > paste into code window
' ============================================================

Private Sub Worksheet_SelectionChange(ByVal Target As Range)
    ' Only process single cell click (not multi-select)
    If Target.Cells.Count > 1 Then Exit Sub
    
    ' Only trigger for columns A through P (data range)
    If Target.Column < 1 Or Target.Column > 16 Then Exit Sub
    
    ' Only from data row 2 onwards (row 1 = header)
    If Target.Row < 2 Then Exit Sub
    
    ' Load selected row into ribbon
    Call QuoteBuilder.LoadRowToRibbon(Target.Row)
End Sub
