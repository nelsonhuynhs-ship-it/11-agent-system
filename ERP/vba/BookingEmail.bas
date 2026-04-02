Attribute VB_Name = "BookingEmail"
Option Explicit

' ============================================================
'  BOOKING EMAIL TEMPLATE ENGINE — ERP V13
'  Generates booking request email (subject + body)
'  No costing visible in email — booking info only.
' ============================================================

Public Function BuildBookingEmail( _
    carrier As String, contractType As String, _
    cont As String, pol As String, pod As String, _
    place As String, sc As String, _
    groupCode As String, nac As String, _
    customer As String, qty As Integer, _
    vol As Double, gw As String, _
    etd As String, hsCode As String, _
    vessel As String) As String

    Dim isFIX As Boolean
    isFIX = InStr(UCase(contractType), "FIX") > 0
    Dim isReefer As Boolean
    isReefer = (UCase(cont) = "20RF" Or UCase(cont) = "40RF")
    Dim isONE As Boolean
    isONE = UCase(Trim(carrier)) = "ONE"
    Dim isCMA As Boolean
    isCMA = InStr(UCase(carrier), "CMA") > 0
    Dim isZIM As Boolean
    isZIM = UCase(Trim(carrier)) = "ZIM"

    ' Contract label
    Dim contractLabel As String
    If isReefer Then
        contractLabel = "REEFER - " & sc
    Else
        contractLabel = sc
    End If

    ' Container display (booking codes)
    Dim contDisp As String
    Select Case UCase(cont)
        Case "20GP": contDisp = "20DC"
        Case "40GP": contDisp = "40DC"
        Case "40HC", "40HQ": contDisp = "40HC"
        Case "45HQ", "45HC": contDisp = "45HC"
        Case "40NOR": contDisp = "40NOR"
        Case "20RF": contDisp = "20RF"
        Case "40RF": contDisp = "40RF"
        Case Else: contDisp = cont
    End Select

    ' POL config
    Dim polFull As String, mtPickup As String
    Dim fullReturn As String, gwDefault As String
    Select Case UCase(Trim(pol))
        Case "HCM"
            polFull = "HO CHI MINH, VN"
            mtPickup = "ICD TANAMEXCO"
            fullReturn = "ICD TANAMEXCO"
            gwDefault = "20 TONS"
        Case "HPH"
            polFull = "HAI PHONG, VN"
            mtPickup = "": fullReturn = ""
            gwDefault = "17 TONS"
        Case "DAD"
            polFull = "DA NANG, VN"
            mtPickup = "": fullReturn = ""
            gwDefault = "17 TONS"
        Case "UIH"
            polFull = "QUI NHON, VN"
            mtPickup = "": fullReturn = ""
            gwDefault = "17 TONS"
        Case "VUT"
            polFull = "VUNG TAU, VN"
            mtPickup = "ICD TANAMEXCO"
            fullReturn = "ICD TANAMEXCO"
            gwDefault = "20 TONS"
        Case Else
            polFull = pol & ", VN"
            mtPickup = "": fullReturn = ""
            gwDefault = "17 TONS"
    End Select
    If Len(Trim(gw)) = 0 Then gw = gwDefault

    ' Subject line
    Dim subject As String
    subject = customer & " BOOKING | " & pol & "-" & place & _
        " VIA " & pod & " | " & qty & "X" & contDisp & " | " & _
        carrier & IIf(isFIX, " FIX", " FAK") & _
        IIf(InStr(UCase(contractType), "SOC") > 0, " SOC", "") & _
        " | NELSON" & IIf(Len(Trim(vessel)) > 0, " | " & vessel, "")

    ' Volume display
    Dim volStr As String
    If vol > 0 Then
        volStr = Format(vol, "#,##0") & " CBM"
    Else
        volStr = "[anh tu dien]"
    End If

    ' ETD display
    Dim etdStr As String
    If Len(Trim(etd)) > 0 Then etdStr = etd Else etdStr = "[anh tu dien]"

    ' Build email body
    Dim b As String
    Dim BL As String: BL = Chr(10)
    b = "Dear Mira Cus Team/Pudong," & BL & BL
    b = b & "Please help me release the booking as below info:" & BL
    b = b & "- Carrier: " & carrier & BL
    b = b & "- Contract number: " & contractLabel & BL

    ' ONE group rate line
    If isONE And Len(Trim(groupCode)) > 0 Then
        b = b & "- Group rate for USCA only " & _
            "(based on pricing's rate, if any): " & groupCode & BL
    End If

    ' NAC line — FIX always, ZIM spot, FAK skip
    If isFIX Or isZIM Then
        Dim nacStr As String
        If Len(Trim(nac)) > 0 Then nacStr = nac Else nacStr = "Actual NAC"
        b = b & "- NAC (if any): " & nacStr & BL
    End If

    b = b & "- POL: " & polFull & BL
    b = b & "- POD: " & pod & BL
    b = b & "- FND/DEL: " & place & BL
    b = b & "- ETD: " & etdStr & BL
    b = b & "- CMD: [anh tu dien]" & BL
    b = b & "- HS code: " & IIf(Len(Trim(hsCode)) > 0, hsCode, "[anh tu dien]") & BL
    b = b & "- Volume: " & volStr & BL
    b = b & "- Gross Weight per container (GW): " & gw & BL
    b = b & "- Stuffing place: WAREHOUSE" & BL

    If Len(mtPickup) > 0 Then
        b = b & "- MT pick up: " & mtPickup & BL
    End If
    If Len(fullReturn) > 0 Then
        b = b & "- Full return: " & fullReturn & BL
    End If

    b = b & "- Special Remark: HOT SHIPMENT, CONT SACH TOT" & BL

    If isReefer Then
        b = b & "- REEFER CONTAINER - TEMPERATURE: " & _
            "-18" & Chr(176) & "C / VENTILATION: CLOSED / HUMIDITY: NO" & BL
    End If

    If isCMA And Not isFIX Then
        b = b & "- Payment term: PREPAID" & BL
    End If

    b = b & BL & "Thank you for your support!"

    ' Return subject||body (caller splits on "||")
    BuildBookingEmail = subject & "||" & b
End Function

' ============================================================
'  BUILD MAILTO LINK
' ============================================================
Public Function BuildMailtoLink(emailContent As String) As String
    Dim parts() As String
    parts = Split(emailContent, "||")
    If UBound(parts) < 1 Then
        BuildMailtoLink = "mailto:?subject=BOOKING&body="
        Exit Function
    End If
    Dim subj As String: subj = parts(0)
    Dim body As String: body = parts(1)

    ' URL encode
    body = Replace(body, " ", "%20")
    body = Replace(body, Chr(10), "%0D%0A")
    body = Replace(body, "&", "%26")
    body = Replace(body, Chr(176), "%C2%B0")
    subj = Replace(subj, " ", "%20")
    subj = Replace(subj, "&", "%26")

    BuildMailtoLink = "mailto:?subject=" & subj & "&body=" & body
End Function
