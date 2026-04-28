"""
reimport-thisworkbook.py — Re-import ThisWorkbook code into ERP_Master_v14.xlsm

ThisWorkbook is a document-level VBA module (not a standard module),
so VBComponents.Import() doesn't work. Must use CodeModule.DeleteLines/AddFromString.

Source: D:/OneDrive/NelsonData/erp/erp-v14-thisworkbook.txt
"""
from __future__ import annotations

import sys
from pathlib import Path

ERP_FOLDER = Path("D:/OneDrive/NelsonData/erp")
XLSM = ERP_FOLDER / "ERP_Master_v14.xlsm"
TXT = ERP_FOLDER / "erp-v14-thisworkbook.txt"


def main() -> int:
    if not XLSM.exists():
        print(f"[ERR] xlsm not found: {XLSM}")
        return 2
    if not TXT.exists():
        print(f"[ERR] thisworkbook source not found: {TXT}")
        return 2

    new_code = TXT.read_text(encoding="utf-8", errors="replace")
    print(f"Source loaded: {TXT.name} ({len(new_code)} chars, "
          f"{new_code.count(chr(10)) + 1} lines)")

    import win32com.client
    import pywintypes

    print(f"Opening {XLSM}...")
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(str(XLSM))
    except pywintypes.com_error as exc:
        print(f"[ERR] cannot open xlsm: {exc}")
        excel.Quit()
        return 3

    try:
        vbp = wb.VBProject
    except pywintypes.com_error:
        print("[ERR] VBProject access denied. Enable Trust access to VBA project object model.")
        wb.Close(SaveChanges=False)
        excel.Quit()
        return 4

    try:
        comp = vbp.VBComponents("ThisWorkbook")
    except pywintypes.com_error as exc:
        print(f"[ERR] ThisWorkbook component not found: {exc}")
        wb.Close(SaveChanges=False)
        excel.Quit()
        return 5

    cm = comp.CodeModule
    line_count = cm.CountOfLines
    print(f"Existing ThisWorkbook code: {line_count} lines")

    if line_count > 0:
        cm.DeleteLines(1, line_count)
        print("  cleared existing lines")

    cm.AddFromString(new_code)
    print(f"  inserted {new_code.count(chr(10)) + 1} lines from {TXT.name}")

    print("Saving workbook...")
    wb.Save()
    wb.Close(SaveChanges=False)
    excel.Quit()

    print("Done. ThisWorkbook re-imported.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
