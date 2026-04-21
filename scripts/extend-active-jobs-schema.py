"""
extend-active-jobs-schema.py — Add 5 hidden Phase 3 cols to Active Jobs sheet.

New cols (appended after existing last col 40 = PRICE_WATCH_DELTA):
    Col 41: SI_CutOff       datetime string "2026-04-21T14:00"
    Col 42: CY_Close        datetime string "2026-04-22T11:00"
    Col 43: Vessel_Voyage   text "YM TOPMOST 024E"
    Col 44: PO_Number       text "LP-95"
    Col 45: Flow_Type       text "DIRECT" or "KEEP_SPACE"

Usage:
    # Dry run — show what would be added, no file changes:
    C:/Users/Nelson/anaconda3/python scripts/extend-active-jobs-schema.py --dry-run

    # Production:
    C:/Users/Nelson/anaconda3/python scripts/extend-active-jobs-schema.py

Notes:
    - Uses win32com (NOT openpyxl) to preserve VBA modules + ribbon (SYSTEM_STANDARDS §5)
    - Idempotent: skips col add if header already exists in Active Jobs
    - Active Jobs header row = 7 (rows 1-6 are title/visual chrome)
    - Hides newly added cols (ColumnWidth = 0) to match hidden col pattern
    - Backs up file with timestamp before any write
    - Errors out if Excel is running (Excel locks the file)
"""
from __future__ import annotations
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

ERP_PATH = r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"
BACKUP_DIR = Path(r"D:\OneDrive\NelsonData\erp")
SHEET_NAME = "Active Jobs"
HEADER_ROW = 7  # Active Jobs: rows 1-6 are title/chrome, row 7 = header

NEW_COLS = [
    "SI_CutOff",
    "CY_Close",
    "Vessel_Voyage",
    "PO_Number",
    "Flow_Type",
]


def _excel_is_running() -> bool:
    """Return True if any Excel process is currently running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/NH"],
            capture_output=True,
            text=True,
        )
        return "EXCEL.EXE" in result.stdout
    except Exception:
        return False  # can't detect — assume not running


def _backup_file(erp_path: str) -> Path:
    """Create a timestamped backup. Returns backup path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    src = Path(erp_path)
    dst = BACKUP_DIR / f"{src.stem}.backup_phase3_{ts}{src.suffix}"
    shutil.copy2(src, dst)
    return dst


def _find_last_col(ws, header_row: int) -> int:
    """Return 1-based index of last non-empty cell in header_row."""
    used = ws.UsedRange.Columns.Count
    # Walk backwards to find real last
    for c in range(used, 0, -1):
        val = ws.Cells(header_row, c).Value
        if val is not None and str(val).strip() != "":
            return c
    return used


def run(dry_run: bool = False) -> dict:
    """
    Main entry point. Returns dict with:
        col_indexes: {name: col_number}
        skipped: [names already present]
        added: [names added]
    """
    erp_path = ERP_PATH

    if not Path(erp_path).exists():
        raise FileNotFoundError(f"ERP file not found: {erp_path}")

    if _excel_is_running():
        raise RuntimeError(
            "Excel is currently running. Close Excel first, then re-run this script."
        )

    if dry_run:
        print("[DRY RUN] No changes will be made.\n")

    # Peek at existing headers using win32com (read mode) to determine col positions
    import win32com.client  # noqa: PLC0415

    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    wb = None
    result = {"col_indexes": {}, "skipped": [], "added": []}

    try:
        wb = excel.Workbooks.Open(str(Path(erp_path).resolve()), ReadOnly=dry_run)
        ws = wb.Sheets(SHEET_NAME)

        # Read current headers
        last_col = _find_last_col(ws, HEADER_ROW)
        existing_headers = {}
        for c in range(1, last_col + 1):
            val = ws.Cells(HEADER_ROW, c).Value
            if val is not None:
                existing_headers[str(val).strip()] = c

        print(f"Active Jobs — header row={HEADER_ROW}, last col={last_col}")
        print(f"Existing col count: {last_col}")

        # Determine which cols to add
        cols_to_add = []
        next_col = last_col + 1

        for name in NEW_COLS:
            if name in existing_headers:
                result["skipped"].append(name)
                result["col_indexes"][name] = existing_headers[name]
                print(f"  SKIP (already exists): {name} @ col {existing_headers[name]}")
            else:
                result["added"].append(name)
                result["col_indexes"][name] = next_col
                cols_to_add.append((next_col, name))
                print(f"  ADD: {name} @ col {next_col}")
                next_col += 1

        if not cols_to_add:
            print("\nAll 5 cols already exist — nothing to do.")
            return result

        if dry_run:
            print("\n[DRY RUN] Would add:", [n for _, n in cols_to_add])
            return result

        # Backup before write
        backup_path = _backup_file(erp_path)
        print(f"\nBackup created: {backup_path.name}")

        # Write headers + hide cols
        for col_idx, col_name in cols_to_add:
            cell = ws.Cells(HEADER_ROW, col_idx)
            cell.Value = col_name
            cell.Font.Bold = True
            # Match existing hidden col style
            ws.Columns(col_idx).ColumnWidth = 0
            ws.Columns(col_idx).Hidden = True

        wb.Save()
        print(f"\nSaved: {erp_path}")

    finally:
        if wb is not None:
            wb.Close(SaveChanges=False)
        excel.Quit()

    return result


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    try:
        result = run(dry_run=dry_run)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n=== Active Jobs — Phase 3 col indexes (use in VBA constants) ===")
    for name, idx in result["col_indexes"].items():
        print(f"  AJ_{name.upper().replace('-', '_')}_COL = {idx}")

    if result["added"]:
        print(f"\nAdded {len(result['added'])} col(s): {result['added']}")
    if result["skipped"]:
        print(f"Skipped {len(result['skipped'])} (already exist): {result['skipped']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
