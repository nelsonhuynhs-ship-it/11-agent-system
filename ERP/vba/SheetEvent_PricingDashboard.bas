' ============================================
' SHEET EVENT CODE — Paste into Pricing Dashboard sheet module
' ============================================
' HOW TO ADD:
' 1. Open VBA Editor (Alt+F11)
' 2. In Project Explorer, find "📊 Pricing Dashboard" under VBAProject
' 3. Double-click to open the sheet module
' 4. Paste this code there
' ============================================

Private Sub Worksheet_Change(ByVal Target As Range)
    ' Delegate to the main handler in QuoteJobWorkflow module
    HandlePricingSheetChange Target
End Sub
