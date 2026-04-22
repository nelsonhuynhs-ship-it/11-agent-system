"""
update-thisworkbook-module.py — update ThisWorkbook module via Excel COM.

ThisWorkbook is a special module (not importable like regular .bas). We use
CodeModule API to replace its content line-by-line.

Source: D:/OneDrive/NelsonData/erp/erp-v14-thisworkbook.txt
"""
import sys
import os
import win32com.client

ERP = r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"
SRC = r"D:\OneDrive\NelsonData\erp\erp-v14-thisworkbook.txt"


def main() -> int:
    with open(SRC, encoding="utf-8") as f:
        new_code = f.read()

    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.AutomationSecurity = 3

    try:
        wb = excel.Workbooks.Open(ERP, UpdateLinks=0, ReadOnly=False)
        vbproj = wb.VBProject

        tw = vbproj.VBComponents("ThisWorkbook")
        cm = tw.CodeModule

        # Clear existing code
        if cm.CountOfLines > 0:
            cm.DeleteLines(1, cm.CountOfLines)
        # Insert new code at line 1
        cm.AddFromString(new_code)
        print(f"ThisWorkbook module updated ({cm.CountOfLines} lines)")

        wb.Save()
        wb.Close(SaveChanges=False)
    finally:
        excel.Quit()

    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
