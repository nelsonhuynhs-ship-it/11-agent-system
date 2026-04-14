"""
install_jobs_automation.py — auto-import VBA module into ERP_Master_v14.xlsm
============================================================================
Nelson's Active Jobs v4 ribbon buttons fail with "Cannot run the macro" until
the handlers in erp-v14-jobs-automation.bas are imported into the workbook's
VBA project. This script does that automatically via Excel COM.

Requires: "Trust access to the VBA project object model" = ON
  (File → Options → Trust Center → Trust Center Settings →
   Macro Settings → ✓ Trust access to the VBA project object model)

Usage:
    python ERP/core/install_jobs_automation.py

If COM import fails (trust access off), the script falls back to printing
the 3-step manual import guide.
"""
from __future__ import annotations

import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

ERP_FILE = r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"
BAS_FILE = r"D:\OneDrive\NelsonData\erp\erp-v14-jobs-automation.bas"
MODULE_NAME = "ERPv14JobsAutomation"


MANUAL_GUIDE = f"""
[Manual import — 30 seconds]

  1. Mở {ERP_FILE}
  2. Bấm Alt + F11  (mở VBA Editor)
  3. File → Import File... → chọn {BAS_FILE}
  4. Bấm Ctrl + S trong VBE (hoặc quay lại Excel, Ctrl+S)
  5. Đóng Excel hoàn toàn → mở lại → click buttons

[Trust access to VBA project (1-time, để auto-import lần sau):]
  File → Options → Trust Center → Trust Center Settings
  → Macro Settings → ✓ Trust access to the VBA project object model
  → OK → OK
"""


def auto_import() -> int:
    try:
        import win32com.client as win32  # type: ignore[import-untyped]
    except ImportError:
        print("[ERROR] pywin32 not installed. pip install pywin32")
        print(MANUAL_GUIDE)
        return 1

    if not os.path.exists(ERP_FILE):
        print(f"[ERROR] ERP file not found: {ERP_FILE}")
        return 1
    if not os.path.exists(BAS_FILE):
        print(f"[ERROR] BAS file not found: {BAS_FILE}")
        return 1

    # First try: attach to a running Excel (Nelson may have file open)
    excel = None
    wb = None
    spawned = False
    try:
        excel = win32.GetActiveObject("Excel.Application")
        print("[+] Attached to running Excel instance")
        # Check if target workbook is already open
        target_name = os.path.basename(ERP_FILE).lower()
        for i in range(1, excel.Workbooks.Count + 1):
            w = excel.Workbooks(i)
            if w.Name.lower() == target_name:
                wb = w
                print(f"    -> target workbook already open: {w.Name}")
                break
    except Exception:
        excel = None

    if excel is None:
        print(f"[+] Launching new Excel instance...")
        excel = win32.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        spawned = True

    try:
        if wb is None:
            wb = excel.Workbooks.Open(ERP_FILE)
            time.sleep(1)

        # Access VBA project — fails if "Trust access" is OFF
        try:
            vb_project = wb.VBProject
        except Exception as e:
            print(f"[ERROR] Cannot access VBProject: {e}")
            print("\n  --> 'Trust access to VBA project object model' is OFF.")
            print(MANUAL_GUIDE)
            wb.Close(SaveChanges=False)
            excel.Quit()
            return 2

        # Remove existing module if present (idempotent)
        components = vb_project.VBComponents
        existing = [c.Name for c in components]
        if MODULE_NAME in existing:
            print(f"    -> removing existing {MODULE_NAME}")
            components.Remove(components(MODULE_NAME))

        # Import fresh
        print(f"    -> importing {BAS_FILE}")
        components.Import(BAS_FILE)

        # Save workbook
        wb.Save()
        if spawned:
            wb.Close(SaveChanges=False)
            excel.Quit()
            print(f"\n[SUCCESS] VBA module '{MODULE_NAME}' imported + saved.")
        else:
            print(f"\n[SUCCESS] VBA module '{MODULE_NAME}' imported + saved.")
            print(f"          Workbook still open in your Excel — ready to click buttons.")
        print("          Buttons: Price Watch | Tracking | Release Alerts | Enrich BKG | etc.\n")
        return 0

    except Exception as e:
        print(f"[ERROR] Unexpected failure: {e}")
        if spawned:
            try:
                excel.Quit()
            except Exception:
                pass
        print(MANUAL_GUIDE)
        return 1


if __name__ == "__main__":
    sys.exit(auto_import())
