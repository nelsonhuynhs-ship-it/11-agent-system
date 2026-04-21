"""
sync-pool-flush.py — Flush booking_pool_state.jsonl → Booking Pool sheet.

Called by Btn_SyncPool_OnAction VBA button via Shell.
Writes result summary to email_engine/data/pool_sync_result.txt (VBA reads it).

Input:
    email_engine/data/booking_pool_state.jsonl  — one JSON object per line
    Event types handled:
        booking_received  → insert/update row in Booking Pool
        si_update         → update cols 11 (SI_CutOff) + 12 (CY_Close) for existing BKG

Output:
    email_engine/data/pool_sync_result.txt  — summary for VBA MsgBox

Notes:
    - Uses win32com to write to xlsm (preserves VBA) — NOT openpyxl
    - Idempotent: dedup by BKG_No in col 1
    - If Excel is running, writes error to result file and exits (non-fatal)
    - Processed events are NOT deleted (keep as audit log); duplicate guard by BKG
    - Booking Pool schema: row 1 = header, data starts row 2
"""
from __future__ import annotations
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
JSONL_PATH = _REPO_ROOT / "email_engine" / "data" / "booking_pool_state.jsonl"
RESULT_PATH = _REPO_ROOT / "email_engine" / "data" / "pool_sync_result.txt"
ERP_PATH = Path(r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm")
POOL_SHEET = "Booking Pool"
POOL_HEADER_ROW = 1  # Booking Pool uses row 1 as header

# Column map (1-based, matches Phase 1 schema)
COL = {
    "BKG_No":        1,
    "Carrier":       2,
    "Customer":      3,
    "POL":           4,
    "POD":           5,
    "Final_Dest":    6,
    "Container":     7,
    "Qty":           8,
    "ETD":           9,
    "ETA":           10,
    "SI_CutOff":     11,
    "CY_Close":      12,
    "Vessel":        13,
    "Voyage":        14,
    "PO_Number":     15,
    "Status":        16,
    "Link_AJ_Row":   17,
    "Date_Booked":   18,
    "Source_Mail_ID": 19,
    "Notes":         20,
}


def _write_result(msg: str) -> None:
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(msg, encoding="utf-8")


def _excel_is_running() -> bool:
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq EXCEL.EXE", "/NH"],
            capture_output=True, text=True,
        )
        return "EXCEL.EXE" in r.stdout
    except Exception:
        return False


def _load_events() -> list[dict]:
    if not JSONL_PATH.exists():
        return []
    events = []
    with JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # skip malformed lines
    return events


def _get_pool_bkg_map(ws) -> dict[str, int]:
    """Return {bkg_no_upper: row_number} for all pool rows (row 2+)."""
    bkg_map: dict[str, int] = {}
    last_row = ws.UsedRange.Rows.Count
    for r in range(2, last_row + 2):
        val = ws.Cells(r, COL["BKG_No"]).Value
        if val is None:
            break
        bkg_map[str(val).strip().upper()] = r
    return bkg_map


def _find_next_empty_row(ws) -> int:
    """Return next empty row index in Booking Pool (start from 2)."""
    r = 2
    while True:
        v1 = ws.Cells(r, COL["BKG_No"]).Value
        v2 = ws.Cells(r, COL["Carrier"]).Value
        if v1 is None and v2 is None:
            return r
        r += 1
        if r > 50000:
            raise RuntimeError("Booking Pool: could not find empty row (sanity limit)")


def _write_booking_row(ws, row: int, ev: dict) -> None:
    """Write a booking_received event into the pool row."""
    ws.Cells(row, COL["BKG_No"]).Value = ev.get("bkg", "")
    ws.Cells(row, COL["Carrier"]).Value = ev.get("carrier", "")
    ws.Cells(row, COL["Customer"]).Value = ev.get("customer", "")
    ws.Cells(row, COL["POL"]).Value = ev.get("pol", "")
    ws.Cells(row, COL["POD"]).Value = ev.get("pod", "")
    ws.Cells(row, COL["Final_Dest"]).Value = ev.get("final_dest", "")
    ws.Cells(row, COL["Container"]).Value = ev.get("container", "")
    ws.Cells(row, COL["Qty"]).Value = ev.get("qty", 1)
    ws.Cells(row, COL["ETD"]).Value = ev.get("etd", "")
    ws.Cells(row, COL["ETA"]).Value = ev.get("eta", "")
    ws.Cells(row, COL["SI_CutOff"]).Value = ev.get("si_cutoff", "")
    ws.Cells(row, COL["CY_Close"]).Value = ev.get("cy_close", "")
    ws.Cells(row, COL["Vessel"]).Value = ev.get("vessel", "")
    ws.Cells(row, COL["Voyage"]).Value = ev.get("voyage", "")
    ws.Cells(row, COL["PO_Number"]).Value = ev.get("po_number", "")
    ws.Cells(row, COL["Status"]).Value = "HOLDING"
    ws.Cells(row, COL["Date_Booked"]).Value = ev.get("date_booked", datetime.now().strftime("%Y-%m-%d %H:%M"))
    ws.Cells(row, COL["Source_Mail_ID"]).Value = ev.get("mail_id", "")
    ws.Cells(row, COL["Notes"]).Value = ev.get("notes", "")
    # Yellow highlight for HOLDING
    ws.Rows(row).Interior.Color = 0xFFFFCC  # RGB(255, 255, 204) in BGR


def main() -> None:
    if _excel_is_running():
        _write_result(
            "ERROR: Excel is open.\nClose Excel and try again (Sync Pool button)."
        )
        sys.exit(0)

    if not ERP_PATH.exists():
        _write_result(f"ERROR: ERP file not found:\n{ERP_PATH}")
        sys.exit(0)

    events = _load_events()
    if not events:
        _write_result(
            "Sync Pool — No events found.\n"
            f"File: {JSONL_PATH}\n"
            "(Booking parser will write here when Custeam mails arrive.)"
        )
        sys.exit(0)

    # Filter relevant event types
    booking_events = [e for e in events if e.get("type") == "booking_received"]
    si_events = [e for e in events if e.get("type") == "si_update"]

    import win32com.client  # noqa: PLC0415

    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    wb = None

    new_count = 0
    update_count = 0
    error_count = 0

    try:
        wb = excel.Workbooks.Open(str(ERP_PATH.resolve()))
        ws = wb.Sheets(POOL_SHEET)
        bkg_map = _get_pool_bkg_map(ws)

        # Process booking_received
        for ev in booking_events:
            bkg = str(ev.get("bkg", "")).strip().upper()
            try:
                if bkg and bkg in bkg_map:
                    # Already exists — update SI/CY if provided (newer data)
                    row = bkg_map[bkg]
                    si_val = ev.get("si_cutoff", "")
                    cy_val = ev.get("cy_close", "")
                    if si_val:
                        ws.Cells(row, COL["SI_CutOff"]).Value = si_val
                    if cy_val:
                        ws.Cells(row, COL["CY_Close"]).Value = cy_val
                    update_count += 1
                else:
                    row = _find_next_empty_row(ws)
                    _write_booking_row(ws, row, ev)
                    if bkg:
                        bkg_map[bkg] = row
                    new_count += 1
            except Exception as exc:
                error_count += 1
                print(f"[WARN] booking row error: {exc}", file=sys.stderr)

        # Process si_update
        for ev in si_events:
            bkg = str(ev.get("bkg", "")).strip().upper()
            if not bkg or bkg not in bkg_map:
                error_count += 1
                continue
            try:
                row = bkg_map[bkg]
                si_val = ev.get("si_cutoff", "")
                cy_val = ev.get("cy_close", "")
                if si_val:
                    ws.Cells(row, COL["SI_CutOff"]).Value = si_val
                if cy_val:
                    ws.Cells(row, COL["CY_Close"]).Value = cy_val
                update_count += 1
            except Exception as exc:
                error_count += 1
                print(f"[WARN] si_update error: {exc}", file=sys.stderr)

        wb.Save()

    except Exception as exc:
        _write_result(f"ERROR during sync:\n{exc}")
        sys.exit(0)
    finally:
        if wb is not None:
            wb.Close(SaveChanges=False)
        excel.Quit()

    ts_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    summary = (
        f"Sync Pool — {ts_str}\n\n"
        f"New bookings added : {new_count}\n"
        f"SI/CY updates      : {update_count}\n"
        f"Errors / skipped   : {error_count}\n\n"
        f"Source: {JSONL_PATH.name}\n"
        f"Total events read  : {len(events)}"
    )
    _write_result(summary)


if __name__ == "__main__":
    main()
