"""
_audit_erp_headers.py — Dump Active Jobs + CRM header rows for schema review.

Usage:
    C:/Users/Nelson/anaconda3/python scripts/_audit_erp_headers.py

Output:
    plans/reports/erp-headers-audit.csv
    stdout: header mappings + sample customer names
"""
from __future__ import annotations
import sys, csv
from pathlib import Path

ERP_PATH = r"D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm"
REPORT_PATH = Path(__file__).parent.parent / "plans" / "reports" / "erp-headers-audit.csv"

SHEETS_TO_AUDIT = ["Active Jobs", "CRM"]
SAMPLE_ROWS = 10


def audit_headers():
    try:
        import win32com.client
        import pythoncom
    except ImportError:
        print("ERROR: pywin32 not installed. Run: pip install pywin32")
        sys.exit(1)

    pythoncom.CoInitialize()
    excel = None
    wb = None
    try:
        print(f"Opening (read-only): {ERP_PATH}")
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(ERP_PATH, ReadOnly=True)

        results = []

        for sheet_name in SHEETS_TO_AUDIT:
            try:
                ws = wb.Worksheets(sheet_name)
            except Exception:
                print(f"  WARN: Sheet '{sheet_name}' not found — skipping")
                continue

            # Find last used column in row 1
            last_col = ws.UsedRange.Columns.Count
            header_row = []
            for col in range(1, last_col + 1):
                val = ws.Cells(1, col).Value
                header_row.append(str(val) if val is not None else "")

            print(f"\n=== Sheet: {sheet_name} ({last_col} cols) ===")
            for i, h in enumerate(header_row, 1):
                print(f"  Col {i:3d}: {h}")

            # Collect sample customer/company names
            # For Active Jobs: look for "CUSTOMER" col
            # For CRM: look for "COMPANY" or "CUSTOMER" col
            customer_col = None
            for i, h in enumerate(header_row):
                h_up = h.upper()
                if h_up in ("CUSTOMER", "COMPANY", "CNEE", "CONSIGNEE"):
                    customer_col = i + 1  # 1-based
                    break

            samples = []
            if customer_col:
                last_row = ws.UsedRange.Rows.Count
                actual_limit = min(SAMPLE_ROWS + 1, last_row)
                for row in range(2, actual_limit + 1):
                    val = ws.Cells(row, customer_col).Value
                    if val:
                        samples.append(str(val))
                print(f"\n  Sample values from col '{header_row[customer_col - 1]}' "
                      f"(col {customer_col}):")
                for s in samples:
                    print(f"    - {s}")
            else:
                print("  (No CUSTOMER/COMPANY column detected in row 1)")

            # Record to CSV output
            for i, h in enumerate(header_row, 1):
                results.append({
                    "sheet": sheet_name,
                    "col_index": i,
                    "col_name": h,
                    "sample_values": ""
                })
            # Append samples in separate rows
            if samples:
                results.append({
                    "sheet": sheet_name,
                    "col_index": "SAMPLES",
                    "col_name": header_row[customer_col - 1] if customer_col else "",
                    "sample_values": " | ".join(samples)
                })

        # Write CSV report
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REPORT_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["sheet", "col_index", "col_name", "sample_values"])
            writer.writeheader()
            writer.writerows(results)

        print(f"\n\nReport saved: {REPORT_PATH}")

        # Check milestone cols already present
        print("\n=== Milestone Cols Pre-check ===")
        milestone_cols = {
            "Active Jobs": ["ATD_DATE", "ETA_DATE", "NOTIFIED_ATD", "NOTIFIED_ETA7"],
            "CRM": ["AUTO_NOTIFY"],
        }
        for sheet_name, expected_cols in milestone_cols.items():
            try:
                ws = wb.Worksheets(sheet_name)
                last_col = ws.UsedRange.Columns.Count
                existing = [str(ws.Cells(1, c).Value or "").upper() for c in range(1, last_col + 1)]
                for col in expected_cols:
                    status = "ALREADY EXISTS" if col.upper() in existing else "MISSING (will add)"
                    print(f"  {sheet_name} / {col}: {status}")
            except Exception:
                print(f"  {sheet_name}: sheet not accessible")

    finally:
        if wb:
            try:
                wb.Close(SaveChanges=False)
            except Exception:
                pass
        if excel:
            try:
                excel.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    audit_headers()
