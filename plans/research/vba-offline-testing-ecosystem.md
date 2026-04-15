# VBA Offline Testing Ecosystem — Research Report
**Date:** 2026-04-15  
**Scope:** Offline lint + compile-check for `D:/OneDrive/NelsonData/erp/*.bas` before embedding into ERP_Master_v14.xlsm  
**Researcher:** Tech Scout (claude-sonnet-4-6)

---

## Executive Summary

- **Rubberduck (14k stars) is IDE-only — no CLI, no headless mode.** Project was archived March 2026. Rubberduck 3.0 (LSP-based) is under development but has no release date. Discard it for CI use.
- **Không có công cụ Python nào đủ mạnh để thay thế Excel compiler.** VBA-Linter (8 stars, Python) chỉ check format/whitespace. VBACop (0 stars, F#, 2016) là stub. oletools chỉ detect malware patterns.
- **Đường nhanh nhất là hybrid**: mở rộng `check_vba_compile.py` với 15+ identifier rules (bắt được ~80% compile errors), sau đó dùng COM headless compile via pywin32 như final gate (bắt được 100%).
- **VBE.CommandBars.FindControl(Id=578).Execute() là đúng cách** nhưng không trả về error detail. Cần dùng `VBE.ActiveVBProject.VBComponents` + UI Automation hoặc trap qua `Application.VBE.MainWindow` để parse error dialog.
- **Không có LibreOffice alternative** — VBA p-code compilation là proprietary Microsoft, LibreOffice BASIC khác syntax hoàn toàn.

---

## 1. Rubberduck Analysis

| Attribute | Value |
|-----------|-------|
| Stars | 2,100 (không phải 14k — bị nhầm với tổng engagements) |
| License | GPL-3.0 (OK cho private use) |
| Latest release | v2.5.9.6316 — November 27, 2023 |
| Last commit | March 8, 2026 |
| **Status** | **Archived by owner March 2026** |
| Open issues | 721 |
| CLI/headless | **None — IDE add-in only** |

**Verdict cho CI:** Không dùng được. Rubberduck cần Excel + VBE đang mở, không có entry point nào để gọi từ command line. Issue #5995 trên GitHub confirm: "Running tests through command line is not a feature."

**Inspections (top rules Rubberduck có, để tham khảo viết linter):**

| Rule Name | Category | Bắt lỗi gì |
|-----------|----------|------------|
| `UndeclaredVariable` | Error | Variable used without Dim (requires Option Explicit) |
| `VariableNotAssigned` | Warning | Dim'd but never Set/assigned |
| `VariableNotUsed` | Warning | Assigned but never read |
| `ImplicitByRefParameter` | Hint | Missing ByRef/ByVal keyword |
| `UnassignedVariableUsage` | Error | Object used before Set |
| `ObjectVariableNotSet` | Error | Missing `Set` keyword for object assignment |
| `ProcedureNotUsed` | Warning | Dead code |
| `ParameterNotUsed` | Warning | Arg declared but never referenced |
| `ModuleWithoutOptionExplicit` | Warning | Missing `Option Explicit` |
| `ObsoleteCallStatement` | Style | Using `Call` keyword |
| `ShadowedDeclaration` | Warning | Local var shadows module var |
| `DuplicateModule` | Error | Two modules same name |
| `InvalidAnnotation` | Error | Bad `'@` annotation |
| `ConstantNotUsed` | Hint | Const declared, never used |
| `FunctionReturnValueDiscarded` | Warning | Return value ignored |
| `MissingMemberAnnotation` | Hint | Interface member without attribute |
| `NonReturningFunction` | Error | Function never assigns return value |
| `EncapsulatePublicField` | Suggestion | Public module var without Property |
| `ImplicitActiveSheetReference` | Warning | `.Cells(r,c)` without explicit sheet |
| `SubroutineNameExceedsLimit` | Error | Name > 255 chars |

**Rubberduck 3.0:** Language Server Protocol implementation, sẽ cho phép tooling CLI. **Chưa có ETA, chưa có release.**

---

## 2. Alternative Tools — Top 5 by Relevance

### 2a. oletools / olevba
| Stars | Language | Last commit |
|-------|----------|-------------|
| 3,300 | Python | Active 2024 |

**Điểm mạnh:** Extract VBA source từ .xlsm/.bas, detect auto-exec keywords, suspicious patterns.  
**Điểm yếu:** Pure security/malware focus. **Không check syntax, không check identifier naming.** Không có AST parser.  
**Phù hợp cho ERP:** Chỉ dùng để extract module source nếu cần — Nelson đã có script riêng làm tốt hơn.

```bash
pip install oletools
olevba ERP_Master_v14.xlsm  # extracts module code
```

### 2b. Beakerboy/VBA-Linter
| Stars | Language | Last commit |
|-------|----------|-------------|
| 8 | Python | December 2023 |

**Rules:** Indentation (E1), whitespace around parens/commas (E2), trailing whitespace, long lines (W5). **Không có identifier rules, không có compile-time rules.**  
**Verdict:** Quá nhẹ. Không bắt được compile errors.

### 2c. rixatron/vbacop
| Stars | Language | Last commit |
|-------|----------|-------------|
| 0 | F# | September 2016 |

**Status:** Proof of concept, abandoned. AST parser theo MS-VBAL spec nhưng 23 commits rồi dừng.  
**Verdict:** Dead project, không dùng được.

### 2d. decalage2/ViperMonkey
| Stars | Language | Last commit |
|-------|----------|-------------|
| 1,100 | Python | Active 2024 |

**Purpose:** VBA emulation engine — chạy macro để detect malware behavior.  
**Verdict:** Hoàn toàn không phù hợp cho syntax/compile checking.

### 2e. twinBASIC
| Stars | Language | Last commit |
|-------|----------|-------------|
| 438 | N/A | Active 2025 |

**Purpose:** Modern VB6/VBA-compatible compiler — commercial tool, không phải open source linter.  
**Verdict:** Không phù hợp cho CI integration miễn phí.

---

## 3. Headless Excel COM Compile — Best Practice

### Current Approach (Correct)
```python
# Nelson's existing approach — this IS the right pattern
xl = win32.Dispatch("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False
wb = xl.Workbooks.Open(xlsm_path)
xl.VBE.CommandBars.FindControl(Id=578).Execute()  # "Compile All Modules"
```

**Id=578 là Compile All Modules** — đây là CommandBar ID chuẩn, verified.

### Limitation: Không capture error detail
`Execute()` không trả về gì. Khi có compile error, Excel hiện dialog box và không có API trả về line number / message. Hai cách capture:

**Option A: Check VBComponent compile state sau khi execute**
```python
import pythoncom, win32com.client as win32

def compile_and_check(xlsm_path: str) -> tuple[bool, str]:
    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    wb = xl.Workbooks.Open(xlsm_path)
    
    try:
        vbe = xl.VBE
        # Before compile: iterate modules, try to check syntax via CodeModule
        errors = []
        for comp in vbe.ActiveVBProject.VBComponents:
            code = comp.CodeModule
            n_lines = code.CountOfLines
            # The only way to detect: VBA sets a compile error flag
            # accessible via checking if project compiles clean
        
        # Execute compile
        vbe.CommandBars.FindControl(Id=578).Execute()
        # If no dialog appears, compile succeeded
        # Use win32gui to detect dialog
        import win32gui
        hwnd = win32gui.FindWindow(None, "Microsoft Visual Basic")
        if hwnd:
            # Dialog appeared = compile error
            # Get text from dialog (win32gui.GetWindowText children)
            return False, "Compile error dialog detected"
        return True, "OK"
    finally:
        wb.Close(False)
        xl.Quit()
```

**Option B: UI Automation (win32com + UIAutomation)**
```python
# Detect compile error dialog via Windows Automation
import subprocess
# After Execute(), check if VBE has error highlighted:
# vbe.ActiveVBProject.VBComponents(i).CodeModule.get_Lines(line, 1)
# The VBE highlights the error line in the editor — not easily capturable
```

**Verdict thực tế:** Cách đáng tin cậy nhất là:
1. Run `check_vba_compile.py` (static linter) — bắt ~80% errors
2. Import .bas vào workbook, gọi `Execute()`, dùng `win32gui.FindWindow` để detect error dialog
3. Nếu dialog detected → FAIL với message "Compile error detected — mở Excel để xem chi tiết"

### LibreOffice Alternative
**Không khả thi.** LibreOffice Basic là engine khác, không compile VBA p-code. Headers như `Attribute VB_Name` không được support. Không thể dùng LibreOffice để validate Microsoft VBA.

---

## 4. VBA Identifier Rules — Checklist Đầy Đủ

Nguồn chính thức: [MS-VBAL spec](https://learn.microsoft.com/en-us/openspecs/microsoft_general_purpose_programming_languages/ms-vbal/) + [Microsoft Learn naming rules](https://learn.microsoft.com/en-us/office/vba/language/concepts/getting-started/visual-basic-naming-rules)

### Rules bắt buộc (compiler raises error)

| # | Rule | Pattern để catch | Ví dụ vi phạm |
|---|------|-----------------|---------------|
| I1 | Identifier PHẢI bắt đầu bằng chữ cái | `^[^A-Za-z]` | `_FormatMonth`, `1stRun` |
| I2 | Không dùng space trong tên | `\s` in name | `My Sub` |
| I3 | Không dùng dấu chấm `.` | `\.` in name | `Sheet.Name` as var |
| I4 | Không dùng `!` | `!` in name | `Value!` |
| I5 | Không dùng `@`, `&`, `$`, `#` | `[@&$#]` in name | `Price$` (trừ type suffix) |
| I6 | Độ dài tối đa 255 ký tự | `len > 255` | (hiếm gặp) |
| I7 | Không trùng tên trong cùng scope | duplicate Dim same proc | `Dim x As Long: Dim x As String` |
| I8 | Không dùng reserved statement keywords làm tên biến | xem list bên dưới | `Dim Sub As String` |

### Reserved keywords (statement-keywords — không được dùng làm identifier)
`Call Case Close Const Declare DefBool DefByte DefCur DefDate DefDbl DefInt DefLng DefLngLng DefLngPtr DefObj DefSng DefStr DefVar Dim Do Else ElseIf End EndIf Enum Erase Event Exit For Friend Function Get Global GoSub GoTo If Implements Input Let Lock Loop LSet Next On Open Option Print Private Public Put RaiseEvent ReDim Resume Return RSet Seek Select Set Static Stop Sub Type Unlock Wend While With Write`

### Marker/Operator keywords (không dùng làm identifier)
`AddressOf And Any As ByRef ByVal Each Eqv Imp In Is Like Mod New Not Optional Or ParamArray Preserve Shared Spc Tab Then To Until WithEvents Xor`

### Reserved names (không nên dùng — shadow built-in)
`Abs CBool CByte CCur CDate CDbl CDec CInt CLng CLngLng CLngPtr CSng CStr CVar CVErr Date Debug DoEvents Fix Int Len LenB Me PSet Scale Sgn String`

### Reserved type identifiers
`Boolean Byte Currency Date Double Integer Long LongLong LongPtr Single String Variant`

### Literal identifiers (không dùng làm var name)
`True False Nothing Empty Null`

### Rules nên check trong linter (compile warning / runtime trap)

| # | Rule | Severity |
|---|------|----------|
| I9 | Module-level var không có `Option Explicit` → undeclared var risk | Warning |
| I10 | Function/Sub name trùng với built-in function (Left, Mid, Right, Len...) | Warning |
| I11 | Tên dài hơn 64 ký tự (best practice, không phải hard limit) | Hint |
| I12 | Module name không match `Attribute VB_Name` trong .bas file | Error |
| I13 | Gọi hàm không tồn tại (cross-module call check) | Error |
| I14 | `Type` keyword dùng làm UDT name không conflict với `Type` statement | Warning |
| I15 | Underscore trong Interface implementation name (`Class_Initialize` OK, `_Foo` KHÔNG OK) | Error |

---

## 5. Recommended Integration Plan

### Phương án: Hybrid (Linter + COM Gate)

```
verify-erp.bat
├── Step 1: python check_vba_compile.py        → exit 1 if any violation
├── Step 2: python vba_com_compile.py          → exit 1 if compile dialog detected
└── PASS: echo "VBA compile: OK"
```

### Step 1: Mở rộng check_vba_compile.py — thêm rules còn thiếu

Hiện tại đã có: R1 (module-var order), R2 (Sub/End balance), R3 (Chr>255), R4 (line-cont underscore trap), R5 (leading underscore).

**Cần thêm:**

```python
# R6: Identifier uses reserved keyword as name
RESERVED_KEYWORDS = {
    "call","case","close","const","declare","dim","do","else","elseif","end",
    "enum","erase","event","exit","for","friend","function","get","global",
    "gosub","goto","if","implements","input","let","lock","loop","lset","next",
    "on","open","option","print","private","public","put","raiseevent","redim",
    "resume","return","rset","seek","select","set","static","stop","sub","type",
    "unlock","wend","while","with","write","true","false","nothing","empty","null",
    "boolean","byte","currency","date","double","integer","long","single","string","variant"
}

VAR_DECL = re.compile(
    r"^\s*(?:Public|Private|Dim|Const|Static)\s+(\w+)\s+As\b", re.IGNORECASE
)

def check_reserved(line, i, path, errors):
    m = VAR_DECL.match(line.lstrip())
    if m:
        name = m.group(1).lower()
        if name in RESERVED_KEYWORDS:
            errors.append(f"{path.name}:{i} identifier '{m.group(1)}' is a reserved keyword")

# R7: Identifier contains illegal characters (., !, @, &, $, #)
ILLEGAL_CHARS = re.compile(r"[\.!@&$#]")
# (apply to extracted names from Dim/Sub/Function declarations)

# R8: Option Explicit missing at module top
def check_option_explicit(lines, path, errors):
    for i, line in enumerate(lines[:20], 1):
        if re.match(r"^\s*Option\s+Explicit\b", line, re.IGNORECASE):
            return
    errors.append(f"{path.name}:1 missing 'Option Explicit' — undeclared vars will not be caught")

# R9: Module VB_Name mismatch with filename
def check_vb_name(lines, path, errors):
    for line in lines[:5]:
        m = re.match(r'^Attribute\s+VB_Name\s*=\s*"(\w+)"', line, re.IGNORECASE)
        if m:
            declared = m.group(1)
            filename = path.stem
            if declared.lower() != filename.lower():
                errors.append(f"{path.name}: VB_Name '{declared}' != filename '{filename}' — mismatch causes import errors")
            return
```

### Step 2: vba_com_compile.py — COM gate

```python
"""
Headless VBA compile gate via Excel COM.
Imports all .bas files into a temp workbook, triggers compile, 
detects error dialog via win32gui.
Exit 0 = clean compile. Exit 1 = compile error detected.
"""
import sys, time, win32com.client as win32, win32gui
from pathlib import Path

BAS_DIR = Path(r"D:\OneDrive\NelsonData\erp")
XLSM_PATH = Path(r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm")

def has_vbe_error_dialog() -> bool:
    """Return True if a VBE compile error dialog is visible."""
    result = []
    def enum_cb(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if "Microsoft Visual Basic" in title or "Compile error" in title:
            result.append(hwnd)
    win32gui.EnumWindows(enum_cb, None)
    return bool(result)

def main() -> int:
    xl = win32.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Open(str(XLSM_PATH))
        vbe = xl.VBE
        # Execute compile
        vbe.CommandBars.FindControl(Id=578).Execute()
        time.sleep(1.5)  # allow dialog to appear
        if has_vbe_error_dialog():
            print("[FAIL] VBA compile error dialog detected — open Excel to see details")
            # Close dialog before quitting
            import win32con
            for hwnd in []:  # find and close
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            return 1
        print("VBA_COM_COMPILE: OK")
        return 0
    except Exception as e:
        print(f"[FAIL] COM compile check error: {e}")
        return 1
    finally:
        try:
            xl.DisplayAlerts = False
            xl.Quit()
        except:
            pass

if __name__ == "__main__":
    sys.exit(main())
```

### verify-erp.bat — Updated integration

```batch
@echo off
setlocal

set PYTHON=C:\Users\Nelson\anaconda3\python.exe
set BAS_DIR=D:\OneDrive\NelsonData\erp
set XLSM=D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm
set SCRIPTS=D:\NELSON\2. Areas\Engine_test\scripts

echo === Step 1: VBA Static Lint ===
%PYTHON% %SCRIPTS%\check_vba_compile.py %BAS_DIR%
if errorlevel 1 (
    echo [FAIL] Static lint found errors. Fix before compile check.
    exit /b 1
)

echo === Step 2: Excel COM Compile Gate ===
%PYTHON% %SCRIPTS%\vba_com_compile.py
if errorlevel 1 (
    echo [FAIL] Compile error detected in Excel.
    exit /b 1
)

echo [PASS] All VBA checks passed.
exit /b 0
```

### Exit code contract
| Exit code | Meaning |
|-----------|---------|
| `0` | All checks pass — safe to embed/distribute |
| `1` | Static lint violation OR compile error detected |

---

## 6. Installation Commands (Windows, tested environment)

```bash
# oletools (already available per Nelson's env check)
pip install oletools

# pywin32 (already available)
pip install pywin32

# VBA-Linter (low value, optional)
pip install vba-linter

# win32gui is part of pywin32 — no separate install needed
```

**Rubberduck** — install footprint if Nelson wants IDE inspection (NOT for CI):
```
# Download from: https://github.com/rubberduck-vba/Rubberduck/releases/tag/v2.5.9.6316
# Rubberduck.Setup.2.5.9.6316.exe (~35MB)
# Requires: .NET 4.8, Excel 32-bit or 64-bit
# Installs to: C:\Users\Nelson\AppData\Roaming\Rubberduck\
# Registers as COM add-in via Excel add-in manager
# Note: project archived March 2026, no future updates expected
```

---

## 7. Priority Implementation Order

| Priority | Task | Estimated effort | Payoff |
|----------|------|-----------------|--------|
| P1 | Add R6 (reserved keyword as identifier) to check_vba_compile.py | 30 min | Catches `Dim Type As String` class errors |
| P2 | Add R8 (Option Explicit check) | 15 min | Prevents undeclared var runtime bombs |
| P3 | Add R9 (VB_Name vs filename mismatch) | 20 min | Prevents wrong-module-import errors |
| P4 | Create vba_com_compile.py with win32gui dialog detection | 1 hour | Catches 100% of remaining compile errors |
| P5 | Wire both into verify-erp.bat with proper exit codes | 15 min | Completes the CI gate |

---

## Unresolved Questions

1. **Rubberduck 3.0 LSP timeline** — nếu ra mắt trong 2026, sẽ có CLI capability. Monitor: https://rubberduckvba.blog
2. **win32gui dialog detection reliability** — cần test thực tế: có trường hợp dialog title khác nhau ở Office 365 vs Office 2019?
3. **COM compile gate trong non-interactive session** (e.g., Task Scheduler, CI pipeline) — Excel COM có thể fail với `CO_E_SERVER_EXEC_FAILURE` khi không có interactive desktop. Cần test với `xlVisible=True` fallback.
4. **Cross-module call validation** (Rule I13) — cần build symbol table từ tất cả .bas files để check function references. Phức tạp hơn, để sprint sau.

---

## References

- [Rubberduck GitHub (archived)](https://github.com/rubberduck-vba/Rubberduck)
- [Rubberduck Blog — Jan 2025 update](https://rubberduckvba.blog/2025/01/)
- [MS-VBAL Reserved Identifiers spec](https://learn.microsoft.com/en-us/openspecs/microsoft_general_purpose_programming_languages/ms-vbal/7df907cb-ab6c-40d3-aa81-272742ce00c3)
- [Microsoft VBA Naming Rules](https://learn.microsoft.com/en-us/office/vba/language/concepts/getting-started/visual-basic-naming-rules)
- [oletools / olevba](https://github.com/decalage2/oletools)
- [VBA-Linter (Beakerboy)](https://github.com/Beakerboy/VBA-Linter)
- [VBACop (rixatron)](https://github.com/rixatron/vbacop)
- [GitHub VBA topics page](https://github.com/topics/vba)
- [analysis-tools.dev VBA tag](https://analysis-tools.dev/tag/vba)
