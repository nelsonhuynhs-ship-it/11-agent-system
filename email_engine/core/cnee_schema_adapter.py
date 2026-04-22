"""cnee_schema_adapter.py — Normalize v5 vs v6 CNEE schema.

V5 schema (cnee_master_v2_final.xlsx) uses CNEE_EMAIL / CNEE_NAME / CNEE_PIC / CMD_NAME.
V6 schema (contact_unified_v6.xlsx) uses EMAIL / COMPANY / PIC / COMMODITY_CATEGORY.

normalize_schema() returns a DataFrame with both old and new column names present
so downstream code works regardless of source file version.
"""
from __future__ import annotations

import pandas as pd

# Map v5 column names → v6 canonical names.
# Applied only when new name is absent (no-overwrite policy).
V5_TO_V6: dict[str, str] = {
    "CNEE_EMAIL":   "EMAIL",
    "CNEE_NAME":    "COMPANY",
    "CNEE_PIC":     "PIC",
    "CAMPAIGN_ID":  "COMMODITY_CATEGORY",   # fallback if COMMODITY_CATEGORY missing
    "CMD_NAME":     "COMMODITY_CATEGORY",   # legacy alias
}

# Reverse map so v5 callers still find old column names.
V6_TO_V5: dict[str, str] = {
    "EMAIL":                "CNEE_EMAIL",
    "COMPANY":              "CNEE_NAME",
    "PIC":                  "CNEE_PIC",
    "COMMODITY_CATEGORY":   "CMD_NAME",
}


def normalize_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Return df with common column names regardless of v5/v6 source.

    Strategy:
    - If old col present but new col absent → create new col from old.
    - If new col present but old col absent → create old col alias from new.
    This means both CNEE_EMAIL and EMAIL always exist after normalization.
    """
    df = df.copy()

    # v5 → v6 direction
    for old, new in V5_TO_V6.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # v6 → v5 direction (backward compat for old callers)
    for new, old in V6_TO_V5.items():
        if new in df.columns and old not in df.columns:
            df[old] = df[new]

    return df


def email_column(df: pd.DataFrame) -> str:
    """Return the name of the email column present in df (prefer v6 'EMAIL')."""
    if "EMAIL" in df.columns:
        return "EMAIL"
    if "CNEE_EMAIL" in df.columns:
        return "CNEE_EMAIL"
    raise KeyError("No email column (EMAIL / CNEE_EMAIL) found in DataFrame")
