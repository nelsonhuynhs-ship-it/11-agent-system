#!/usr/bin/env python3
"""
normalize_parquet.py — Normalize Cleaned_Master_History parquet per Phase 06 decisions.

Owner approved (2026-04-25):
1. POD: LAX-LGB → LA/LGB (slash separator)
2. Container: 40HQ → 40HC, 45HQ → 45HC, 45'HQ → 45HC (Owner decided 2026-04-26)
3. POL: trim trailing spaces (DAD  → DAD)
4. POL: delete rows where len(POL) < 3

Usage: python normalize_parquet.py [--slim]
"""
import argparse
import os
import shutil
import pandas as pd
import sys

BACKUP_DIR = "D:/OneDrive/NelsonData/pricing/_backup"
PARQUET_DIR = "D:/OneDrive/NelsonData/pricing"

def backup_file(path):
    basename = os.path.basename(path)
    backup_path = os.path.join(BACKUP_DIR, basename.replace('.parquet', '_BACKUP_phase06_20260425.parquet'))
    shutil.copy2(path, backup_path)
    print(f"  Backup: {backup_path}")
    return backup_path

def normalize_parquet(parquet_path, description):
    print(f"\n{'='*60}")
    print(f"Normalizing: {description}")
    print(f"File: {parquet_path}")
    print(f"{'='*60}")

    # Read
    df = pd.read_parquet(parquet_path)
    rows_before = len(df)
    print(f"  Rows before: {rows_before:,}")

    # 1. POD normalization
    pod_before_dash = df['POD'].str.contains(r'-LGB|-LAX', regex=True, na=False).sum()
    pod_before_space = df['POD'].str.contains(r'/ ', regex=True, na=False).sum()
    print(f"\n  [POD] LAX-LGB / LGB-LAX dash count: {pod_before_dash:,}")
    print(f"  [POD] space-after-slash count: {pod_before_space:,}")

    df['POD'] = df['POD'].str.replace('-LGB', '/LGB', regex=False)
    df['POD'] = df['POD'].str.replace('-LAX', '/LAX', regex=False)
    df['POD'] = df['POD'].str.replace('/ ', '/', regex=False)

    pod_after_dash = df['POD'].str.contains(r'-LGB|-LAX', regex=True, na=False).sum()
    pod_after_space = df['POD'].str.contains(r'/ ', regex=True, na=False).sum()
    print(f"  [POD] After: dash={pod_after_dash:,}, space-after-slash={pod_after_space:,}")

    # 2. Container normalization — 40HQ → 40HC, 45HQ → 45HC, 45'HQ → 45HC (Owner 2026-04-26)
    cont_40hq_before = (df['Container_Type'] == '40HQ').sum()
    cont_45hq_before = (df['Container_Type'] == '45HQ').sum()
    cont_45hq_prime_before = (df["Container_Type"] == "45'HQ").sum()
    print(f"\n  [Container] 40HQ before: {cont_40hq_before:,} (→ 40HC)")
    print(f"  [Container] 45HQ before: {cont_45hq_before:,} (→ 45HC)")
    print(f"  [Container] 45'HQ before: {cont_45hq_prime_before:,} (→ 45HC)")

    df['Container_Type'] = df['Container_Type'].replace({
        '40HQ': '40HC',
        '45HQ': '45HC',
        "45'HQ": '45HC',
    })

    cont_40hq_after = (df['Container_Type'] == '40HQ').sum()
    cont_40hc_after = (df['Container_Type'] == '40HC').sum()
    cont_45hq_after = (df['Container_Type'] == '45HQ').sum()
    cont_45hq_prime_after = (df["Container_Type"] == "45'HQ").sum()
    cont_45hc_after = (df['Container_Type'] == '45HC').sum()
    print(f"  [Container] 40HQ after: {cont_40hq_after:,} (should be 0)")
    print(f"  [Container] 40HC after: {cont_40hc_after:,}")
    print(f"  [Container] 45HQ after: {cont_45hq_after:,} (should be 0)")
    print(f"  [Container] 45'HQ after: {cont_45hq_prime_after:,} (should be 0)")
    print(f"  [Container] 45HC after: {cont_45hc_after:,}")

    # 3. POL — trim trailing spaces
    pol_trailing_before = (df['POL'] != df['POL'].str.strip()).sum()
    print(f"\n  [POL] trailing space rows: {pol_trailing_before:,}")

    df['POL'] = df['POL'].str.strip()

    # 4. POL — delete rows with len < 3
    pol_short_before = (df['POL'].str.len() < 3).sum()
    print(f"  [POL] len<3 rows (will DELETE): {pol_short_before:,}")

    df = df[df['POL'].str.len() >= 3]

    # 5. Charge_Name typo: COMMISION → COMMISSION
    typo_before = (df['Charge_Name'] == 'COMMISION').sum()
    print(f"\n  [Charge_Name] 'COMMISION' typo: {typo_before:,}")
    df['Charge_Name'] = df['Charge_Name'].replace({'COMMISION': 'COMMISSION'})

    rows_after = len(df)
    rows_deleted = rows_before - rows_after
    print(f"\n  Rows after: {rows_after:,} (deleted {rows_deleted:,} rows)")

    # Write atomically
    tmp_path = parquet_path + '.tmp'
    df.to_parquet(tmp_path, index=False)
    os.replace(tmp_path, parquet_path)
    print(f"  Written: {parquet_path}")

    return {
        'rows_before': rows_before,
        'rows_after': rows_after,
        'rows_deleted': rows_deleted,
        'pod_dash_fixed': pod_before_dash,
        'pod_space_fixed': pod_before_space,
        'cont_40hq_fixed': cont_40hq_before,
    }

def main():
    parser = argparse.ArgumentParser(description='Normalize parquet files per Phase 06 decisions')
    parser.add_argument('--slim', action='store_true', help='Only normalize slim parquet')
    parser.add_argument('--main-only', action='store_true', help='Only normalize main parquet')
    args = parser.parse_args()

    results = {}

    # Main parquet
    if not args.slim:
        main_path = os.path.join(PARQUET_DIR, "Cleaned_Master_History.parquet")
        results['main'] = normalize_parquet(main_path, "Main parquet (6.98M rows)")

    # Slim parquet
    if not args.main_only:
        slim_path = os.path.join(PARQUET_DIR, "Cleaned_Master_History_slim.parquet")
        results['slim'] = normalize_parquet(slim_path, "Slim parquet (624K rows)")

    # Summary
    print(f"\n{'='*60}")
    print("NORMALIZATION COMPLETE — SUMMARY")
    print(f"{'='*60}")
    for name, r in results.items():
        print(f"\n  [{name.upper()}]")
        print(f"    Rows: {r['rows_before']:,} → {r['rows_after']:,} (Δ {r['rows_deleted']:+,})")
        print(f"    POD dash fixed: {r['pod_dash_fixed']:,}")
        print(f"    POD space fixed: {r['pod_space_fixed']:,}")
        print(f"    Container 40HQ→40HC: {r['cont_40hq_fixed']:,}")

if __name__ == '__main__':
    main()
