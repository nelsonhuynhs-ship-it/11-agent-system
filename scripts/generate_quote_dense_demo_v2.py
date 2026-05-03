"""
generate_quote_dense_demo_v2.py
Creates QUOTE_DENSE_DEMO_v2.xlsm with VBA action buttons.
Nelson Freight · 2026-04-25

Uses win32com.client.Dispatch (NOT EnsureDispatch — avoids broken gencache).
VBA module injected via COM into the workbook before save.
"""
import os, win32com.client as win32

OUT_DIR  = os.path.abspath("docs/visual-tour/quote-mockups")
OUT_FILE = os.path.join(OUT_DIR, "QUOTE_DENSE_DEMO_v2.xlsm")

def fc(r, g, b):
    return (b << 16) | (g << 8) | r  # BGR for Excel

def hex_fc(h):
    r, g, b = int(h[1:3],16), int(h[3:5],16), int(h[5:7],16)
    return fc(r, g, b)

# Excel color constants (BGR)
C_GREEN   = fc(74, 222, 128)
C_RED     = fc(239, 68, 68)
C_AMBER   = fc(245, 158, 11)
C_GRAY    = fc(107, 114, 128)
C_DKBLUE  = fc(30, 58, 95)
C_LTTEAL  = fc(239, 246, 255)
C_WHITE   = fc(255, 255, 255)
C_LTGRAY  = fc(248, 250, 252)
C_BLUE    = fc(37, 99, 235)

HEADERS = ['#','Customer','Carrier','POL','POD','20GP','40GP','40HC','45HC','40NOR','Margin','Status','Date','Actions']
ROWS = [
    (1,'GOWIN INTERNATIONAL','ONE','HCM','LAX/LGB',1800,2200,2300,3000,2500,200,'WIN','2026-04-25'),
    (2,'ALENE TRADING','HPL','HPH','USNYC',1900,2400,2500,3200,2700,150,'PENDING','2026-04-25'),
    (3,'DOUSHENG GROUP','CMA','HCM','USEC',2000,2500,2600,3300,2800,50,'LOST','2026-04-24'),
    (4,'HML LOGISTICS','YML','HPH','USLGB',1850,2300,2400,3100,2600,180,'WIN','2026-04-25'),
    (5,'CAROLINA TRADE','COSCO','HCM','USNYC',1950,2450,2550,3250,2750,220,'WIN','2026-04-24'),
    (6,'TRALINKS CO','MSC','HPH','USOAK',2100,2600,2700,3400,2900,100,'PENDING','2026-04-23'),
    (7,'SOFIA SHIPPING','EMC','HCM','USTAC',1880,2330,2430,3130,2630,180,'WIN','2026-04-23'),
    (8,'LKB EXPRESS','ZIM','HPH','USORF',1990,2490,2590,3290,2790,80,'EXPIRED','2026-04-20'),
    (9,'GSV CONSULTANTS','WHL','HCM','USCHS',2050,2550,2650,3350,2850,250,'WIN','2026-04-25'),
    (10,'NEW PROSPECT','HMM','HPH','USSAV',1870,2320,2420,3120,2620,60,'PENDING','2026-04-25'),
    (11,'PUDONG PRIME','ONE','HCM','USMOB',1920,2420,2520,3220,2720,190,'WIN','2026-04-24'),
    (12,'NELSON DIRECT','HPL','HPH','USJAX',2080,2580,2680,3380,2880,120,'PENDING','2026-04-23'),
    (13,'CMA TEST CO','CMA','HCM','LAX/LGB',1810,2210,2310,3010,2510,90,'LOST','2026-04-22'),
    (14,'BRAVO IMPORT','COSCO','HPH','USHOU',2110,2610,2710,3410,2910,280,'WIN','2026-04-25'),
    (15,'DELTA EXPORT','YML','HCM','USPDX',1970,2470,2570,3270,2770,70,'EXPIRED','2026-04-19'),
]

VBA_CODE = '''Attribute VB_Name = "QuoteActions"
' Quote Dense Demo v2 - VBA Action Macros
' Nelson Freight - 2026-04-25

Public Sub Action_View_Quote()
    Dim r As Long, msg As String
    r = ActiveCell.Row
    If r < 5 Then MsgBox "Click một row (từ row 5 trở xuống) trước khi View.", vbExclamation: Exit Sub
    msg = "Customer: " & Cells(r,2).Value & vbCrLf & "Carrier: " & Cells(r,3).Value & vbCrLf & _
          "Route: " & Cells(r,4).Value & " -> " & Cells(r,5).Value & vbCrLf & _
          "Containers: " & Cells(r,6).Value & "/" & Cells(r,7).Value & "/" & Cells(r,8).Value & vbCrLf & _
          "Margin: $" & Format(Cells(r,11).Value,"#,##0") & vbCrLf & _
          "Status: " & Cells(r,12).Value & vbCrLf & "Date: " & Cells(r,13).Value
    MsgBox msg, vbInformation, "Quote Detail -- Row " & r
End Sub

Public Sub Action_Mark_WIN()
    Dim r As Long
    r = ActiveCell.Row: If r < 5 Then Exit Sub
    Cells(r,12).Value = "WIN": Cells(r,12).Interior.Color = RGB(74,222,128)
    Cells(r,12).Font.Color = RGB(32,80,32): Cells(r,12).Font.Bold = True
    Cells(r,13).Value = Date: Cells(r,13).NumberFormat = "yyyy-mm-dd"
    MsgBox "Row " & r & " -> WIN", vbInformation, "Mark WIN"
End Sub

Public Sub Action_Mark_LOST()
    Dim r As Long, reason As String
    r = ActiveCell.Row: If r < 5 Then Exit Sub
    reason = InputBox("Lý do LOST?", "Mark LOST -- Row " & r)
    Cells(r,12).Value = "LOST": Cells(r,12).Interior.Color = RGB(239,68,68)
    Cells(r,12).Font.Color = RGB(255,255,255): Cells(r,12).Font.Bold = True
    Cells(r,13).Value = Date: Cells(r,13).NumberFormat = "yyyy-mm-dd"
    MsgBox "Row " & r & " -> LOST. Reason: " & reason, vbInformation, "Mark LOST"
End Sub

Public Sub Action_Re_Quote()
    Dim r As Long, newR As Long
    r = ActiveCell.Row: If r < 5 Then Exit Sub
    newR = ActiveSheet.UsedRange.Rows.Count + 1: If newR < 5 Then newR = 20
    ActiveSheet.Range(ActiveSheet.Cells(r,1),ActiveSheet.Cells(r,14)).Copy ActiveSheet.Cells(newR,1)
    With ActiveSheet.Cells(newR,1)
        .Value = newR - 4
        .Offset(0,11).Value = "PENDING"
        .Offset(0,11).Interior.Color = RGB(245,158,11)
        .Offset(0,11).Font.Color = RGB(255,255,255): .Offset(0,11).Font.Bold = True
        .Offset(0,12).Value = Date: .Offset(0,12).NumberFormat = "yyyy-mm-dd"
        .Offset(0,13).Value = "View  WIN  LOST  ReQ"
        .Offset(0,13).Font.Color = RGB(37,99,235): .Offset(0,13).Font.Size = 9
    End With
    On Error Resume Next
    ActiveSheet.ListObjects("QuotesTable").Resize ActiveSheet.Range("A4:N" & newR)
    On Error GoTo 0
    MsgBox "Row " & r & " -> Re-quoted as Row " & newR & " (PENDING)", vbInformation, "Re-Quote"
End Sub

Public Sub ShowHelp()
    MsgBox "QUOTE DENSE DEMO v2 - Hướng Dẫn" & vbCrLf & vbCrLf & _
           "1. Banner trên: tự động recalc khi add/edit row" & vbCrLf & _
           "2. Status màu: WIN=green | LOST=red | PENDING=amber | EXPIRED=gray" & vbCrLf & _
           "3. Cột Margin: heatmap red-yellow-green" & vbCrLf & _
           "4. Chạy macro: Developer -> Macros -> chọn -> Run" & vbCrLf & _
           "5. Alt+F8 gọi nhanh" & vbCrLf & _
           "6. Data -> Filter để filter động", vbInformation, "Hướng Dẫn"
End Sub
'''

# ── Excel COM ─────────────────────────────────────────────────────────────────
print("Starting Excel via COM...")
excel = win32.DispatchEx("Excel.Application")
excel.Visible = 0
excel.DisplayAlerts = 0

wb = excel.Workbooks.Add()
ws = wb.Worksheets(1)
ws.Name = "Quotes_DENSE"

# ── BANNER (rows 1-3) ─────────────────────────────────────────────────────────
banner_defs = [
    # label  col, val col, hint col,  label_text,   formula,                             num_fmt,  hint
    ("A","B","C", "WIN HÔM NAY",   '=COUNTIFS(L5:L19,"WIN",M5:M19,">="&TODAY())', "",       "Tự động recalc khi add row"),
    ("A","B","C", "WIN TUẦN NÀY",  '=COUNTIFS(L5:L19,"WIN",M5:M19,">="&TODAY()-7)',"",     "WIN trong 7 ngày qua"),
    ("A","B","C", "TỔNG MARGIN",   '=SUMIFS(K5:K19,L5:L19,"WIN")',                  '$#,##0', "Sum margin WIN"),
    ("E","F","G", "WIN RATE",      '=IFERROR(COUNTIFS(L5:L19,"WIN")/COUNTA(L5:L19),0)','0.0%',"% WIN / total"),
    ("E","F","G", "TOTAL QUOTES",  '=COUNTA(L5:L19)',                                '',     "Số rows trong bảng"),
    ("E","F","G", "PENDING",       '=COUNTIFS(L5:L19,"PENDING")',                    '',     "Đang chờ phản hồi"),
]

for row_i, (lc, vc, hc, lbl, formula, num_fmt, hint) in enumerate(banner_defs, start=1):
    c_l = ws.Range(f"{lc}{row_i}")
    c_v = ws.Range(f"{vc}{row_i}")
    c_h = ws.Range(f"{hc}{row_i}")

    c_l.Value = lbl;   c_l.Font.Size = 10;  c_l.Font.Bold = True;  c_l.Font.Color = C_DKBLUE
    c_v.Formula = formula;  c_v.Font.Size = 22;  c_v.Font.Bold = True;  c_v.Font.Color = C_DKBLUE
    c_h.Value = hint;  c_h.Font.Size = 8;   c_h.Font.Italic = True;  c_h.Font.Color = C_GRAY

    for col in [lc, vc, hc]:
        ws.Range(f"{col}{row_i}").Interior.Color = C_LTTEAL

    if num_fmt:
        c_v.NumberFormat = num_fmt

# banner border
for r in range(1, 4):
    for c in ['A','B','C','D','E','F','G']:
        ws.Range(f"{c}{r}").Borders.LineStyle = -4142  # xlHairline

# ── HEADER ROW (row 4) ────────────────────────────────────────────────────────
col_widths = [4, 24, 10, 7, 11, 8, 8, 8, 8, 8, 9, 11, 12, 14]
for ci, hdr in enumerate(HEADERS, start=1):
    c = ws.Cells(4, ci)
    c.Value = hdr; c.Font.Bold = True; c.Font.Color = C_WHITE; c.Font.Size = 10
    c.Interior.Color = C_DKBLUE; c.HorizontalAlignment = -4108
    ws.Columns(ci).ColumnWidth = col_widths[ci-1]
ws.Rows(4).RowHeight = 20

# ── DATA ROWS (5-19) ──────────────────────────────────────────────────────────
status_fill = {
    'WIN':    (C_GREEN,  fc(32,80,32)),
    'LOST':   (C_RED,    C_WHITE),
    'PENDING':(C_AMBER,  C_WHITE),
    'EXPIRED':(C_GRAY,   C_WHITE),
}
for ri, row in enumerate(ROWS, start=5):
    bg = C_LTGRAY if ri % 2 == 0 else C_WHITE
    for ci, val in enumerate(row, start=1):
        c = ws.Cells(ri, ci)
        c.Value = val; c.Font.Size = 10; c.HorizontalAlignment = -4108
        if ci == 2:   c.Font.Size = 9;  c.HorizontalAlignment = -4131
        if ci == 11:  c.NumberFormat = '#,##0'
        if ci == 13:  c.NumberFormat = 'yyyy-mm-dd'
        if ci == 14:  c.Value = 'View  WIN  LOST  ReQ'; c.Font.Size = 9; c.Font.Color = C_BLUE
        if ci != 12:   c.Interior.Color = bg

    sv = row[11]
    sc = ws.Cells(ri, 12)
    sc.Value = sv; sc.Font.Bold = True; sc.HorizontalAlignment = -4108
    if sv in status_fill:
        fill_c, font_c = status_fill[sv]
        sc.Interior.Color = fill_c; sc.Font.Color = font_c

# ── MARGIN HEATMAP (K5:K19) ───────────────────────────────────────────────────
mr = ws.Range("K5:K19")
cfc = mr.FormatConditions.AddColorScale(3)
cfc.ColorScaleCriteria(1).Type = 1;  cfc.ColorScaleCriteria(1).FormatColor.Color = fc(252,165,165)
cfc.ColorScaleCriteria(2).Type = 5;  cfc.ColorScaleCriteria(2).Value = 150
cfc.ColorScaleCriteria(2).FormatColor.Color = fc(252,211,77)
cfc.ColorScaleCriteria(3).Type = 2;  cfc.ColorScaleCriteria(3).FormatColor.Color = fc(110,231,183)

# ── FREEZE PANES at B5 ────────────────────────────────────────────────────────
ws.Range("B5").Select()
excel.ActiveWindow.FreezePanes = True

# ── EXCEL TABLE (QuotesTable) ─────────────────────────────────────────────────
last_row = 4 + len(ROWS)
tbl_ref = f"A4:N{last_row}"
tbl_obj = ws.ListObjects.Add(1, ws.Range(tbl_ref), "", 1)  # xlSrcRange, has headers
tbl_obj.Name = "QuotesTable"
tbl_obj.TableStyle = "TableStyleMedium2"

# ── INSTRUCTIONS (row 21+) ─────────────────────────────────────────────────────
instr = [
    "HƯỚNG DẪN SỬ DỤNG:",
    "1. Banner trên có 4 formulas DYNAMIC -- add row mới → tự cập nhật",
    "2. Status cells tự đổi màu: WIN=green | LOST=red | PENDING=amber | EXPIRED=gray",
    "3. Cột Margin: heatmap red-yellow-green theo giá trị tuyệt đối",
    "4. Actions per row: Developer -> Macros -> chọn macro -> Run",
    "5. Alt+F8 gọi nhanh macro",
    "6. Chọn header -> Data -> Filter để filter động",
]
ws.Cells(21, 1).Value = instr[0]
ws.Cells(21, 1).Font.Bold = True; ws.Cells(21, 1).Font.Size = 11; ws.Cells(21, 1).Font.Color = C_DKBLUE
for i, line in enumerate(instr[1:], start=22):
    ws.Cells(i, 1).Value = line; ws.Cells(i, 1).Font.Size = 9; ws.Cells(i, 1).Font.Color = C_GRAY

# ── VBA MODULE ────────────────────────────────────────────────────────────────
print("Injecting VBA module...")
vbproj = wb.VBProject
vbcomp = vbproj.VBComponents.Add(1)   # vbext_ct_StdModule = 1
vbcomp.Name = "QuoteActions"
vbcomp.CodeModule.AddFromString(VBA_CODE)

# ── SAVE as .xlsm ─────────────────────────────────────────────────────────────
print(f"Saving to {OUT_FILE}...")
wb.SaveAs(OUT_FILE, FileFormat=52)   # 52 = xlOpenXMLWorkbookMacroEnabled
wb.Close()
excel.Quit()

size = os.path.getsize(OUT_FILE)
print(f"\nOutput : {OUT_FILE}")
print(f"Size   : {size:,} bytes ({size/1024:.1f} KB)")
print(f"Rows   : {len(ROWS)} data + header(4) + banner(3) = 19 data rows")
print(f"VBA    : 5 macros (View, WIN, LOST, ReQuote, ShowHelp)")
print("\nDone. Open in Excel -> Developer tab -> Macros -> Run.")