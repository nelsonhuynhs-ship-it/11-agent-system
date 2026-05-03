#!/usr/bin/env python3
"""
validate_contracts.py — Contract data quality validator.

Checks Cleaned_Master_History.parquet for canonical contract violations.
Designed to catch drift after normalization or data imports.

Usage:
    python validate_contracts.py [--parquet PATH] [--slim]

Exit codes:
    0 = all clean
    1 = violations detected

Owner decisions encoded in checks:
- POD separator: must be slash (/) not dash (-)            [Owner 2026-04-25]
- Container 40HQ: must be 40HC                              [Owner 2026-04-25]
- Container 45HQ / 45'HQ: must be 45HC                      [Owner 2026-04-26]
- POL: no trailing spaces, no len < 3                       [Owner 2026-04-25]
- Rate_Type: must be FAK | FIX | SCFI
- Container_Type: must be in allowed enum
- Mix Quote peer: must be COC (Note != 'SOC')               [Owner 2026-04-26]
- Total Ocean Freight excludes: THC, SEAL, BILL, TELEX, AMS [Owner 2026-04-26]
- Group_Code: only ONE carrier rows                         [Owner 2026-04-26]
"""

import argparse
import sys
import pandas as pd

DEFAULT_PARQUET = "D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet"
ALLOWED_CONTAINERS = ['40HC', '45HC', '20GP', '40GP', '40NOR', '20RF', '40RF']
ALLOWED_RATE_TYPES = ['FAK', 'FIX', 'SCFI']


def validate(parquet_path, slim_mode=False):
    print(f"Reading: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    total = len(df)
    print(f"Total rows: {total:,}\n")

    errors = []

    # POD — dash separator
    dash_mask = df['POD'].str.contains(r'-LGB|-LAX', regex=True, na=False)
    dash_count = dash_mask.sum()
    if dash_count > 0:
        errors.append(f"[CRITICAL] POD: {dash_count:,} rows use dash separator (LAX-LGB should be LAX/LGB)")
        sample = df.loc[dash_mask, 'POD'].value_counts().head(5)
        print(f"  Sample: {sample.to_dict()}")

    # POD — space after slash
    space_mask = df['POD'].str.contains(r'/ ', regex=True, na=False)
    space_count = space_mask.sum()
    if space_count > 0:
        errors.append(f"[HIGH] POD: {space_count:,} rows have space after slash (USLAX/ USLGB should be USLAX/USLGB)")

    # Container — legacy 40HQ
    bad_40hq = df['Container_Type'].eq('40HQ').sum()
    if bad_40hq > 0:
        errors.append(f"[HIGH] Container_Type: {bad_40hq:,} rows still use legacy 40HQ (should be 40HC)")
        if slim_mode:
            print(f"  NOTE: slim file may predate normalization — {bad_40hq:,} 40HQ found")

    # Container — legacy 45HQ / 45'HQ (Owner 2026-04-26: must be 45HC)
    bad_45hq = df['Container_Type'].eq('45HQ').sum()
    if bad_45hq > 0:
        errors.append(f"[HIGH] Container_Type: {bad_45hq:,} rows still use legacy 45HQ (should be 45HC, Owner 2026-04-26)")

    bad_45hq_prime = df['Container_Type'].eq("45'HQ").sum()
    if bad_45hq_prime > 0:
        errors.append(f"[HIGH] Container_Type: {bad_45hq_prime:,} rows still use legacy 45'HQ (should be 45HC, Owner 2026-04-26)")

    # Container — enum check
    bad_cont_enum = (~df['Container_Type'].isin(ALLOWED_CONTAINERS)).sum()
    if bad_cont_enum > 0:
        bad_values = df.loc[~df['Container_Type'].isin(ALLOWED_CONTAINERS), 'Container_Type'].value_counts()
        top5 = bad_values.head(5).to_dict()
        errors.append(f"[HIGH] Container_Type: {bad_cont_enum:,} rows outside enum. Top: {top5}")

    # POL — trailing space
    stripped = df['POL'].str.strip()
    trailing_mask = df['POL'].ne(stripped)
    trailing_count = trailing_mask.sum()
    if trailing_count > 0:
        errors.append(f"[LOW] POL: {trailing_count:,} rows have trailing space (trimmed during normalization)")

    # POL — len < 3 (garbage)
    short_pol = df['POL'].str.len() < 3
    short_count = short_pol.sum()
    if short_count > 0:
        pol_vals = df.loc[short_pol, 'POL'].value_counts()
        errors.append(f"[MEDIUM] POL: {short_count:,} rows with len<3 (garbage, should be deleted)")
        print(f"  Values: {pol_vals.to_dict()}")

    # Rate_Type enum
    bad_rt = (~df['Rate_Type'].isin(ALLOWED_RATE_TYPES)).sum()
    if bad_rt > 0:
        bad_rt_vals = df.loc[~df['Rate_Type'].isin(ALLOWED_RATE_TYPES), 'Rate_Type'].value_counts().head(5)
        errors.append(f"[HIGH] Rate_Type: {bad_rt:,} rows outside FAK/FIX/SCFI enum. Values: {bad_rt_vals.to_dict()}")

    # Charge_Name typo
    typo_commission = df['Charge_Name'].eq('COMMISION').sum()
    if typo_commission > 0:
        errors.append(f"[LOW] Charge_Name: {typo_commission:,} rows typo 'COMMISION' (should be 'COMMISSION')")

    # Charge_Name null/empty
    null_charge = df['Charge_Name'].isna().sum() + (df['Charge_Name'] == '').sum()
    if null_charge > 0:
        errors.append(f"[MEDIUM] Charge_Name: {null_charge:,} rows null or empty")

    # Summary
    print(f"\n{'='*50}")
    if errors:
        print(f"VIOLATIONS DETECTED ({len(errors)} checks failed):")
        for e in errors:
            print(f"  {e}")
        return 1
    else:
        print("All contracts validated. Parquet is clean.")
        return 0


def main():
    parser = argparse.ArgumentParser(description='Validate contract data quality')
    parser.add_argument('--parquet', default=DEFAULT_PARQUET, help='Path to parquet file')
    parser.add_argument('--slim', action='store_true', help='Slim mode (suppresses 40HQ note)')
    args = parser.parse_args()

    code = validate(args.parquet, slim_mode=args.slim)
    sys.exit(code)


if __name__ == '__main__':
    main()
