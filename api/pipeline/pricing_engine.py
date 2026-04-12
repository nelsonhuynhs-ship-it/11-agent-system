"""
pricing_engine.py — DuckDB-powered pricing queries for FreightBrian.
Queries active rates only (Exp >= today) with sub-second performance.
"""
import os
import time
from pathlib import Path

import duckdb
import pandas as pd

DATA_DIR = Path(os.environ.get("NELSON_DATA_DIR", "/opt/nelson/data"))
PARQUET_PATH = DATA_DIR / "pricing" / "Cleaned_Master_History.parquet"


def _normalize_container(container: str) -> str:
    return container.upper().replace("'", "").replace("'", "").strip()


def _get_con():
    return duckdb.connect()


    # Charges that represent the final quote price per contract type:
# FAK  → ALL IN COST (includes all surcharges)
# SCFI → Total Ocean Freight (mapped from HLCU Offer in rate_importer)
# FIX  → Base Ocean Freight (FIX has no surcharges, base = final)
QUOTABLE_CHARGES = ('ALL IN COST', 'Total Ocean Freight', 'Base Ocean Freight')


def get_active_rates(
    pol: str,
    pod: str,
    carrier: str = None,
    container: str = "40HQ",
    rate_type: str = None,
    limit: int = 20,
    all_charges: bool = False,
) -> pd.DataFrame:
    """Query active rates for email quoting. Only returns final quotable prices by default."""
    con = _get_con()
    container_norm = _normalize_container(container)

    query = """
        SELECT POL, POD, Place, Carrier, Commodity, Eff, Exp,
               REPLACE(Container_Type, chr(39), '') AS Container_Type,
               ROUND(Amount, 2) AS Amount, Rate_Type, Charge_Name, Note
        FROM read_parquet(?)
        WHERE Exp >= CURRENT_DATE
          AND UPPER(REPLACE(Container_Type, chr(39), '')) = ?
          AND UPPER(TRIM(POL)) = UPPER(TRIM(?))
          AND (UPPER(TRIM(POD)) = UPPER(TRIM(?)) OR UPPER(TRIM(Place)) = UPPER(TRIM(?)))
    """
    params = [str(PARQUET_PATH), container_norm, pol, pod, pod]

    # Filter to quotable charges only (unless all_charges=True for debugging)
    if not all_charges:
        placeholders = ", ".join(["?"] * len(QUOTABLE_CHARGES))
        query += f" AND Charge_Name IN ({placeholders})"
        params.extend(QUOTABLE_CHARGES)

    if carrier:
        query += " AND UPPER(TRIM(Carrier)) = UPPER(TRIM(?))"
        params.append(carrier)

    if rate_type:
        query += " AND UPPER(Rate_Type) = UPPER(?)"
        params.append(rate_type)

    query += " ORDER BY Amount ASC LIMIT ?"
    params.append(limit)

    return con.execute(query, params).fetchdf()


def get_best_rate(pol: str, pod: str, container: str = "40HQ") -> dict:
    """Return cheapest active rate for a route."""
    df = get_active_rates(pol, pod, container=container, limit=1)
    if df.empty:
        return {"found": False, "pol": pol, "pod": pod, "container": container}
    row = df.iloc[0]
    return {
        "found": True,
        "pol": row["POL"],
        "pod": row["POD"],
        "carrier": row["Carrier"],
        "amount": float(row["Amount"]),
        "container": row["Container_Type"],
        "exp": str(row["Exp"]),
        "charge": row["Charge_Name"],
        "rate_type": row["Rate_Type"],
    }


def get_rate_summary(pol: str, pod: str) -> dict:
    """Summary of all active rates for a route across carriers and containers."""
    con = _get_con()
    df = con.execute("""
        SELECT Carrier,
               REPLACE(Container_Type, chr(39), '') AS Container,
               ROUND(MIN(Amount), 2) AS min_rate,
               ROUND(AVG(Amount), 2) AS avg_rate,
               ROUND(MAX(Amount), 2) AS max_rate,
               COUNT(*) AS rate_count
        FROM read_parquet(?)
        WHERE Exp >= CURRENT_DATE
          AND UPPER(TRIM(POL)) = UPPER(TRIM(?))
          AND (UPPER(TRIM(POD)) = UPPER(TRIM(?)) OR UPPER(TRIM(Place)) = UPPER(TRIM(?)))
          AND Charge_Name IN ('ALL IN COST', 'Total Ocean Freight', 'Base Ocean Freight')
        GROUP BY Carrier, Container
        ORDER BY Carrier, Container
    """, [str(PARQUET_PATH), pol, pod, pod]).fetchdf()

    return {
        "pol": pol,
        "pod": pod,
        "carriers": sorted(df["Carrier"].unique().tolist()) if not df.empty else [],
        "rates": df.to_dict("records") if not df.empty else [],
    }


def match_cnee_rates(cnee_pol: str, cnee_destination: str) -> pd.DataFrame:
    """Match a CNEE's route to best available rates for cold email personalization."""
    con = _get_con()
    return con.execute("""
        SELECT Carrier,
               REPLACE(Container_Type, chr(39), '') AS Container,
               ROUND(MIN(Amount), 2) AS best_rate,
               Exp AS valid_until
        FROM read_parquet(?)
        WHERE Exp >= CURRENT_DATE
          AND UPPER(TRIM(POL)) = UPPER(TRIM(?))
          AND (UPPER(TRIM(POD)) LIKE '%' || UPPER(TRIM(?)) || '%'
               OR UPPER(TRIM(Place)) LIKE '%' || UPPER(TRIM(?)) || '%')
          AND Charge_Name = 'Total Ocean Freight'
        GROUP BY Carrier, Container, Exp
        ORDER BY best_rate ASC
        LIMIT 10
    """, [str(PARQUET_PATH), cnee_pol, cnee_destination, cnee_destination]).fetchdf()
