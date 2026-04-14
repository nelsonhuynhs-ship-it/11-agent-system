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

# Modules to (re)import — order matters: ribbon callbacks first, automation second
# since automation may reference ribbon helpers
BAS_MODULES = [
    ("ERPv14Ribbon",          r"D:\OneDrive\NelsonData\erp\erp-v14-ribbon-callbacks.bas"),
    ("ERPv14JobsAutomation",  r"D:\OneDrive\NelsonData\erp\erp-v14-jobs-automation.bas"),
]

# Backward compat — legacy single-file var used elsewhere
BAS_FILE = BAS_MODULES[1][1]
MODULE_NAME = BAS_MODULES[1][0]


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

        components = vb_project.VBComponents

        # Re-import each module — prefer CodeModule.DeleteLines + AddFromFile
        # (preserves module identity, safer for modules with references)
        imported = []
        skipped = []
        for mod_name, bas_path in BAS_MODULES:
            if not os.path.exists(bas_path):
                print(f"    [skip] {mod_name}: file not found at {bas_path}")
                skipped.append(mod_name)
                continue

            existing = [c.Name for c in components]
            if mod_name in existing:
                try:
                    # In-place replace: clear existing CodeModule content, reload from file
                    comp = components(mod_name)
                    cm = comp.CodeModule
                    if cm.CountOfLines > 0:
                        cm.DeleteLines(1, cm.CountOfLines)
                    cm.AddFromFile(bas_path)
                    # Strip attribute header re-injected by AddFromFile if present
                    # (optional; VBE auto-strips). Then remove the module-name 'Attribute' line
                    # that comes from the .bas Attribute VB_Name="..." — VBE handles it.
                    print(f"    -> reloaded {mod_name} in-place (CodeModule.AddFromFile)")
                    imported.append(mod_name)
                    continue
                except Exception as e:
                    print(f"    [warn] in-place reload of {mod_name} failed: {e}")
                    # Fall through to Remove+Import
                    try:
                        components.Remove(components(mod_name))
                    except Exception as e2:
                        print(f"    [skip] {mod_name}: cannot remove ({e2}) — import skipped")
                        skipped.append(mod_name)
                        continue
            try:
                components.Import(bas_path)
                print(f"    -> imported fresh {mod_name}")
                imported.append(mod_name)
            except Exception as e:
                print(f"    [skip] {mod_name}: import failed ({e})")
                skipped.append(mod_name)

        # Save workbook
        wb.Save()
        if spawned:
            wb.Close(SaveChanges=False)
            excel.Quit()
        print(f"\n[SUCCESS] VBA imported: {', '.join(imported) if imported else '(none)'}")
        if skipped:
            print(f"          Skipped: {', '.join(skipped)} (import manually via Alt+F11 if needed)")
        print("          v4 layout: MarkQuoteWin writes to cols A-S (MONTH, FAST_ID, CUSTOMER, POL-POD, ...)\n")
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
