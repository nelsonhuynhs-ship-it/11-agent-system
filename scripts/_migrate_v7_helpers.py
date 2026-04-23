# -*- coding: utf-8 -*-
"""
scripts/_migrate_v7_helpers.py — Helpers for migrate-to-unified-v7.py
======================================================================
Contains: schema definition, v7 new cols, enrich logic, merge helpers,
          TIER scoring, backup rotation (v7 variant),
          Contact Info sheet parser (shipment-level gold emails).
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Re-export from v6 helpers (avoid duplication) ────────────────────────────
from _panjiva_helpers import (
    SCHEMA_V6_COLS,
    TIER_LOCK_VALUES,
    backup_rotation as _backup_rotation_v6,
    norm_email,
    valid_email,
    MAX_BACKUPS,
)

# ── 5-col LOCK (expanded for multi-channel in v7) ────────────────────────────
LOCKED_COLUMNS: frozenset[str] = frozenset({
    "EMAIL_STATUS",
    "SEND_COUNT",        # legacy single-channel col (v6 rows may have this)
    "SEND_COUNT_EMAIL",
    "SEND_COUNT_WA",
    "SEND_COUNT_LI",
    "LAST_SENT_DATE",    # legacy
    "LAST_SENT_EMAIL",
    "LAST_SENT_WA",
    "LAST_SENT_LI",
    "REPLY_STATUS",
})

LOCKED_IF_TIER: frozenset[str] = frozenset(TIER_LOCK_VALUES)  # CUSTOMER, VIP

# ── 15 new v7 columns (default NaN for v6 rows) ──────────────────────────────
V7_NEW_COLS: list[str] = [
    "REVENUE_USD",
    "EMPLOYEES",
    "TOTAL_SHIPMENTS_ALL",
    "MATCHED_SHIPMENTS",
    "PARENT_COMPANY",
    "DUNS",
    "PIC_NAME",
    "PIC_POSITION",
    "TOP_SUPPLIERS",
    "TOP_PRODUCTS",
    "LAST_SHIPMENT_DATE",
    "ROUTE_DESC",
    "PANJIVA_URL",
    "WEBSITE",
    "CITY",
    "ZIP",
    "COUNTRY_DEST",
    "POL_LIST",
    "ORIGIN_COUNTRIES",
    "MULTI_ORIGIN",
    "PRIMARY_POL",
    "TIER_AUTO_SCORE",
]

# Build v7 schema: v6 cols + new cols (dedup, order preserved)
_seen_v7: set[str] = set()
SCHEMA_V7_COLS: list[str] = [
    c for c in (SCHEMA_V6_COLS + V7_NEW_COLS)
    if not (_seen_v7.add(c) or c in _seen_v7 - {c})
]


# ── Backup rotation for v7 ────────────────────────────────────────────────────

def backup_rotation_v7(target_file: Path, backup_dir: Path) -> Optional[Path]:
    """Copy target_file to backup_dir with v7 timestamp suffix; keep last 14 copies."""
    if not target_file.exists():
        return None
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    backup_name = f"contact_unified_v7.backup_{ts}.xlsx"
    backup_path = backup_dir / backup_name
    shutil.copy2(target_file, backup_path)

    all_backups = sorted(
        backup_dir.glob("contact_unified_v7.backup_*.xlsx"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in all_backups[MAX_BACKUPS:]:
        old.unlink(missing_ok=True)

    return backup_path


# ── Schema migration: add v7 cols to existing v6 DataFrame ───────────────────

def add_v7_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add all V7_NEW_COLS to df with empty string default (preserves v6 data)."""
    df = df.copy()
    for col in V7_NEW_COLS:
        if col not in df.columns:
            df[col] = ""
    return df


def align_to_v7_schema(df: pd.DataFrame, sheet: str = "CNEE") -> pd.DataFrame:
    """Ensure df has all v7 schema cols in order. Missing → "". Extra → dropped."""
    df = add_v7_columns(df)
    for col in SCHEMA_V7_COLS:
        if col not in df.columns:
            df[col] = ""

    if "ACTIVATE_GATE" in df.columns:
        default_gate = "HOLD" if sheet == "SHIPPER" else "ACTIVE"
        mask_empty = df["ACTIVATE_GATE"].replace("", None).isna()
        df.loc[mask_empty, "ACTIVATE_GATE"] = default_gate

    return df[SCHEMA_V7_COLS].copy()


# ── Enrichment: fill v6 row with Panjiva firmographic data ───────────────────

def enrich_row(v6_row: pd.Series, panjiva_row: pd.Series) -> tuple[pd.Series, list[str]]:
    """Merge panjiva_row into v6_row with LOCKED_COLUMNS protection.

    Strategy: only fill if current cell is empty/NaN. Never overwrite locked cols.
    TIER is locked when existing value is CUSTOMER or VIP.

    Returns (updated_row, list_of_changed_cols).
    """
    result = v6_row.copy()
    changed: list[str] = []

    for col, new_val in panjiva_row.items():
        if col in LOCKED_COLUMNS:
            continue
        if col == "TIER":
            current_tier = str(result.get("TIER", "") or "").strip().upper()
            if current_tier in LOCKED_IF_TIER:
                continue

        # Special merge cols
        if col in ("POL_LIST", "POL"):
            result["POL_LIST"] = merge_pol_list(
                str(result.get("POL_LIST", "") or ""),
                str(new_val or ""),
            )
            if result["POL_LIST"] != str(v6_row.get("POL_LIST", "") or ""):
                changed.append("POL_LIST")
            continue

        if col == "COMMODITY_CATEGORY":
            merged = merge_commodity_category(
                str(result.get("COMMODITY_CATEGORY", "") or ""),
                str(new_val or ""),
            )
            if merged != str(result.get("COMMODITY_CATEGORY", "") or ""):
                result["COMMODITY_CATEGORY"] = merged
                changed.append("COMMODITY_CATEGORY")
            continue

        if col == "ORIGIN_COUNTRIES":
            merged = merge_pol_list(
                str(result.get("ORIGIN_COUNTRIES", "") or ""),
                str(new_val or ""),
            )
            if merged != str(result.get("ORIGIN_COUNTRIES", "") or ""):
                result["ORIGIN_COUNTRIES"] = merged
                changed.append("ORIGIN_COUNTRIES")
            continue

        # Default: fill only if current is empty
        current = result.get(col)
        is_empty = (
            current is None
            or current == ""
            or (isinstance(current, float) and pd.isna(current))
            or str(current).strip() in ("", "nan", "NaN", "None")
        )
        if is_empty and new_val is not None and str(new_val).strip() not in ("", "nan", "NaN"):
            result[col] = new_val
            changed.append(col)

    return result, changed


# ── Multi-origin merge helpers ────────────────────────────────────────────────

def merge_pol_list(v6_pol: str, panjiva_pol: str) -> str:
    """Union unique POLs/origins from both sources, sorted alphabetically."""
    def _split(s: str) -> set[str]:
        return {p.strip() for p in s.split(",") if p.strip()} if s else set()

    union = sorted(_split(v6_pol) | _split(panjiva_pol))
    return ",".join(union)


def merge_commodity_category(v6_cat: str, panjiva_cat: str) -> str:
    """Union unique commodity categories — buyer may import multiple commodity types."""
    def _split(s: str) -> set[str]:
        return {p.strip() for p in s.split(",") if p.strip()} if s else set()

    union = sorted(_split(v6_cat) | _split(panjiva_cat))
    return ",".join(union)


# ── Matching: Panjiva row → v6 row ───────────────────────────────────────────

def _fuzzy_score(name_a: str, name_b: str) -> float:
    """Compare two company names. Returns 0.0–1.0. Uses rapidfuzz if available."""
    a = re.sub(r"[^A-Z0-9 ]", "", (name_a or "").upper().strip())
    b = re.sub(r"[^A-Z0-9 ]", "", (name_b or "").upper().strip())
    if not a or not b:
        return 0.0
    try:
        from rapidfuzz.fuzz import WRatio  # type: ignore[import]
        return WRatio(a, b) / 100.0
    except ImportError:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()


def match_panjiva_to_v6(
    panjiva_row: dict,
    v6_df: pd.DataFrame,
    email_index: dict[str, int],
    domain_index: dict[str, list[int]],
    threshold: float = 0.85,
) -> tuple[Optional[int], str]:
    """Return (v6_row_index, match_type) or (None, 'NEW').

    Match order:
      1. Exact EMAIL (lowercase, strip) — primary key
      2. Fuzzy COMPANY name (WRatio >= threshold)
      3. Email domain + fuzzy company (weak, flag for review)
    """
    em = norm_email(panjiva_row.get("EMAIL", "") or "")

    # Match 1: Exact email
    if em and em in email_index:
        return email_index[em], "EMAIL_EXACT"

    # Match 2: Fuzzy company name against all v6 rows
    panjiva_company = (panjiva_row.get("COMPANY", "") or "").strip()
    if panjiva_company and "COMPANY" in v6_df.columns:
        best_idx: Optional[int] = None
        best_score = 0.0
        for idx, v6_company in v6_df["COMPANY"].items():
            score = _fuzzy_score(panjiva_company, str(v6_company or ""))
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_score >= threshold and best_idx is not None:
            return best_idx, "COMPANY_FUZZY"

    # Match 3: Domain + fuzzy company (weak match)
    if em and "@" in em:
        domain = em.split("@", 1)[1]
        candidates = domain_index.get(domain, [])
        for idx in candidates:
            v6_company = str(v6_df.at[idx, "COMPANY"] if "COMPANY" in v6_df.columns else "")
            score = _fuzzy_score(panjiva_company, v6_company)
            if score >= threshold * 0.80:  # relaxed threshold for domain match
                return idx, "DOMAIN_FUZZY"

    return None, "NEW"


def build_email_index(df: pd.DataFrame) -> tuple[dict[str, int], dict[str, list[int]]]:
    """Build email_index + domain_index from df for fast lookup."""
    email_index: dict[str, int] = {}
    domain_index: dict[str, list[int]] = {}

    for idx, email_raw in df["EMAIL"].items():
        em = norm_email(str(email_raw or ""))
        if not em or "@" not in em:
            continue
        if em not in email_index:
            email_index[em] = idx
        domain = em.split("@", 1)[1]
        domain_index.setdefault(domain, []).append(idx)

    return email_index, domain_index


# ── TIER auto-scoring ─────────────────────────────────────────────────────────

def compute_tier_auto_score(row: pd.Series) -> str:
    """Derive a TIER string from firmographic data.

    Does NOT override CUSTOMER/VIP — caller must check that before applying.

    Score bands:
      HOT  : revenue > 10M OR total_shipments > 100
      WARM : revenue > 1M  OR total_shipments > 20
      COLD : otherwise
    """
    try:
        revenue = float(str(row.get("REVENUE_USD", "") or "0").replace(",", "") or 0)
    except (ValueError, TypeError):
        revenue = 0.0
    try:
        shipments = float(str(row.get("TOTAL_SHIPMENTS_ALL", "") or "0").replace(",", "") or 0)
    except (ValueError, TypeError):
        shipments = 0.0

    if revenue > 10_000_000 or shipments > 100:
        return "HOT"
    if revenue > 1_000_000 or shipments > 20:
        return "WARM"
    return "COLD"


def apply_tier_auto_score(df: pd.DataFrame) -> pd.DataFrame:
    """Compute TIER_AUTO_SCORE for all rows. Never overrides TIER if CUSTOMER/VIP."""
    df = df.copy()
    scores = df.apply(compute_tier_auto_score, axis=1)
    df["TIER_AUTO_SCORE"] = scores

    # Promote TIER only if current TIER is empty
    if "TIER" in df.columns:
        mask_empty_tier = df["TIER"].replace("", None).isna() | (df["TIER"].str.strip() == "")
        df.loc[mask_empty_tier, "TIER"] = df.loc[mask_empty_tier, "TIER_AUTO_SCORE"]

    return df


# ── Panjiva batch dedup (across multiple files) ───────────────────────────────

def dedup_panjiva_batch(combined: pd.DataFrame) -> pd.DataFrame:
    """Dedup within combined Panjiva batch before matching against v6.

    Strategy: group by EMAIL. Merge commodity + POL lists. Keep first row's
    firmographic data (highest total_shipments wins).
    """
    if combined.empty:
        return combined

    if "EMAIL" not in combined.columns:
        return combined

    combined = combined.copy()
    combined["_em"] = combined["EMAIL"].apply(norm_email)

    # Split: rows with valid email vs rows without
    mask_valid = combined["_em"].str.contains("@", na=False)
    valid_df = combined[mask_valid].copy()
    invalid_df = combined[~mask_valid].copy()

    if valid_df.empty:
        combined.drop(columns=["_em"], inplace=True)
        return combined

    # Sort: highest shipments first so first-row wins on firmographic data
    try:
        valid_df["_ships"] = pd.to_numeric(valid_df.get("TOTAL_SHIPMENTS_ALL", pd.Series(dtype=str)), errors="coerce").fillna(0)
        valid_df = valid_df.sort_values("_ships", ascending=False)
        valid_df.drop(columns=["_ships"], inplace=True)
    except Exception:
        pass

    # Aggregate commodities and POL lists per email
    def _agg(group: pd.DataFrame) -> pd.Series:
        first = group.iloc[0].copy()
        if len(group) > 1:
            cats = ",".join(str(v) for v in group.get("COMMODITY_CATEGORY", pd.Series()).dropna() if v)
            pols = ",".join(str(v) for v in group.get("POL_LIST", pd.Series()).dropna() if v)
            origins = ",".join(str(v) for v in group.get("ORIGIN_COUNTRIES", pd.Series()).dropna() if v)
            first["COMMODITY_CATEGORY"] = merge_commodity_category("", cats)
            first["POL_LIST"] = merge_pol_list("", pols)
            first["ORIGIN_COUNTRIES"] = merge_pol_list("", origins)
        return first

    agg_df = valid_df.groupby("_em", sort=False).apply(_agg).reset_index(drop=True)
    agg_df.drop(columns=["_em"], errors="ignore", inplace=True)

    # Re-attach rows without valid email (pass-through)
    invalid_df.drop(columns=["_em"], errors="ignore", inplace=True)
    result = pd.concat([agg_df, invalid_df], ignore_index=True)
    return result


# ── Contact Info sheet → v7 rows ──────────────────────────────────────────────

def parse_contact_info_to_v7_rows(
    contacts_df: pd.DataFrame,
    aggregated_df: pd.DataFrame,
    commodity_hint: str = "",
    origin_country_hint: str = "",
    source_file: str = "",
) -> pd.DataFrame:
    """Convert Contact Info sheet rows → v7-schema rows.

    Contact Info sheet columns (Panjiva standard):
      Company, Contact Type, Contact Name, Position, Email, Phone,
      Profile URL, Company URL

    Strategy:
    - 1 contact row = 1 output row (multi-PIC per company OK)
    - Skip rows without valid email
    - Enrich firmographic from aggregated_df by fuzzy company name match
    - Source tag: PANJIVA_CONTACT

    Args:
        contacts_df:     Raw Contact Info sheet DataFrame
        aggregated_df:   Aggregated CNEE rows from same shipment file
        commodity_hint:  Commodity category string
        origin_country_hint: ISO 2-letter origin country
        source_file:     Source filename for audit trail

    Returns:
        DataFrame with v7 schema columns. Empty if no valid emails.
    """
    if contacts_df.empty:
        return pd.DataFrame(columns=SCHEMA_V7_COLS)

    # ── Normalize column names (case-insensitive) ─────────────────────────────
    col_map: dict[str, str] = {}
    for col in contacts_df.columns:
        cl = col.strip().lower()
        if cl == "company":
            col_map[col] = "COMPANY"
        elif cl in ("contact name", "name"):
            col_map[col] = "PIC_NAME"
        elif cl == "position":
            col_map[col] = "PIC_POSITION"
        elif cl == "email":
            col_map[col] = "EMAIL"
        elif cl == "phone":
            col_map[col] = "PHONE_PRIMARY"
        elif cl in ("profile url", "panjiva url"):
            col_map[col] = "PANJIVA_URL"
        elif cl in ("company url", "website"):
            col_map[col] = "WEBSITE"

    df = contacts_df.rename(columns=col_map).copy()

    # Ensure required columns exist
    for req_col in ("EMAIL", "COMPANY", "PIC_NAME", "PIC_POSITION"):
        if req_col not in df.columns:
            df[req_col] = ""

    # ── Build aggregated lookup dict: COMPANY_NORM → row dict ────────────────
    agg_lookup: dict[str, dict] = {}
    if not aggregated_df.empty and "COMPANY" in aggregated_df.columns:
        for _, agg_row in aggregated_df.iterrows():
            co_norm = re.sub(r"[^A-Z0-9 ]", "", str(agg_row.get("COMPANY", "") or "").upper().strip())
            if co_norm:
                agg_lookup[co_norm] = agg_row.to_dict()

    def _agg_lookup_fuzzy(company: str) -> dict:
        """Find best matching aggregated row by normalized company name."""
        co_norm = re.sub(r"[^A-Z0-9 ]", "", (company or "").upper().strip())
        if not co_norm:
            return {}
        # Exact match first
        if co_norm in agg_lookup:
            return agg_lookup[co_norm]
        # Prefix match (e.g. "ADIDAS AMERICA" matches "ADIDAS AMERICA INC")
        for key, val in agg_lookup.items():
            if co_norm in key or key in co_norm:
                return val
        return {}

    # ── Build output rows ─────────────────────────────────────────────────────
    rows: list[dict] = []
    import_date = datetime.now().strftime("%Y-%m-%d")

    for _, row in df.iterrows():
        email_raw = str(row.get("EMAIL", "") or "").strip().lower()
        if not valid_email(email_raw):
            continue

        company = str(row.get("COMPANY", "") or "").strip()
        pic_name = str(row.get("PIC_NAME", "") or "").strip()
        pic_pos = str(row.get("PIC_POSITION", "") or "").strip()
        phone = str(row.get("PHONE_PRIMARY", "") or "").strip()
        panjiva_url = str(row.get("PANJIVA_URL", "") or "").strip()
        website = str(row.get("WEBSITE", "") or "").strip()

        # Firmographic enrichment from aggregated shipment data
        agg = _agg_lookup_fuzzy(company)

        new_row: dict = {col: "" for col in SCHEMA_V7_COLS}
        new_row["EMAIL"]              = email_raw
        new_row["COMPANY"]           = company
        new_row["PIC_NAME"]          = pic_name
        new_row["PIC_POSITION"]      = pic_pos
        new_row["PHONE_PRIMARY"]     = phone
        new_row["PANJIVA_URL"]       = panjiva_url or agg.get("PANJIVA_URL", "")
        new_row["WEBSITE"]           = website or agg.get("WEBSITE", "")
        new_row["COMMODITY_CATEGORY"] = commodity_hint.upper() if commodity_hint else ""
        new_row["ORIGIN_COUNTRY"]    = origin_country_hint.upper() if origin_country_hint else ""
        new_row["ORIGIN_COUNTRIES"]  = agg.get("ORIGIN_COUNTRIES", origin_country_hint.upper() if origin_country_hint else "")
        new_row["POL_LIST"]          = agg.get("POL_LIST", "")
        new_row["PRIMARY_POL"]       = agg.get("PRIMARY_POL", "")
        new_row["MULTI_ORIGIN"]      = agg.get("MULTI_ORIGIN", False)
        new_row["TOP_CARRIER"]       = agg.get("TOP_CARRIER", "") if "TOP_CARRIER" in SCHEMA_V7_COLS else ""
        new_row["TOTAL_SHIPMENTS_ALL"] = agg.get("TOTAL_SHIPMENTS_ALL", "")
        new_row["LAST_SHIPMENT_DATE"]  = agg.get("LAST_SHIPMENT_DATE", "")
        new_row["ADDRESS"]           = agg.get("ADDRESS", "")
        new_row["STATE"]             = agg.get("STATE", "")
        new_row["CITY"]              = agg.get("CITY", "")
        new_row["ZIP"]               = agg.get("ZIP", "")
        new_row["COUNTRY_DEST"]      = agg.get("COUNTRY_DEST", "US")
        new_row["EMAIL_STATUS"]      = "NEW"
        new_row["SEND_COUNT"]        = "0"
        new_row["SEND_COUNT_EMAIL"]  = "0"
        new_row["SEND_COUNT_WA"]     = "0"
        new_row["SEND_COUNT_LI"]     = "0"
        new_row["ACTIVATE_GATE"]     = "ACTIVE"
        new_row["SHEET"]             = "CNEE"
        new_row["SOURCE_TAG"]        = "PANJIVA_CONTACT"
        new_row["IMPORT_DATE"]       = import_date
        new_row["TIER"]              = ""  # set by TIER_AUTO_SCORE step

        rows.append(new_row)

    if not rows:
        return pd.DataFrame(columns=SCHEMA_V7_COLS)

    result = pd.DataFrame(rows)
    # Ensure all schema cols present
    for col in SCHEMA_V7_COLS:
        if col not in result.columns:
            result[col] = ""
    return result[[c for c in SCHEMA_V7_COLS if c in result.columns]].reset_index(drop=True)
