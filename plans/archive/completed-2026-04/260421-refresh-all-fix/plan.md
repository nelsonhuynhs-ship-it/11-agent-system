---
name: Refresh All Button — Reliability Fix
created: 2026-04-21
status: completed
shipped: 2026-04-21
note: URL bug fix (3rd recurrence) + defensive post-inject verification in customui_utils.py. Ribbon 2-tab fix also shipped.
effort: ~1h
owner: Nelson
priority: HIGH
---

# Plan — Refresh All Button Fix

## 🎯 Problem

Nút "Refresh All" trên ERP ribbon **chập chờn** dù Nelson dùng cùng 1 laptop (không phải PC Home vs Laptop VP như em nghĩ trước):
- Ở nhà: đôi lúc bấm work (refresh Python → reopen Excel)
- Ở công ty: đôi lúc bấm thì **tự mở file trên OneDrive Web** trong browser, không refresh gì cả

## 🔍 Root cause (certain)

`ThisWorkbook.FullName` trả về 2 loại path khác nhau tùy Excel đang mở file kiểu nào:

| Cách anh mở xlsm | FullName value | Refresh All |
|-----------------|----------------|-------------|
| File Explorer → double-click | `D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm` | ✅ Work |
| Desktop shortcut (local) | Local path | ✅ Work |
| Teams chat link → click | `https://...sharepoint.com/...` | ❌ Mở web |
| Outlook mail attachment (cloud) | `https://d.docs.live.net/...` | ❌ Mở web |
| Office 365 Recent Files "Cloud" pick | `https://...` | ❌ Mở web |
| AutoSave khôi phục sau crash | Có thể URL | ❌ Flaky |
| OneDrive "Files On-Demand" chưa download | URL (placeholder) | ❌ Flaky |

Bootstrap bat line 74 làm:
```bat
start "" "%XLSM%"
```
- Local path → Windows mở Excel ✅
- URL → Windows mở default browser (Edge/Chrome) → OneDrive Web ❌

**Log evidence:** `refresh_all_log.txt` chỉ có **1 entry thành công** trong tất cả lần Nelson bấm → các lần fail WMI không fire hoặc XLSM=URL.

## 📐 Solution — 3 layers

### Layer 1: URL detection + canonical fallback (file jobs-automation.bas)

```vba
' Top of module
Private Const CANONICAL_ERP_PATH As String = "D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"

Public Sub OnAction_RefreshAll(control As IRibbonControl)
    On Error GoTo ErrHandler
    Dim fso As Object: Set fso = CreateObject("Scripting.FileSystemObject")
    
    Dim rawPath As String: rawPath = ThisWorkbook.FullName
    Dim fullPath As String
    Dim isUrl As Boolean
    isUrl = (InStr(LCase(rawPath), "://") > 0) Or (Left(LCase(rawPath), 4) = "http")
    
    If isUrl Then
        ' File đang mở từ web/Teams — dùng canonical local path
        If Not fso.FileExists(CANONICAL_ERP_PATH) Then
            MsgBox "File đang mở từ OneDrive Web." & vbCrLf & vbCrLf & _
                   "Vui lòng:" & vbCrLf & _
                   "  1. Đóng file này (bản web)" & vbCrLf & _
                   "  2. Mở File Explorer" & vbCrLf & _
                   "  3. Đi tới: " & CANONICAL_ERP_PATH & vbCrLf & _
                   "  4. Double-click file để mở local" & vbCrLf & vbCrLf & _
                   "Refresh All chỉ hoạt động khi file mở từ local.", _
                   vbExclamation + vbOKOnly, "Refresh All — File mở sai cách"
            LogRefreshClick rawPath, "URL_BLOCKED", CANONICAL_ERP_PATH
            Exit Sub
        End If
        
        ' Warn + switch to local
        If MsgBox("Đang mở từ OneDrive Web. Hệ thống sẽ:" & vbCrLf & _
                  "  1. Đóng bản web" & vbCrLf & _
                  "  2. Mở bản local: " & CANONICAL_ERP_PATH & vbCrLf & _
                  "  3. Chạy refresh pipeline" & vbCrLf & vbCrLf & _
                  "Tiếp tục?", vbYesNo + vbQuestion, "Refresh All") = vbNo Then
            Exit Sub
        End If
        
        fullPath = CANONICAL_ERP_PATH
        LogRefreshClick rawPath, "URL_REDIRECTED", CANONICAL_ERP_PATH
    Else
        fullPath = rawPath
        LogRefreshClick rawPath, "LOCAL_OK", fullPath
    End If
    
    ' ... rest of original OnAction_RefreshAll logic (bootstrap spawn, save, close)
    ' Use `fullPath` (guaranteed local now) instead of rawPath
```

### Layer 2: Click logger (new helper sub)

```vba
Private Sub LogRefreshClick(rawPath As String, status As String, finalPath As String)
    On Error Resume Next
    Dim logPath As String: logPath = "D:\OneDrive\NelsonData\erp\refresh_all_log.txt"
    Dim ff As Integer: ff = FreeFile
    Open logPath For Append As #ff
    Print #ff, Format(Now, "yyyy-mm-dd hh:nn:ss") & " | CLICK | " & status & _
               " | raw=" & rawPath & " | final=" & finalPath
    Close #ff
End Sub
```

→ Mọi lần bấm đều có log, dù fail hay success. Dễ debug sau này.

### Layer 3: Bootstrap bat guard (file refresh-all-bootstrap.bat)

```bat
REM Add at top after "set XLSM=%~1":
echo %XLSM% | findstr /i /c:"http://" /c:"https://" >nul
if %ERRORLEVEL%==0 (
    echo [bootstrap] ERROR: XLSM is URL, not local path. Aborting. >> "%LOGF%"
    echo [bootstrap] XLSM=%XLSM% >> "%LOGF%"
    exit /b 10
)
```

→ Defense in depth: ngay cả khi VBA miss URL check, bootstrap cũng refuse.

## 🧪 Test plan

### Test case A — Local file (happy path)
1. Mở xlsm từ File Explorer
2. Bấm Refresh All
3. Expect: confirm dialog → save → close → bootstrap run → reopen local
4. Log có entry `LOCAL_OK`

### Test case B — Web/URL file
1. Click xlsm link trong Teams hoặc Outlook
2. Excel mở từ URL
3. Bấm Refresh All
4. Expect: warning dialog → confirm → close web version → bootstrap open local → refresh
5. Log có entry `URL_REDIRECTED`

### Test case C — Canonical file missing
1. Rename local xlsm tạm thời
2. Mở từ URL, bấm Refresh All
3. Expect: error dialog hướng dẫn, abort
4. Log có entry `URL_BLOCKED`

### Test case D — Multiple instances
1. Mở xlsm từ local (instance A)
2. Mở xlsm từ Teams URL (instance B)
3. Bấm Refresh All từ instance B
4. Expect: instance B detect URL, close, bootstrap open local → conflict với instance A?
5. → Cần bootstrap detect existing Excel process + skip reopen?

## 📂 Files to modify

| File | Change |
|------|--------|
| `D:/OneDrive/NelsonData/erp/erp-v14-jobs-automation.bas` | OnAction_RefreshAll + add LogRefreshClick helper |
| `ERP/vba-v14-mirror/erp-v14-jobs-automation.bas` | Same changes (git mirror) |
| `scripts/refresh-all-bootstrap.bat` | Add URL guard at top |
| `scripts/reimport-erp-vba-modules.py` | Run to load updated .bas into xlsm |

## 🚨 Risks

| Risk | Mitigation |
|------|-----------|
| Nelson có 2 Excel mở cùng lúc (web + local) | Bootstrap check duplicate instance, warn user |
| Canonical path khác (Nelson move file) | Config file `erp_config.json` với path override |
| User confirm dialog quá phiền | Silent redirect mode (no confirm) sau lần đầu |
| VBA log file conflict với Python writers | Separate log `refresh_click_log.txt` distinct từ `refresh_all_log.txt` |

## 🎯 Success criteria

- [ ] Test A pass — local flow không thay đổi
- [ ] Test B pass — URL flow tự redirect local, refresh work
- [ ] Test C pass — missing file → clear error
- [ ] Log có entry cho MỌI button click (success/fail)
- [ ] 1 tuần sau deploy: 0 Nelson complain "Refresh All không work"

## 📝 Out of scope

- Không thay đổi Python refresh pipeline (refresh-v14.py) — đang work
- Không thay đổi bootstrap chain logic (chỉ add URL guard)
- Không auto-close other Excel instances (user responsibility)
- Không cache parquet hoặc optimize pipeline speed (separate task)

## 🚦 Rollout

1. Review plan (Nelson)
2. Code fix in .bas file
3. Test locally (Nelson manual test A + B)
4. Reimport via `reimport-erp-vba-modules.py`
5. Git commit: `fix(erp): Refresh All handle URL path (OneDrive web/Teams)`
6. Monitor log 1 tuần
