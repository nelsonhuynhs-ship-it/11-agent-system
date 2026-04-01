# -*- coding: utf-8 -*-
"""
rate_router.py — Rate Endpoints (DuckDB-powered)
====================================================
All pricing/rate-related endpoints.
Data access via FreightDB (DuckDB) for Parquet queries
and dal for carrier rules (JSON).

Migration: Replaced all Pandas Parquet reads via dal with FreightDB (DuckDB) methods.
Original backup: rate_router.py.bak
"""
from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

# ── Imports ───────────────────────────────────────────────────────────────────
# Ensure api dir is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_access import dal  # Still used for carrier_rules (JSON), NOT for Parquet

# DuckDB engine — replaces all Pandas Parquet reads
_ENGINE_TEST_DIR = Path(__file__).parent.parent.parent  # Engine_test/
sys.path.insert(0, str(_ENGINE_TEST_DIR))
from db.duckdb_engine import FreightDB

# ── FreightDB Singleton ──────────────────────────────────────────────────────
_PARQUET_PATH = _ENGINE_TEST_DIR / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"
freight_db = FreightDB(_PARQUET_PATH)

router = APIRouter(prefix="/api/rates", tags=["Rates"])

# ── Region classifier ────────────────────────────────────────────────────────
_REGION_PATTERNS = {
    "WC": ["LAX", "LGB", "LONG BEACH", "LOS ANGELES", "OAK", "OAKLAND",
           "SEA", "SEATTLE", "TAC", "TACOMA", "PDX", "PORTLAND", "SFO"],
    "EC": ["NYK", "NEW YORK", "SAV", "SAVANNAH", "CHS", "CHARLESTON",
           "BAL", "BALTIMORE", "NFK", "NORFOLK", "PHI", "PHILADELPHIA",
           "BOS", "BOSTON", "JAX", "JACKSONVILLE", "WILMINGTON"],
    "GULF": ["HOU", "HOUSTON", "NOL", "NEW ORLEANS", "MOB", "MOBILE",
             "MIA", "MIAMI", "TAM", "TAMPA", "GAL", "GALVESTON"],
}

DRY_CONTAINERS = ["20GP", "40GP", "40HQ", "45'HQ", "40NOR"]
REEFER_CONTAINERS = ["20RF", "40RF"]
_CT_DISPLAY = {"45'HQ": "45HQ"}


def _classify_region(pod: str) -> str:
    pod_upper = str(pod).upper()
    for region, patterns in _REGION_PATTERNS.items():
        if any(p in pod_upper for p in patterns):
            return region
    return "IPI"


# ==============================================================================
# ENDPOINTS (all migrated to DuckDB via FreightDB)
# ==============================================================================

@router.get("")
def get_rates(
    pol: Optional[str] = Query(None),
    pod: Optional[str] = Query(None),
    place: Optional[str] = Query(None),
    carrier: Optional[str] = Query(None),
    container: str = Query("40HQ"),
    soc: Optional[bool] = Query(None),
    top: int = Query(20),
):
    """Query pricing rates from Parquet via DuckDB. Returns best price per carrier."""
    # Use FreightDB for initial query (DuckDB pushdown for date + charge filter)
    df = freight_db.query_rates(pol=pol, pod=pod, container_type=container, days=90)

    if df is None or df.empty:
        return {"rates": [], "total": 0, "error": "No rates found"}

    result = df.copy()

    # Additional filters not handled by FreightDB query (Pandas in-memory)
    if carrier:
        result = result[result['Carrier'].str.upper().str.contains(
            carrier.upper(), na=False)]
    if soc is True:
        result = result[result['Note'].astype(str).str.upper().str.contains(
            'SOC', na=False)]
    elif soc is False:
        result = result[~result['Note'].astype(str).str.upper().str.contains(
            'SOC', na=False)]
    if place:
        mask = pd.Series(False, index=result.index)
        for col in ['Place', 'POD']:
            if col in result.columns:
                mask |= result[col].astype(str).str.upper().str.contains(
                    place.upper(), na=False)
        result = result[mask]

    if result.empty:
        return {"rates": [], "total": 0}

    best = (
        result.sort_values('Amount')
              .drop_duplicates(subset=['Carrier', 'Note'], keep='first')
              .sort_values('Amount')
              .head(top)
    )

    carrier_rules = dal.get_carrier_rules()
    rates = []
    for _, row in best.iterrows():
        c = str(row.get('Carrier', '')).strip().upper()
        cr = carrier_rules.get(c, {})
        is_soc = 'SOC' in str(row.get('Note', '')).upper()
        rates.append({
            "carrier":        row.get('Carrier', ''),
            "pol":            row.get('POL', ''),
            "pod":            row.get('POD', ''),
            "place":          row.get('Place', ''),
            "container":      row.get('Container_Type', ''),
            "amount":         float(row.get('Amount', 0)),
            "transit":        row.get('Transit', '') if 'Transit' in row.index else '',
            "note":           row.get('Note', ''),
            "commodity":      row.get('Commodity', ''),
            "effective":      str(row.get('Eff', '')),
            "expiry":         str(row.get('Exp', '')),
            "is_soc":         is_soc,
            "is_direct":      'DIRECT' in str(row.get('Note', '')).upper(),
            "freetime_det":   cr.get("DET", ""),
            "freetime_dem":   cr.get("DEM", ""),
        })
    return {"rates": rates, "total": len(rates)}


@router.get("/carriers")
def get_carriers():
    """List all active carriers with rate counts."""
    # Use FreightDB for carrier list + DuckDB for counts
    df = freight_db.query_rates(days=90)
    if df is None or df.empty:
        return {"carriers": []}
    counts = df['Carrier'].value_counts().to_dict()
    return {"carriers": [{"name": k, "rates": v} for k, v in counts.items()]}


@router.get("/stats")
def get_rate_stats():
    """Overall pricing stats."""
    df = freight_db.query_rates(days=90)
    if df is None or df.empty:
        return {}
    return {
        "total_rates": len(df),
        "carriers": df['Carrier'].nunique(),
        "routes": df.apply(
            lambda r: f"{r.get('POL','')}-{r.get('POD','')}", axis=1
        ).nunique(),
        "loaded_at": None,  # DuckDB doesn't have a cache timestamp
    }


@router.get("/breakdown")
def get_rates_breakdown(
    pol: str = Query("HPH"),
    place: Optional[str] = Query(None),
    pod: Optional[str] = Query(None),
    carrier: Optional[str] = Query(None),
    container: str = Query("40HQ"),
):
    """Get full cost breakdown per carrier/route."""
    # DuckDB: load ALL charge types (not just Total Ocean Freight)
    # We need the full data for breakdown, so use a direct DuckDB query
    con = freight_db._connect()
    try:
        conditions = [
            freight_db._date_filter(90),
            "Amount > 0",
            f"UPPER(TRIM(POL)) = UPPER('{pol}')",
        ]
        params = []

        if container:
            conditions.append(f"UPPER(Container_Type) = UPPER('{container}')")

        where = " AND ".join(conditions)
        df_full = con.execute(f"""
            SELECT POL, POD, Place, Carrier, Container_Type,
                   Amount, Eff, Exp, Rate_Type, Note, Commodity,
                   Contract, Charge_Name
            FROM read_parquet('{freight_db._parquet}')
            WHERE {where}
        """).fetchdf()
    finally:
        con.close()

    if df_full is None or df_full.empty:
        return {"breakdowns": [], "error": "No rates found"}

    result = df_full.copy()
    if place:
        result = result[
            result['Place'].astype(str).str.upper().str.contains(place.upper(), na=False) |
            result['POD'].astype(str).str.upper().str.contains(place.upper(), na=False)
        ]
    if pod:
        result = result[result['POD'].astype(str).str.upper().str.contains(pod.upper(), na=False)]
    if carrier:
        result = result[result['Carrier'].str.upper().str.contains(carrier.upper(), na=False)]

    if result.empty:
        return {"breakdowns": [], "total": 0}

    breakdowns = []
    groups = result.groupby(['Carrier', 'Note', 'POD', 'Place'], dropna=False)
    for (carr, note, gpod, gplace), grp in groups:
        total_row = grp[grp['Charge_Name'].str.contains('Total Ocean Freight', na=False)]
        if total_row.empty:
            continue
        total_amt = float(total_row['Amount'].min())
        is_soc = 'SOC' in str(note).upper()
        charges = {}
        for _, row in grp.iterrows():
            cn = str(row['Charge_Name']).strip()
            if cn and cn != 'Total Ocean Freight':
                charges[cn] = float(row['Amount'])
        breakdowns.append({
            "carrier": str(carr), "pod": str(gpod), "place": str(gplace),
            "note": str(note) if note else "", "is_soc": is_soc,
            "container": container, "total": total_amt, "charges": charges,
            "transit": str(total_row.iloc[0].get('Note', '')),
            "expiry": str(total_row.iloc[0].get('Exp', '')),
            "effective": str(total_row.iloc[0].get('Eff', '')),
            "region": _classify_region(str(gpod)),
        })

    breakdowns.sort(key=lambda x: x["total"])
    return {"breakdowns": breakdowns[:30], "total": len(breakdowns)}


@router.get("/regions")
def get_rates_regions(pol: str = Query("HPH"), container: str = Query("40HQ")):
    """Region summary — best carrier per WC/EC/GULF/IPI."""
    df = freight_db.query_rates(pol=pol, container_type=container, days=90)
    if df is None or df.empty:
        return {"regions": {}}

    result = df.copy()
    result['region'] = result['POD'].apply(_classify_region)

    regions = {}
    for region in ["WC", "EC", "GULF", "IPI"]:
        region_data = result[result['region'] == region]
        if region_data.empty:
            regions[region] = {"count": 0, "best_carrier": None, "avg_price": 0,
                               "min_price": 0, "carriers": 0, "pods": 0}
            continue
        best = region_data.loc[region_data['Amount'].idxmin()]
        carrier_counts = region_data.groupby('Carrier')['Amount'].agg(
            ['min', 'mean', 'count']).reset_index()
        carrier_counts.columns = ['carrier', 'min_price', 'avg_price', 'count']
        carrier_summary = carrier_counts.sort_values('min_price').to_dict('records')
        regions[region] = {
            "count": len(region_data),
            "best_carrier": str(best['Carrier']),
            "best_price": float(best['Amount']),
            "avg_price": round(float(region_data['Amount'].mean()), 0),
            "min_price": round(float(region_data['Amount'].min()), 0),
            "carriers": int(region_data['Carrier'].nunique()),
            "pods": int(region_data['POD'].nunique()),
            "top_carriers": [{"carrier": str(c['carrier']),
                              "min_price": round(float(c['min_price']), 0),
                              "avg_price": round(float(c['avg_price']), 0),
                              "count": int(c['count'])} for c in carrier_summary[:5]],
        }
    return {"regions": regions, "pol": pol, "container": container}


@router.get("/compare")
def get_rates_compare(
    pol: str = Query("HPH"),
    place: Optional[str] = Query(None),
    pod: Optional[str] = Query(None),
):
    """Compare all carriers for a route — all container types."""
    df = freight_db.query_rates(pol=pol, days=90)
    if df is None or df.empty:
        return {"compare": []}

    result = df.copy()
    if place:
        result = result[
            result['Place'].astype(str).str.upper().str.contains(place.upper(), na=False) |
            result['POD'].astype(str).str.upper().str.contains(place.upper(), na=False)
        ]
    if pod:
        result = result[result['POD'].astype(str).str.upper().str.contains(pod.upper(), na=False)]
    if result.empty:
        return {"compare": []}
    pivot = result.groupby(['Carrier', 'Container_Type'])['Amount'].min().reset_index()
    carriers = sorted(pivot['Carrier'].unique())
    containers = sorted(pivot['Container_Type'].unique())
    compare = []
    for c in carriers:
        carr_data = pivot[pivot['Carrier'] == c]
        row = {"carrier": c}
        for ct in containers:
            val = carr_data[carr_data['Container_Type'] == ct]['Amount']
            row[ct] = round(float(val.iloc[0]), 0) if not val.empty else None
        compare.append(row)
    return {"compare": compare, "containers": containers, "carriers": carriers}


@router.get("/matrix")
def get_rates_matrix(
    pol: str = Query("HPH"),
    pod: Optional[str] = Query(None),
    place: Optional[str] = Query(None),
    mode: str = Query("DRY"),
    sort_by: str = Query("40HQ"),
):
    """Carrier x Container comparison matrix with surcharge breakdown + market envelope."""
    # DuckDB: load ALL charge types for breakdown
    ct_list = DRY_CONTAINERS if mode.upper() == "DRY" else REEFER_CONTAINERS
    ct_filter = "','".join(ct_list)

    con = freight_db._connect()
    try:
        sql = f"""
            SELECT POL, POD, Place, Carrier, Container_Type,
                   Amount, Eff, Exp, Rate_Type, Note, Commodity,
                   Contract, Charge_Name
            FROM read_parquet('{freight_db._parquet}')
            WHERE UPPER(TRIM(POL)) = UPPER(?)
              AND Container_Type IN ('{ct_filter}')
              AND {freight_db._date_filter(90)}
              AND Amount > 0
        """
        params = [pol]
        df_full = con.execute(sql, params).fetchdf()
    finally:
        con.close()

    if df_full is None or df_full.empty:
        return {"rows": [], "containers": [_CT_DISPLAY.get(c, c) for c in ct_list],
                "error": "No rates found"}

    result = df_full.copy()
    if place:
        result = result[
            result['Place'].astype(str).str.upper().str.contains(place.upper(), na=False) |
            result['POD'].astype(str).str.upper().str.contains(place.upper(), na=False)
        ]
    if pod:
        result = result[result['POD'].astype(str).str.upper().str.contains(pod.upper(), na=False)]
    if result.empty:
        return {"rows": [], "containers": [_CT_DISPLAY.get(c, c) for c in ct_list]}

    total_rows = result[result['Charge_Name'].str.contains('Total Ocean Freight', na=False)]
    surcharge_rows = result[~result['Charge_Name'].str.contains('Total Ocean Freight', na=False)]

    groups = total_rows.groupby(['Carrier', 'Rate_Type', 'POD', 'Place', 'Note'], dropna=False)
    rows = []
    for (carr, rate_type, gpod, gplace, note), grp in groups:
        container_prices = {}
        for _, row in grp.iterrows():
            ct = _CT_DISPLAY.get(row['Container_Type'], row['Container_Type'])
            amt = float(row['Amount'])
            if ct not in container_prices or amt < container_prices[ct]:
                container_prices[ct] = amt

        surcharges = {}
        cs = surcharge_rows[
            (surcharge_rows['Carrier'] == carr) &
            (surcharge_rows['POD'] == gpod) &
            (surcharge_rows['Place'] == gplace)
        ]
        for _, srow in cs.iterrows():
            cn = str(srow['Charge_Name']).strip()
            ct = _CT_DISPLAY.get(srow['Container_Type'], srow['Container_Type'])
            if ct not in surcharges:
                surcharges[ct] = {}
            surcharges[ct][cn] = float(srow['Amount'])

        eff = grp['Eff'].min()
        exp = grp['Exp'].max()
        note_str = str(note).strip() if note else ""
        is_soc = 'SOC' in note_str.upper()
        badge = rate_type if rate_type else ""
        if is_soc:
            badge = "SOC"
        elif 'FIXED' in note_str.upper():
            badge = "FIXED"

        pod_code = str(gpod).split(",")[0].strip() if gpod else ""
        place_str = str(gplace).strip() if gplace else ""
        routing = f"{place_str} ({pod_code})" if pod_code and place_str and pod_code != place_str else place_str or pod_code

        rows.append({
            "carrier": str(carr), "badge": badge, "is_soc": is_soc,
            "routing": routing, "pod": str(gpod), "place": str(gplace),
            "prices": container_prices, "surcharges": surcharges,
            "eff": eff.strftime("%d %b") if pd.notna(eff) else "",
            "exp": exp.strftime("%d %b") if pd.notna(exp) else "",
            "valid": f"{eff.strftime('%d %b') if pd.notna(eff) else '?'}–{exp.strftime('%d %b') if pd.notna(exp) else '?'}",
            "region": _classify_region(str(gpod)),
        })

    sort_key = _CT_DISPLAY.get(sort_by, sort_by)
    rows.sort(key=lambda r: r["prices"].get(sort_key, 999999))

    cheapest = {}
    for ct in [_CT_DISPLAY.get(c, c) for c in ct_list]:
        prices = [r["prices"].get(ct, None) for r in rows if r["prices"].get(ct) is not None]
        cheapest[ct] = min(prices) if prices else None

    carrier_rules = dal.get_carrier_rules()
    for row in rows:
        cr = carrier_rules.get(row["carrier"].strip().upper(), {})
        row["freetime"] = cr.get("DET", "")

    # ── NEW: Market Envelope via DuckDB ──────────────────────────────
    envelope = {}
    if pod or place:
        search_term = pod or place
        envelope = freight_db.get_market_envelope(
            pol=pol,
            pod=search_term,
            container_type=sort_by,
            days=90,
        )

    return {
        "rows": rows[:50], "total": len(rows),
        "containers": [_CT_DISPLAY.get(c, c) for c in ct_list],
        "cheapest": cheapest, "sort_by": sort_key,
        "envelope": envelope,
    }


@router.get("/best")
def get_rates_best(
    pol: str = Query("HPH"),
    pod: Optional[str] = Query(None),
    place: Optional[str] = Query(None),
    containers: str = Query("40HQ"),
):
    """Get best (cheapest) carrier for each container type on a route."""
    df = freight_db.query_rates(pol=pol, days=90)
    if df is None or df.empty:
        return {"best": {}, "error": "No rates found"}

    result = df.copy()
    if place:
        result = result[
            result['Place'].astype(str).str.upper().str.contains(place.upper(), na=False) |
            result['POD'].astype(str).str.upper().str.contains(place.upper(), na=False)
        ]
    if pod:
        result = result[result['POD'].astype(str).str.upper().str.contains(pod.upper(), na=False)]

    ct_list = [c.strip().upper() for c in containers.split(",")]
    carrier_rules = dal.get_carrier_rules()
    best = {}
    for ct in ct_list:
        ct_data = result[result['Container_Type'].str.upper() == ct]
        if ct_data.empty:
            best[ct] = []
            continue
        top = ct_data.sort_values('Amount').drop_duplicates(
            subset=['Carrier', 'Note'], keep='first').head(5)
        cs = []
        for _, row in top.iterrows():
            c = str(row.get('Carrier', '')).strip().upper()
            cr = carrier_rules.get(c, {})
            is_soc = 'SOC' in str(row.get('Note', '')).upper()
            cs.append({
                "carrier": row.get('Carrier', ''),
                "ocean_freight": float(row.get('Amount', 0)),
                "badge": "SOC" if is_soc else "",
                "transit": row.get('Transit', '') if 'Transit' in row.index else '',
                "note": row.get('Note', ''),
                "effective": str(row.get('Eff', '')),
                "expiry": str(row.get('Exp', '')),
                "freetime": cr.get("DET", ""),
                "pod": row.get('POD', ''),
                "place": row.get('Place', ''),
            })
        best[ct] = cs
    return {"best": best, "containers": ct_list}


# ── NEW: Envelope-only endpoint ──────────────────────────────────────────────
@router.get("/envelope")
def get_rate_envelope(
    pol: str = Query("HPH"),
    pod: str = Query(..., description="POD to search for"),
    container_type: str = Query("40HQ"),
    days: int = Query(30),
):
    """Get market envelope (p2.5/avg/p97.5) for a route."""
    envelope = freight_db.get_market_envelope(
        pol=pol, pod=pod, container_type=container_type, days=days,
    )
    stats = freight_db.get_rate_stats(
        pol=pol, pod=pod, container_type=container_type, days=days,
    )
    return {
        "route": f"{pol} → {pod}",
        "container_type": container_type,
        "days": days,
        "envelope": envelope,
        "stats": stats,
    }
