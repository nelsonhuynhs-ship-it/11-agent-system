"""
price_watch.py — Price Watch / Re-quote Alert (Active Jobs v4 Feature 1)
=========================================================================
Monitors PENDING quotes in ERP_Master_v14.xlsm against latest Pricing Dry/Reefer.
When a carrier's buy price DROPS below the quoted buy rate by >= threshold,
fires a re-quote alert — Nelson can resend a lower offer to win the deal.

Inputs (ERP_Master_v14.xlsm):
  - Quotes sheet (42 cols, headers row 1): PENDING = Status blank or not WIN/LOST/EXPIRED
  - Pricing Dry (14+ cols) / Pricing Reefer — latest buy rates per POL/POD/Carrier/Cont

Outputs:
  - Fills Quotes Status cell yellow/red based on delta vs current buy
  - Creates/refreshes "Price_Watch" sheet listing alerts sorted by priority
  - Stamps Active Jobs col 35 (PRICE_WATCH_STATUS) + col 36 (PRICE_WATCH_DELTA)
    for WIN-converted quotes whose rate moved post-WIN

Usage:
    python ERP/intelligence/price_watch.py
    python ERP/intelligence/price_watch.py --threshold 50
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Final

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "core"))
from ribbon_guard import save_preserving_ribbon  # noqa: E402
from active_jobs_cols import COL as AJ_COL  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

DEFAULT_ERP_FILE: Final = r"D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm"

# Quotes sheet (header row 1)
Q_COL: Final = {
    "QuoteID": 1, "Date": 2, "Customer": 3, "Carrier": 4,
    "POL": 5, "POD": 6, "Place": 7, "Via": 8,
    "Eff": 9, "Exp": 10, "Source": 11,
    "Buy_20GP": 12, "Buy_40GP": 13, "Buy_40HC": 14, "Buy_45HC": 15,
    "Buy_40NOR": 16, "Buy_20RF": 17, "Buy_40RF": 18,
    "Sell_20GP": 29, "Sell_40GP": 30, "Sell_40HC": 31, "Sell_45HC": 32,
    "Sell_40NOR": 33, "Sell_20RF": 34, "Sell_40RF": 35,
    "Status": 36, "Remark": 37, "StatusDate": 38,
    "Qty": 39, "Volume": 40, "JobID": 41, "ContType": 42,
}

# Pricing Dry/Reefer sheet (header row 1)
P_COL: Final = {
    "POL": 1, "POD": 2, "Place": 3, "Carrier": 4, "Commodity": 5,
    "Eff": 6, "Exp": 7, "Note": 8, "Source": 9,
    "20GP": 10, "40GP": 11, "40HQ": 12, "45HQ": 13, "40NOR": 14,
    "20RF": 10, "40RF": 11,  # Reefer sheet uses different positions
}

CONT_TO_BUY_COL: Final = {
    "20GP": "Buy_20GP", "40GP": "Buy_40GP", "40HC": "Buy_40HC",
    "40HQ": "Buy_40HC", "45HC": "Buy_45HC", "45HQ": "Buy_45HC",
    "40NOR": "Buy_40NOR", "20RF": "Buy_20RF", "40RF": "Buy_40RF",
}
CONT_TO_PRICE_COL: Final = {
    "20GP": ("Dry", "20GP"), "40GP": ("Dry", "40GP"),
    "40HC": ("Dry", "40HQ"), "40HQ": ("Dry", "40HQ"),
    "45HC": ("Dry", "45HQ"), "45HQ": ("Dry", "45HQ"),
    "40NOR": ("Dry", "40NOR"),
    "20RF": ("Reefer", "20RF"), "40RF": ("Reefer", "40RF"),
}


@dataclass
class Alert:
    quote_id: str
    row: int
    customer: str
    route: str
    carrier: str
    cont_type: str
    quoted_buy: float
    current_buy: float
    delta: float
    kind: str  # DROP | RISE | NO_MATCH
    priority: str  # P1 | P2 | P3
    action: str


# ── Loaders ──
def load_latest_pricing(wb) -> dict:
    """Return dict: (pol, pod, place, carrier, cont_type) → (buy, eff_date, source)."""
    out: dict[tuple, tuple[float, datetime | None, str]] = {}

    def _ingest(sheet_name: str, cont_cols: dict[str, int]) -> int:
        if sheet_name not in wb.sheetnames:
            return 0
        ws = wb[sheet_name]
        n = 0
        for r in range(2, ws.max_row + 1):
            pol = (ws.cell(r, 1).value or "")
            if not pol:
                continue
            pod = (ws.cell(r, 2).value or "")
            place = (ws.cell(r, 3).value or "")
            carrier = (ws.cell(r, 4).value or "")
            eff = ws.cell(r, 6).value
            source = ws.cell(r, 9).value or ""
            for cont, col in cont_cols.items():
                val = ws.cell(r, col).value
                if not isinstance(val, (int, float)) or val <= 0:
                    continue
                key = (str(pol).upper().strip(),
                       str(pod).upper().strip(),
                       str(place).upper().strip(),
                       str(carrier).upper().strip(),
                       cont)
                prev = out.get(key)
                # keep the most recent eff date
                if prev is None or (isinstance(eff, datetime)
                                    and (not isinstance(prev[1], datetime) or eff > prev[1])):
                    out[key] = (float(val), eff if isinstance(eff, datetime) else None, str(source))
                n += 1
        return n

    n_dry = _ingest("Pricing Dry", {"20GP": 10, "40GP": 11, "40HC": 12, "45HC": 13, "40NOR": 14})
    n_rf = _ingest("Pricing Reefer", {"20RF": 10, "40RF": 11})
    print(f"    -> pricing scanned: dry={n_dry} reefer={n_rf} unique_keys={len(out)}")
    return out


def iter_pending_quotes(wb):
    """Yield (row_idx, quote_dict) for PENDING quotes (Status not WIN/LOST/EXPIRED/blank is PENDING)."""
    ws = wb["Quotes"]
    for r in range(2, ws.max_row + 1):
        qid = ws.cell(r, Q_COL["QuoteID"]).value
        if not qid:
            continue
        status = (ws.cell(r, Q_COL["Status"]).value or "").strip().upper()
        if status in ("LOST", "EXPIRED"):
            continue
        # "" (blank) and "WIN" both matter: blank = pending re-quote; WIN = monitor for post-WIN moves
        q = {k: ws.cell(r, c).value for k, c in Q_COL.items()}
        q["_row"] = r
        q["_status"] = status or "PENDING"
        yield r, q


# ── Comparison ──
def compute_alerts(quotes, pricing_latest: dict, threshold: float) -> list[Alert]:
    alerts: list[Alert] = []
    for row, q in quotes:
        qid = str(q.get("QuoteID") or "").strip()
        carrier = str(q.get("Carrier") or "").upper().strip()
        pol = str(q.get("POL") or "").upper().strip()
        pod = str(q.get("POD") or "").upper().strip()
        place = str(q.get("Place") or "").upper().strip()
        cust = str(q.get("Customer") or "")

        # For each container type the quote has a Buy rate for
        for cont, buy_key in CONT_TO_BUY_COL.items():
            quoted = q.get(buy_key)
            if not isinstance(quoted, (int, float)) or quoted <= 0:
                continue

            _, price_cont = CONT_TO_PRICE_COL[cont]
            # Exact match: POL + POD + Place + Carrier + Cont
            key = (pol, pod, place, carrier, price_cont)
            cur = pricing_latest.get(key)
            if cur is None:
                # Fallback 1: same POL/POD/Carrier/Cont, Place == POD (direct port, no inland)
                key2 = (pol, pod, pod, carrier, price_cont)
                cur = pricing_latest.get(key2)
            if cur is None:
                # Fallback 2: fuzzy carrier — "ONE" ⊂ "Ocean Network Express"
                matches = [v for k, v in pricing_latest.items()
                           if k[0] == pol and k[1] == pod and k[2] == place
                           and k[4] == price_cont
                           and carrier and (carrier in k[3] or k[3] in carrier)]
                if not matches:
                    continue
                cur = matches[0]

            current_buy = cur[0]
            delta = current_buy - float(quoted)  # negative = price dropped

            if abs(delta) < threshold:
                continue

            if delta < 0:
                alerts.append(Alert(
                    quote_id=qid, row=row, customer=cust,
                    route=f"{pol}-{pod}", carrier=carrier, cont_type=cont,
                    quoted_buy=float(quoted), current_buy=current_buy,
                    delta=delta, kind="DROP",
                    priority="P1" if q["_status"] == "PENDING" else "P2",
                    action=f"Re-quote {cust}: buy dropped ${abs(delta):,.0f} ({cont})",
                ))
            else:
                alerts.append(Alert(
                    quote_id=qid, row=row, customer=cust,
                    route=f"{pol}-{pod}", carrier=carrier, cont_type=cont,
                    quoted_buy=float(quoted), current_buy=current_buy,
                    delta=delta, kind="RISE",
                    priority="P2" if q["_status"] == "WIN" else "P3",
                    action=f"⚠ Cost rose ${delta:,.0f} ({cont}) — margin squeeze",
                ))
    return alerts


# ── Writers ──
FILL_ALERT = PatternFill("solid", fgColor="FEE2E2")
FILL_WARN = PatternFill("solid", fgColor="FEF3C7")
FILL_OK = PatternFill("solid", fgColor="D1FAE5")
THIN = Side(style="thin", color="888888")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def stamp_quotes_sheet(wb, alerts: list[Alert]):
    """Color the Status cell of each alerted quote row."""
    ws = wb["Quotes"]
    touched_rows: set[int] = set()
    by_row: dict[int, list[Alert]] = {}
    for a in alerts:
        by_row.setdefault(a.row, []).append(a)
    for r, row_alerts in by_row.items():
        # strongest signal = max priority drop
        has_drop = any(a.kind == "DROP" for a in row_alerts)
        cell = ws.cell(r, Q_COL["Status"])
        cell.fill = FILL_ALERT if has_drop else FILL_WARN
        # Remark col: prepend alert
        remark_cell = ws.cell(r, Q_COL["Remark"])
        note = "; ".join(f"{a.kind}:{a.cont_type}:${a.delta:+,.0f}" for a in row_alerts)
        existing = (remark_cell.value or "").strip()
        tag = f"[PW {datetime.now():%d%b %H:%M}] {note}"
        if existing and not existing.startswith("[PW "):
            remark_cell.value = f"{tag} | {existing}"
        else:
            remark_cell.value = tag
        touched_rows.add(r)
    return touched_rows


def write_price_watch_sheet(wb, alerts: list[Alert]):
    """Create/refresh Price_Watch summary sheet."""
    if "Price_Watch" in wb.sheetnames:
        del wb["Price_Watch"]
    ws = wb.create_sheet("Price_Watch")

    # Title
    ws.merge_cells("A1:J1")
    ws["A1"] = f"PRICE WATCH — {datetime.now():%d %b %Y %H:%M}"
    ws["A1"].font = Font(bold=True, size=14, color="1F4E79")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 24

    # Headers
    hdrs = ["Priority", "Kind", "QuoteID", "Customer", "Route",
            "Carrier", "Cont", "Quoted Buy", "Current Buy", "Δ Delta"]
    for i, h in enumerate(hdrs, 1):
        c = ws.cell(3, i, h)
        c.font = Font(bold=True, color="FFFFFF", size=10, name="Segoe UI")
        c.fill = PatternFill("solid", fgColor="1F4E79")
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER
    widths = [10, 8, 12, 18, 14, 12, 8, 12, 12, 12]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    # Sort by priority then absolute delta
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    alerts_sorted = sorted(alerts, key=lambda a: (priority_order.get(a.priority, 9), -abs(a.delta)))

    for r, a in enumerate(alerts_sorted, start=4):
        row = [a.priority, a.kind, a.quote_id, a.customer, a.route,
               a.carrier, a.cont_type, a.quoted_buy, a.current_buy, a.delta]
        for i, v in enumerate(row, 1):
            cell = ws.cell(r, i, v)
            cell.font = Font(size=10, name="Segoe UI")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = BORDER
            if i in (8, 9, 10):
                cell.number_format = '"$"#,##0'
        # color row by priority
        fill = FILL_ALERT if a.priority == "P1" else FILL_WARN if a.priority == "P2" else None
        if fill:
            for i in range(1, 11):
                ws.cell(r, i).fill = fill
        # color delta green if drop (good) / red if rise (bad)
        dc = ws.cell(r, 10)
        dc.font = Font(size=10, name="Segoe UI", bold=True,
                       color="00804A" if a.delta < 0 else "C00000")

    ws.freeze_panes = "A4"


def stamp_active_jobs(wb, alerts: list[Alert]):
    """Write PRICE_WATCH_STATUS (col 35) + PRICE_WATCH_DELTA (col 36) for WIN quotes linked to Active Jobs."""
    if "Active Jobs" not in wb.sheetnames:
        return 0
    ws = wb["Active Jobs"]
    # Build map: quote_id → [alerts]
    by_qid: dict[str, list[Alert]] = {}
    for a in alerts:
        by_qid.setdefault(a.quote_id, []).append(a)

    # Active Jobs rows: match via Bkg_No (col 4) OR Notes (col 24) referencing Quote_ID?
    # Actually the quote has JobID (col 41) which is the Active Jobs Job_ID (Nelson uses CRM_ID col 1 as Job_ID in v14).
    # For now match by customer name via CRM_ID.
    stamped = 0
    for r in range(8, ws.max_row + 1):
        crm = ws.cell(r, AJ_COL["CRM_ID"]).value
        if not crm:
            continue
        # Find any alert whose customer name matches CRM_ID (best-effort)
        crm_up = str(crm).upper().strip()
        matched = []
        for a in alerts:
            if a.customer and a.customer.upper().strip() in crm_up:
                matched.append(a)
            elif crm_up in (a.customer or "").upper().strip():
                matched.append(a)
        if not matched:
            continue
        # Strongest signal: largest magnitude drop = most actionable
        drops = [a for a in matched if a.kind == "DROP"]
        pick = max(drops, key=lambda a: abs(a.delta)) if drops else min(matched, key=lambda a: -abs(a.delta))
        ws.cell(r, AJ_COL["PRICE_WATCH_STATUS"], pick.kind)
        ws.cell(r, AJ_COL["PRICE_WATCH_DELTA"], round(pick.delta))
        ws.cell(r, AJ_COL["PRICE_WATCH_STATUS"]).fill = FILL_ALERT if pick.kind == "DROP" else FILL_WARN
        stamped += 1
    return stamped


# ── Main ──
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--erp", default=DEFAULT_ERP_FILE)
    ap.add_argument("--threshold", type=float, default=50.0,
                    help="Minimum |buy delta| in USD to trigger alert (default: 50)")
    args = ap.parse_args()

    if not os.path.exists(args.erp):
        print(f"[ERROR] ERP file not found: {args.erp}")
        return 1
    try:
        with open(args.erp, "r+b"):
            pass
    except PermissionError:
        print(f"[ERROR] ERP file is open in Excel. Close it first.")
        return 2

    print(f"[+] Price Watch run @ {datetime.now():%Y-%m-%d %H:%M}")
    wb = openpyxl.load_workbook(args.erp, keep_vba=True)

    pricing = load_latest_pricing(wb)
    quotes = list(iter_pending_quotes(wb))
    print(f"    -> quotes to inspect: {len(quotes)}")

    alerts = compute_alerts(quotes, pricing, args.threshold)
    drops = [a for a in alerts if a.kind == "DROP"]
    rises = [a for a in alerts if a.kind == "RISE"]
    print(f"    -> alerts: {len(alerts)} (DROP={len(drops)} RISE={len(rises)})")

    if alerts:
        stamp_quotes_sheet(wb, alerts)
        write_price_watch_sheet(wb, alerts)
        stamped_aj = stamp_active_jobs(wb, alerts)
        print(f"    -> stamped {stamped_aj} Active Jobs row(s)")
    else:
        # Still refresh Price_Watch sheet so stale alerts are cleared
        if "Price_Watch" in wb.sheetnames:
            del wb["Price_Watch"]
        ws = wb.create_sheet("Price_Watch")
        ws["A1"] = f"Price Watch — No alerts as of {datetime.now():%d %b %Y %H:%M}"
        ws["A1"].font = Font(italic=True, color="666666")

    result = save_preserving_ribbon(wb, args.erp)
    wb.close()
    print(f"[OK] ERP saved: {args.erp}  (ribbon: {result})")

    # Print top 5 alerts
    if alerts:
        print("\nTop alerts:")
        priority_order = {"P1": 0, "P2": 1, "P3": 2}
        for a in sorted(alerts, key=lambda a: (priority_order.get(a.priority, 9), -abs(a.delta)))[:5]:
            arrow = "↓" if a.delta < 0 else "↑"
            print(f"  [{a.priority}] {a.quote_id} {a.customer[:16]:16s} {a.route:12s} "
                  f"{a.carrier:6s} {a.cont_type:5s} {arrow}${abs(a.delta):>6,.0f}  {a.action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
