"""
active_jobs_cols.py — single source of truth for Active Jobs v4 column layout
=============================================================================
After the 2026-04-14 mockup migration, Active Jobs uses a visible-19-cols layout
matching plans/260414-email-automation-v3/visuals/active-jobs-layout.html.

Every Python helper and test must import COL from this module — do NOT hard-code
column indices anywhere else. VBA constants in erp-v14-ribbon-callbacks.bas
mirror these values and are kept in sync manually.

Header row: 7    Data row start: 8    Total cols: 40 (19 visible + 21 hidden)
"""
from __future__ import annotations
from typing import Final

HDR_ROW: Final = 7
DATA_START: Final = 8

# ── Visible cols A..S (19) — matches HTML mockup ──
COL: Final = {
    # A..S visible cols
    "MONTH":          1,   # TEXT(ETD, "MMM-YY") — auto-updated on save or via formula
    "FAST_ID":        2,
    "Job_ID":         3,   # internal (e.g. NF-2604-001); manual or auto
    "CRM_ID":         4,   # customer name (keep key name for backward compat)
    "POL_POD":        5,   # "HPH→USLGB" — derived from Routing (stored raw in col 20)
    "Door_Address":   6,   # "FINAL DEST"
    "Carrier":        7,
    "Bkg_No":         8,
    "HBL_NO":         9,
    "Container_Type": 10,  # "CONT"
    "Quantity":       11,  # "QTY"
    "SERVICE":        12,  # CY-CY / CY-DOOR
    "ETD":            13,
    "Status":         14,
    "TRACKING":       15,  # dot-string rendered from TRACKING_STAGE_RAW
    "Selling_Rate":   16,  # "SELL"
    "Buying_Rate":    17,  # "COST"
    "Profit":         18,
    "Request_BKG":    19,  # "EMAIL" mailto link (📧)

    # T..AN hidden cols (21) — preserved data + v4 extras
    "Routing":           20,  # compound "HPH-LAX/LGB" or "HPH-CHICAGO VIA USLAX"
    "ETA":               21,
    "ATA":               22,
    "Contract_Type":     23,
    "Profit_Margin":     24,
    "Customer_Type":     25,
    "SI_Received":       26,
    "CY_Cutoff":         27,
    "Door_Delivery":     28,
    "Door_Status":       29,
    "Delay_Count":       30,
    "Delay_Log":         31,
    "Notes":             32,
    "Created_Date":      33,
    "Last_Updated":      34,
    "Cost_Breakdown":    35,
    "TRACKING_STAGE":    36,  # raw text "5/7 ATD" — source for col 15 display
    "RELEASE_EMAIL_SENT": 37,
    "RELEASE_CONFIRMED":  38,
    "PRICE_WATCH_STATUS": 39,
    "PRICE_WATCH_DELTA":  40,
}

# Last visible col (S)
LAST_VISIBLE_COL: Final = 19
TOTAL_COLS: Final = 40

# Reverse lookup
COL_TO_NAME: Final = {v: k for k, v in COL.items()}


def col_letter(n: int) -> str:
    """1 → 'A', 27 → 'AA'."""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ── Helper: derive MONTH + POL_POD from ETD + Routing ──
def derive_month(etd) -> str:
    """Render 'APR-26' from datetime."""
    if not etd:
        return ""
    try:
        return etd.strftime("%b-%y").upper()
    except Exception:
        return ""


def derive_pol_pod(routing: str) -> str:
    """Render 'HPH→USLGB' or 'HPH→LAX/LGB' from 'HPH-USLGB' or 'HPH-CHICAGO VIA USLAX'."""
    if not routing:
        return ""
    s = str(routing)
    if "-" not in s:
        return s
    pol, tail = s.split("-", 1)
    # If "CHICAGO VIA USLAX" -> show POL→POD (the port)
    if " VIA " in tail.upper():
        idx = tail.upper().rfind(" VIA ")
        pod = tail[idx + 5:].strip()
        return f"{pol.strip()}→{pod}"
    return f"{pol.strip()}→{tail.strip()}"


# ── Helper: render tracking dots ──
_DOT_FULL = "●"
_DOT_EMPTY = "○"
_DOT_PARTIAL = "◐"

STAGE_NAMES: Final = {
    1: "BKG", 2: "Conf", 3: "SI Cut", 4: "Gate-in",
    5: "ATD", 6: "ETA", 7: "Done",
}


def render_tracking_dots(stage_raw: str | int | None) -> str:
    """Turn '5/7 ATD' or int 5 into '●●●●●○○'."""
    if stage_raw is None or stage_raw == "":
        return _DOT_EMPTY * 7
    try:
        if isinstance(stage_raw, int):
            stage = stage_raw
        else:
            # '5/7 ATD' → 5
            stage = int(str(stage_raw).split("/")[0])
    except (ValueError, IndexError):
        return _DOT_EMPTY * 7
    stage = max(0, min(7, stage))
    return _DOT_FULL * stage + _DOT_EMPTY * (7 - stage)
