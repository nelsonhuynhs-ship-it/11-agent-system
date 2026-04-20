Attribute VB_Name = "ERPv14JobsAutomation"
Option Explicit

' ============================================================
'  ERP v14 — Active Jobs v4 Automation (Python shell-out)
'  ---------------------------------------------------------
'  Handlers for new Operations-tab ribbon buttons that call
'  the Active Jobs v4 Python helpers:
'
'    btnPriceWatch    → ERP/intelligence/price_watch.py
'    btnTrackingSync  → ERP/jobs/shipment_tracker.py
'    btnReleaseAlert  → ERP/jobs/release_alerts.py
'    btnEnrichEmail   → ERP/jobs/enrichment.py
'    btnMonthlyV4     → ERP/intelligence/monthly_report.py
'
'  Shared pattern cloned from OnAction_RefreshRates:
'    - locate Python + script via known paths
'    - run hidden cmd, wait, read exit code + log
'    - show MsgBox with result; reload workbook if needed
'
'  Import into ThisWorkbook via VBE → File → Import File...
'  Then rebind buttons in CustomUI_v14.xml.
' ============================================================

Private Const PY_HOME As String = "C:\Users\Nelson\anaconda3\python.exe"
Private Const PY_ALT As String = "C:\Users\ADMIN\anaconda3\python.exe"

' ── Month combo state (2026-04-21) ──────────────────────────────────────────
' MUST be declared here at top-of-module (gotcha #11: no declarations after
' first Sub/Function). No leading underscore (gotcha #12).
Private m_Months() As String         ' display labels e.g. "APR 2026 (26 jobs)"
Private m_MonthISO() As String       ' ISO labels for filtering e.g. "APR-26"
Private m_MonthCount As Long         ' total items in combo (includes "All" entry)
Private m_SelectedMonthLabel As String  ' current display label shown in combo

' DEPRECATED 2026-04-21 — kept to avoid compile errors if old ribbon binding
' is still cached on some machines. Replaced by cmbMonth combo callbacks.
Private m_CurrentMonth As String     ' was: ISO "YYYY-MM" for old Prev/Next nav

Private Function FindPython() As String
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    If fso.FileExists(PY_HOME) Then FindPython = PY_HOME: Exit Function
    If fso.FileExists(PY_ALT) Then FindPython = PY_ALT: Exit Function
    FindPython = "python"
End Function

Private Function FindScript(relPath As String) As String
    ' Try 3 bases: OneDrive erp folder, PC Home repo, Laptop VP repo
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    Dim bases As Variant
    bases = Array( _
        "D:\NELSON\2. Areas\Engine_test\", _
        "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test\", _
        fso.GetParentFolderName(ThisWorkbook.FullName) & "\..\..\..\" _
    )
    Dim i As Long, p As String
    For i = 0 To UBound(bases)
        p = CStr(bases(i)) & relPath
        p = Replace(p, "/", "\")
        If fso.FileExists(p) Then FindScript = p: Exit Function
    Next i
    FindScript = ""
End Function

Private Function RunPythonHidden(script As String, args As String, logFile As String) As Long
    Dim py As String: py = FindPython()
    Dim cmd As String
    cmd = """" & py & """ """ & script & """ " & args & " > """ & logFile & """ 2>&1"
    Dim wsh As Object: Set wsh = CreateObject("WScript.Shell")
    RunPythonHidden = wsh.Run("cmd /c " & cmd, 0, True)
End Function

Private Function ReadLog(logFile As String, maxLines As Long) As String
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(logFile) Then ReadLog = "(no log)": Exit Function
    Dim ts As Object: Set ts = fso.OpenTextFile(logFile, 1)
    Dim s As String, n As Long: n = 0
    Do While Not ts.AtEndOfStream And n < maxLines
        s = s & ts.ReadLine & vbCrLf
        n = n + 1
    Loop
    ts.Close
    ReadLog = s
End Function

Private Function EnsureFileClosedThenReopen(fullPath As String, fn As String) As Boolean
    ' Close workbook so Python can write — needed for most helpers
    Application.StatusBar = fn & "... Please wait"
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False
    Application.Visible = False
    ThisWorkbook.Save
    ThisWorkbook.Close SaveChanges:=False
    EnsureFileClosedThenReopen = True
End Function

Private Sub ReopenWorkbook(fullPath As String)
    Workbooks.Open fullPath
    Application.Visible = True
    Application.WindowState = xlMaximized
    Application.DisplayAlerts = True
    Application.ScreenUpdating = True
    Application.StatusBar = False
End Sub

' ============================================================
'  BUTTON: PRICE WATCH
' ============================================================
Public Sub OnAction_PriceWatch(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim script As String: script = FindScript("ERP\intelligence\price_watch.py")
    If script = "" Then
        MsgBox "price_watch.py not found — check Engine_test repo path.", vbExclamation, "Price Watch"
        Exit Sub
    End If

    If MsgBox("Run Price Watch scan?" & vbCrLf & _
              "(File will close, run, reopen — takes ~10-30s)", _
              vbYesNo + vbQuestion, "Price Watch") = vbNo Then Exit Sub

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "price_watch_log.txt"

    Call EnsureFileClosedThenReopen(fullPath, "Price Watch")
    Dim rc As Long: rc = RunPythonHidden(script, "--erp """ & fullPath & """", logFile)
    Call ReopenWorkbook(fullPath)

    If rc <> 0 Then
        MsgBox "Price Watch failed (exit " & rc & "):" & vbCrLf & vbCrLf & _
               ReadLog(logFile, 20), vbExclamation, "Price Watch"
        Exit Sub
    End If

    Dim log As String: log = ReadLog(logFile, 12)
    Call MsgBoxOrSilent("Price Watch complete." & vbCrLf & vbCrLf & log & _
           vbCrLf & "See 'Price_Watch' sheet for alerts.", vbInformation, "Price Watch")

    ' Jump to alerts sheet if any
    On Error Resume Next
    If ThisWorkbook.Worksheets("Price_Watch").Cells(4, 1).Value <> "" Then
        ThisWorkbook.Worksheets("Price_Watch").Activate
    End If
    On Error GoTo 0
    Exit Sub

ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "Price Watch error: " & Err.Description, vbCritical, "Price Watch"
End Sub

' ============================================================
'  BUTTON: TRACKING SYNC
' ============================================================
Public Sub OnAction_TrackingSync(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim script As String: script = FindScript("ERP\jobs\shipment_tracker.py")
    If script = "" Then
        MsgBox "shipment_tracker.py not found.", vbExclamation, "Tracking Sync"
        Exit Sub
    End If

    If MsgBox("Tracking Sync — tính lại 7 stages (BKG->Confirmed->...->Delivered)" & vbCrLf & _
              "cho mọi Active Job từ ETD/ATA/Status/SI_Received." & vbCrLf & vbCrLf & _
              "File sẽ đóng ~15s rồi tự mở lại. Tiếp tục?", _
              vbYesNo + vbQuestion, "Tracking Sync") = vbNo Then Exit Sub

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "tracking_log.txt"

    Call EnsureFileClosedThenReopen(fullPath, "Tracking Sync")
    Dim rc As Long: rc = RunPythonHidden(script, "--erp """ & fullPath & """", logFile)
    Call ReopenWorkbook(fullPath)

    If rc <> 0 Then
        MsgBox "Tracking Sync failed:" & vbCrLf & ReadLog(logFile, 15), vbExclamation, "Tracking Sync"
        Exit Sub
    End If

    Call MsgBoxOrSilent("Shipment stages synced." & vbCrLf & vbCrLf & _
           ReadLog(logFile, 12), vbInformation, "Tracking Sync")
    Exit Sub

ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "Tracking Sync error: " & Err.Description, vbCritical, "Tracking Sync"
End Sub

' ============================================================
'  BUTTON: RELEASE ALERTS (2h countdown)
' ============================================================
Public Sub OnAction_ReleaseAlert(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim script As String: script = FindScript("ERP\jobs\release_alerts.py")
    If script = "" Then
        MsgBox "release_alerts.py not found.", vbExclamation, "Release Alert"
        Exit Sub
    End If

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "release_log.txt"

    Call EnsureFileClosedThenReopen(fullPath, "Release Alert")
    Dim rc As Long: rc = RunPythonHidden(script, "--erp """ & fullPath & """", logFile)
    Call ReopenWorkbook(fullPath)

    Dim hasUrgent As Boolean: hasUrgent = (rc = 1)
    If rc < 0 Or rc > 1 Then
        MsgBox "Release Alerts failed:" & vbCrLf & ReadLog(logFile, 15), _
               vbExclamation, "Release Alert"
        Exit Sub
    End If

    Dim log As String: log = ReadLog(logFile, 20)
    If hasUrgent Then
        MsgBox "URGENT release alerts pending!" & vbCrLf & vbCrLf & log, _
               vbExclamation, "Release Alert — ACTION NEEDED"
        On Error Resume Next
        ThisWorkbook.Worksheets("Release_Alerts").Activate
        On Error GoTo 0
    Else
        Call MsgBoxOrSilent("Release alerts refreshed." & vbCrLf & vbCrLf & log, _
               vbInformation, "Release Alert")
    End If
    Exit Sub

ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "Release Alert error: " & Err.Description, vbCritical, "Release Alert"
End Sub

' ============================================================
'  BUTTON: ENRICH EMAIL LINKS (booking mailto)
' ============================================================
Public Sub OnAction_EnrichEmail(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim script As String: script = FindScript("ERP\jobs\enrichment.py")
    If script = "" Then
        MsgBox "enrichment.py not found.", vbExclamation, "Enrich Email"
        Exit Sub
    End If

    Dim force As VbMsgBoxResult
    force = MsgBox("Overwrite existing email links?" & vbCrLf & _
                   "Yes = refresh all rows | No = only fill missing", _
                   vbYesNoCancel + vbQuestion, "Enrich Email Links")
    If force = vbCancel Then Exit Sub

    Dim args As String: args = "--erp """ & ThisWorkbook.FullName & """"
    If force = vbYes Then args = args & " --force"

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "enrich_log.txt"

    Call EnsureFileClosedThenReopen(fullPath, "Enrich Email")
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    Call ReopenWorkbook(fullPath)

    If rc <> 0 Then
        MsgBox "Enrich failed:" & vbCrLf & ReadLog(logFile, 15), vbExclamation, "Enrich Email"
        Exit Sub
    End If
    Call MsgBoxOrSilent("Email links updated." & vbCrLf & vbCrLf & _
           ReadLog(logFile, 10), vbInformation, "Enrich Email")
    Exit Sub

ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "Enrich error: " & Err.Description, vbCritical, "Enrich Email"
End Sub

' ============================================================
'  BUTTON: MONTHLY REPORT v4 (24-col Nelson template)
' ============================================================
Public Sub OnAction_MonthlyReportV4(control As IRibbonControl)
    On Error GoTo ErrHandler

    Dim script As String: script = FindScript("ERP\intelligence\monthly_report.py")
    If script = "" Then
        MsgBox "monthly_report.py not found.", vbExclamation, "Monthly Report"
        Exit Sub
    End If

    Dim monthInput As String
    monthInput = InputBox("Which month? (YYYY-MM or 'APR-2026'; leave blank = current)", _
                          "Monthly Report v4", "")

    Dim args As String: args = "--erp """ & ThisWorkbook.FullName & """"
    If Trim(monthInput) <> "" Then args = args & " --month """ & monthInput & """"

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "monthly_log.txt"

    ' monthly_report reads read-only — no need to close ERP
    Application.StatusBar = "Building monthly report..."
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    Application.StatusBar = False

    Dim log As String: log = ReadLog(logFile, 15)
    If rc <> 0 Then
        MsgBox "Monthly Report failed:" & vbCrLf & log, vbExclamation, "Monthly Report"
        Exit Sub
    End If

    ' Parse output path from log (last line starting with "-> ")
    Dim lines() As String: lines = Split(log, vbCrLf)
    Dim outPath As String, i As Long
    For i = UBound(lines) To 0 Step -1
        If InStr(lines(i), "->") > 0 And InStr(lines(i), ".xlsx") > 0 Then
            outPath = Trim(Mid(lines(i), InStr(lines(i), "->") + 2))
            Exit For
        End If
    Next i

    Dim openIt As VbMsgBoxResult
    openIt = MsgBox("Monthly Report built." & vbCrLf & vbCrLf & log & vbCrLf & _
                    "Open the file now?", vbYesNo + vbInformation, "Monthly Report")
    If openIt = vbYes And outPath <> "" Then
        On Error Resume Next
        Workbooks.Open outPath
        On Error GoTo 0
    End If
    Exit Sub

ErrHandler:
    Application.StatusBar = False
    MsgBox "Monthly Report error: " & Err.Description, vbCritical, "Monthly Report"
End Sub

' ============================================================
'  BUTTON: TRANSIT TIME AUTO-CALCULATOR (F9)
' ============================================================
Public Sub OnAction_TransitTime(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim script As String: script = FindScript("ERP\jobs\transit_time.py")
    If script = "" Then MsgBox "transit_time.py not found.", vbExclamation, "Transit Time": Exit Sub

    Dim mode As VbMsgBoxResult
    mode = MsgBox("Overwrite existing ETA values?" & vbCrLf & _
                  "Yes = replace all | No = fill missing only", _
                  vbYesNoCancel + vbQuestion, "Transit Time")
    If mode = vbCancel Then Exit Sub
    Dim args As String: args = "--erp """ & ThisWorkbook.FullName & """"
    If mode = vbYes Then args = args & " --overwrite"

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "transit_log.txt"
    Call EnsureFileClosedThenReopen(fullPath, "Transit Time")
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    Call ReopenWorkbook(fullPath)
    If rc <> 0 Then
        MsgBox "Transit Time failed:" & vbCrLf & ReadLog(logFile, 15), vbExclamation, "Transit Time"
        Exit Sub
    End If
    Call MsgBoxOrSilent("Transit ETA computed." & vbCrLf & vbCrLf & _
           ReadLog(logFile, 15), vbInformation, "Transit Time")
    Exit Sub
ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "Transit Time error: " & Err.Description, vbCritical, "Transit Time"
End Sub

' ============================================================
'  BUTTON: WEEKLY REPORT (F6)
' ============================================================
Public Sub OnAction_WeeklyReport(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim script As String: script = FindScript("ERP\intelligence\weekly_report.py")
    If script = "" Then MsgBox "weekly_report.py not found.", vbExclamation, "Weekly Report": Exit Sub

    Dim weekInput As String
    weekInput = InputBox("Which week? (YYYY W## e.g. '2026 W16'; blank = current)", _
                         "Weekly Report", "")
    Dim args As String: args = "--erp """ & ThisWorkbook.FullName & """"
    If Trim(weekInput) <> "" Then
        Dim parts() As String: parts = Split(weekInput, " ")
        If UBound(parts) >= 1 Then
            Dim wk As String: wk = Replace(UCase(parts(1)), "W", "")
            args = args & " --year " & parts(0) & " --week " & wk
        End If
    End If

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "weekly_log.txt"
    Application.StatusBar = "Building weekly report..."
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    Application.StatusBar = False

    Dim log As String: log = ReadLog(logFile, 15)
    If rc <> 0 Then
        MsgBox "Weekly Report failed:" & vbCrLf & log, vbExclamation, "Weekly Report"
        Exit Sub
    End If

    ' Extract output path
    Dim lines() As String: lines = Split(log, vbCrLf)
    Dim outPath As String, i As Long
    For i = UBound(lines) To 0 Step -1
        If InStr(lines(i), "->") > 0 And InStr(lines(i), ".xlsx") > 0 Then
            outPath = Trim(Mid(lines(i), InStr(lines(i), "->") + 2)): Exit For
        End If
    Next i

    If MsgBox("Weekly Report built." & vbCrLf & vbCrLf & log & vbCrLf & _
              "Open the file now?", vbYesNo + vbInformation, "Weekly Report") = vbYes _
       And outPath <> "" Then
        On Error Resume Next
        Workbooks.Open outPath
        On Error GoTo 0
    End If
    Exit Sub
ErrHandler:
    Application.StatusBar = False
    MsgBox "Weekly Report error: " & Err.Description, vbCritical, "Weekly Report"
End Sub

' ============================================================
'  BUTTON: YML EMAIL SCAN (F8)
' ============================================================
Public Sub OnAction_YmlScan(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim script As String: script = FindScript("ERP\jobs\yml_email_scan.py")
    If script = "" Then MsgBox "yml_email_scan.py not found.", vbExclamation, "YML Scan": Exit Sub

    Dim daysInput As String: daysInput = InputBox( _
        "Scan Outlook for YML tracking emails — how many days back?", _
        "YML Email Scan", "7")
    If Trim(daysInput) = "" Then Exit Sub
    If Not IsNumeric(daysInput) Then MsgBox "Not a number.", vbExclamation: Exit Sub

    Dim args As String
    args = "--erp """ & ThisWorkbook.FullName & """ --days " & CLng(daysInput)
    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "yml_scan_log.txt"

    Call EnsureFileClosedThenReopen(fullPath, "YML Scan")
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    Call ReopenWorkbook(fullPath)
    If rc <> 0 Then
        MsgBox "YML Scan failed:" & vbCrLf & ReadLog(logFile, 20), vbExclamation, "YML Scan"
        Exit Sub
    End If
    Call MsgBoxOrSilent("YML Scan complete." & vbCrLf & vbCrLf & _
           ReadLog(logFile, 15), vbInformation, "YML Scan")
    Exit Sub
ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "YML Scan error: " & Err.Description, vbCritical, "YML Scan"
End Sub

' ============================================================
'  BUTTON: FAST ID VALIDATOR (F4)
' ============================================================
Public Sub OnAction_FastIdCheck(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim script As String: script = FindScript("ERP\jobs\fast_id.py")
    If script = "" Then MsgBox "fast_id.py not found.", vbExclamation, "FAST ID": Exit Sub

    Dim mode As VbMsgBoxResult
    mode = MsgBox("Auto-normalize invalid FAST IDs?" & vbCrLf & _
                  "Yes = --fix (normalize + paint warnings) | No = --check only", _
                  vbYesNoCancel + vbQuestion, "FAST ID")
    If mode = vbCancel Then Exit Sub
    Dim args As String: args = "--erp """ & ThisWorkbook.FullName & """"
    If mode = vbYes Then args = args & " --fix" Else args = args & " --check"

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "fast_id_log.txt"

    If mode = vbYes Then Call EnsureFileClosedThenReopen(fullPath, "FAST ID Fix")
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    If mode = vbYes Then Call ReopenWorkbook(fullPath)

    If rc <> 0 Then
        MsgBox "FAST ID check failed:" & vbCrLf & ReadLog(logFile, 20), vbExclamation, "FAST ID"
        Exit Sub
    End If
    Call MsgBoxOrSilent("FAST ID " & IIf(mode = vbYes, "normalized", "checked") & "." & vbCrLf & vbCrLf & _
           ReadLog(logFile, 20), vbInformation, "FAST ID")
    Exit Sub
ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "FAST ID error: " & Err.Description, vbCritical, "FAST ID"
End Sub

' ============================================================
'  BUTTON: REEFER PLUG FEE (F7)
' ============================================================
Public Sub OnAction_ReeferPlug(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim script As String: script = FindScript("ERP\jobs\reefer_plug.py")
    If script = "" Then MsgBox "reefer_plug.py not found.", vbExclamation, "Reefer Plug": Exit Sub

    Dim writeNotes As VbMsgBoxResult
    writeNotes = MsgBox("Write optimal drop dates to Notes column?" & vbCrLf & _
                       "Yes = save to Active Jobs | No = preview only", _
                       vbYesNoCancel + vbQuestion, "Reefer Plug")
    If writeNotes = vbCancel Then Exit Sub
    Dim args As String: args = "--erp """ & ThisWorkbook.FullName & """"
    If writeNotes = vbYes Then args = args & " --write"

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "reefer_log.txt"

    If writeNotes = vbYes Then Call EnsureFileClosedThenReopen(fullPath, "Reefer Plug")
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    If writeNotes = vbYes Then Call ReopenWorkbook(fullPath)

    If rc <> 0 Then
        MsgBox "Reefer Plug failed:" & vbCrLf & ReadLog(logFile, 20), vbExclamation, "Reefer Plug"
        Exit Sub
    End If
    Call MsgBoxOrSilent("Reefer Plug scan complete." & vbCrLf & vbCrLf & _
           ReadLog(logFile, 25), vbInformation, "Reefer Plug")
    Exit Sub
ErrHandler:
    Application.Visible = True: Application.DisplayAlerts = True
    Application.ScreenUpdating = True: Application.StatusBar = False
    MsgBox "Reefer Plug error: " & Err.Description, vbCritical, "Reefer Plug"
End Sub

' ============================================================
'  BUTTON: ENRICH MONTHLY REPORT (F10 — Commission/Insurance)
' ============================================================
Public Sub OnAction_EnrichMonthly(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim script As String: script = FindScript("ERP\intelligence\enrich_monthly_report.py")
    If script = "" Then MsgBox "enrich_monthly_report.py not found.", vbExclamation, "Enrich Monthly": Exit Sub

    Dim xlsxPath As String
    xlsxPath = Application.GetOpenFilename("Excel Files,*.xlsx", Title:="Select monthly report to enrich")
    If xlsxPath = "False" Or xlsxPath = "" Then Exit Sub

    Dim args As String: args = """" & xlsxPath & """"
    Dim folder As String: folder = Left(ThisWorkbook.FullName, InStrRev(ThisWorkbook.FullName, "\"))
    Dim logFile As String: logFile = folder & "enrich_monthly_log.txt"
    Application.StatusBar = "Enriching monthly report with KICK BACK..."
    Dim rc As Long: rc = RunPythonHidden(script, args, logFile)
    Application.StatusBar = False

    If rc <> 0 Then
        MsgBox "Enrich Monthly failed:" & vbCrLf & ReadLog(logFile, 15), vbExclamation, "Enrich Monthly"
        Exit Sub
    End If
    Call MsgBoxOrSilent("Monthly report enriched with KICK BACK columns (Client/Carrier/Tax + Net Profit)." & _
           vbCrLf & vbCrLf & ReadLog(logFile, 15), vbInformation, "Enrich Monthly")
    Exit Sub
ErrHandler:
    Application.StatusBar = False
    MsgBox "Enrich Monthly error: " & Err.Description, vbCritical, "Enrich Monthly"
End Sub

' ============================================================
'  BUTTON: REFRESH ALL — one-click full pipeline
'  (rate_importer --import-pending  +  refresh-v14.py)
'  Nelson's request: 1 button instead of Desktop shortcut + Refresh Rates
' ============================================================
Public Sub OnAction_RefreshAll(control As IRibbonControl)
    ' 2026-04-17 FIX (Nelson): previous implementation called
    ' `ThisWorkbook.Close` then `wsh.Run("cmd /c chain.bat", 0, True)`.
    ' Excel aborts VBA execution when the host workbook closes itself,
    ' so `wsh.Run` never fired — chain bat never ran, log stayed stale,
    ' ribbon "Last refresh" label never updated. User bấm nút, file
    ' "saved" (from ThisWorkbook.Save), but Python pipeline was silent.
    '
    ' New flow:
    '   1. Launch async bootstrap bat BEFORE closing workbook.
    '   2. Bootstrap polls for xlsm file unlock, then runs chain,
    '      then reopens Excel (`start "" xlsm`).
    '   3. VBA just saves + closes; no post-close code needed.
    On Error GoTo ErrHandler

    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")

    Dim bootstrapBat As String: bootstrapBat = FindScript("scripts\refresh-all-bootstrap.bat")
    If bootstrapBat = "" Then
        MsgBox "scripts\refresh-all-bootstrap.bat not found — check Engine_test repo path.", _
               vbExclamation, "Refresh All"
        Exit Sub
    End If

    If MsgBox("Refresh All — full pipeline:" & vbCrLf & vbCrLf & _
              "  1. Scan Outlook + import pending rate files (~30-60s)" & vbCrLf & _
              "  2. Rebuild parquet (if new files)" & vbCrLf & _
              "  3. Pull into Pricing Dry/Reefer + RateVersions" & vbCrLf & vbCrLf & _
              "File will close, refresh runs in background, then Excel reopens. Continue?", _
              vbYesNo + vbQuestion, "Refresh All") = vbNo Then Exit Sub

    Dim fullPath As String: fullPath = ThisWorkbook.FullName
    Dim folder As String: folder = Left(fullPath, InStrRev(fullPath, "\"))
    Dim logFile As String: logFile = folder & "refresh_all_log.txt"

    ' Launch bootstrap via WMI Win32_Process.Create — this creates the
    ' process OUTSIDE Excel's Job Object, so it survives when Excel exits.
    ' VBA Shell() and wsh.Run() both put the child in Excel's job, which
    ' gets killed when Excel terminates (tested 2026-04-17: bootstrap never
    ' ran because Excel job cleanup killed it mid-poll).
    Dim bootCmd As String
    bootCmd = "cmd /c """"" & bootstrapBat & """ """ & fullPath & """ """ & logFile & """"""
    Dim wmi As Object
    Set wmi = GetObject("winmgmts:\\.\root\cimv2:Win32_Process")
    Dim procId As Variant
    Dim rcCreate As Long
    rcCreate = wmi.Create(bootCmd, Null, Null, procId)
    If rcCreate <> 0 Then
        Application.Visible = True
        MsgBox "Could not launch refresh bootstrap (WMI rc=" & rcCreate & ")." & vbCrLf & _
               "Check anti-virus / group policy for WMI access.", vbCritical, "Refresh All"
        Exit Sub
    End If

    ' Now save and close — bootstrap is already running and waiting.
    Application.StatusBar = "Refresh All: closing workbook (refresh runs in background)..."
    Application.DisplayAlerts = False
    ThisWorkbook.Save
    ThisWorkbook.Close SaveChanges:=False
    ' VBA terminates here; bootstrap takes over and reopens Excel when done.
    Exit Sub

ErrHandler:
    Application.DisplayAlerts = True
    Application.StatusBar = False
    MsgBox "Refresh All error: " & Err.Description, vbCritical, "Refresh All"
End Sub

' ============================================================
'  RIBBON CALLBACKS v5 — cmbMonth combo dropdown (2026-04-21)
'  Shows "APR 2026 (26 jobs)" per month, filters Active Jobs + Archive
'  Note: m_Months, m_MonthISO, m_MonthCount, m_SelectedMonthLabel
'        declared at TOP of module (gotcha #11, #12).
' ============================================================

' ── Internal: scan Active Jobs + Archive → build months list ──────────────
Public Sub RebuildMonthsList()
    ' Scans Active Jobs MONTH col (col 1) and Archive MONTH col (col 15).
    ' Builds m_Months() with display labels, m_MonthISO() with ISO codes.
    ' First item = "Tat ca (N jobs)" (show all). Sorted newest first.
    On Error GoTo ErrBuild

    Dim wsJ As Worksheet, wsA As Worksheet
    On Error Resume Next
    Set wsJ = ThisWorkbook.Worksheets("Active Jobs")
    Set wsA = ThisWorkbook.Worksheets("Archive")
    On Error GoTo ErrBuild

    ' Collect all ISO month values + counts into a scripting dictionary
    Dim dict As Object
    Set dict = CreateObject("Scripting.Dictionary")
    dict.CompareMode = 1  ' case-insensitive

    Dim totalJobs As Long: totalJobs = 0

    ' Active Jobs: col 1 = MONTH, data from row 8
    If Not wsJ Is Nothing Then
        Dim ajLast As Long: ajLast = wsJ.Cells(wsJ.Rows.Count, 1).End(xlUp).Row
        Dim ajRow As Long
        For ajRow = 8 To ajLast
            Dim ajMonth As String
            ajMonth = Trim(CStr(wsJ.Cells(ajRow, 1).Value))
            If ajMonth <> "" Then
                If Not dict.Exists(ajMonth) Then dict.Add ajMonth, 0
                dict(ajMonth) = dict(ajMonth) + 1
                totalJobs = totalJobs + 1
            End If
        Next ajRow
    End If

    ' Archive: col 15 = MONTH (added 2026-04-21), data from row 3
    If Not wsA Is Nothing Then
        Dim arcLast As Long: arcLast = wsA.Cells(wsA.Rows.Count, 6).End(xlUp).Row
        Dim arcRow As Long
        For arcRow = 3 To arcLast
            Dim arcMonth As String
            arcMonth = Trim(CStr(wsA.Cells(arcRow, 15).Value))
            If arcMonth <> "" Then
                If Not dict.Exists(arcMonth) Then dict.Add arcMonth, 0
                dict(arcMonth) = dict(arcMonth) + 1
                totalJobs = totalJobs + 1
            End If
        Next arcRow
    End If

    ' Sort keys newest first (ISO format "APR-26" — sort by year then month)
    Dim keys() As Variant: keys = dict.Keys
    Dim nKeys As Long: nKeys = dict.Count

    ' Simple bubble sort: convert "MMM-YY" to sortable "YYMM" integer
    Dim i As Long, j As Long, tmp As Variant
    For i = 0 To nKeys - 2
        For j = i + 1 To nKeys - 1
            If MonthSortKey(CStr(keys(i))) < MonthSortKey(CStr(keys(j))) Then
                tmp = keys(i): keys(i) = keys(j): keys(j) = tmp
            End If
        Next j
    Next i

    ' Allocate arrays: nKeys items + 1 for "All" entry at position 0
    Dim total As Long: total = nKeys + 1
    ReDim m_Months(0 To total - 1)
    ReDim m_MonthISO(0 To total - 1)

    ' Item 0 = "Tat ca" (show all)
    m_Months(0) = "Tat ca (" & totalJobs & " jobs)"
    m_MonthISO(0) = ""  ' empty = no filter

    For i = 0 To nKeys - 1
        Dim isoKey As String: isoKey = CStr(keys(i))
        Dim cnt As Long: cnt = CLng(dict(isoKey))
        Dim displayYear As String
        ' Convert "APR-26" -> "APR 2026 (N jobs)"
        displayYear = MonthISOToDisplay(isoKey) & " (" & cnt & " jobs)"
        m_Months(i + 1) = displayYear
        m_MonthISO(i + 1) = isoKey
    Next i

    m_MonthCount = total

    ' Default selection = current month if present, else "All"
    If m_SelectedMonthLabel = "" Then
        Dim curISO As String: curISO = UCase(Format(Date, "mmm-yy"))
        Dim k As Long
        For k = 1 To m_MonthCount - 1
            If m_MonthISO(k) = curISO Then
                m_SelectedMonthLabel = m_Months(k)
                Exit For
            End If
        Next k
        If m_SelectedMonthLabel = "" Then m_SelectedMonthLabel = m_Months(0)
    End If
    Exit Sub

ErrBuild:
    ' Fallback: single "All" entry so combo doesn't crash
    ReDim m_Months(0 To 0)
    ReDim m_MonthISO(0 To 0)
    m_Months(0) = "Tat ca"
    m_MonthISO(0) = ""
    m_MonthCount = 1
    m_SelectedMonthLabel = m_Months(0)
End Sub

Private Function MonthSortKey(isoLabel As String) As Long
    ' "APR-26" -> 2604 (sortable integer, higher = newer)
    ' Handles "APR-26" format (MMM-YY)
    On Error Resume Next
    If Len(isoLabel) < 5 Then MonthSortKey = 0: Exit Function
    Dim parts() As String: parts = Split(isoLabel, "-")
    If UBound(parts) < 1 Then MonthSortKey = 0: Exit Function
    Dim yy As Long: yy = Val(parts(1))
    Dim mm As Long: mm = Month(DateValue("1 " & parts(0) & " 2000"))
    If mm = 0 Then mm = 1
    MonthSortKey = yy * 100 + mm
End Function

Private Function MonthISOToDisplay(isoLabel As String) As String
    ' "APR-26" -> "APR 2026"
    On Error Resume Next
    If Len(isoLabel) < 5 Then MonthISOToDisplay = isoLabel: Exit Function
    Dim parts() As String: parts = Split(isoLabel, "-")
    If UBound(parts) < 1 Then MonthISOToDisplay = isoLabel: Exit Function
    Dim yy As Long: yy = Val(parts(1))
    Dim fullYear As Long
    If yy >= 0 And yy <= 99 Then fullYear = 2000 + yy Else fullYear = yy
    MonthISOToDisplay = UCase(parts(0)) & " " & fullYear
End Function

Private Sub EnsureMonthsLoaded()
    If m_MonthCount = 0 Then RebuildMonthsList
End Sub

' ── Ribbon combo callbacks (registered in CustomUI_v14.xml) ──────────────

Public Sub GetItemCount_Month(control As IRibbonControl, ByRef count As Variant)
    EnsureMonthsLoaded
    count = m_MonthCount
End Sub

Public Sub GetItemLabel_Month(control As IRibbonControl, index As Long, ByRef label As Variant)
    EnsureMonthsLoaded
    If index >= 0 And index < m_MonthCount Then
        label = m_Months(index)
    Else
        label = ""
    End If
End Sub

Public Sub GetText_Month(control As IRibbonControl, ByRef text As Variant)
    EnsureMonthsLoaded
    text = m_SelectedMonthLabel
End Sub

Public Sub OnChange_Month(control As IRibbonControl, text As String)
    ' text = display label e.g. "APR 2026 (26 jobs)" or "Tat ca (174 jobs)"
    ' Find matching ISO key and apply AutoFilter to Active Jobs + Archive.
    On Error GoTo ErrChange

    EnsureMonthsLoaded
    m_SelectedMonthLabel = text

    ' Find ISO for this label
    Dim selISO As String: selISO = ""
    Dim i As Long
    For i = 0 To m_MonthCount - 1
        If m_Months(i) = text Then
            selISO = m_MonthISO(i)
            Exit For
        End If
    Next i
    ' If not found (user typed custom text), try direct ISO match
    If selISO = "" And text <> "" Then
        For i = 1 To m_MonthCount - 1
            If InStr(1, text, m_MonthISO(i), vbTextCompare) > 0 Then
                selISO = m_MonthISO(i): Exit For
            End If
        Next i
    End If

    ' Apply filter to Active Jobs (col 1 = MONTH)
    Dim wsJ As Worksheet
    On Error Resume Next
    Set wsJ = ThisWorkbook.Worksheets("Active Jobs")
    On Error GoTo ErrChange
    If Not wsJ Is Nothing Then
        If selISO = "" Then
            ' Show all
            wsJ.AutoFilterMode = False
        Else
            wsJ.Range("A7").AutoFilter Field:=1, Criteria1:=selISO
        End If
    End If

    ' Apply filter to Archive (col 15 = MONTH, relative to filtered range)
    Dim wsA As Worksheet
    On Error Resume Next
    Set wsA = ThisWorkbook.Worksheets("Archive")
    On Error GoTo ErrChange
    If Not wsA Is Nothing Then
        If selISO = "" Then
            wsA.AutoFilterMode = False
        Else
            ' Archive header at row 2; MONTH is col 15 = Field 15
            wsA.Range("A2").AutoFilter Field:=15, Criteria1:=selISO
        End If
    End If

    Exit Sub
ErrChange:
    ' Silent fail — filter not critical, don't interrupt user
    On Error Resume Next
    Application.StatusBar = False
End Sub

' ── DEPRECATED 2026-04-21 — replaced by cmbMonth combo ───────────────────
' Kept to avoid "Sub or Function not defined" if old ribbon binding is cached.
' Remove in next major VBA release after confirming cmbMonth is stable.

Private Function CurrentMonthISO() As String
    ' DEPRECATED 2026-04-21
    If m_CurrentMonth = "" Then m_CurrentMonth = Format(Date, "yyyy-mm")
    CurrentMonthISO = m_CurrentMonth
End Function

Private Function FormatMonthLabel(iso As String) As String
    ' DEPRECATED 2026-04-21
    If iso = "" Or InStr(iso, "-") = 0 Then
        FormatMonthLabel = UCase(Format(Date, "mmm yyyy")): Exit Function
    End If
    Dim parts() As String: parts = Split(iso, "-")
    Dim y As Long: y = CLng(parts(0))
    Dim m As Long: m = CLng(parts(1))
    FormatMonthLabel = UCase(Format(DateSerial(y, m, 1), "mmm yyyy"))
End Function

Public Sub GetLabel_CurrentMonth(control As IRibbonControl, ByRef label As Variant)
    ' DEPRECATED 2026-04-21 — XML no longer uses getLabel on month control.
    On Error Resume Next
    label = FormatMonthLabel(CurrentMonthISO())
    If Err.Number <> 0 Then label = "Thang hien tai"
    On Error GoTo 0
End Sub

Private Sub ShiftMonth(ByVal delta As Long)
    ' DEPRECATED 2026-04-21
    On Error Resume Next
    Dim iso As String: iso = m_CurrentMonth
    If Len(iso) < 7 Then iso = Format(Date, "yyyy-mm")
    Dim y As Long: y = Val(Left(iso, 4))
    Dim m As Long: m = Val(Mid(iso, 6, 2))
    If y = 0 Then y = Year(Date)
    If m = 0 Then m = Month(Date)
    m = m + delta
    Do While m < 1
        m = m + 12: y = y - 1
    Loop
    Do While m > 12
        m = m - 12: y = y + 1
    Loop
    m_CurrentMonth = y & "-" & Format(m, "00")
End Sub

Public Sub OnAction_MonthPrev(control As IRibbonControl)
    ' DEPRECATED 2026-04-21 — button removed from CustomUI_v14.xml.
    ' Stub kept in case old ribbon binding is cached; does nothing.
    On Error Resume Next
End Sub

Public Sub OnAction_MonthNext(control As IRibbonControl)
    ' DEPRECATED 2026-04-21 — button removed from CustomUI_v14.xml.
    On Error Resume Next
End Sub

Public Sub OnAction_MonthReset(control As IRibbonControl)
    ' DEPRECATED 2026-04-21 — button removed from CustomUI_v14.xml.
    On Error Resume Next
End Sub

' ── Tracking dots: colored per-character + hover tooltip ──
'   stage 1..7  = number of stages completed
'   partial     = True if stage is in-progress (adds ◐ amber after done dots)
Public Sub ApplyTrackingDots(targetCell As Range, ByVal stage As Long, _
                              Optional ByVal partial As Boolean = False)
    On Error Resume Next
    If stage < 0 Then stage = 0
    If stage > 7 Then stage = 7

    Dim done As Long: done = stage
    Dim partialCount As Long: partialCount = IIf(partial And stage < 7, 1, 0)
    Dim empty_ As Long: empty_ = 7 - done - partialCount
    If empty_ < 0 Then empty_ = 0

    ' Build 7-char string: ● (done) + ◐ (partial) + ○ (empty)
    Dim s As String
    s = String(done, ChrW(9679))        ' ●
    If partialCount > 0 Then s = s & ChrW(9680)   ' ◐
    s = s & String(empty_, ChrW(9675))  ' ○

    targetCell.Value = s
    targetCell.HorizontalAlignment = xlCenter
    targetCell.Font.Name = "Segoe UI"
    targetCell.Font.Size = 11

    ' Per-character color
    If done > 0 Then
        targetCell.Characters(Start:=1, Length:=done).Font.Color = RGB(34, 197, 94)    ' green
    End If
    If partialCount > 0 Then
        targetCell.Characters(Start:=done + 1, Length:=1).Font.Color = RGB(245, 158, 11)  ' amber
    End If
    If empty_ > 0 Then
        targetCell.Characters(Start:=done + partialCount + 1, Length:=empty_).Font.Color = RGB(200, 200, 200)  ' gray
    End If

    ' Hover tooltip (cell Comment) with stage names
    Dim stages(1 To 7) As String
    stages(1) = "BKG":      stages(2) = "Confirmed": stages(3) = "SI Cut"
    stages(4) = "Gate-in":  stages(5) = "ATD":       stages(6) = "ETA"
    stages(7) = "Delivered"
    Dim tooltip As String, i As Long
    For i = 1 To 7
        If i <= done Then
            tooltip = tooltip & ChrW(10003) & " " & stages(i)  ' ✓
        ElseIf i = done + 1 And partialCount > 0 Then
            tooltip = tooltip & ChrW(8987) & " " & stages(i) & " (pending)"  ' ⌛
        Else
            tooltip = tooltip & ChrW(9675) & " " & stages(i)   ' ○
        End If
        If i < 7 Then tooltip = tooltip & vbCrLf
    Next i
    targetCell.ClearComments
    targetCell.AddComment tooltip
    targetCell.Comment.Shape.TextFrame.AutoSize = True
End Sub

' ── Build mailto: hyperlink for booking request email ──
Public Sub ApplyBookingMailto(targetCell As Range, _
                                customer As String, pol As String, pod As String, _
                                place As String, carrier As String, contType As String, _
                                qty As Long, contract As String)
    On Error Resume Next
    Dim pol_full As String, gw As String, mt_pickup As String, full_return As String
    Select Case UCase(pol)
        Case "HPH": pol_full = "HAI PHONG, VN": gw = "17 TONS"
        Case "HCM": pol_full = "HO CHI MINH, VN": gw = "20 TONS"
                    mt_pickup = "ICD TANAMEXCO": full_return = "ICD TANAMEXCO"
        Case "DAD": pol_full = "DA NANG, VN": gw = "17 TONS"
        Case "VUT": pol_full = "VUNG TAU, VN": gw = "20 TONS"
                    mt_pickup = "ICD TANAMEXCO": full_return = "ICD TANAMEXCO"
        Case "UIH": pol_full = "QUI NHON, VN": gw = "17 TONS"
        Case Else:  pol_full = pol: gw = "17 TONS"
    End Select
    Dim contDisp As String
    Select Case UCase(contType)
        Case "20GP": contDisp = "20DC"
        Case "40GP": contDisp = "40DC"
        Case "40HC", "40HQ": contDisp = "40HC"
        Case "45HC", "45HQ": contDisp = "45HC"
        Case Else: contDisp = contType
    End Select
    Dim isSOC As Boolean: isSOC = InStr(UCase(contract), "SOC") > 0
    Dim isReefer As Boolean: isReefer = (contType = "20RF") Or (contType = "40RF")
    Dim carrierDisp As String: carrierDisp = carrier & IIf(isSOC, " SOC", "")

    Dim subj As String
    If place <> "" And place <> pod Then
        subj = customer & " BOOKING | " & pol & "-" & place & " VIA " & pod & _
               " | " & qty & "X" & contDisp & " | " & carrierDisp & " | NELSON"
    Else
        subj = customer & " BOOKING | " & pol & "-" & pod & _
               " | " & qty & "X" & contDisp & " | " & carrierDisp & " | NELSON"
    End If

    Dim body As String
    body = "Dear Mira Cus Team/Pudong," & vbCrLf & vbCrLf
    body = body & "Please help me release the booking as below info:" & vbCrLf
    body = body & "- Carrier: " & carrierDisp & vbCrLf
    body = body & "- Contract number: " & contract & vbCrLf
    body = body & "- NAC (if any): Actual NAC" & vbCrLf
    body = body & "- POL: " & pol_full & vbCrLf
    body = body & "- POD: " & pod & vbCrLf
    body = body & "- FND/DEL: " & place & vbCrLf
    body = body & "- ETD: " & vbCrLf
    body = body & "- CMD: " & vbCrLf
    body = body & "- HS code: " & vbCrLf
    body = body & "- Volume: " & qty & "X" & contDisp & vbCrLf
    body = body & "- Gross Weight per container (GW): " & gw & vbCrLf
    body = body & "- Stuffing place: WAREHOUSE" & vbCrLf
    If mt_pickup <> "" Then
        body = body & "- MT pick up: " & mt_pickup & vbCrLf
        body = body & "- Full return: " & full_return & vbCrLf
    End If
    body = body & "- Special Remark: HOT SHIPMENT, CONT SACH TOT" & vbCrLf
    If isReefer Then
        body = body & "- REEFER CONTAINER - Temperature: -18C | Ventilation: CLOSED | Humidity: NO" & vbCrLf
    End If
    body = body & vbCrLf & "With warmest regards,"

    ' URL-encode subject + body (manual — Excel's EncodeURL not always available)
    Dim mailtoStr As String
    mailtoStr = "mailto:cus_team@pudongprime.vn?subject=" & UrlEncodeStr(subj)
    mailtoStr = mailtoStr & "&body=" & UrlEncodeStr(body)

    ' Assign hyperlink (use simple "Send BKG" text — emoji hyperlinks can break)
    targetCell.Value = "Send BKG"
    targetCell.Hyperlinks.Delete
    targetCell.Hyperlinks.Add Anchor:=targetCell, Address:=mailtoStr, _
                               TextToDisplay:="Send BKG"
    targetCell.Font.Color = RGB(5, 99, 193)
    targetCell.Font.Underline = xlUnderlineStyleSingle
    targetCell.HorizontalAlignment = xlCenter
End Sub

' URL-encode — simple replace-based. Handles common special chars in
' mailto subject/body. Vietnamese diacritics pass through unescaped
' (Outlook / Windows shell handles them OK).
Private Function UrlEncodeStr(s As String) As String
    On Error Resume Next
    Dim r As String: r = s
    r = Replace(r, "%", "%25")   ' first, to avoid double-encoding
    r = Replace(r, " ", "%20")
    r = Replace(r, vbCrLf, "%0A")
    r = Replace(r, vbLf, "%0A")
    r = Replace(r, vbCr, "")
    r = Replace(r, vbTab, "%09")
    r = Replace(r, "&", "%26")
    r = Replace(r, "?", "%3F")
    r = Replace(r, "|", "%7C")
    r = Replace(r, "/", "%2F")
    r = Replace(r, "#", "%23")
    r = Replace(r, """", "%22")
    UrlEncodeStr = r
End Function

' ── Archive: move Delivered row to Archive sheet ──
Public Sub OnAction_ArchiveJob(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim wsJ As Worksheet, wsA As Worksheet
    Set wsJ = ThisWorkbook.Worksheets("Active Jobs")
    On Error Resume Next
    Set wsA = ThisWorkbook.Worksheets("Archive")
    On Error GoTo ErrHandler
    If wsJ Is Nothing Or wsA Is Nothing Then
        MsgBox "Cần có sheet 'Active Jobs' + 'Archive'", vbExclamation, "Archive"
        Exit Sub
    End If
    If ActiveSheet.Name <> wsJ.Name Then
        MsgBox "Đứng ở Active Jobs trước!", vbExclamation, "Archive"
        Exit Sub
    End If
    Dim r As Long: r = Selection.Row
    If r < 8 Then
        MsgBox "Chọn row Active Job (row 8+)", vbExclamation, "Archive"
        Exit Sub
    End If

    ' Archive cols: Job_ID, FAST_ID, CUSTOMER, POL-POD, CARRIER, Bkg_No, HBL_NO, Cont, Qty, Sell, Cost, Profit, Delivered_Date, Reason
    Dim ar As Long: ar = wsA.Cells(wsA.Rows.Count, 1).End(xlUp).Row + 1
    If ar < 3 Then ar = 3
    wsA.Cells(ar, 1).Value = wsJ.Cells(r, 3).Value     ' Job_ID
    wsA.Cells(ar, 2).Value = wsJ.Cells(r, 2).Value     ' FAST_ID
    wsA.Cells(ar, 3).Value = wsJ.Cells(r, 4).Value     ' CUSTOMER
    wsA.Cells(ar, 4).Value = wsJ.Cells(r, 5).Value     ' POL-POD
    wsA.Cells(ar, 5).Value = wsJ.Cells(r, 7).Value     ' CARRIER
    wsA.Cells(ar, 6).Value = wsJ.Cells(r, 8).Value     ' Bkg_No
    wsA.Cells(ar, 7).Value = wsJ.Cells(r, 9).Value     ' HBL_NO
    wsA.Cells(ar, 8).Value = wsJ.Cells(r, 10).Value    ' Container
    wsA.Cells(ar, 9).Value = wsJ.Cells(r, 11).Value    ' Qty
    wsA.Cells(ar, 10).Value = wsJ.Cells(r, 16).Value   ' SELL
    wsA.Cells(ar, 11).Value = wsJ.Cells(r, 17).Value   ' COST
    wsA.Cells(ar, 12).Value = wsJ.Cells(r, 18).Value   ' PROFIT
    wsA.Cells(ar, 13).Value = wsJ.Cells(r, 22).Value   ' ATA (hidden col 22)
    wsA.Cells(ar, 14).Value = "Delivered"              ' reason

    ' Clear source row (don't delete to preserve row numbering)
    wsJ.Rows(r).Delete Shift:=xlUp
    Call MsgBoxOrSilent("Archived to Archive sheet row " & ar, vbInformation, "Archive")
    Exit Sub
ErrHandler:
    MsgBox "Archive error: " & Err.Description, vbCritical, "Archive"
End Sub

' ============================================================
'  Helper: MsgBoxOrSilent  — matches ERPv14Core behavior
' ============================================================
Private Sub MsgBoxOrSilent(prompt As String, buttons As VbMsgBoxStyle, title As String)
    ' Defer to ERPv14Core.MsgBoxOrSilent if present, else MsgBox
    On Error Resume Next
    Application.Run "ERPv14Core.MsgBoxOrSilent", prompt, buttons, title
    If Err.Number <> 0 Then MsgBox prompt, buttons, title
    On Error GoTo 0
End Sub
