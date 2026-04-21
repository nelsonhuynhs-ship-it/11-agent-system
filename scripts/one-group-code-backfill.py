"""
one-group-code-backfill.py — One-shot backfill Group_Code for existing parquet.

Loads Cleaned_Master_History.parquet, resolves Group_Code for all Carrier=ONE rows
using Pricing_Engine/one_group_resolver.py, writes parquet back in-place.

Non-ONE rows: Group_Code set to empty string (preserve schema).
Idempotent: safe to re-run.

Usage:
    python scripts/one-group-code-backfill.py
"""
import sys
import time
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / 'Pricing_Engine'))

import pandas as pd  # noqa: E402
from one_group_resolver import resolve_one_group_code  # noqa: E402

PARQUET = Path("D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet")
BACKUP = PARQUET.with_suffix(".parquet.backup_pre_group_code")


def main() -> int:
    if not PARQUET.exists():
        print(f"ERROR: parquet not found at {PARQUET}", file=sys.stderr)
        return 1

    print(f"Reading parquet: {PARQUET}")
    t0 = time.time()
    df = pd.read_parquet(PARQUET)
    print(f"  rows={len(df):,}  cols={len(df.columns)}  t={time.time()-t0:.1f}s")

    if "Group_Code" not in df.columns:
        print("  Group_Code col missing, creating empty col")
        df["Group_Code"] = ""
    df["Group_Code"] = df["Group_Code"].fillna("").astype(str)

    # Backup before write
    if not BACKUP.exists():
        print(f"Backup → {BACKUP}")
        t0 = time.time()
        df.to_parquet(BACKUP, index=False)
        print(f"  backup written in {time.time()-t0:.1f}s")
    else:
        print(f"Backup already exists, skip")

    # Filter ONE rows
    one_mask = df["Carrier"].astype(str).str.upper() == "ONE"
    n_one = int(one_mask.sum())
    print(f"ONE rows to resolve: {n_one:,}")

    if n_one == 0:
        print("No ONE rows, nothing to do")
        return 0

    # Subset for resolve — only unique (Rate_Type, Commodity, Note, POD) combos
    subset_cols = ["Rate_Type", "Commodity", "Note", "POD"]
    for c in subset_cols:
        if c not in df.columns:
            print(f"ERROR: col {c} missing", file=sys.stderr)
            return 1

    one_df = df.loc[one_mask, subset_cols].copy()
    one_df = one_df.fillna("")

    unique_combos = one_df.drop_duplicates()
    print(f"Unique (rate_type, commodity, note, pod) combos: {len(unique_combos):,}")

    # Build lookup dict
    lookup: dict[tuple, str] = {}
    t0 = time.time()
    for _, r in unique_combos.iterrows():
        key = (str(r["Rate_Type"]), str(r["Commodity"]), str(r["Note"]), str(r["POD"]))
        try:
            code, _label = resolve_one_group_code(*key)
        except Exception as e:
            print(f"  WARN resolver error on {key}: {e}")
            code = ""
        lookup[key] = code
    print(f"  resolver built {len(lookup):,} lookups in {time.time()-t0:.1f}s")

    # Apply via map for speed
    t0 = time.time()
    one_keys = list(zip(
        one_df["Rate_Type"].astype(str),
        one_df["Commodity"].astype(str),
        one_df["Note"].astype(str),
        one_df["POD"].astype(str),
    ))
    one_codes = [lookup.get(k, "") for k in one_keys]
    df.loc[one_mask, "Group_Code"] = one_codes
    print(f"  applied to {n_one:,} ONE rows in {time.time()-t0:.1f}s")

    # Sanity stats
    resolved = df.loc[one_mask, "Group_Code"].ne("").sum()
    print(f"  ONE rows with non-empty Group_Code: {resolved:,}/{n_one:,}")
    counts = df.loc[one_mask, "Group_Code"].value_counts().head(15)
    print(f"  top codes:\n{counts.to_string()}")

    # Write back
    t0 = time.time()
    df.to_parquet(PARQUET, index=False)
    print(f"Parquet saved in {time.time()-t0:.1f}s")

    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
