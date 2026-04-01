# -*- coding: utf-8 -*-
"""
parse_product_update.py — NLP parser for Custeam Product Update (.docx)

Extracts structured data from free-text weekly reports:
- Carrier space status (OPEN / TIGHT / FULL)
- Blank sailing events
- Equipment status
- Risk flags (roll, overweight, omit)
- Advisory notes

Usage:
  python parse_product_update.py data/Product\ update\ W08.docx
  python parse_product_update.py --all           # Parse all Product update files
  python parse_product_update.py --show          # Show parsed history
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
import json
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from docx import Document

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_JSON = DATA_DIR / "custeam" / "parsed_product_updates.json"
OUTPUT_PARQUET = DATA_DIR / "custeam" / "custeam_history.parquet"

# ─── CARRIER DETECTION ─────────────────────────────────────────
CARRIER_PATTERNS = {
    'ONE': r'\bONE\b',
    'YML': r'\bYML\b',
    'CMA': r'\bCMA\b',
    'MSC': r'\bMSC\b',
    'HPL': r'\bHPL\b|SCFI',
    'COSCO': r'\bCOSCO\b',
    'ZIM': r'\bZIM\b',
    'WHL': r'\bWHL\b|WAN HAI',
    'EMC': r'\bEMC\b|EVERGREEN',
    'HMM': r'\bHMM\b|HYUNDAI',
}

# ─── SPACE STATUS KEYWORDS ─────────────────────────────────────
FULL_KW = ['full', 'stop release', 'không release', 'ngưng release']
TIGHT_KW = ['protect case by case', 'roll', 'trimdown', 'sub to roll',
            'dấu hiệu roll', 'overweight', 'cần kéo rỗng sớm',
            'keep sớm', 'shipping guarantee']
OPEN_KW = ['open', 'chưa có dấu hiệu full', 'chưa full', 'rls bình thường',
           'release được', 'chưa ghi nhận']

# ─── BLANK SAILING / OMIT ──────────────────────────────────────
OMIT_RE = re.compile(
    r'(Z7S|ZXB|ZEX|PS\d|GS\d|EC\d|SAX|PN\d)\s+omit\s+(?:ETD\s+)?(\d{1,2}\s*\w{3})',
    re.IGNORECASE
)
BLANK_KW = ['omit', 'blank sailing', 'cancel', 'skip']

# ─── EQUIPMENT ──────────────────────────────────────────────────
EQUIP_SHORTAGE_KW = ['thiếu rỗng', 'shortage', 'thiếu container', 'thiếu']
EQUIP_NORMAL_KW = ['chưa ghi nhận', 'bình thường', 'normal', 'đủ rỗng']


def detect_week(text):
    """Extract week number and year from title line like 'Product update W08/2026'."""
    m = re.search(r'W(\d{1,2})\s*/?\s*(\d{4})', text)
    if m:
        week_num = int(m.group(1))
        year = int(m.group(2))
        # Convert ISO week to Monday date
        d = datetime.strptime(f'{year}-W{week_num:02d}-1', '%G-W%V-%u')
        return week_num, year, d.strftime('%Y-%m-%d')
    return None, None, None


def detect_section(line_upper):
    """Detect which section the line belongs to."""
    if 'SPECIAL NOTE' in line_upper:
        return 'SPECIAL_NOTE'
    if 'SPACE SITUATION' in line_upper:
        return 'SPACE'
    if 'EQUIPMENT' in line_upper:
        return 'EQUIPMENT'
    if 'BLANK SAILING' in line_upper or 'SCHEDULE' in line_upper:
        return 'SCHEDULE'
    return None


def detect_carriers(line):
    """Detect which carriers are mentioned in a line."""
    found = []
    for carrier, pattern in CARRIER_PATTERNS.items():
        if re.search(pattern, line, re.IGNORECASE):
            found.append(carrier)
    return found


def classify_space(line_lower):
    """Classify space status from text. Check OPEN first to handle negations."""
    # Check OPEN first (handles 'chưa có dấu hiệu full' before 'full')
    for kw in OPEN_KW:
        if kw in line_lower:
            return 'OPEN'
    for kw in FULL_KW:
        if kw in line_lower:
            return 'FULL'
    for kw in TIGHT_KW:
        if kw in line_lower:
            return 'TIGHT'
    return 'UNKNOWN'


def extract_omits(line):
    """Extract blank sailing/omit events: service + ETD date."""
    omits = []
    matches = OMIT_RE.findall(line)
    for service, etd in matches:
        omits.append({'service': service.upper(), 'etd': etd.strip()})
    # Also catch generic "omit" mentions
    if not matches and any(kw in line.lower() for kw in BLANK_KW):
        omits.append({'service': 'UNKNOWN', 'etd': ''})
    return omits


def extract_risk_flags(line_lower):
    """Extract risk indicators."""
    flags = []
    if 'roll' in line_lower:
        flags.append('ROLL_RISK')
    if 'overweight' in line_lower:
        flags.append('OVERWEIGHT')
    if 'omit' in line_lower:
        flags.append('BLANK_SAILING')
    if 'stop release' in line_lower:
        flags.append('STOP_RELEASE')
    if 'trimdown' in line_lower:
        flags.append('TRIMDOWN')
    if 'full' in line_lower and 'chưa' not in line_lower:
        flags.append('CAPACITY_FULL')
    return flags


def parse_product_update(filepath):
    """Parse a single Product Update docx file into structured data."""
    doc = Document(filepath)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not lines:
        return None

    # Detect week
    week_num, year, week_date = detect_week(lines[0])
    if not week_num:
        print(f"  ⚠️ Could not detect week from: {lines[0]}")
        return None

    result = {
        'week': week_num,
        'year': year,
        'week_date': week_date,
        'source_file': Path(filepath).name,
        'special_notes': [],
        'carriers': {},
        'equipment': 'NORMAL',
        'equipment_notes': '',
        'omit_events': [],
    }

    current_section = None
    current_carriers = []

    for line in lines[1:]:
        line_upper = line.upper().strip()
        line_lower = line.lower().strip()

        # Detect section change
        section = detect_section(line_upper)
        if section:
            current_section = section
            current_carriers = []
            continue

        # SPECIAL NOTE section
        if current_section == 'SPECIAL_NOTE':
            result['special_notes'].append(line)
            continue

        # EQUIPMENT section
        if current_section == 'EQUIPMENT':
            if any(kw in line_lower for kw in EQUIP_SHORTAGE_KW):
                result['equipment'] = 'SHORTAGE'
            elif any(kw in line_lower for kw in EQUIP_NORMAL_KW):
                result['equipment'] = 'NORMAL'
            result['equipment_notes'] = line
            continue

        # SPACE SITUATION section
        if current_section == 'SPACE':
            # Detect carriers mentioned
            mentioned = detect_carriers(line)
            if mentioned:
                current_carriers = mentioned

            # Classify space and extract data for current carrier(s)
            space = classify_space(line_lower)
            omits = extract_omits(line)
            risks = extract_risk_flags(line_lower)

            for carrier in current_carriers:
                if carrier not in result['carriers']:
                    result['carriers'][carrier] = {
                        'space_status': 'UNKNOWN',
                        'risk_flags': [],
                        'notes': [],
                        'omit_events': [],
                        'services_mentioned': [],
                    }

                c = result['carriers'][carrier]

                # Update space (only upgrade severity: UNKNOWN < OPEN < TIGHT < FULL)
                SEVERITY = {'UNKNOWN': 0, 'OPEN': 1, 'TIGHT': 2, 'FULL': 3}
                if SEVERITY.get(space, 0) > SEVERITY.get(c['space_status'], 0):
                    c['space_status'] = space

                c['risk_flags'].extend(risks)
                c['risk_flags'] = list(set(c['risk_flags']))
                c['notes'].append(line)

                if omits:
                    c['omit_events'].extend(omits)
                    result['omit_events'].extend(
                        [{**o, 'carrier': carrier} for o in omits]
                    )

                # Extract service names
                svc_matches = re.findall(
                    r'\b(PS\d|GS\d|EC\d|Z7S|ZXB|ZEX|SAX|PN\d|WC|EC)\b',
                    line, re.IGNORECASE
                )
                c['services_mentioned'].extend([s.upper() for s in svc_matches])
                c['services_mentioned'] = list(set(c['services_mentioned']))

    return result


def to_flat_records(parsed):
    """Convert parsed result to flat records for parquet storage."""
    records = []
    week_date = parsed['week_date']
    week = parsed['week']
    year = parsed['year']

    for carrier, data in parsed['carriers'].items():
        records.append({
            'Week': pd.Timestamp(week_date),
            'Week_Num': week,
            'Year': year,
            'Carrier': carrier,
            'Space_Status': data['space_status'],
            'Equipment': parsed['equipment'],
            'Risk_Flags': ','.join(data['risk_flags']) if data['risk_flags'] else '',
            'Blank_Sailings': len(data['omit_events']),
            'Services': ','.join(data['services_mentioned']),
            'Notes': ' | '.join(data['notes'][:3]),  # First 3 notes
            'Source': parsed['source_file'],
        })

    return records


def parse_all():
    """Parse all Product Update files in data/."""
    files = sorted(DATA_DIR.glob('Product update W*.docx'))
    if not files:
        print("📭 No Product Update files found in data/")
        return

    all_parsed = []
    all_records = []

    for fp in files:
        print(f"\n📄 Parsing: {fp.name}")
        result = parse_product_update(fp)
        if result:
            all_parsed.append(result)
            all_records.extend(to_flat_records(result))

            # Print summary
            print(f"   Week {result['week']}/{result['year']} ({result['week_date']})")
            for carrier, data in sorted(result['carriers'].items()):
                status_icon = {'OPEN': '🟢', 'TIGHT': '🟡', 'FULL': '🔴'}.get(
                    data['space_status'], '⚪')
                flags = f" [{','.join(data['risk_flags'])}]" if data['risk_flags'] else ''
                omits = f" | {len(data['omit_events'])} omit(s)" if data['omit_events'] else ''
                print(f"   {status_icon} {carrier:6s} {data['space_status']:6s}{flags}{omits}")

            if result['omit_events']:
                print(f"   🚫 Omit events:")
                for o in result['omit_events']:
                    print(f"      {o['carrier']} {o['service']} ETD {o['etd']}")

            print(f"   🔧 Equipment: {result['equipment']}")

    # Save JSON (full structured data)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(all_parsed, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n💾 Saved JSON: {OUTPUT_JSON}")

    # Save parquet (flat records)
    if all_records:
        df = pd.DataFrame(all_records)
        df.to_parquet(OUTPUT_PARQUET, index=False)
        print(f"💾 Saved parquet: {OUTPUT_PARQUET} ({len(df)} records)")

    return all_parsed


def show_summary():
    """Show parsed history summary."""
    if not OUTPUT_PARQUET.exists():
        print("📭 No parsed history yet. Run with --all first.")
        return

    df = pd.read_parquet(OUTPUT_PARQUET)
    print(f"\n📊 Custeam Product Update History:")
    print(f"   Weeks: {df['Week_Num'].min()} → {df['Week_Num'].max()}")
    print(f"   Records: {len(df)}")

    pivot = df.pivot_table(
        index='Carrier', columns='Week_Num',
        values='Space_Status', aggfunc='first'
    )
    print(f"\n   Space Status by Week:")
    icon_map = {'OPEN': '🟢', 'TIGHT': '🟡', 'FULL': '🔴', 'UNKNOWN': '⚪'}
    header = '   ' + ''.join(f'W{w:02d} ' for w in pivot.columns)
    print(header)
    for carrier in pivot.index:
        icons = ''.join(
            f' {icon_map.get(pivot.loc[carrier, w], "⚪")} ' for w in pivot.columns
        )
        print(f"   {carrier:6s}{icons}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parse Custeam Product Update')
    parser.add_argument('file', nargs='?', help='Specific docx file to parse')
    parser.add_argument('--all', '-a', action='store_true', help='Parse all files')
    parser.add_argument('--show', '-s', action='store_true', help='Show parsed summary')
    args = parser.parse_args()

    if args.show:
        show_summary()
    elif args.all:
        parse_all()
    elif args.file:
        result = parse_product_update(args.file)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        parse_all()
