# -*- coding: utf-8 -*-
"""
normalize_parquet.py — Apply pipeline_rules.json normalization
==============================================================
Normalizes Container_Type, Commodity, Note, and Source_File
in the master Parquet file.

Usage:
  python Pricing_Engine/scripts/normalize_parquet.py
  
Can also be imported:
  from normalize_parquet import normalize_parquet_data
  normalize_parquet_data()
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
import shutil
import pandas as pd
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PE_DIR = os.path.dirname(SCRIPT_DIR)  # Pricing_Engine/
PARQUET_FILE = os.path.join(PE_DIR, "data", "Cleaned_Master_History.parquet")
BACKUP_DIR = os.path.join(PE_DIR, "data", "_backup")

# ══════════════════════════════════════════════════════════════════
# CONTAINER TYPE NORMALIZATION
# ══════════════════════════════════════════════════════════════════
CONTAINER_MAP = {
    "20'":   "20GP",
    "40'":   "40GP",
    "40'HC": "40HQ",
    "45'HQ": "45HQ",
    "40NOR": "40NOR",
    # Already correct names pass through
}

def normalize_container_types(df):
    """Normalize Container_Type column using CONTAINER_MAP."""
    if 'Container_Type' not in df.columns:
        return df, 0
    before = df['Container_Type'].nunique()
    df['Container_Type'] = df['Container_Type'].replace(CONTAINER_MAP)
    after = df['Container_Type'].nunique()
    changed = before - after
    return df, changed


# ══════════════════════════════════════════════════════════════════
# COMMODITY NORMALIZATION
# ══════════════════════════════════════════════════════════════════

# Universal rules (all carriers)
UNIVERSAL_COMMODITY = [
    # FAK Including Garment variants
    (r'FAK\s*\(?(?:Including|Incl)[\s.]*Garment', 'FAK INCL GARMENT'),
    # FAK Excluding Garment variants
    (r'FAK\s*\(?(?:Excluding|Excl)[\s.]*Garment', 'FAK EXCL GARMENT'),
]

# Carrier-specific rules (checked after universal)
CARRIER_COMMODITY = {
    "COSCO": [
        (r'Garments?/Textile', 'GARMENT'),
    ],
    "ONE": [
        (r'REEFER', 'REEFER FAK'),
        (r'FAK:\s*TPE1\s*-\s*FAK\s*Straight', 'FAK: TPE1'),
        (r'SHORT\s*TERM\s*GDSM', 'SHORT TERM GDSM'),
        (r'GARMENT', 'GARMENT'),
        (r'S1.*TPE9.*Group\s*SOC', 'S1-TPE9 Group SOC'),
    ],
    "YML": [
        (r'GROUP\s*A\s*:\s*FAK\s*\(NON.HAZ', 'GROUP A : FAK'),
        (r'FAK\s*\(NON.HAZ', 'FAK'),
        (r'SHIPS.*BOATS.*VEHICLES', 'VEHICLES/CARS'),
    ],
    "CMA": [
        (r'subject\s+to\s+Panama', 'PANAMA SURCHG'),
        (r'direct\s+service', 'DIRECT SVC'),
    ],
    "EMC": [
        (r'RATE\s*1\s*-?\s*GENERAL\s*CARGO', 'RATE 1'),
    ],
    "ZIM": [
        (r'subject\s+to\s+OWS\s+for\s+20GP', 'OWS 20GP'),
        # FAK including garment handled by universal rule
    ],
}

def normalize_commodity(commodity, carrier):
    """Normalize a single commodity value."""
    if not commodity or pd.isna(commodity):
        return ''
    commodity = str(commodity).strip()
    if not commodity:
        return ''

    # Universal rules first
    for pattern, replacement in UNIVERSAL_COMMODITY:
        if re.search(pattern, commodity, re.IGNORECASE):
            return replacement

    # Carrier-specific rules
    if carrier in CARRIER_COMMODITY:
        for pattern, replacement in CARRIER_COMMODITY[carrier]:
            if re.search(pattern, commodity, re.IGNORECASE):
                return replacement

    # Truncate very long commodity strings (>60 chars)
    if len(commodity) > 60:
        return commodity[:57] + '...'

    return commodity


# ══════════════════════════════════════════════════════════════════
# NOTE NORMALIZATION
# ══════════════════════════════════════════════════════════════════

SOC_TRANSIT_KEYWORDS = ['YANTIAN', 'KAOHSIUNG', 'HONG KONG', 'SINGAPORE', 'SHANGHAI']

# Carrier-specific note rules (checked first for carrier-specific patterns)
CARRIER_NOTE_RULES = {
    "ZIM": [
        (r'Z7S.*OWS\s*incl', 'Z7S OWS INCL'),
        (r'Z7S.*(?:subject\s+to|OWS)', 'Z7S OWS EXTRA'),
        (r'Z7S', 'Z7S'),
        (r'ZXB.*OWS\s*incl', 'ZXB OWS INCL'),
        (r'ZXB.*(?:subject\s+to|OWS)', 'ZXB OWS EXTRA'),
        (r'ZXB', 'ZXB'),
        (r'ZEX', 'ZEX'),
    ],
    "EMC": [
        (r'(?:TRF\s+)?PCTF.*STF.*(?:CMEP|CAI\s*MEP)', 'via CMEP PCTF/STF'),
        (r'(?:TRF\s+)?PCTF.*STF', 'PCTF/STF SURCHG'),
        (r'(?:PCS|SUEZ).*(?:CMEP|CAI\s*MEP)', 'via CMEP PCS/SUEZ'),
        (r'PCS|SUEZ', 'PCS/SUEZ'),
        (r'(?:via\s+)?(?:CMEP|CAI\s*MEP)', 'via CMEP'),
    ],
    "COSCO": [
        (r'NILE.*POINTE', 'NILE/P-NOIRE'),
        (r'via\s+OPNW', 'via OPNW'),
    ],
    "MSC": [
        (r'America.*Empire.*Amberjack|AMR.*EMP.*AMB', 'AMR/EMP/AMB SvcGroup1'),
        (r'Sentosa.*Pearl', 'Sentosa/Pearl'),
        (r'LONE\s*STAR.*PELICAN', 'LONE STAR/PELICAN'),
        (r'(?:on\s+)?Chinook', 'Chinook'),
    ],
    "CMA": [
        (r'service\s*:\s*SAX\s*CS', 'SAX CS'),
        (r'service\s*:\s*TWS\s*EVER', 'TWS EVER'),
    ],
}

def normalize_note(note, carrier):
    """Normalize a single note value."""
    if not note or pd.isna(note):
        return ''
    note = str(note).strip()
    if not note:
        return ''
    note_upper = note.upper()

    # Carrier-specific rules first
    if carrier in CARRIER_NOTE_RULES:
        for pattern, replacement in CARRIER_NOTE_RULES[carrier]:
            if re.search(pattern, note, re.IGNORECASE):
                return replacement

    # SOC routing (all carriers)
    if 'SOC' in note_upper:
        for kw in SOC_TRANSIT_KEYWORDS:
            if kw in note_upper:
                return 'SOC TRANSIT'
        if 'CAI MEP' in note_upper or 'EC3' in note_upper or 'CMEP' in note_upper:
            return 'SOC Cai Mep (EC3)'
        if any(x in note_upper for x in ['DIRECT', 'HPH', 'HAIPHONG']):
            return 'SOC DIRECT'
        if 'BRVT' in note_upper:
            return 'SOC BRVT'
        return 'SOC'

    # Non-SOC routing
    for kw in SOC_TRANSIT_KEYWORDS:
        if kw.lower() in note.lower() or kw in note_upper:
            return 'TRANSIT'
    if 'CAI MEP' in note_upper or 'CMEP' in note_upper:
        return 'Cai Mep (EC3)'
    if 'DIRECT' in note_upper:
        return 'DIRECT'
    if 'BRVT' in note_upper:
        return 'via BRVT'

    # CY/R and similar short notes — keep as is
    if len(note) < 20:
        return note

    # Truncate very long notes
    if len(note) > 40:
        return note[:37] + '...'

    return note


# ══════════════════════════════════════════════════════════════════
# SOURCE NORMALIZATION
# ══════════════════════════════════════════════════════════════════

def normalize_source(source):
    """Shorten source file name."""
    if not source or pd.isna(source):
        return ''
    s = str(source).strip()
    su = s.upper()
    if 'FAK' in su:
        m = re.search(r'(\d{1,2})\s*([A-Z]{3})\s*NO\.?\s*(\d+)', su)
        if m:
            return f"FAK {m.group(1)}{m.group(2)} NO.{m.group(3)}"
        return 'FAK'
    if 'SCFI' in su:
        return 'SCFI'
    if 'FIX' in su:
        return 'FIX'
    if 'SPECIAL' in su:
        return 'SPECIAL RATE'
    if 'OCR' in su:
        return 'OCR'
    return s[:15] if len(s) > 15 else s


# ══════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ══════════════════════════════════════════════════════════════════

def normalize_parquet_data(parquet_path=None, backup=True):
    """
    Apply all normalization rules to the Parquet file.
    Returns dict with stats.
    """
    path = parquet_path or PARQUET_FILE

    if not os.path.exists(path):
        print(f"[ERROR] Parquet not found: {path}")
        return None

    print(f"\n{'='*60}")
    print(f"  PARQUET NORMALIZATION")
    print(f"{'='*60}")

    df = pd.read_parquet(path)
    total = len(df)
    print(f"  Loaded: {total:,} rows, {len(df.columns)} columns")

    stats = {}

    # Step 1: Container type
    df, ct_changes = normalize_container_types(df)
    stats['container_types_merged'] = ct_changes
    if 'Container_Type' in df.columns:
        print(f"  [1/4] Container types: {df['Container_Type'].nunique()} unique")

    # Step 2: Commodity
    if 'Commodity' in df.columns:
        before_nunique = df['Commodity'].nunique()
        df['Commodity'] = df.apply(
            lambda r: normalize_commodity(r.get('Commodity', ''), r.get('Carrier', '')),
            axis=1
        )
        after_nunique = df['Commodity'].nunique()
        stats['commodity_before'] = before_nunique
        stats['commodity_after'] = after_nunique
        print(f"  [2/4] Commodity: {before_nunique} → {after_nunique} unique values")

    # Step 3: Note
    if 'Note' in df.columns:
        before_nunique = df['Note'].nunique()
        df['Note'] = df.apply(
            lambda r: normalize_note(r.get('Note', ''), r.get('Carrier', '')),
            axis=1
        )
        after_nunique = df['Note'].nunique()
        stats['note_before'] = before_nunique
        stats['note_after'] = after_nunique
        print(f"  [3/4] Note: {before_nunique} → {after_nunique} unique values")

    # Step 4: Source
    source_col = 'Source_File' if 'Source_File' in df.columns else 'Source'
    if source_col in df.columns:
        before_nunique = df[source_col].nunique()
        df[source_col] = df[source_col].apply(normalize_source)
        after_nunique = df[source_col].nunique()
        stats['source_before'] = before_nunique
        stats['source_after'] = after_nunique
        print(f"  [4/4] Source: {before_nunique} → {after_nunique} unique values")

    # Report top values
    print(f"\n  === AFTER NORMALIZATION ===")
    for col in ['Commodity', 'Note', source_col]:
        if col in df.columns:
            print(f"\n  {col} top 8:")
            for val, cnt in df[col].value_counts().head(8).items():
                print(f"    {cnt:>10,}  {val}")

    # Backup
    if backup:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        backup_path = os.path.join(BACKUP_DIR, f"Parquet_pre_normalize_{ts}.parquet")
        shutil.copy2(path, backup_path)
        stats['backup'] = backup_path
        print(f"\n  [BACKUP] {backup_path}")

    # Save
    df.to_parquet(path, index=False)
    stats['rows'] = total
    print(f"  [SAVED] {total:,} rows normalized")
    print(f"{'='*60}")

    return stats


if __name__ == "__main__":
    result = normalize_parquet_data()
    if not result:
        sys.exit(1)
