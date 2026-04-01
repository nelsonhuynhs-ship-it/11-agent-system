# -*- coding: utf-8 -*-
"""
query_engine.py — Sprint Reorg Phase 4
Parquet data loading + query engine. Singleton pattern for in-memory cache.
Reads carrier_rules.json for freetime rules.

Exports:
  load_parquet(force)          -> pd.DataFrame | None
  load_carrier_rules()         -> dict
  query_parquet(parsed, top_n) -> pd.DataFrame | None
  get_parquet_loaded_time()    -> datetime | None
"""
import json
import logging
import os
from datetime import date, datetime

import pandas as pd

logger = logging.getLogger(__name__)

# ── Paths (resolved relative to this file) ────────────────────────────────────
_THIS_DIR      = os.path.dirname(os.path.abspath(__file__))
_ENGINE_DIR    = os.path.join(os.path.dirname(_THIS_DIR), "Pricing_Engine")

PARQUET_FILE       = os.path.join(_ENGINE_DIR, "data", "Cleaned_Master_History.parquet")
CARRIER_RULES_FILE = os.path.join(_ENGINE_DIR, "data", "carrier_rules.json")

# ── Module-level singletons ───────────────────────────────────────────────────
_parquet_df:     pd.DataFrame | None = None
_parquet_loaded: datetime | None     = None
_carrier_rules:  dict                = {}

_CACHE_TTL_SECONDS = 3600   # reload Parquet max once/hour


# Columns needed for rate queries
_RATE_COLUMNS = [
    'POL', 'POD', 'Place', 'Carrier', 'Container_Type',
    'Amount', 'Eff', 'Exp', 'Rate_Type', 'Note',
    'Charge_Name', 'Contract', 'Commodity',
]


def load_parquet(force: bool = False) -> pd.DataFrame | None:
    """
    Load Cleaned_Master_History.parquet, cache active rates (Exp >= today).
    Uses Arrow pushdown filters to avoid loading 10M+ rows into RAM.
    Skips reload if cache is < 1 hour old unless force=True.
    """
    global _parquet_df, _parquet_loaded
    now = datetime.now()

    if (not force
            and _parquet_df is not None
            and _parquet_loaded
            and (now - _parquet_loaded).seconds < _CACHE_TTL_SECONDS):
        return _parquet_df

    if not os.path.exists(PARQUET_FILE):
        logger.warning(f"Parquet not found: {PARQUET_FILE}")
        return None

    try:
        today = pd.Timestamp(date.today())

        try:
            # Arrow pushdown: only read matching rows from disk (no full load)
            df = pd.read_parquet(
                PARQUET_FILE,
                columns=_RATE_COLUMNS,
                filters=[
                    ('Exp', '>=', today),
                    ('Charge_Name', '==', 'Total Ocean Freight'),
                ],
            )
        except Exception:
            # Fallback if pushdown fails (old Parquet format)
            logger.warning("Arrow pushdown failed — falling back to full load")
            df = pd.read_parquet(PARQUET_FILE, columns=_RATE_COLUMNS)
            df['Exp'] = pd.to_datetime(df['Exp'], errors='coerce')
            df = df[
                df['Charge_Name'].str.contains('Total Ocean Freight', na=False) &
                (df['Exp'] >= today)
            ]

        df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
        df = df[df['Amount'] > 900].copy()

        _parquet_df    = df
        _parquet_loaded = now
        logger.info(f"Parquet loaded (pushdown): {len(df):,} active rates (Exp >= {today.date()})")
        return df

    except Exception as exc:
        logger.error(f"Parquet load error: {exc}")
        return None



def load_carrier_rules() -> dict:
    """Load carrier_rules.json (DET/DEM/Power Charge). Cached in-memory."""
    global _carrier_rules
    if _carrier_rules:
        return _carrier_rules
    if not os.path.exists(CARRIER_RULES_FILE):
        logger.warning(f"carrier_rules.json not found: {CARRIER_RULES_FILE}")
        return {}
    try:
        with open(CARRIER_RULES_FILE, encoding='utf-8') as f:
            _carrier_rules = json.load(f)
        logger.info(f"Loaded carrier rules for {len(_carrier_rules)} carriers")
        return _carrier_rules
    except Exception as exc:
        logger.error(f"carrier_rules load error: {exc}")
        return {}


def get_parquet_loaded_time() -> datetime | None:
    """Return when the Parquet was last loaded (for /status display)."""
    return _parquet_loaded


# ── Query engine ──────────────────────────────────────────────────────────────

def query_parquet(parsed: dict, top_n: int = 3) -> pd.DataFrame | None:
    """
    Query the Parquet dataframe using a parsed query dict from query_parser.
    Returns top_n rows sorted by Amount ascending (best price first).
    One row per unique (Carrier, Note) combination.

    Parsed dict keys used:
      pol, pod, carrier, service (SOC/COC/REEFER),
      commodity, container, place_terms
    """
    df = load_parquet()
    if df is None or df.empty:
        return None

    result = df.copy()

    # ── Filter POL ────────────────────────────────────────────────────────────
    if parsed.get('pol'):
        result = result[result['POL'].str.upper().str.strip() == parsed['pol'].upper()]

    # ── Filter carrier ────────────────────────────────────────────────────────
    if parsed.get('carrier'):
        result = result[result['Carrier'].str.upper().str.contains(
            parsed['carrier'].upper(), na=False)]

    # ── Filter POD ───────────────────────────────────────────────────────────
    if parsed.get('pod'):
        result = result[result['POD'].astype(str).str.upper().str.contains(
            parsed['pod'].upper(), na=False)]

    # ── Filter service (SOC / COC / REEFER) ──────────────────────────────────
    if parsed.get('service'):
        svc = parsed['service'].upper()
        if svc == 'SOC':
            result = result[result['Note'].astype(str).str.upper().str.contains(
                'SOC', na=False)]
        elif svc == 'COC':
            result = result[~result['Note'].astype(str).str.upper().str.contains(
                'SOC', na=False)]
        elif svc == 'REEFER':
            result = result[
                result['Note'].astype(str).str.upper().str.contains('REEFER', na=False) |
                result['Commodity'].astype(str).str.upper().str.contains('REEFER', na=False)
            ]

    # ── Filter commodity ─────────────────────────────────────────────────────
    if parsed.get('commodity'):
        result = result[result['Commodity'].astype(str).str.upper().str.contains(
            parsed['commodity'].upper(), na=False)]

    # ── Filter container type (default 40HQ) ─────────────────────────────────
    cont   = parsed.get('container', '40HQ')
    result = result[result['Container_Type'].str.upper() == cont.upper()]

    # ── Filter place terms (fuzzy against Place + POD columns) ───────────────
    for term in (parsed.get('place_terms') or []):
        mask = pd.Series(False, index=result.index)
        for col in ['Place', 'POD']:
            if col in result.columns:
                mask |= result[col].astype(str).str.upper().str.contains(
                    term.upper(), na=False)
        if mask.any():
            result = result[mask]

    if result.empty:
        return None

    # ── Best price per carrier (one row per Carrier+Note, sorted asc) ─────────
    best = (
        result.sort_values('Amount')
              .drop_duplicates(subset=['Carrier', 'Note'], keep='first')
              .sort_values('Amount')
              .head(top_n)
    )
    return best if not best.empty else None
