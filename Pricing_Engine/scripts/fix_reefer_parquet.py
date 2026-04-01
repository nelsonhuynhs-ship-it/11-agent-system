# -*- coding: utf-8 -*-
"""
fix_reefer_parquet.py -- Fix ONLY FAK_20260313 records for ONE/COSCO REEFER
============================================================================
rate_importer.py imported FAK_20260313 without reefer remap, causing
REEFER containers to stay as 20GP/40GP/40HQ instead of 20RF/40RF.

Usage:
    python fix_reefer_parquet.py           # dry-run
    python fix_reefer_parquet.py --apply   # fix + backup
"""
import sys, os, shutil
from datetime import datetime
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
PARQUET_FILE = DATA_DIR / "Cleaned_Master_History.parquet"


def fix_reefer_containers(apply=False):
    if not PARQUET_FILE.exists():
        print(f"[ERROR] Parquet not found: {PARQUET_FILE}")
        return

    df = pd.read_parquet(PARQUET_FILE)
    print(f"Loaded {len(df):,} rows")

    # Target ONLY FAK_20260313 records + ONE/COSCO + REEFER commodity
    mask_file = df['Source_File'].str.contains('FAK_20260313', na=False)
    mask_reefer = df['Commodity'].str.contains('REEFER', case=False, na=False)
    mask_carrier = df['Carrier'].isin(['ONE', 'COSCO'])
    mask = mask_file & mask_reefer & mask_carrier

    print(f"\nTarget records (FAK_20260313 + ONE/COSCO + REEFER): {mask.sum()}")

    if mask.sum() == 0:
        print("[OK] No records to fix")
        return

    # Show current state
    print("\n=== BEFORE ===")
    print(df[mask].groupby(['Carrier', 'Container_Type']).size().to_string())

    # Identify wrong containers
    wrong_20 = mask & df['Container_Type'].str.contains('20', na=False) & \
               ~df['Container_Type'].str.contains('RF', na=False)
    wrong_40 = mask & df['Container_Type'].str.contains('40', na=False) & \
               ~df['Container_Type'].str.contains('RF', na=False)
    total_wrong = wrong_20.sum() + wrong_40.sum()

    print(f"\nWrong containers: {total_wrong}")
    print(f"  20xx -> 20RF: {wrong_20.sum()}")
    print(f"  40xx -> 40RF: {wrong_40.sum()}")

    if total_wrong == 0:
        print("[OK] All containers already correct")
        return

    if not apply:
        print("\n[DRY RUN] Use --apply to fix")
        return

    # Backup
    backup = DATA_DIR / f"Cleaned_Master_History_BACKUP_{datetime.now().strftime('%Y%m%d_%H%M')}.parquet"
    shutil.copy2(PARQUET_FILE, backup)
    print(f"\n[Backup] {backup.name}")

    # Apply fix
    df.loc[wrong_20, 'Container_Type'] = '20RF'
    df.loc[wrong_40, 'Container_Type'] = '40RF'

    # Save
    df.to_parquet(PARQUET_FILE, index=False, engine='pyarrow')
    print(f"[Saved] {PARQUET_FILE.name}")

    # Verify
    print("\n=== AFTER ===")
    mask_after = mask_file & mask_reefer & mask_carrier
    print(df[mask_after].groupby(['Carrier', 'Container_Type']).size().to_string())

    remaining = df[mask_after & df['Container_Type'].isin(['20GP', '40GP', '40HQ', '40NOR'])]
    print(f"\n[{'OK' if len(remaining)==0 else 'WARN'}] {len(remaining)} wrong containers remain")


if __name__ == "__main__":
    fix_reefer_containers(apply="--apply" in sys.argv)
