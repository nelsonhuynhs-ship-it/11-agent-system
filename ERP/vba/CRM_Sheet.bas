Attribute VB_Name = "CRM_Sheet"
Option Explicit

' ============================================================
'  CRM_Sheet — Customer SOP Lookup Module
'  Sheet: "CRM" — Row 1 = Header, Row 2+ = Customer data
'  Single source of truth for docteam operations
' ============================================================

' ============================================================
'  GetCRMField — Lookup any field by Customer_Name
'  customerName: match against col B (Customer_Name)
'  fieldCol: column letter (e.g. "U" for MT_Pickup_ICD)
'  Returns "" if not found
' ============================================================
Public Function GetCRMField(customerName As String, fieldCol As String) As String
    On Error Resume Next
    GetCRMField = ""
    
    If Len(Trim(customerName)) = 0 Then Exit Function
    If Len(Trim(fieldCol)) = 0 Then Exit Function
    
    Dim wsCRM As Worksheet
    Set wsCRM = Nothing
    Set wsCRM = ThisWorkbook.Sheets("CRM")
    If wsCRM Is Nothing Then Exit Function
    
    Dim colNum As Long
    colNum = Range(fieldCol & "1").Column
    If colNum = 0 Then Exit Function
    
    Dim searchName As String
    searchName = UCase(Trim(customerName))
    
    Dim r As Long
    Dim lastRow As Long
    lastRow = wsCRM.Cells(wsCRM.Rows.Count, 2).End(xlUp).Row
    
    For r = 2 To lastRow
        If UCase(Trim(CStr(wsCRM.Cells(r, 2).Value))) = searchName Then
            GetCRMField = CStr(wsCRM.Cells(r, colNum).Value)
            Exit Function
        End If
    Next r
    
    On Error GoTo 0
End Function

' ============================================================
'  GetCRMFieldByCRMID — Lookup any field by CRM_ID (col A)
'  crmID: match against col A (CRM_ID)
'  fieldCol: column letter (e.g. "B" for Customer_Name)
'  Returns "" if not found
' ============================================================
Public Function GetCRMFieldByCRMID(crmID As String, fieldCol As String) As String
    On Error Resume Next
    GetCRMFieldByCRMID = ""
    
    If Len(Trim(crmID)) = 0 Then Exit Function
    If Len(Trim(fieldCol)) = 0 Then Exit Function
    
    Dim wsCRM As Worksheet
    Set wsCRM = Nothing
    Set wsCRM = ThisWorkbook.Sheets("CRM")
    If wsCRM Is Nothing Then Exit Function
    
    Dim colNum As Long
    colNum = Range(fieldCol & "1").Column
    If colNum = 0 Then Exit Function
    
    Dim searchID As String
    searchID = UCase(Trim(crmID))
    
    Dim r As Long
    Dim lastRow As Long
    lastRow = wsCRM.Cells(wsCRM.Rows.Count, 1).End(xlUp).Row
    
    For r = 2 To lastRow
        If UCase(Trim(CStr(wsCRM.Cells(r, 1).Value))) = searchID Then
            GetCRMFieldByCRMID = CStr(wsCRM.Cells(r, colNum).Value)
            Exit Function
        End If
    Next r
    
    On Error GoTo 0
End Function
