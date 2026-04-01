"""
clean_parquet.py
================
Cleans the Cleaned_Master_History.parquet by removing rows that are:

  Rule A: "Total Ocean Freight" rows where Amount is below realistic minimum
          for Vietnam POL routes. These are sub-charges (surcharges, ISPS, etc.)
          that were incorrectly labeled as the total freight rate.
          
  Rule B: "Total Ocean Freight" rows where Place equals a raw port code
          (e.g. "LAX/LGB") AND an ICD/city rate for the SAME carrier/POD/cont
          exists in the data. We keep port-only rates ONLY when there is no
          better ICD alternative from the same carrier.

Saves cleaned file as:  Cleaned_Master_History_v2.parquet
Also overwrites:        Cleaned_Master_History.parquet  (after backup)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import shutil, os
from datetime import date

DATA_DIR = r'D:\NELSON\2. Areas\PricingSystem\Engine_test\Pricing_Engine\data'
SRC  = os.path.join(DATA_DIR, 'Cleaned_Master_History.parquet')
BKUP = os.path.join(DATA_DIR, 'Cleaned_Master_History_BACKUP.parquet')
OUT  = os.path.join(DATA_DIR, 'Cleaned_Master_History_v2.parquet')

print("Loading Parquet...", end='', flush=True)
df = pd.read_parquet(SRC)
print(f" {len(df):,} rows")

n_before = len(df)

# ─── RULE A: Remove sub-charges mislabeled as Total Ocean Freight ─────────────
# For VN POL routes, realistic min Total Ocean Freight (USD):
#   20GP/40GP/40HQ/45HQ must be > 500 to US/Canada
#   40NOR must be > 500 (NOR rates are special equipment, usually higher)
MIN_AMOUNT = {
    'HPH': 500, 'HCM': 500, 'DAD': 500, 'UIH': 500, 'VUT': 500,
}

is_total_freight = df['Charge_Name'].str.contains('Total Ocean Freight', na=False)

# Flag rows: VN POL + below threshold
def below_min(row):
    pol = str(row.get('POL', ''))
    min_val = MIN_AMOUNT.get(pol)
    if min_val is None:
        return False
    try:
        return float(row['Amount']) < min_val
    except:
        return False

vn_pol_mask = df['POL'].isin(['HPH', 'HCM', 'DAD', 'UIH', 'VUT'])
df['_amount_num'] = pd.to_numeric(df['Amount'], errors='coerce')

# Rule A: Total Ocean Freight + VN POL + Amount < 500
rule_a_mask = is_total_freight & vn_pol_mask & (df['_amount_num'] < 500)
n_rule_a = rule_a_mask.sum()
print(f"\nRule A (below $500 threshold): removing {n_rule_a:,} rows")
print("Sample:")
print(df[rule_a_mask][['Carrier','POL','POD','Place','Container_Type','Amount','Note','Source_File']].sort_values('Amount').head(10).to_string())

# ─── RULE B: Port-code-only Place where better ICD exists ──────────────────────
# Identify port-code-only Place: Place = POD value (exact match) or
# Place is a short code like "LAX/LGB", "LAX-LGB" containing "/" or "-" and <10 chars
total_freight_df = df[is_total_freight & ~rule_a_mask].copy()
total_freight_df['_amount_num2'] = pd.to_numeric(total_freight_df['Amount'], errors='coerce')

# Port-code indicator: Place == POD OR (Place has "/" or "-" AND len <= 10 AND no space)
is_port_code_place = (
    (total_freight_df['Place'] == total_freight_df['POD']) |
    (
        total_freight_df['Place'].str.contains(r'[-/]', na=False) &
        (total_freight_df['Place'].str.len() <= 10) &
        (~total_freight_df['Place'].str.contains(' ', na=False))
    )
)

port_code_rows = total_freight_df[is_port_code_place]
non_port_code_rows = total_freight_df[~is_port_code_place]

# For each port-code row, check if same Carrier+POL+POD+Container_Type has ICD alternatives
# Build lookup: set of (Carrier, POL, POD, Container_Type) with ICD rates
icd_keys = set(
    zip(
        non_port_code_rows['Carrier'],
        non_port_code_rows['POL'],
        non_port_code_rows['POD'],
        non_port_code_rows['Container_Type']
    )
)

def has_icd_alternative(row):
    key = (row['Carrier'], row['POL'], row['POD'], row['Container_Type'])
    return key in icd_keys

# Mark port-code rows that have ICD alternatives → remove them
port_code_with_icd = port_code_rows[port_code_rows.apply(has_icd_alternative, axis=1)]
n_rule_b = len(port_code_with_icd)
print(f"\nRule B (port-code-only Place with ICD alternatives): removing {n_rule_b:,} rows")
print("Sample:")
print(port_code_with_icd[['Carrier','POL','POD','Place','Container_Type','Amount']].drop_duplicates(['Carrier','POL','POD','Place','Container_Type']).sort_values('Amount').head(10).to_string())

# ─── APPLY CLEANING ────────────────────────────────────────────────────────────
bad_indices = set(df[rule_a_mask].index) | set(port_code_with_icd.index)
df_clean = df[~df.index.isin(bad_indices)].copy()
df_clean.drop(columns=['_amount_num'], errors='ignore', inplace=True)

n_after = len(df_clean)
n_removed = n_before - n_after
print(f"\n{'='*60}")
print(f"CLEANING RESULTS:")
print(f"  Original rows:  {n_before:,}")
print(f"  Rule A removed: {n_rule_a:,}")
print(f"  Rule B removed: {n_rule_b:,}")
print(f"  Total removed:  {n_removed:,}")
print(f"  Clean rows:     {n_after:,}")

# ─── VERIFY: Check if $391 YML is gone ────────────────────────────────────────
check = df_clean[
    (df_clean['Carrier'] == 'YML') &
    (df_clean['Amount'] == 391) &
    (df_clean['POL'] == 'HPH')
]
print(f"\n  $391 YML HPH rows remaining: {len(check)} ← should be 0")

# ─── SAVE ──────────────────────────────────────────────────────────────────────
print(f"\nBacking up original → {os.path.basename(BKUP)}")
shutil.copy2(SRC, BKUP)

print(f"Saving cleaned v2 → {os.path.basename(OUT)}")
df_clean.to_parquet(OUT, index=False)

print(f"Overwriting main file → {os.path.basename(SRC)}")
shutil.copy2(OUT, SRC)

print("\nDONE! Parquet cleaned and saved.")
print("Run bot /reload to pick up new data.")
