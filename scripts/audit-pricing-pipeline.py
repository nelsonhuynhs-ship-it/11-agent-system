"""
audit-pricing-pipeline.py — trace data loss between Parquet → Pricing Dry/Reefer.

Simulates refresh-v14.py pipeline step-by-step and reports row counts at each stage.
Focus on reported issues:
  - ONE HCM-TACOMA missing FAK COC (SHORT TERM GDSM)
  - ONE reefer missing NORFOLK/HALIFAX NS/SAVANNAH
  - COSCO reefer missing BOSTON/BALTIMORE
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import duckdb

PARQUET = "D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet"


def audit_carrier_ports(carrier: str, rate_type: str):
    """Compare parquet active ports vs post-pipeline ports."""
    print(f"\n{'='*70}")
    print(f"AUDIT: {carrier} {rate_type}")
    print('='*70)

    # Stage 1: raw parquet active
    df = duckdb.query(f"""
    SELECT POL, POD, Place, Carrier, Commodity, Note, Eff, Exp, Rate_Type,
           Container_Type, Amount, Charge_Name
    FROM '{PARQUET}'
    WHERE Carrier='{carrier}' AND POL='HCM'
      AND Rate_Type='{rate_type}'
      AND Exp >= '{datetime.now().strftime("%Y-%m-%d")}'
    """).df()
    print(f"[1] Parquet raw active: {len(df):,} rows, {df['Place'].nunique()} places")

    # Stage 2: 15-day filter (RefreshDate = Eff fallback Exp)
    df['Eff'] = pd.to_datetime(df['Eff'], errors='coerce')
    df['Exp'] = pd.to_datetime(df['Exp'], errors='coerce')
    df['RefreshDate'] = df['Eff'].where(df['Eff'].notna(), df['Exp'])
    cutoff = datetime.now() - timedelta(days=15)
    df15 = df[df['RefreshDate'] >= cutoff]
    print(f"[2] After 15-day filter: {len(df15):,} rows, {df15['Place'].nunique()} places")

    # Stage 3: Total Ocean Freight filter
    df_tof = df15[df15['Charge_Name'].str.contains('Total Ocean', case=False, na=False)].copy()
    print(f"[3] After Total Ocean filter: {len(df_tof):,} rows, {df_tof['Place'].nunique()} places")

    if len(df_tof) == 0:
        print("  WARN: Zero rows — Charge_Name mismatch")
        return

    # Stage 4: pivot
    id_cols = [c for c in ['POL', 'POD', 'Place', 'Carrier', 'Commodity', 'Eff', 'Exp', 'Note', 'Rate_Type']
               if c in df_tof.columns]
    for col in ['Note', 'Commodity']:
        if col in df_tof.columns:
            df_tof[col] = df_tof[col].fillna('')
    pivot = df_tof.pivot_table(
        index=id_cols, columns='Container_Type', values='Amount', aggfunc='first'
    ).reset_index()
    pivot = pivot.rename(columns={'Rate_Type': 'Source'})
    print(f"[4] After pivot: {len(pivot):,} rows, {pivot['Place'].nunique()} places")

    # Stage 5: dedup by route_key
    route_key = [c for c in ['POL', 'POD', 'Place', 'Carrier', 'Note', 'Source'] if c in pivot.columns]
    pivot = pivot.sort_values('Eff', ascending=False, na_position='last')
    pivot_dedup = pivot.drop_duplicates(subset=route_key, keep='first')
    print(f"[5] After dedup: {len(pivot_dedup):,} rows, {pivot_dedup['Place'].nunique()} places")

    # Stage 6: dry/reefer split
    dry_cols = [c for c in ['20GP', '40GP', '40HQ', '45HQ', "45'HQ", '40NOR'] if c in pivot_dedup.columns]
    rf_cols = [c for c in ['20RF', '40RF'] if c in pivot_dedup.columns]

    dry_mask = pivot_dedup[dry_cols].notna().any(axis=1) if dry_cols else pd.Series(False, index=pivot_dedup.index)
    rf_mask = pivot_dedup[rf_cols].notna().any(axis=1) if rf_cols else pd.Series(False, index=pivot_dedup.index)
    reefer_note = pivot_dedup['Note'].astype(str).str.contains('REEFER', case=False, na=False) if 'Note' in pivot_dedup.columns else pd.Series(False, index=pivot_dedup.index)
    reefer_cmd = pivot_dedup['Commodity'].astype(str).str.contains('REEFER', case=False, na=False) if 'Commodity' in pivot_dedup.columns else pd.Series(False, index=pivot_dedup.index)

    pivot_dry = pivot_dedup[dry_mask & ~reefer_note & ~reefer_cmd]
    pivot_reefer = pivot_dedup[rf_mask | reefer_note | reefer_cmd]
    if rf_cols:
        pivot_reefer = pivot_reefer.dropna(how='all', subset=rf_cols)

    print(f"[6a] Pricing Dry:    {len(pivot_dry):,} rows, {pivot_dry['Place'].nunique()} places")
    print(f"[6b] Pricing Reefer: {len(pivot_reefer):,} rows, {pivot_reefer['Place'].nunique()} places")

    # Show places
    parquet_places = set(df15['Place'].dropna().unique())
    dry_places = set(pivot_dry['Place'].dropna().unique())
    reefer_places = set(pivot_reefer['Place'].dropna().unique())

    # For FAK check reefer specifically
    lost_reefer = parquet_places - reefer_places - dry_places
    print(f"\n[!] Places in parquet but LOST entirely: {sorted(lost_reefer) if lost_reefer else 'None'}")

    print("\n[!] Places ONLY in parquet (not in Dry/Reefer output):")
    for p in sorted(parquet_places):
        in_dry = p in dry_places
        in_reefer = p in reefer_places
        if not in_dry and not in_reefer:
            # Check if any row for this place in pivot_dedup — what mask did it fail?
            sub = pivot_dedup[pivot_dedup['Place'] == p]
            notes = sub['Note'].unique() if 'Note' in sub.columns else []
            cmds = sub['Commodity'].unique() if 'Commodity' in sub.columns else []
            print(f"    {p}: rows_in_dedup={len(sub)}, notes={list(notes)[:3]}, cmds={[str(c)[:40] for c in list(cmds)[:2]]}")

    # For FAK REEFER specifically, check Note/Commodity Reefer signal for missing ports
    if rate_type == 'FAK':
        reefer_in_parquet_places = set(df15[
            (df15['Container_Type'].isin(['20RF', '40RF']))
        ]['Place'].dropna().unique())
        missing_from_reefer = reefer_in_parquet_places - reefer_places
        if missing_from_reefer:
            print(f"\n[!] REEFER ports in parquet but missing from Pricing Reefer: {sorted(missing_from_reefer)}")
            for p in sorted(missing_from_reefer):
                sub = pivot_dedup[pivot_dedup['Place'] == p]
                print(f"    {p}:")
                for _, r in sub.iterrows():
                    note = str(r.get('Note', ''))[:30]
                    cmd = str(r.get('Commodity', ''))[:40]
                    src = r.get('Source', '')
                    has_20rf = pd.notna(r.get('20RF')) if '20RF' in sub.columns else False
                    has_40rf = pd.notna(r.get('40RF')) if '40RF' in sub.columns else False
                    has_dry = any(pd.notna(r.get(c)) for c in dry_cols if c in sub.columns)
                    print(f"      Source={src} Note={note!r} Cmd={cmd!r} has_20RF={has_20rf} has_40RF={has_40rf} has_dry={has_dry}")


if __name__ == "__main__":
    audit_carrier_ports("ONE", "FAK")
    audit_carrier_ports("COSCO", "FAK")
    print("\n" + "="*70)
    print("DONE")
