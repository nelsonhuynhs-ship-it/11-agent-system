# -*- coding: utf-8 -*-
"""
booking_pool_schema.py — Shared constants for the Booking Pool sheet.

Imported by:
  - scripts/setup-booking-pool-sheet.py   (one-shot sheet creator)
  - email_engine/core/booking_pool_writer.py  (Phase 2 sidecar writer)
  - VBA setup helpers (Phase 3)

Convention: 1-based column indexes (Excel standard).
"""

POOL_SHEET_NAME = "Booking Pool"

# Col indexes (1-based Excel convention)
POOL_COLS: dict[str, int] = {
    "BKG_No": 1,           # A — Primary key
    "Carrier": 2,          # B
    "Customer": 3,         # C
    "POL": 4,              # D
    "POD": 5,              # E
    "Final_Dest": 6,       # F
    "Container": 7,        # G
    "Qty": 8,              # H
    "ETD": 9,              # I
    "ETA": 10,             # J
    "SI_CutOff": 11,       # K
    "CY_Close": 12,        # L
    "Vessel": 13,          # M
    "Voyage": 14,          # N
    "PO_Number": 15,       # O
    "Status": 16,          # P  HOLDING / ASSIGNED / EXPIRED / CANCELLED
    "Link_AJ_Row": 17,     # Q  row number in Active Jobs once assigned
    "Date_Booked": 18,     # R  when Custeam sent the mail
    "Source_Mail_ID": 19,  # S  Outlook EntryID (audit trail)
    "Notes": 20,           # T  free text
}

# Status values
POOL_STATUS_HOLDING = "HOLDING"
POOL_STATUS_ASSIGNED = "ASSIGNED"
POOL_STATUS_EXPIRED = "EXPIRED"
POOL_STATUS_CANCELLED = "CANCELLED"

# Total number of columns (convenience)
POOL_COL_COUNT = len(POOL_COLS)  # 20

# Sidecar JSONL path — Phase 2 booking_pool_writer appends here;
# VBA "Sync Pool" button flushes this into the sheet.
POOL_SIDECAR_PATH = "email_engine/data/booking_pool_state.jsonl"

# Column widths (Excel character units) for setup script
POOL_COL_WIDTHS: dict[str, float] = {
    "BKG_No": 16,
    "Carrier": 10,
    "Customer": 22,
    "POL": 8,
    "POD": 10,
    "Final_Dest": 18,
    "Container": 10,
    "Qty": 6,
    "ETD": 12,
    "ETA": 12,
    "SI_CutOff": 16,
    "CY_Close": 16,
    "Vessel": 20,
    "Voyage": 8,
    "PO_Number": 12,
    "Status": 12,
    "Link_AJ_Row": 12,
    "Date_Booked": 14,
    "Source_Mail_ID": 30,
    "Notes": 30,
}
