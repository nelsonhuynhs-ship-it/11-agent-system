# ERP v14 VBA — System Standards

**Last updated:** 2026-04-17
**Status:** 🔒 AUTHORITATIVE — mọi thay đổi ribbon/VBA PHẢI tuân thủ.

Tài liệu này ra đời sau incident 2026-04-17 khi ribbon "Refresh All/Rates" bấm mà Python không chạy do VBA launch pattern sai. Đọc TRƯỚC khi sửa bất kỳ ribbon callback nào.

---

## Canonical source of truth

| Artifact | Location | Owner |
|----------|----------|-------|
| Live xlsm | `D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm` | OneDrive |
| VBA `.bas` exports | `D:/OneDrive/NelsonData/erp/*.bas` | OneDrive (canonical) |
| CustomUI XML | `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` | OneDrive |
| refresh-v14.py | `D:/OneDrive/NelsonData/erp/refresh-v14.py` | OneDrive |
| Bootstrap bats | `{repo}/scripts/refresh-*-bootstrap.bat` | Git repo |
| Chain bat | `{repo}/scripts/refresh-all-chain.bat` | Git repo |
| Re-import tool | `{repo}/scripts/reimport-erp-vba-modules.py` | Git repo |

Mirror (backup) `.bas` trong repo tại `ERP/vba-v14-mirror/` — **không phải source of truth**, chỉ để peer review + khôi phục khi OneDrive mất file.

---

## RULE 1 — Không bao giờ dùng `Shell` hay `wsh.Run` để launch process sống sót qua Excel exit

**Sai:**
```vb
Shell "cmd /c mybat.bat", vbHide             ' ❌ bị kill cùng Excel
wsh.Run "cmd /c mybat.bat", 0, True           ' ❌ blocking + bị kill nếu workbook close
wsh.Run "cmd /c start "" mybat.bat", 0, False ' ❌ start /B vẫn trong Job Object
```

**Đúng (WMI detach):**
```vb
Dim bootCmd As String
bootCmd = "cmd /c """"" & batPath & """ """ & arg1 & """ """ & arg2 & """"""
Dim wmi As Object
Set wmi = GetObject("winmgmts:\\.\root\cimv2:Win32_Process")
Dim procId As Variant
Dim rcCreate As Long
rcCreate = wmi.Create(bootCmd, Null, Null, procId)
If rcCreate <> 0 Then
    MsgBox "WMI launch failed rc=" & rcCreate, vbCritical
    Exit Sub
End If
```

**Why:** Excel 2013+ gom tất cả child process vào Job Object với flag `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`. Khi Excel exit, Job Object đóng → child bị kill. `Shell`/`wsh.Run` đều tạo child thuộc job. **WMI Win32_Process.Create** tạo process qua WMI service → không thuộc job → sống sót.

Incident 2026-04-17: `Shell "cmd /c start "" /B bootstrap.bat ..."` cũng bị kill (vì `start ""` chỉ detach console window, không break khỏi job). Chỉ WMI mới detach thật sự.

---

## RULE 2 — Không bao giờ `ThisWorkbook.Close` rồi chạy code phía sau

**Sai:**
```vb
ThisWorkbook.Save
ThisWorkbook.Close SaveChanges:=False
Shell "cmd /c mybat.bat", vbHide    ' ❌ macro đã bị abort
MsgBox "Done"                        ' ❌ không hiển thị
```

**Đúng:**
```vb
' Launch WMI process FIRST (nó sẽ đợi xlsm unlock)
Set wmi = GetObject("winmgmts:\\.\root\cimv2:Win32_Process")
wmi.Create bootCmd, Null, Null, procId

' RỒI mới save + close
ThisWorkbook.Save
ThisWorkbook.Close SaveChanges:=False
' VBA exit tự nhiên — bootstrap đã chạy ngoài
```

**Why:** Excel forcibly terminate VBA execution khi host workbook close chính nó. Bất kỳ code nào sau `ThisWorkbook.Close` trong cùng module có thể không chạy.

---

## RULE 3 — Bootstrap bat phải poll xlsm file lock trước khi chạy Python

Python script (openpyxl) cần xlsm UNLOCK mới ghi được. Sau `ThisWorkbook.Close`, Windows có thể giữ lock thêm vài giây. Bootstrap PHẢI poll:

```bat
set "LOCKED=1"
for /L %%i in (1,1,60) do (
    if "!LOCKED!"=="1" (
        2>nul ( (call ) 9>>"%XLSM%" ) && set "LOCKED=0"
        if "!LOCKED!"=="1" ping -n 1 -w 500 127.0.0.1 >nul
    )
)
```

30s timeout (60 × 500ms) đủ cho Excel flush + OneDrive sync.

---

## RULE 4 — Bootstrap phải reopen xlsm qua `start "" "<xlsm>"` (file association)

**Đúng:**
```bat
start "" "%XLSM%"
```

→ Excel launch với file association như double-click desktop. VBA enable, ribbon normal.

**Sai:**
```bat
excel.exe "%XLSM%"           ' ❌ path phụ thuộc version
"%excel_com_path%" "%XLSM%"  ' ❌ fragile
```

---

## RULE 5 — VBA ribbon callback phải check tồn tại của bat file trước

Mọi callback gọi external script PHẢI dùng `FindScript(relPath)` helper (trong `erp-v14-jobs-automation.bas`). FindScript tìm trong 3 bases:
1. `D:\NELSON\2. Areas\Engine_test\`
2. `C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test\`
3. Relative to xlsm location `..\..\..\`

Nếu không tìm thấy → MsgBox rõ ràng + Exit Sub. Không được silent fail.

---

## RULE 6 — Mọi VBA module change phải qua re-import script

Workflow sửa .bas:
1. Edit `D:/OneDrive/NelsonData/erp/erp-v14-*.bas` (canonical)
2. Chạy `python scripts/reimport-erp-vba-modules.py` (requires Trust access VBA enabled)
3. Test trong Excel
4. Khi pass → commit .bas mirror vào repo `ERP/vba-v14-mirror/`

**KHÔNG** edit VBA trực tiếp trong Excel VBE rồi forget export. Sẽ mất code khi OneDrive sync conflict.

---

## RULE 7 — Prerequisite: "Trust access to the VBA project object model"

`reimport-erp-vba-modules.py` dùng `VBProject` COM access → yêu cầu Excel setting:

**File → Options → Trust Center → Trust Center Settings → Macro Settings → ENABLE "Trust access to the VBA project object model"**

One-time setup per machine.

---

## Checklist khi thêm ribbon button mới

- [ ] Add button vào `CustomUI_v14.xml` với `id=` và `onAction=OnAction_XXX`
- [ ] Viết `Sub OnAction_XXX(control As IRibbonControl)` trong đúng module
- [ ] Nếu cần chạy external script:
  - [ ] Tạo bootstrap bat trong `scripts/`
  - [ ] VBA dùng WMI Win32_Process.Create (RULE 1)
  - [ ] Launch WMI TRƯỚC `ThisWorkbook.Close` (RULE 2)
  - [ ] Bootstrap poll file lock (RULE 3)
  - [ ] Bootstrap reopen qua `start ""` (RULE 4)
- [ ] `FindScript` để resolve path (RULE 5)
- [ ] Run `scripts/reimport-erp-vba-modules.py` để inject vào xlsm
- [ ] Verify qua zipfile grep:
  ```bash
  python -c "import zipfile; vba = zipfile.ZipFile('.../ERP_Master_v14.xlsm').read('xl/vbaProject.bin'); print('Win32_Process:', vba.count(b'Win32_Process'))"
  ```
- [ ] Test trong Excel → check log file update + file reopen
- [ ] Commit `.bas` mirror + bootstrap bat + reimport script to git

---

## Incident log

**2026-04-17 — Refresh All/Rates không chạy Python**

Symptoms:
- Nelson bấm Refresh All 15:50 → xlsm modified nhưng log/status stale từ 15:40
- Ribbon label "Last refresh" không đổi
- Thử hàng chục lần, không lần nào work

Root cause:
1. `ThisWorkbook.Close SaveChanges:=False` terminate VBA macro
2. Code `wsh.Run "cmd /c chain.bat", 0, True` sau đó không chạy
3. Thử fix với `Shell "cmd /c start "" /B bootstrap.bat"` — vẫn fail vì child nằm trong Job Object của Excel, Excel exit → Windows kill child

Fix:
- `GetObject("winmgmts:").Create(cmd)` — WMI tạo process bên ngoài Job Object
- Bootstrap bat poll xlsm lock 30s, chạy chain, reopen Excel
- Re-import via `reimport-erp-vba-modules.py`

Verified:
- xlsm vbaProject.bin contains 4× `Win32_Process`, 2× `winmgmts`
- Nelson tested: ribbon label updated to current time ✓

---

## Related standards

- `docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md` — email send path
- `docs/CHARGE_NAME_SOURCE_OF_TRUTH.md` — rate charge mapping
- `docs/erp-v14-source-of-truth.md` — ERP v14 layout + files
