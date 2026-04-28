---
phase: 1
title: Smart logic cho OnAction_QuoteImage
status: pending
effort_loc: ~40 VBA
owner: MM M2.7
---

# Phase 1 — OnAction_QuoteImage smart-aware

## Context
Hiện tại `OnAction_QuoteImage` (file `erp-v14-ribbon-callbacks.bas` line 3224 in OneDrive canonical) yêu cầu user phải:
1. Đứng đúng sheet "Quotes" (line 3257-3260: `If Not ActiveSheet.Name = wsQ.Name Then ... Exit Sub`)
2. Select range ≥ row 2 (line 3286-3289: `If rowCount = 0 Then ... Exit Sub`)

Nelson đang khó chịu khi: vừa generate quote ở Pricing → phải tự sang Quotes → tự select dòng. Đặc biệt với multi-port quote (5 cảng), bấm select 5 dòng dễ sót.

## Spec đã chốt (HTML v3 28/04/2026)

| Anh đang ở đâu | Selection state | Behavior |
|---|---|---|
| Sheet Pricing | — | Activate sheet Quotes → tự lấy nhóm latest (cùng customer + ngày) → render |
| Sheet Quotes | empty/single empty cell | Tự lấy nhóm latest → render |
| Sheet Quotes | select N rows ≥ row 2 với QuoteID | Render đúng N rows đó (giữ nguyên cách cũ) |
| Hôm nay chưa có quote | — | MsgBox "Chưa có quote nào hôm nay" — Exit Sub |

## Implementation steps

### Step 1: Wrap existing logic
Đổi tên hàm hiện tại `OnAction_QuoteImage` thành `Private Sub QuoteImage_RenderRows(rowNums() As Long, rowCount As Long)`. Hàm mới nhận sẵn array rows + count, KHÔNG đọc Selection nữa, KHÔNG check ActiveSheet.

Move out: section "Collect selected rows" (line 3262-3289). Section đó sẽ ở caller mới.

Body của hàm (rendering logic line 3290+) giữ nguyên — chỉ đổi nơi rowNums/rowCount đến từ.

### Step 2: New `OnAction_QuoteImage` smart dispatcher
Replace lines 3224-3289 với logic mới (~40 LOC):

```vba
Public Sub OnAction_QuoteImage(Optional control As IRibbonControl = Nothing)
    On Error GoTo ErrHandler

    Dim wsQ As Worksheet
    Set wsQ = ERPv14Core.FindSheet("Quotes")
    If wsQ Is Nothing Then
        Call MsgBoxOrSilent("Quotes sheet not found!", vbExclamation, "Quote Image")
        Exit Sub
    End If

    Dim rowNums() As Long
    Dim rowCount As Long: rowCount = 0

    ' Decide mode: smart-auto vs explicit-selection
    Dim useSmartMode As Boolean
    useSmartMode = True  ' default

    If ActiveSheet.Name = wsQ.Name Then
        ' On Quotes sheet — check if user has meaningful selection
        Dim hasRealSelection As Boolean: hasRealSelection = False
        Dim selArea As Range, ri As Long, sr As Long
        For Each selArea In Selection.Areas
            For ri = 1 To selArea.Rows.Count
                sr = selArea.Rows(ri).Row
                If sr >= 2 And Trim(wsQ.Cells(sr, 1).Value) <> "" Then
                    hasRealSelection = True
                    Exit For
                End If
            Next ri
            If hasRealSelection Then Exit For
        Next selArea

        If hasRealSelection Then
            useSmartMode = False
            ' Reuse old collect-from-selection logic into rowNums/rowCount
            Call QuoteImage_CollectFromSelection(wsQ, rowNums, rowCount)
        End If
    End If

    If useSmartMode Then
        ' Auto-pick latest group: same customer + same date as row QUOTES_DATA_START (row 5)
        Call QuoteImage_CollectLatestGroup(wsQ, rowNums, rowCount)
    End If

    If rowCount = 0 Then
        Call MsgBoxOrSilent("Chua co quote nao trong nhom moi nhat hom nay." & vbCrLf & _
                            "Hay tao quote truoc, hoac sang sheet Quotes va chon dong cu the.", _
                            vbInformation, "Quote Image")
        Exit Sub
    End If

    ' Auto-jump to Quotes sheet if not already there
    If ActiveSheet.Name <> wsQ.Name Then
        wsQ.Activate
    End If

    ' Delegate to renderer (existing logic now in helper)
    Call QuoteImage_RenderRows(wsQ, rowNums, rowCount)
    Exit Sub

ErrHandler:
    MsgBox "Quote Image error: " & Err.Description, vbCritical, "Quote Image"
End Sub
```

### Step 3: Helper `QuoteImage_CollectFromSelection`
Refactored từ existing line 3262-3289. Same logic, output qua ByRef params:

```vba
Private Sub QuoteImage_CollectFromSelection(wsQ As Worksheet, _
                                            ByRef rowNums() As Long, _
                                            ByRef rowCount As Long)
    rowCount = 0
    Dim selArea As Range
    Dim sr As Long, isDup As Boolean, chk As Long, ri As Long
    For Each selArea In Selection.Areas
        For ri = 1 To selArea.Rows.Count
            sr = selArea.Rows(ri).Row
            If sr >= 2 And Trim(wsQ.Cells(sr, 1).Value) <> "" Then
                isDup = False
                If rowCount > 0 Then
                    For chk = 1 To rowCount
                        If rowNums(chk) = sr Then isDup = True: Exit For
                    Next chk
                End If
                If Not isDup Then
                    rowCount = rowCount + 1
                    ReDim Preserve rowNums(1 To rowCount)
                    rowNums(rowCount) = sr
                End If
            End If
        Next ri
    Next selArea
End Sub
```

### Step 4: Helper `QuoteImage_CollectLatestGroup`
Logic mới — tìm nhóm latest:

```vba
Private Sub QuoteImage_CollectLatestGroup(wsQ As Worksheet, _
                                          ByRef rowNums() As Long, _
                                          ByRef rowCount As Long)
    rowCount = 0
    ' QUOTES_DATA_START = 5 (per DOMAIN-ERP Rule 1)
    Dim startRow As Long: startRow = QUOTES_DATA_START
    If IsEmpty(wsQ.Cells(startRow, 1).Value) Or Trim(wsQ.Cells(startRow, 1).Value) = "" Then
        Exit Sub  ' No quotes today
    End If

    Dim refCust As String: refCust = UCase(Trim(CStr(wsQ.Cells(startRow, 3).Value)))
    Dim refDate As String: refDate = Format(wsQ.Cells(startRow, 2).Value, "yyyy-mm-dd")
    Dim refGid As String: refGid = Trim(CStr(wsQ.Cells(startRow, 43).Value))

    ' Walk down from row 5 while customer + date match
    Dim r As Long: r = startRow
    Dim lastRow As Long
    lastRow = wsQ.Cells(wsQ.Rows.Count, 1).End(xlUp).Row

    Do While r <= lastRow
        Dim qid As String: qid = Trim(CStr(wsQ.Cells(r, 1).Value))
        If qid = "" Then Exit Do

        Dim cust As String: cust = UCase(Trim(CStr(wsQ.Cells(r, 3).Value)))
        Dim dt As String: dt = Format(wsQ.Cells(r, 2).Value, "yyyy-mm-dd")
        Dim gid As String: gid = Trim(CStr(wsQ.Cells(r, 43).Value))

        Dim match As Boolean: match = False
        If refGid <> "" And gid = refGid Then
            match = True  ' QuoteGroupID match (most reliable)
        ElseIf cust = refCust And dt = refDate Then
            match = True  ' fallback: same customer + same date
        End If

        If Not match Then Exit Do  ' stop at first non-match

        rowCount = rowCount + 1
        ReDim Preserve rowNums(1 To rowCount)
        rowNums(rowCount) = r
        r = r + 1
    Loop
End Sub
```

### Step 5: Update screentip in CustomUI_v14.xml
Line 192-194 hiện tại:
```xml
<button id="btnQuoteImage" label="Quote Img" size="normal"
        imageMso="Camera" onAction="OnAction_QuoteImage"
        screentip="Create quote image to clipboard"/>
```
→ Update screentip:
```xml
<button id="btnQuoteImage" label="Quote Img" size="normal"
        imageMso="Camera" onAction="OnAction_QuoteImage"
        screentip="Smart auto-render: lay nhom quote moi nhat hom nay (cung khach + ngay). Hoac chon dong cu the truoc khi bam de render dung dong do."/>
```

Label giữ nguyên "Quote Img". Icon giữ Camera. Position giữ nguyên.

## Acceptance (cho phase này)

| Test | Pass criteria |
|------|--------------|
| Đứng ở Pricing, bấm Quote Img sau Generate Quote | Activate Quotes sheet + render group | 
| Đứng ở Quotes, không select | Render group latest | 
| Đứng ở Quotes, select 1 dòng cụ thể | Render đúng dòng đó (không phải group) |
| Đứng ở Quotes, select 3 dòng (rời nhau) | Render 3 dòng đó |
| Sheet Quotes empty (chưa có quote) | MsgBox info, không crash |
| Selection chỉ là cell trống ở Quotes | Fallback smart mode → group latest |

## Files modified
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` (modify line 3224 area)
- `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` (line 192-194 screentip)

After edit:
```bash
cp "D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas" "Engine_test/ERP/vba-v14-mirror/"
cp "D:/OneDrive/NelsonData/erp/CustomUI_v14.xml" "Engine_test/ERP/vba-v14-mirror/"
```
