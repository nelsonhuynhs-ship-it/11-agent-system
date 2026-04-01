"""
export_30day.py — Export last 30 days of Parquet data
=====================================================
Creates a lightweight rates_30day.parquet for VPS deployment.
Full Parquet = 10.2M rows → filtered to ~last 30 days only.
"""
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Paths
ENGINE_DIR = Path(__file__).parent
DATA_DIR = ENGINE_DIR / "data"
FULL_PARQUET = DATA_DIR / "Cleaned_Master_History.parquet"
OUTPUT_PARQUET = DATA_DIR / "rates_30day.parquet"


def export_30day():
    """Filter Parquet to last 30 days and save as rates_30day.parquet."""
    if not FULL_PARQUET.exists():
        print(f"[ERROR] Source not found: {FULL_PARQUET}")
        sys.exit(1)

    print(f"[1/3] Loading {FULL_PARQUET.name}...")
    df = pd.read_parquet(str(FULL_PARQUET))
    print(f"  Full dataset: {len(df):,} rows")

    # Filter by Exp date (rates expiring in the future or recently)
    cutoff = datetime.now() - timedelta(days=30)
    print(f"[2/3] Filtering: Exp >= {cutoff.strftime('%Y-%m-%d')}...")

    # Try to parse Exp column
    if "Exp" in df.columns:
        df["Exp"] = pd.to_datetime(df["Exp"], errors="coerce")
        filtered = df[df["Exp"] >= cutoff].copy()
    elif "exp" in df.columns:
        df["exp"] = pd.to_datetime(df["exp"], errors="coerce")
        filtered = df[df["exp"] >= cutoff].copy()
    else:
        # Fallback: take last 50,000 rows
        print("  [WARN] No Exp column found — taking last 50,000 rows")
        filtered = df.tail(50_000).copy()

    print(f"  Filtered: {len(filtered):,} rows ({len(filtered)/len(df)*100:.1f}%)")

    # Save
    print(f"[3/3] Saving {OUTPUT_PARQUET.name}...")
    filtered.to_parquet(str(OUTPUT_PARQUET), index=False, engine="pyarrow")

    size_mb = OUTPUT_PARQUET.stat().st_size / (1024 * 1024)
    print(f"  Done: {OUTPUT_PARQUET.name} ({size_mb:.1f} MB, {len(filtered):,} rows)")
    return str(OUTPUT_PARQUET)


if __name__ == "__main__":
    export_30day()
