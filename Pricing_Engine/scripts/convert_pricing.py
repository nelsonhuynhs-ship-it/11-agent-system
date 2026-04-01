"""
convert_pricing.py — Auto-convert raw pricing files to standardized format

Usage:
  python convert_pricing.py --scfi "data/Origin/HPL SCFI CONTRACT 36.xlsx"
  python convert_pricing.py --special "data/Origin/Fixed Rate Summary Table NO.16.xlsx"
  python convert_pricing.py --scfi "data/Origin/HPL SCFI CONTRACT 36.xlsx" --output "data/HPL_SCFI_N36.xlsx"
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import argparse
import pandas as pd
import os
from pathlib import Path

# ═════════════════════════════════════════════════════════════
# Configuration
# ═════════════════════════════════════════════════════════════

# POL codes mapping (raw → standardized)
POL_MAP = {
    'VUT': 'HCM',
    'HCM': 'HCM',
    'HPH': 'HPH',
    'SGN': 'HCM',
    'VNSGN': 'HCM',
    'VNHPH': 'HPH',
}

# ═════════════════════════════════════════════════════════════
# SCFI Converter (HPL SCFI raw → standardized)
# ═════════════════════════════════════════════════════════════

def convert_scfi(input_file, output_file, default_pol='HCM'):
    """
    Convert raw HPL SCFI file to standardized format.
    
    RAW format (RATE TABLE sheet):
      Destination | via PORT | via | VALID | END | BASE O/F 20'/40'/40'HC | ...charges...
    
    Standardized format:
      POL | POD | PlaceOfDelivery | Effective Date | Expiration Date | BASE O/F 20'/40'/40'HC | ...charges...
    
    Key transform:
      - ADD POL (default "HCM")
      - via PORT → POD (gateway port)
      - Destination → PlaceOfDelivery (final destination)
      - DROP: via, HLCU Offer columns
    """
    print(f'📂 Loading SCFI: {input_file}')
    
    # Read from RATE TABLE sheet
    df_raw = pd.read_excel(input_file, sheet_name='RATE TABLE')
    print(f'   Raw data: {df_raw.shape[0]} rows × {df_raw.shape[1]} cols')
    
    # Get sub-header row (row 0 has container type labels: 20', 40', 40'HC)
    sub_headers = df_raw.iloc[0].tolist()
    
    # Remove sub-header row from data
    df = df_raw.iloc[1:].copy().reset_index(drop=True)
    
    # Remove empty rows
    df = df.dropna(subset=[df_raw.columns[0]], how='all').reset_index(drop=True)
    
    # Build output DataFrame
    result = pd.DataFrame()
    
    # POL (added - not in raw)
    result['POL'] = [default_pol] * len(df)
    
    # POD = via PORT (gateway port) — SWAPPED from raw
    result['POD'] = df.iloc[:, 1].values  # via PORT column
    
    # PlaceOfDelivery = Destination (final city) — SWAPPED from raw
    result['PlaceOfDelivery'] = df.iloc[:, 0].values  # Destination column
    
    # For base port rows (Dest == via PORT), Place = POD
    mask_same = result['POD'] == result['PlaceOfDelivery']
    # Keep as-is, both are the same for base ports
    
    # Effective Date & Expiration Date
    result['Effective Date'] = pd.to_datetime(df.iloc[:, 3])  # VALID column
    result['Expiration Date'] = pd.to_datetime(df.iloc[:, 4])  # END column
    
    # Charge columns — copy from raw, skip via(col2), VALID(col3), END(col4)
    # Identify charge columns: BASE O/F, ISPS, EMF, DLF, COMMISSION
    raw_cols = df_raw.columns.tolist()
    charge_groups = []
    skip_cols = {'Destination', 'via PORT', 'via', 'VALID', 'Unnamed: 4'}
    
    for i, col in enumerate(raw_cols):
        col_str = str(col)
        if col_str in skip_cols or 'Unnamed' in col_str:
            # Check if this unnamed col is part of a charge group
            if i > 0 and 'Unnamed' in col_str:
                # Part of previous charge group
                parent = None
                for j in range(i-1, -1, -1):
                    if 'Unnamed' not in str(raw_cols[j]):
                        parent = str(raw_cols[j])
                        break
                if parent and parent not in skip_cols and parent != 'HLCU Offer':
                    sub_h = sub_headers[i] if i < len(sub_headers) else ''
                    result[f'{parent}_{sub_h}'] = df.iloc[:, i].values
            continue
        if col_str == 'HLCU Offer':
            # Skip internal HPL pricing
            continue
        if col_str in ('BASE O/F', 'ISPS', 'EMF', 'DLF', 'COMMISSION'):
            sub_h = sub_headers[i] if i < len(sub_headers) else ''
            result[f'{col_str}_{sub_h}'] = df.iloc[:, i].values
    
    # Clean column names
    result.columns = [c.replace("_nan", "").strip() for c in result.columns]
    
    # Remove rows where POD is NaN
    result = result.dropna(subset=['POD']).reset_index(drop=True)
    
    # Save
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    result.to_excel(output_file, index=False)
    
    print(f'   ✅ Output: {result.shape[0]} rows → {output_file}')
    print(f'   Columns: {result.columns.tolist()}')
    
    # Statistics
    base_ports = mask_same.sum()
    inland = (~mask_same).sum()
    print(f'   Base port rows: {base_ports}')
    print(f'   Inland rows: {inland}')
    
    return result


# ═════════════════════════════════════════════════════════════
# Special Rate / Fixed Rate Converter
# ═════════════════════════════════════════════════════════════

def convert_special_rate(input_file, output_file, sheets=None):
    """
    Convert raw Fixed Rate / Special Rate file to standardized format.
    
    RAW format (Fixed Rate Summary Table):
      POL | POD | Place of Delivery | Transit Port | SERVICE note | MODE | 
      Carrier | Effective Date | Expiration Date | GROUP CODE | Transit time | 
      Contract Identifier | Base Ocean Freight 20GP/40GP/40HQ/45'HQ/40NOR
    
    OUTPUT format (matches V4_FINAL_CHECK_FIX_ONE_SPECIAL RATE.csv mapping):
      A: POL | B: POD | C: PlaceOfDelivery | D: Routing note | E: ROUTING |
      F: CARRIER | G: Effective Date | H: Expiration Date | 
      I: Group rate or Service note | J: Commodity | K: Transit time |
      L: Contract Identifier | M: 20GP | N: 40GP | O: 40HQ | P: 45'HQ | Q: 40NOR
    """
    print(f'📂 Loading Special Rate: {input_file}')
    
    xls = pd.ExcelFile(input_file)
    all_sheets = xls.sheet_names if sheets is None else sheets
    print(f'   Sheets: {all_sheets}')
    
    all_results = []
    
    for sheet_name in all_sheets:
        print(f'   Processing sheet: {sheet_name}')
        df_raw = pd.read_excel(xls, sheet_name=sheet_name)
        
        # Skip if empty
        if df_raw.shape[0] < 2:
            print(f'     ⚠️ Empty sheet, skipping')
            continue
        
        # Check for sub-header row (container types)
        first_row = df_raw.iloc[0]
        has_sub_header = any(str(v) in ['20GP', '40GP', '40HQ', "45'HQ", '40NOR'] 
                           for v in first_row.values if pd.notna(v))
        
        if has_sub_header:
            df = df_raw.iloc[1:].copy().reset_index(drop=True)
        else:
            df = df_raw.copy()
        
        # Map raw columns to values
        raw_data = {}
        for col in df_raw.columns:
            col_str = str(col).strip()
            if col_str == 'POL':
                raw_data['POL'] = df[col].map(lambda x: POL_MAP.get(str(x).strip(), str(x).strip()) if pd.notna(x) else x)
            elif col_str == 'POD':
                raw_data['POD'] = df[col]
            elif col_str in ('Place of Delivery', 'PlaceOfDelivery'):
                raw_data['Place'] = df[col]
            elif col_str == 'SERVICE note':
                raw_data['Note'] = df[col]
            elif col_str == 'MODE':
                raw_data['Routing'] = df[col]
            elif col_str == 'Carrier':
                raw_data['Carrier'] = df[col]
            elif col_str.startswith('Effective'):
                raw_data['Eff'] = pd.to_datetime(df[col], errors='coerce')
            elif col_str.startswith('Expir'):
                raw_data['Exp'] = pd.to_datetime(df[col], errors='coerce')
            elif col_str == 'GROUP CODE':
                raw_data['Group'] = df[col]
            elif col_str == 'Transit time':
                raw_data['Transit'] = df[col]
            elif col_str.startswith('Contract'):
                raw_data['Contract'] = df[col]
            elif col_str.startswith('Base Ocean'):
                base_idx = df_raw.columns.get_loc(col)
                for i, ct in enumerate(['20GP', '40GP', '40HQ', "45'HQ", '40NOR']):
                    cidx = base_idx + i
                    if cidx < len(df_raw.columns):
                        raw_data[ct] = df.iloc[:, cidx].values
        
        # Build output in EXACT V4 mapping column order
        n = len(df)
        result = pd.DataFrame()
        result['POL'] = raw_data.get('POL', [''] * n)
        result['POD'] = raw_data.get('POD', [''] * n)
        result['PlaceOfDelivery'] = raw_data.get('Place', [''] * n)
        result['Routing note'] = raw_data.get('Note', [''] * n)        # Col D
        result['ROUTING'] = raw_data.get('Routing', [''] * n)          # Col E
        result['CARRIER'] = raw_data.get('Carrier', [''] * n)          # Col F
        result['Effective Date'] = raw_data.get('Eff', [''] * n)       # Col G
        result['Expiration Date'] = raw_data.get('Exp', [''] * n)      # Col H
        result['Group rate or Service note'] = raw_data.get('Group', [''] * n)  # Col I
        result['Commodity'] = [''] * n                                  # Col J (not in raw)
        result['Transit time'] = raw_data.get('Transit', [''] * n)     # Col K
        result['Contract Identifier'] = raw_data.get('Contract', [''] * n)  # Col L
        result['Base Ocean Freight'] = raw_data.get('20GP', [None] * n) # Col M (20GP)
        # Unnamed columns for 40GP, 40HQ, 45'HQ, 40NOR (like original format)
        result['Unnamed: 13'] = raw_data.get('40GP', [None] * n)       # Col N (40GP)
        result['Unnamed: 14'] = raw_data.get('40HQ', [None] * n)       # Col O (40HQ)
        result['Unnamed: 15'] = raw_data.get("45'HQ", [None] * n)      # Col P (45'HQ)
        result['Unnamed: 16'] = raw_data.get('40NOR', [None] * n)      # Col Q (40NOR)
        
        # Remove empty rows
        result = result.dropna(subset=['POD'], how='all').reset_index(drop=True)
        
        all_results.append(result)
        print(f'     ✓ {result.shape[0]} rows')
    
    # Combine all sheets
    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        combined.to_excel(output_file, index=False)
        print(f'   ✅ Output: {combined.shape[0]} rows → {output_file}')
        return combined
    else:
        print('   ⚠️ No data found')
        return None


# ═════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Convert raw pricing files to standardized format')
    parser.add_argument('--scfi', help='Path to raw HPL SCFI file')
    parser.add_argument('--special', help='Path to raw Fixed Rate / Special Rate file')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--pol', default='HCM', help='Default POL for SCFI (default: HCM)')
    parser.add_argument('--sheets', nargs='*', help='Specific sheet names to process')
    
    args = parser.parse_args()
    
    if not args.scfi and not args.special:
        parser.print_help()
        print('\nExample:')
        print('  python convert_pricing.py --scfi "data/Origin/HPL SCFI CONTRACT 36.xlsx"')
        print('  python convert_pricing.py --special "data/Origin/Fixed Rate Summary Table NO.16.xlsx"')
        return
    
    if args.scfi:
        input_path = Path(args.scfi)
        if not args.output:
            # Auto-generate output name
            stem = input_path.stem.replace('CONTRACT', 'N').replace(' ', '_')
            args.output = str(input_path.parent.parent / f'{stem}_converted.xlsx')
        
        print('=' * 60)
        print('🔄 SCFI CONVERTER')
        print('=' * 60)
        convert_scfi(args.scfi, args.output, default_pol=args.pol)
    
    if args.special:
        input_path = Path(args.special)
        if not args.output:
            stem = input_path.stem.replace(' ', '_')
            args.output = str(input_path.parent.parent / f'{stem}_converted.xlsx')
        
        print('=' * 60)
        print('🔄 SPECIAL RATE CONVERTER')
        print('=' * 60)
        convert_special_rate(args.special, args.output, sheets=args.sheets)


if __name__ == '__main__':
    main()
