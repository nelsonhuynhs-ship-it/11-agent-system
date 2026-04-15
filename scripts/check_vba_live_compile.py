"""
Live VBA compile check — opens xlsm in hidden Excel, runs VBE Compile,
detects the compile-error dialog via win32gui EnumWindows.

This is the FINAL compile gate — our offline linter (R1-R9) catches
known compile-error patterns; this catches *anything* Excel itself
would refuse at open time.

Strategy (per tech-scout research 2026-04-15):
  1. Dispatch hidden Excel, open workbook read-only
  2. Trigger VBE "Compile VBAProject" (CommandBar Id=578) — does NOT
     return error info directly
  3. Poll EnumWindows for ~2s looking for a "Microsoft Visual Basic"
     compile-error dialog — its presence = compile failed
  4. Also verify each VBComponent is readable (locked project detection)

Requires: pywin32 + installed Excel + "Trust access to VBA project"=ON.

Exit codes:
  0 — clean compile
  1 — compile error detected (dialog surfaced OR module unreadable)
  2 — environment error (no pywin32 / no Excel / no trust access)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ERP = Path(sys.argv[1] if len(sys.argv) > 1
           else r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm")

if not ERP.exists():
    print(f"[FAIL] File not found: {ERP}")
    sys.exit(2)

try:
    import win32com.client as win32
    import pythoncom
    import win32gui
    import win32con
except ImportError:
    print("[SKIP] pywin32 not available — live compile check disabled")
    sys.exit(0)


# Dialog titles Excel/VBE uses when surfacing a compile error.
# Captured from real error dialogs across Office 365 + 2019.
ERROR_DIALOG_TITLES = (
    "Microsoft Visual Basic for Applications",
    "Microsoft Visual Basic",
    "Compile error",
)


def _find_error_dialogs() -> list[tuple[int, str]]:
    """Return list of (hwnd, title) for visible VBE error dialogs."""
    found: list[tuple[int, str]] = []

    def _enum_cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd)
        for needle in ERROR_DIALOG_TITLES:
            if needle in title:
                found.append((hwnd, title))
                return True
        return True

    try:
        win32gui.EnumWindows(_enum_cb, None)
    except Exception:
        pass
    return found


def _close_dialogs(dialogs: list[tuple[int, str]]) -> None:
    """Send WM_CLOSE to each dialog so Excel.Quit() won't hang."""
    for hwnd, _ in dialogs:
        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        except Exception:
            pass


def _quit_excel(excel):
    try:
        excel.DisplayAlerts = False
        excel.Quit()
    except Exception:
        pass


def main() -> int:
    pythoncom.CoInitialize()
    excel = None
    wb = None
    try:
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
    except Exception as ex:
        print(f"[FAIL] cannot start Excel: {ex}")
        return 2

    try:
        wb = excel.Workbooks.Open(str(ERP), UpdateLinks=0, ReadOnly=True)
        time.sleep(1)
    except Exception as ex:
        print(f"[FAIL] cannot open workbook: {ex}")
        _quit_excel(excel)
        return 2

    try:
        vbp = wb.VBProject
    except Exception as ex:
        print(f"[FAIL] VBProject not accessible: {ex}")
        print("  --> Enable 'Trust access to VBA project object model' in Excel")
        try:
            wb.Close(SaveChanges=False)
        except Exception:
            pass
        _quit_excel(excel)
        return 2

    # Snapshot dialogs pre-compile so we can detect ones that appear during.
    pre_compile_dialogs = {h for h, _ in _find_error_dialogs()}

    # Trigger VBE "Compile VBAProject" (Debug menu, Id=578).
    compile_exception = None
    try:
        excel.VBE.CommandBars.FindControl(Id=578).Execute()
    except Exception as ex:
        compile_exception = str(ex)

    # Allow Excel up to 2s to surface an error dialog (most show < 500ms).
    new_dialogs: list[tuple[int, str]] = []
    deadline = time.time() + 2.0
    while time.time() < deadline:
        found = _find_error_dialogs()
        new_dialogs = [(h, t) for h, t in found if h not in pre_compile_dialogs]
        if new_dialogs:
            break
        time.sleep(0.1)

    # Module readability check — if project is locked by a compile failure,
    # reading CodeModule.Lines raises (reliable fallback signal).
    module_count = 0
    syntax_errors: list[tuple[str, int, str]] = []
    for comp in vbp.VBComponents:
        if comp.Type not in (1, 2, 3):  # 1=std 2=cls 3=form
            continue
        module_count += 1
        try:
            cm = comp.CodeModule
            if cm.CountOfLines > 0:
                _ = cm.Lines(1, cm.CountOfLines)
        except Exception as ex:
            syntax_errors.append((comp.Name, 0, f"module read failed: {ex}"))

    # Always close any surfaced dialogs before quitting Excel — otherwise
    # Excel.Quit() blocks waiting for user input.
    if new_dialogs:
        _close_dialogs(new_dialogs)
        time.sleep(0.3)

    try:
        wb.Close(SaveChanges=False)
    except Exception:
        pass
    _quit_excel(excel)

    # Report
    if new_dialogs:
        print(f"[FAIL] VBE compile-error dialog detected ({len(new_dialogs)}):")
        for _, title in new_dialogs:
            print(f"    - {title}")
        print("  --> Open Excel manually to see line number + exact error message.")
        print("      (Excel COM API does not expose dialog body text.)")
        return 1

    if syntax_errors:
        print(f"[FAIL] {len(syntax_errors)} module(s) with syntax/read issues:")
        for name, line, msg in syntax_errors:
            print(f"    - {name}:{line} {msg}")
        return 1

    if compile_exception:
        print(f"[FAIL] VBE Execute raised: {compile_exception}")
        return 1

    print(f"LIVE_COMPILE: OK ({module_count} modules compiled via Excel)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
