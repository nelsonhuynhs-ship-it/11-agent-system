# -*- coding: utf-8 -*-
"""
Master Loader V2 - Mapping-Driven Column Selection
Uses Mapping CSV files to correctly identify Basic O/F vs Total columns
"""
import pandas as pd
import os
import numpy as np
import sys
import glob

# Fix encoding for Windows console (guard for pythonw.exe where stdout=None)
if sys.platform == 'win32':
    import io
    if sys.stdout is None or not hasattr(sys.stdout, 'buffer') or sys.stdout.buffer is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    else:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)  # Pricing_Engine folder
# Resolve OneDrive canonical paths via shared/paths (single source of truth).
try:
    _repo_root = os.path.dirname(BASE_DIR)
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from shared import paths as _sp
    DATA_DIR = str(_sp.PRICING_DATA)
    MAPPING_DIR = str(_sp.MAPPING_DIR)
except Exception as _e:
    print(f"[WARN] shared.paths unavailable ({_e}); using legacy repo paths")
    DATA_DIR = os.path.join(BASE_DIR, "data")  # Pricing_Engine/data
MAPPING_DIR = os.path.join(BASE_DIR, "Mapping")  # Pricing_Engine/Mapping
HISTORY_DIR = DATA_DIR  # Luôn lưu parquet trong Pricing_Engine/data
OUTPUT_FILE = os.path.join(HISTORY_DIR, "Cleaned_Master_History.parquet")
def _find_puc_file():
    """Auto-detect latest PUC file (PUC_SOC.xlsx or PUC {MONTH} {YEAR}.xlsx)."""
    import glob
    legacy = os.path.join(DATA_DIR, "PUC_SOC.xlsx")
    if os.path.exists(legacy):
        return legacy
    # Search DATA_DIR and OneDrive pricing for PUC*.xlsx
    candidates = glob.glob(os.path.join(DATA_DIR, "PUC*.xlsx"))
    # Also check OneDrive pricing path if different
    try:
        import sys
        sys.path.insert(0, os.path.dirname(BASE_DIR))
        from shared import paths as sp
        for d in [sp.PRICING_DATA, sp.PRICING_DATA / "rate-tables"]:
            candidates.extend(glob.glob(str(d / "PUC*.xlsx")))
    except Exception:
        pass
    candidates = [f for f in candidates if "PUC_SOC" not in os.path.basename(f)]
    candidates.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    if candidates:
        print(f"  [PUC] Auto-detected: {os.path.basename(candidates[0])}")
        return candidates[0]
    return legacy

PUC_SOC_FILE = _find_puc_file()

# Container type normalization
CONTAINER_NORMALIZE = {
    "20'": "20GP", "40'": "40GP", "40'HC": "40HQ",
    "20GP": "20GP", "40GP": "40GP", "40HQ": "40HQ",
    "45'HQ": "45'HQ", "40NOR": "40NOR",
    "20RF": "20RF", "40RF": "40RF"
}

# Charge name normalization - map to standard names
CHARGE_NORMALIZE = {
    "BASE O/F": "BASIC O/F",
    # NOTE: "BASIC O/F" is kept as-is (not merged into Base Ocean Freight)
    # so the Basic Cost sheet can show the true base O/F separately from ALL IN COST
    "ALL IN COST": "Total Ocean Freight",  # Keep separate from Basic
    "HLCU Offer": "Total Ocean Freight",  # SCFI: HLCU Offer = all-in rate
    "ISPS": "ISPS",
    "DLF": "DLF",
    "EMF": "EMF",
    "COMMISSION": "COMMISSION"
}

CORE_HEADERS = ["POL", "POD", "Place", "Note", "Group Rate", "Carrier", "Eff", "Exp", "Commodity", "Contract"]

# Rate priority for smart dedup
RATE_PRIORITY = {
    'FAK': 1, 'FIX': 2, 'SCFI': 3, 'SPECIAL': 4, 'OCR': 5
}


def excel_col_to_idx(col_letter):
    """Convert Excel column letter (A, B, ..., Z, AA, AB...) to 0-based index"""
    result = 0
    for char in col_letter.upper():
        result = result * 26 + (ord(char) - ord('A') + 1)
    return result - 1


# ─────────────────────────────────────────────────────────────────────────────
# PUC SOC RULES (CMA / ONE / YML only)
# ─────────────────────────────────────────────────────────────────────────────
# These 3 carriers quote SOC rates with PUC sometimes included, sometimes not.
# The FAK file has a dedicated column 'PSS/PUC' per container type.
#
# RULE 1 — FAK PUC cell is empty (0):  Total = Basic + PUC_SOC
# RULE 2 — FAK PUC < PUC_SOC:          Total = Basic + FAK_PUC + (PUC_SOC - FAK_PUC) = Basic + PUC_SOC
# RULE 3 — FAK PUC >= PUC_SOC:         Total = Basic + FAK_PUC  (no change, already correct)
#
# In all cases, the CORRECT Total Ocean Freight = Basic + PUC_SOC  (Rules 1 & 2)
#                                               = Basic + FAK_PUC  (Rule 3, PUC_SOC <= FAK)
# i.e., always: Total = Basic + max(FAK_PUC, PUC_SOC)
# ─────────────────────────────────────────────────────────────────────────────

PUC_CARRIERS = {'CMA', 'ONE', 'YML', 'HPL'}   # SOC carriers that use PUC_SOC.xlsx correction

# Place name aliases: PUC file uses full names, parquet uses port codes
_PUC_PLACE_ALIASES = {
    'LOS ANGELES': ['LAX', 'LGB', 'LAX/LGB', 'LONG BEACH'],
    'NEW YORK': ['NYC', 'NEWARK', 'NEW YORK/NEW JERSEY'],
    'SAVANNAH': ['SAV'],
    'HOUSTON': ['HOU'],
    'NORFOLK': ['ORF'],
    'CHARLESTON': ['CHS'],
    'MIAMI': ['MIA'],
    'CHICAGO': ['CHI'],
    'DALLAS': ['DAL', 'DFW'],
    'SEATTLE': ['SEA'],
    'PORTLAND': ['PDX'],
    'ST LOUIS': ['SAINT LOUIS'],
    'ST PAUL': ['SAINT PAUL'],
    'MOBILE': ['MOB'],
    'MEMPHIS': ['MEM'],
    'ATLANTA': ['ATL'],
}


def load_puc_soc_lookup(puc_file: str) -> dict:
    """
    Load PUC_SOC.xlsx into a lookup dict:
      { normalized_place: {'20GP': float, '40GP': float, '40HQ': float, "45'HQ": float} }
    Returns {} if file not found or error.
    """
    if not os.path.exists(puc_file):
        print(f"  [PUC] PUC_SOC.xlsx not found at {puc_file}")
        return {}
    try:
        df_puc = pd.read_excel(puc_file, header=0)
        # Normalise header: first col = PlaceOfDelivery or Place
        df_puc.columns = [str(c).strip() for c in df_puc.columns]
        place_col = next((c for c in df_puc.columns if 'place' in c.lower()), df_puc.columns[0])

        # Resolve container columns (various header styles)
        def _find_col(candidates):
            for c in candidates:
                if c in df_puc.columns:
                    return c
                # Try numeric (40 stored as int)
                try:
                    if int(float(c)) in df_puc.columns or str(int(float(c))) in df_puc.columns:
                        return str(int(float(c)))
                except Exception:
                    pass
            return None

        col_20 = _find_col(['20GP', '20DC', '20', 'Col_20'])
        col_40 = _find_col(['40GP', '40HC', '40HQ', '40', 'Col_40'])
        col_45 = _find_col(["45'HQ", '45HQ', '45', 'Col_45'])
        # Fallback: use positional (0-indexed after place col)
        cols = list(df_puc.columns)
        place_idx = cols.index(place_col)
        if col_20 is None and len(cols) > place_idx + 1:
            col_20 = cols[place_idx + 1]
        if col_40 is None and len(cols) > place_idx + 2:
            col_40 = cols[place_idx + 2]
        if col_45 is None and len(cols) > place_idx + 3:
            col_45 = cols[place_idx + 3]

        lookup = {}
        for _, row in df_puc.iterrows():
            place_raw = str(row.get(place_col, '')).strip()
            if not place_raw or place_raw.lower() in ('nan', 'placeofdelivery', 'place'):
                continue
            place_key = place_raw.upper().split(',')[0].strip()  # normalize

            def _get(col):
                if col is None:
                    return 0.0
                v = row.get(col, 0)
                try:
                    # Allow negative PUC (rebates) — do NOT clip with max(0,)
                    return float(v) if pd.notna(v) else 0.0
                except Exception:
                    return 0.0

            v40 = _get(col_40)
            lookup[place_key] = {
                '20GP':  _get(col_20),
                '40GP':  v40,
                '40HQ':  v40,   # same as 40GP unless 45 col exists
                "45'HQ": _get(col_45) or v40,
                '40NOR': v40,
            }
        # Expand aliases: LOS ANGELES → also match LAX, LGB, LONG BEACH
        expanded = {}
        for place_key, vals in lookup.items():
            expanded[place_key] = vals
            for alias_src, alias_targets in _PUC_PLACE_ALIASES.items():
                if place_key == alias_src:
                    for t in alias_targets:
                        if t not in expanded:
                            expanded[t] = vals
                # Reverse: if parquet has full name but PUC has code
                for t in alias_targets:
                    if place_key == t and alias_src not in expanded:
                        expanded[alias_src] = vals
        lookup = expanded
        print(f"  [PUC] Loaded {len(lookup)} place entries (with aliases) from PUC_SOC.xlsx")
        return lookup
    except Exception as exc:
        print(f"  [PUC] Error loading PUC_SOC.xlsx: {exc}")
        return {}


def apply_puc_soc_correct(df: pd.DataFrame, puc_file: str) -> pd.DataFrame:
    """
    Apply correct PUC logic for CMA/ONE/YML SOC 'Total Ocean Freight' rows.

    Reads the FAK 'PSS/PUC' sub-charge recorded in the Parquet for the same
    Carrier/POL/POD/Place/Container/Eff/Exp key, then:

      correct_puc = max(fak_puc_in_data, puc_soc_lookup)
      Total_OF    = Basic_OF + correct_puc

    The function:
      1. Keeps BASIC O/F rows unchanged (raw reference).
      2. Upserts 'Total Ocean Freight' rows for CMA/ONE/YML SOC
         using Basic_OF + corrected PUC.
      3. Leaves all other carriers / non-SOC rows untouched.
    """
    puc_lookup = load_puc_soc_lookup(puc_file)
    if not puc_lookup:
        print("  [PUC] No PUC lookup — skipping PUC correction")
        return df

    # Only correct Total Ocean Freight and ALL IN COST — BASIC O/F must stay raw
    BASE_CHARGES = ['Total Ocean Freight', 'ALL IN COST']
    PSS_PUC_LABEL = 'PSS/PUC'  # Charge_Name label stored from mapping cols AM-AP

    # ── Identify CMA/ONE/YML SOC rows ──────────────────────────────────────
    mask_carrier = df['Carrier'].str.upper().apply(
        lambda c: any(t in str(c).upper() for t in PUC_CARRIERS)
    )
    mask_soc = df['Note'].str.upper().str.contains('SOC', na=False)
    mask_base = df['Charge_Name'].isin(BASE_CHARGES)
    soc_base_mask = mask_carrier & mask_soc & mask_base

    # ── Build FAK PUC lookup from existing PSS/PUC charge rows ─────────────
    pss_rows = df[
        mask_carrier & mask_soc &
        (df['Charge_Name'].str.contains('PSS|PUC', case=False, na=False))
    ].copy()
    df['_amt'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)

    # Key: (Carrier, POL, POD, Place, Container_Type, Eff, Exp) → FAK PUC value
    KEY_COLS = ['Carrier', 'POL', 'POD', 'Place', 'Container_Type', 'Eff', 'Exp']
    pss_lookup = {}
    if len(pss_rows) > 0:
        pss_rows['_amt'] = pd.to_numeric(pss_rows['Amount'], errors='coerce').fillna(0.0)
        for _, row in pss_rows.iterrows():
            key = tuple(str(row.get(c, '')) for c in KEY_COLS)
            pss_lookup[key] = max(pss_lookup.get(key, 0.0), row['_amt'])

    print(f"  [PUC] {soc_base_mask.sum()} CMA/ONE/YML SOC base rows to process")
    print(f"  [PUC] {len(pss_lookup)} FAK PSS/PUC sub-charge keys found")

    corrected = 0
    skipped   = 0

    for idx in df[soc_base_mask].index:
        row    = df.loc[idx]
        cont   = str(row.get('Container_Type', ''))
        place  = str(row.get('Place', '')).strip().upper().split(',')[0].strip()
        basic  = float(row.get('_amt', 0) or 0)

        # PUC_SOC target for this place+container
        puc_target = puc_lookup.get(place, {}).get(cont, 0.0)
        if puc_target == 0.0:
            skipped += 1
            continue  # Exactly 0 = no rule → leave unchanged
        # Non-zero (positive OR negative) = rule applies

        # FAK embedded PUC (from PSS/PUC column rows)
        key = tuple(str(row.get(c, '')) for c in KEY_COLS)
        fak_puc = pss_lookup.get(key, 0.0)

        # 3-case rule — works for both positive (surcharge) and negative (rebate):
        #
        # POSITIVE PUC (surcharge — most destinations):
        #   Case 1: fak_puc == 0          → add full puc_target
        #   Case 2: fak_puc < puc_target  → add delta to top up
        #   Case 3: fak_puc >= puc_target → already correct, skip
        #
        # NEGATIVE PUC (rebate — El Paso, Denver, Phoenix, Salt Lake, Halifax):
        #   Case 1: fak_puc == 0           → add puc_target (negative → reduces amount)
        #   Case 2: fak_puc > puc_target   → FAK rebate is smaller, apply full puc_target
        #   Case 3: fak_puc <= puc_target  → FAK already has equal/more rebate, skip
        if puc_target >= 0:
            # Positive surcharge logic
            if fak_puc >= puc_target:
                skipped += 1   # Rule 3: already correct
                continue
        else:
            # Negative rebate logic (reversed inequality)
            if fak_puc <= puc_target:
                skipped += 1   # Rule 3: FAK already has as much/more rebate
                continue

        puc_to_add = puc_target - fak_puc
        df.at[idx, 'Amount'] = basic + puc_to_add
        corrected += 1

    df.drop(columns=['_amt'], errors='ignore', inplace=True)
    print(f"  [PUC] Corrected {corrected} rows | Skipped {skipped} (already correct or no PUC entry)")
    return df


# Keep old function name as alias pointing to correct logic
def strip_puc_from_soc_rows(df, puc_file):
    """DEPRECATED — Redirects to apply_puc_soc_correct (correct 3-case PUC logic)."""
    return apply_puc_soc_correct(df, puc_file)



def load_mapping_file(mode, filename):
    """Load mapping CSV file for the given mode (FAK/SCFI/FIX)"""
    if not os.path.exists(MAPPING_DIR):
        return None
    
    # Find matching mapping file
    pattern = f"V4_FINAL_CHECK_{mode}_*.csv"
    mapping_files = glob.glob(os.path.join(MAPPING_DIR, pattern))
    
    if not mapping_files:
        return None
    
    # Read the first matching mapping file
    try:
        mapping_df = pd.read_csv(mapping_files[0])
        print(f"  [MAPPING] Loaded: {os.path.basename(mapping_files[0])}")
        return mapping_df
    except Exception as e:
        print(f"  [!] Error loading mapping: {e}")
        return None


def parse_file_with_mapping(file_path, file_name, mode):
    """Parse Excel file using mapping-driven column selection"""
    
    # Load mapping
    mapping_df = load_mapping_file(mode, file_name)
    
    # Read raw Excel — SCFI files have 'RATE TABLE' sheet
    header_rows = 2 if mode in ["FAK", "SCFI"] else 1
    if mode == "SCFI":
        try:
            xls = pd.ExcelFile(file_path)
            if 'RATE TABLE' in xls.sheet_names:
                df_full = pd.read_excel(file_path, sheet_name='RATE TABLE', header=None)
                print(f"  [SHEET] Reading 'RATE TABLE' sheet")
            else:
                df_full = pd.read_excel(file_path, header=None)
                print(f"  [SHEET] No 'RATE TABLE' sheet, using first sheet")
        except Exception:
            df_full = pd.read_excel(file_path, header=None)
    else:
        df_full = pd.read_excel(file_path, header=None)
    df_data = df_full.iloc[header_rows:, :].copy().reset_index(drop=True)  # Reset index!
    
    all_records = []
    
    if mapping_df is not None:
        # === MAPPING-DRIVEN PARSING ===
        
        # Build column index map from mapping
        col_map = {}
        for _, row in mapping_df.iterrows():
            if pd.isna(row.get('Excel_Col')) or row.get('Status', 'ACTIVE') != 'ACTIVE':
                continue
            
            col_letter = str(row['Excel_Col']).strip()
            charge_group = str(row.get('Charge_Group', '')).strip() if pd.notna(row.get('Charge_Group')) else ''
            cont_type = str(row.get('Cont_Type', '')).strip() if pd.notna(row.get('Cont_Type')) else ''
            
            if col_letter and charge_group:
                col_idx = excel_col_to_idx(col_letter)
                col_map[col_idx] = {
                    'charge': charge_group,
                    'container': cont_type
                }
        
        # Extract base columns (POL, POD, Place, Eff, Exp, etc.)
        base_col_indices = []
        base_col_names = []
        
        for idx, info in col_map.items():
            if info['charge'] in ['POL', 'POD', 'PlaceOfDelivery', 'Place of Delivery', 
                                   'Effective Date', 'Expiration Date', 'CARRIER',
                                   'Commodity', 'Contract Identifier', 'Routing note',
                                   'Group rate or Service note']:
                base_col_indices.append(idx)
                # Normalize column name
                charge = info['charge']
                if 'Effective' in charge: charge = 'Eff'
                elif 'Expiration' in charge: charge = 'Exp'
                elif 'Place' in charge: charge = 'Place'
                elif 'Routing' in charge: charge = 'Note'  # Only Routing note -> Note (contains SOC)
                elif 'Group rate' in charge: charge = 'Group Rate'  # Group rate -> separate col
                elif 'Contract' in charge: charge = 'Contract'
                elif 'CARRIER' in charge: charge = 'Carrier'
                base_col_names.append(charge)
        
        # Extract base data
        base_data = {}
        for idx, name in zip(base_col_indices, base_col_names):
            if idx < df_data.shape[1]:
                base_data[name] = df_data.iloc[:, idx]
        
        # Fill missing base columns
        for col in CORE_HEADERS:
            if col not in base_data:
                if mode == "SCFI" and col == "Carrier":
                    base_data[col] = "HPL"
                elif mode == "SCFI" and col == "POL":
                    base_data[col] = "HCM"
                else:
                    base_data[col] = ""
        
        # Extract price columns (charges with container types)
        for idx, info in col_map.items():
            if not info['container']:  # Skip non-price columns
                continue
            if idx >= df_data.shape[1]:
                continue
            
            charge_name = info['charge']
            container_type = info['container']
            
            # Normalize charge name
            if charge_name in CHARGE_NORMALIZE:
                charge_name = CHARGE_NORMALIZE[charge_name]
            
            # Normalize container type
            if container_type in CONTAINER_NORMALIZE:
                container_type = CONTAINER_NORMALIZE[container_type]
            
            # Get values for this column
            values = pd.to_numeric(df_data.iloc[:, idx], errors='coerce')
            
            # Create records for non-null values
            for row_idx, amount in enumerate(values):
                if pd.notna(amount) and amount != 0:
                    def _get_val(key, default=''):
                        """Get value from base_data: handles both Series and scalar."""
                        v = base_data.get(key, default)
                        if isinstance(v, pd.Series):
                            return v.iloc[row_idx] if row_idx < len(v) else default
                        return v  # scalar string (e.g. 'HPL', 'HCM')
                    
                    record = {
                        'POL': _get_val('POL'),
                        'POD': _get_val('POD'),
                        'Place': _get_val('Place'),
                        'Carrier': _get_val('Carrier', 'HPL' if mode == 'SCFI' else ''),
                        'Commodity': _get_val('Commodity'),
                        'Contract': _get_val('Contract'),
                        'Eff': _get_val('Eff'),
                        'Exp': _get_val('Exp'),
                        'Note': '' if mode == 'SCFI' else _get_val('Note'),
                        'Group Rate': _get_val('Group Rate'),
                        'Charge_Name': charge_name,
                        'Container_Type': container_type,
                        'Amount': amount,
                        'Source_File': file_name,
                        'Rate_Type': mode
                    }
                    all_records.append(record)
    else:
        # === FALLBACK: Original parsing logic ===
        print(f"  [!] No mapping found, using fallback parsing")
        # Use simplified extraction
        return parse_file_fallback(df_full, df_data, file_name, mode, header_rows)
    
    return pd.DataFrame(all_records) if all_records else pd.DataFrame()


def parse_file_fallback(df_full, df_data, file_name, mode, header_rows):
    """Fallback parsing when no mapping file exists"""
    row_parent = df_full.iloc[0].ffill()
    col_names = []
    
    for i in range(df_full.shape[1]):
        charge = str(row_parent[i]).strip() if i < len(row_parent) else "Extra"
        cont = ""
        if header_rows > 1:
            cont = str(df_full.iloc[1, i]).strip()
        col_names.append(f"{charge}|{cont}|{i}")
    
    df_data.columns = col_names
    
    # Basic column extraction
    if mode == "SCFI":
        base_indices = [0, 1, 2, 3, 4]
        used_headers = ["POL", "POD", "Place", "Eff", "Exp"]
    else:
        base_indices = [0, 1, 2, 3, 5, 6, 7, 9, 11]
        used_headers = ["POL", "POD", "Place", "Note", "Carrier", "Eff", "Exp", "Commodity", "Contract"]
    
    valid_base_cols = [col_names[i] for i in base_indices if i < len(col_names)]
    final_headers = used_headers[:len(valid_base_cols)]
    
    # Add missing columns for SCFI
    if mode == "SCFI":
        for missing_col in ["Carrier", "Commodity", "Contract", "Note"]:
            temp_col_name = f"__{missing_col}__"
            df_data[temp_col_name] = "HPL" if missing_col == "Carrier" else ""
            valid_base_cols.append(temp_col_name)
            final_headers.append(missing_col)
    
    # Price columns start at index 5 for SCFI, 12 for FAK
    price_start_idx = 5 if mode == "SCFI" else 12
    price_cols = [c for c in col_names[price_start_idx:]]
    
    melted = df_data.melt(
        id_vars=valid_base_cols,
        value_vars=price_cols,
        var_name="Charge_Meta", value_name="Amount"
    )
    
    col_rename_dict = dict(zip(valid_base_cols, final_headers))
    melted = melted.rename(columns=col_rename_dict)
    
    meta_split = melted["Charge_Meta"].str.split("|", expand=True)
    melted["Charge_Name"] = meta_split[0]
    melted["Container_Type"] = meta_split[1].replace(CONTAINER_NORMALIZE)
    
    melted["Source_File"] = file_name
    melted["Rate_Type"] = mode
    melted["Amount"] = pd.to_numeric(melted["Amount"], errors='coerce')
    
    return melted.dropna(subset=["Amount"])


def master_loader_v2():
    """Main loader function with mapping-driven parsing"""
    
    # Collect Excel files - only pricing files (FAK, SCFI, SPECIAL RATE)
    EXCLUDE_FILES = ['PUC_SOC', 'Port_Code', 'Schedule', 'Master', 'Group_Code']
    files = [f for f in os.listdir(DATA_DIR) 
             if f.endswith('.xlsx') 
             and not f.startswith('~$') 
             and not any(excl in f for excl in EXCLUDE_FILES)]
    if not files:
        print(f"[!] No Excel files found in: {DATA_DIR}")
        return
    
    print(f"[+] Found {len(files)} files to process")
    print(f"[+] Mapping directory: {MAPPING_DIR}")
    
    all_data_list = []
    
    for file_name in files:
        file_path = os.path.join(DATA_DIR, file_name)
        print(f"\n[>] Processing: {file_name}")
        
        fname_up = file_name.upper()
        mode = "FAK" if "FAK" in fname_up else ("SCFI" if "SCFI" in fname_up else "FIX")
        
        try:
            df_result = parse_file_with_mapping(file_path, file_name, mode)
            if not df_result.empty:
                all_data_list.append(df_result)
                print(f"  [OK] Extracted {len(df_result):,} records")
        except Exception as e:
            print(f"  [!] Error: {e}")
            import traceback
            traceback.print_exc()
    
    if not all_data_list:
        print("[!] No data extracted")
        return
    
    print("\n[+] Merging all data...")
    final_df = pd.concat(all_data_list, ignore_index=True)
    print(f"  → Total records: {len(final_df):,}")
    
    # String cleanup
    for col in CORE_HEADERS + ["Charge_Name", "Container_Type", "Source_File"]:
        if col in final_df.columns and col not in ["Eff", "Exp"]:
            final_df[col] = final_df[col].astype(str).replace('nan', '')

    # === APPLY CORRECT PUC TO SOC ROWS (CMA/ONE/YML — 3-case rule) ===
    print("\n[+] Applying PUC_SOC correction to CMA/ONE/YML SOC rows...")
    final_df = apply_puc_soc_correct(final_df, PUC_SOC_FILE)

    # Reefer logic
    is_reefer = final_df['Commodity'].str.contains("REEFER", case=False, na=False)
    is_target_carrier = final_df['Carrier'].str.upper().isin(["ONE", "COSCO"])
    final_df.loc[is_reefer & is_target_carrier & final_df['Container_Type'].str.contains("20", na=False), 'Container_Type'] = "20RF"
    final_df.loc[is_reefer & is_target_carrier & final_df['Container_Type'].str.contains("40", na=False), 'Container_Type'] = "40RF"
    
    # Date conversion
    final_df['Eff'] = pd.to_datetime(final_df['Eff'], errors='coerce')
    final_df['Exp'] = pd.to_datetime(final_df['Exp'], errors='coerce')
    
    # === APPEND TO EXISTING DATA ===
    existing_df = None
    if os.path.exists(OUTPUT_FILE):
        print(f"\n[+] Reading existing parquet...")
        try:
            existing_df = pd.read_parquet(OUTPUT_FILE)
            print(f"  → Existing: {len(existing_df):,} rows")
        except Exception as e:
            print(f"  ! Parquet corrupted: {e}")
            existing_df = None
    
    if existing_df is not None:
        combined_df = pd.concat([existing_df, final_df], ignore_index=True)
        print(f"  → Combined: {len(combined_df):,} rows")
        
        # Smart dedup
        combined_df['Rate_Priority'] = combined_df['Rate_Type'].map(RATE_PRIORITY).fillna(99)
        combined_df = combined_df.sort_values(
            by=['POL', 'POD', 'Carrier', 'Container_Type', 'Rate_Priority', 'Source_File'],
            ascending=[True, True, True, True, True, False]
        )
        combined_df = combined_df.drop_duplicates(
            subset=['POL', 'POD', 'Carrier', 'Place', 'Commodity', 'Note',
                    'Container_Type', 'Charge_Name', 'Eff', 'Exp'],
            keep='first'
        )
        combined_df = combined_df.drop(columns=['Rate_Priority'])
        print(f"  → After dedup: {len(combined_df):,} rows")
        final_df = combined_df
    else:
        print("\n[+] Creating new parquet...")
        final_df['Rate_Priority'] = final_df['Rate_Type'].map(RATE_PRIORITY).fillna(99)
        final_df = final_df.sort_values(
            by=['POL', 'POD', 'Carrier', 'Container_Type', 'Rate_Priority', 'Source_File'],
            ascending=[True, True, True, True, True, False]
        )
        final_df = final_df.drop_duplicates(
            subset=['POL', 'POD', 'Carrier', 'Place', 'Commodity', 'Note',
                    'Container_Type', 'Charge_Name', 'Eff', 'Exp'],
            keep='first'
        )
        final_df = final_df.drop(columns=['Rate_Priority'])
    
    # Ensure output directory exists
    if not os.path.exists(os.path.dirname(OUTPUT_FILE)):
        os.makedirs(os.path.dirname(OUTPUT_FILE))
    
    # Save
    final_df.to_parquet(OUTPUT_FILE, index=False, engine='pyarrow')
    
    print(f"\n[COMPLETE]")
    print(f"→ Saved to: {OUTPUT_FILE}")
    print(f"→ Total rows: {len(final_df):,}")
    
    # Breakdown by charge type
    if 'Charge_Name' in final_df.columns:
        print(f"\n[CHARGE BREAKDOWN]")
        for charge, count in final_df['Charge_Name'].value_counts().head(10).items():
            print(f"  → {charge}: {count:,}")
    
    # Breakdown by rate type
    if 'Rate_Type' in final_df.columns:
        print(f"\n[RATE TYPE BREAKDOWN]")
        for rate_type, count in final_df['Rate_Type'].value_counts().items():
            print(f"  → {rate_type}: {count:,}")


if __name__ == "__main__":
    master_loader_v2()
