"""
erp-add-milestone-cols.py — Add milestone notification columns to ERP_Master_v14.xlsm

Cols added:
    CRM sheet:          AUTO_NOTIFY (Y/N dropdown, default N)
    Active Jobs sheet:  ATD_DATE (date), ETA_DATE (date),
                        NOTIFIED_ATD (Y/N), NOTIFIED_ETA7 (Y/N)

Usage:
    # Test on COPY first (ALWAYS run this first):
    C:/Users/Nelson/anaconda3/python scripts/erp-add-milestone-cols.py --test

    # Production (only after --test verified OK):
    C:/Users/Nelson/anaconda3/python scripts/erp-add-milestone-cols.py

    # Rollback — export cols to CSV then remove them:
    C:/Users/Nelson/anaconda3/python scripts/erp-add-milestone-cols.py --rollback

    # Rollback on test copy:
    C:/Users/Nelson/anaconda3/python scripts/erp-add-milestone-cols.py --rollback --test

Notes:
    - Uses win32com (NOT openpyxl) to preserve VBA modules + ribbon (SYSTEM_STANDARDS §5)
    - Idempotent: skips col add if col already exists
    - Inserts at END of existing cols (does not shift existing data)
    - Backs up file with timestamp before any production change
"""
from __future__ import annotations
import sys, csv, shutil
from datetime import datetime
from pathlib import Path

ERP_PATH = r"D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm"
ERP_PATH_TEST = r"D:/OneDrive/NelsonData/erp/ERP_Master_v14.migration_test.xlsm"
BACKUP_DIR = Path(r"D:/OneDrive/NelsonData/erp")
ROLLBACK_EXPORT = Path(__file__).parent.parent / "plans" / "reports" / "erp-milestone-rollback-export.csv"

# Active Jobs sheet uses row 7 as header (rows 1-6 are title/visual chrome)
# CRM sheet uses row 1 as header (standard)
SHEET_HEADER_ROW = {
    "Active Jobs": 7,
    "CRM": 1,
}


def _get_target_path(test_mode: bool) -> str:
    return ERP_PATH_TEST if test_mode else ERP_PATH


def _get_header_row(ws) -> int:
    """Return the header row index for this worksheet (1-based)."""
    sheet_name = ws.Name
    return SHEET_HEADER_ROW.get(sheet_name, 1)


def _find_last_col(ws) -> int:
    """Return the 1-based index of the last used column in the header row."""
    hrow = _get_header_row(ws)
    used_cols = ws.UsedRange.Columns.Count
    # Walk backwards from UsedRange boundary to find last non-empty header
    while used_cols > 0 and not ws.Cells(hrow, used_cols).Value:
        used_cols -= 1
    return used_cols


def _col_exists(ws, col_name: str) -> int | None:
    """Return 1-based col index if col_name found in header row, else None."""
    hrow = _get_header_row(ws)
    last_col = ws.UsedRange.Columns.Count
    for c in range(1, last_col + 1):
        val = ws.Cells(hrow, c).Value
        if val and str(val).strip().upper() == col_name.upper():
            return c
    return None


def _add_text_col(ws, col_name: str, default_val: str = "") -> int:
    """Add text column at end. Returns new col index (1-based)."""
    existing = _col_exists(ws, col_name)
    if existing:
        print(f"    SKIP: '{col_name}' already at col {existing}")
        return existing

    hrow = _get_header_row(ws)
    new_col = _find_last_col(ws) + 1
    ws.Cells(hrow, new_col).Value = col_name

    # Fill existing data rows with default
    last_row = ws.UsedRange.Rows.Count
    data_start = hrow + 1
    if default_val and last_row >= data_start:
        for row in range(data_start, last_row + 1):
            # Only fill if row appears to have data (check col A)
            if ws.Cells(row, 1).Value is not None:
                ws.Cells(row, new_col).Value = default_val

    print(f"    ADDED: '{col_name}' at col {new_col} (default='{default_val}', "
          f"data rows {data_start}-{last_row})")
    return new_col


def _add_date_col(ws, col_name: str) -> int:
    """Add date-formatted column at end. Returns new col index."""
    existing = _col_exists(ws, col_name)
    if existing:
        print(f"    SKIP: '{col_name}' already at col {existing}")
        return existing

    hrow = _get_header_row(ws)
    new_col = _find_last_col(ws) + 1
    ws.Cells(hrow, new_col).Value = col_name

    # Apply date format to data rows
    last_row = ws.UsedRange.Rows.Count
    data_start = hrow + 1
    if last_row >= data_start:
        col_range = ws.Range(
            ws.Cells(data_start, new_col),
            ws.Cells(max(last_row, data_start), new_col)
        )
        col_range.NumberFormat = "DD/MM/YYYY"

    print(f"    ADDED: '{col_name}' (date format) at col {new_col}")
    return new_col


def _add_dropdown_validation(ws, col_idx: int, list_vals: list[str], last_row: int):
    """Add Y/N dropdown data validation to col from data_start to last_row."""
    hrow = _get_header_row(ws)
    data_start = hrow + 1
    if last_row < data_start:
        return
    try:
        col_range = ws.Range(
            ws.Cells(data_start, col_idx),
            ws.Cells(max(last_row, data_start), col_idx)
        )
        dv = col_range.Validation
        dv.Delete()
        dv.Add(
            Type=3,             # xlValidateList
            AlertStyle=1,       # xlValidAlertStop
            Operator=1,         # xlBetween
            Formula1=",".join(list_vals)
        )
        dv.InCellDropdown = True
        dv.ShowError = True
        dv.ErrorTitle = "Invalid value"
        dv.ErrorMessage = f"Please select: {', '.join(list_vals)}"
        print(f"    Dropdown validation added to col {col_idx}: {list_vals}")
    except Exception as e:
        print(f"    WARN: Could not add dropdown to col {col_idx}: {e}")


def _verify_vba_modules(wb) -> list[str]:
    """Return list of VBA module names to verify they survived migration."""
    modules = []
    try:
        for i in range(1, wb.VBProject.VBComponents.Count + 1):
            modules.append(wb.VBProject.VBComponents.Item(i).Name)
    except Exception as e:
        print(f"    WARN: Could not enumerate VBA modules (may need Trust access to VBA): {e}")
    return modules


def _backup_file(target_path: str) -> str:
    """Create timestamped backup. Returns backup path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    src = Path(target_path)
    backup_name = src.stem + f".backup_{ts}" + src.suffix
    backup_path = src.parent / backup_name
    shutil.copy2(src, backup_path)
    print(f"  Backup created: {backup_path}")
    return str(backup_path)


def run_migration(test_mode: bool = False):
    """Add all milestone columns to xlsm."""
    try:
        import win32com.client
        import pythoncom
    except ImportError:
        print("ERROR: pywin32 not installed. Run: pip install pywin32")
        sys.exit(1)

    target = _get_target_path(test_mode)
    mode_label = "TEST COPY" if test_mode else "PRODUCTION"
    print(f"\n=== ERP Milestone Migration [{mode_label}] ===")
    print(f"Target: {target}")

    if not test_mode:
        # Check source exists for COPY creation if needed
        if not Path(ERP_PATH).exists():
            print(f"ERROR: ERP file not found: {ERP_PATH}")
            sys.exit(1)
        # Backup before production change
        _backup_file(target)
    else:
        # Create test copy from production
        if not Path(ERP_PATH).exists():
            print(f"ERROR: Source ERP file not found: {ERP_PATH}")
            sys.exit(1)
        if not Path(ERP_PATH_TEST).exists():
            shutil.copy2(ERP_PATH, ERP_PATH_TEST)
            print(f"  Created test copy: {ERP_PATH_TEST}")
        else:
            print(f"  Test copy already exists: {ERP_PATH_TEST}")

    pythoncom.CoInitialize()
    excel = None
    wb = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False

        print(f"\nOpening: {target}")
        wb = excel.Workbooks.Open(target)

        # ── VBA check BEFORE ─────────────────────────────────────────────
        modules_before = _verify_vba_modules(wb)
        if modules_before:
            print(f"\nVBA modules before: {modules_before}")
        else:
            print("\nVBA modules: (access disabled or none found)")

        # ── CRM sheet: add AUTO_NOTIFY ────────────────────────────────────
        print("\n[CRM sheet]")
        try:
            crm = wb.Worksheets("CRM")
            crm_last_row = crm.UsedRange.Rows.Count
            col_auto_notify = _add_text_col(crm, "AUTO_NOTIFY", default_val="N")
            _add_dropdown_validation(crm, col_auto_notify, ["Y", "N"], crm_last_row)
        except Exception as e:
            print(f"  ERROR on CRM sheet: {e}")

        # ── Active Jobs sheet: add 4 cols ─────────────────────────────────
        print("\n[Active Jobs sheet]")
        try:
            active = wb.Worksheets("Active Jobs")
            active_last_row = active.UsedRange.Rows.Count

            col_atd = _add_date_col(active, "ATD_DATE")
            col_eta = _add_date_col(active, "ETA_DATE")
            col_notified_atd = _add_text_col(active, "NOTIFIED_ATD", default_val="N")
            _add_dropdown_validation(active, col_notified_atd, ["Y", "N"], active_last_row)
            col_notified_eta7 = _add_text_col(active, "NOTIFIED_ETA7", default_val="N")
            _add_dropdown_validation(active, col_notified_eta7, ["Y", "N"], active_last_row)
        except Exception as e:
            print(f"  ERROR on Active Jobs sheet: {e}")

        # ── Save ──────────────────────────────────────────────────────────
        print(f"\nSaving {target} ...")
        wb.Save()
        print("  Save OK")

        # ── VBA check AFTER ───────────────────────────────────────────────
        modules_after = _verify_vba_modules(wb)
        if modules_after:
            print(f"\nVBA modules after: {modules_after}")
            if set(modules_before) == set(modules_after):
                print("  VBA INTEGRITY: OK (no modules lost)")
            else:
                lost = set(modules_before) - set(modules_after)
                gained = set(modules_after) - set(modules_before)
                if lost:
                    print(f"  WARNING: VBA modules lost: {lost}")
                if gained:
                    print(f"  INFO: New VBA modules: {gained}")

        print(f"\nMigration complete [{mode_label}]")
        print("Next step: Open the file in Excel manually to verify:")
        print("  1. Ribbon buttons visible + clickable")
        print("  2. New dropdown cols show Y/N options")
        print("  3. No repair dialog on open")

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


def run_rollback(test_mode: bool = False):
    """Export new cols to CSV first, then remove them."""
    try:
        import win32com.client
        import pythoncom
    except ImportError:
        print("ERROR: pywin32 not installed.")
        sys.exit(1)

    target = _get_target_path(test_mode)
    print(f"\n=== ERP Milestone Rollback ===")
    print(f"Target: {target}")

    MILESTONE_COLS = {
        "CRM": ["AUTO_NOTIFY"],
        "Active Jobs": ["ATD_DATE", "ETA_DATE", "NOTIFIED_ATD", "NOTIFIED_ETA7"],
    }

    pythoncom.CoInitialize()
    excel = None
    wb = None
    try:
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(target)

        # Export data first
        ROLLBACK_EXPORT.parent.mkdir(parents=True, exist_ok=True)
        export_rows = []

        for sheet_name, cols in MILESTONE_COLS.items():
            try:
                ws = wb.Worksheets(sheet_name)
                last_row = ws.UsedRange.Rows.Count
                hrow = SHEET_HEADER_ROW.get(sheet_name, 1)
                data_start = hrow + 1

                for col_name in cols:
                    col_idx = _col_exists(ws, col_name)
                    if col_idx is None:
                        print(f"  SKIP: '{col_name}' not found in {sheet_name}")
                        continue
                    # Export values
                    for row in range(data_start, last_row + 1):
                        val = ws.Cells(row, col_idx).Value
                        if val is not None:
                            # Get primary key from col A
                            pk = ws.Cells(row, 1).Value
                            export_rows.append({
                                "sheet": sheet_name,
                                "row": row,
                                "primary_key_col_A": pk,
                                "col_name": col_name,
                                "value": val,
                            })
            except Exception as e:
                print(f"  ERROR on {sheet_name}: {e}")

        # Write CSV
        if export_rows:
            with ROLLBACK_EXPORT.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["sheet", "row", "primary_key_col_A", "col_name", "value"]
                )
                writer.writeheader()
                writer.writerows(export_rows)
            print(f"\nExported {len(export_rows)} data values to: {ROLLBACK_EXPORT}")
        else:
            print("  No data to export (cols are empty or not found)")

        # Now delete the cols (iterate in reverse to keep indices stable)
        print("\nDeleting milestone cols...")
        for sheet_name, cols in MILESTONE_COLS.items():
            try:
                ws = wb.Worksheets(sheet_name)
                # Collect col indices to delete (sort descending so deleting right→left)
                to_delete = []
                for col_name in cols:
                    idx = _col_exists(ws, col_name)
                    if idx:
                        to_delete.append(idx)
                to_delete.sort(reverse=True)
                for idx in to_delete:
                    col_name_val = ws.Cells(1, idx).Value
                    ws.Columns(idx).Delete()
                    print(f"  Deleted col {idx} ('{col_name_val}') from {sheet_name}")
            except Exception as e:
                print(f"  ERROR deleting from {sheet_name}: {e}")

        wb.Save()
        print("\nRollback complete. File saved.")

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
    test_mode = "--test" in sys.argv
    rollback = "--rollback" in sys.argv

    if rollback:
        run_rollback(test_mode=test_mode)
    else:
        run_migration(test_mode=test_mode)
