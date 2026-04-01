# -*- coding: utf-8 -*-
"""
EasyOCR Implementation for COSCO Reefer Pricing Extraction
23-row structure with proper POD vs PlaceOfDelivery distinction
"""

import os
import re
import sys
import io
from datetime import datetime
import pandas as pd

# Fix Windows console encoding issue (guard for pythonw.exe where stdout=None)
if sys.platform == 'win32':
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    elif sys.stdout is None:
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    elif sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
MAPPING_FILE = os.path.join(BASE_DIR, "data", "Port_Code_Mapping_Final.xlsx")

# --- COSCO REEFER 23-ROW DESTINATION MASTER ---
# Maps OCR patterns to structured POD + PlaceOfDelivery
COSCO_DESTINATION_MASTER = [
    # Direct West Coast
    {'patterns': ['LGB/LA', 'LA/LGB', 'LAX/LGB', 'LGB', 'LGBZLA'], 
     'destinations': [
         {'POD': 'USLAX', 'Place': 'LOS ANGELES, CA'},
         {'POD': 'USLGB', 'Place': 'LONG BEACH, CA'}
     ]},
    {'patterns': ['SEATTLE'], 'destinations': [{'POD': 'USSEA', 'Place': 'SEATTLE, WA'}]},
    {'patterns': ['TACOMA'], 'destinations': [{'POD': 'USTIW', 'Place': 'TACOMA, WA'}]},
    {'patterns': ['OAKLAND'], 'destinations': [{'POD': 'USOAK', 'Place': 'OAKLAND, CA'}]},
    
    # East Coast
    {'patterns': ['NEW YORK', 'NEWYORK', 'NEW O'], 'destinations': [{'POD': 'USNYC', 'Place': 'NEW YORK, NY'}]},
    {'patterns': ['NORFOLK'], 'destinations': [{'POD': 'USORF', 'Place': 'NORFOLK, VA'}]},
    {'patterns': ['SAVANNAH'], 'destinations': [{'POD': 'USSAV', 'Place': 'SAVANNAH, GA'}]},
    {'patterns': ['CHARLESTON'], 'destinations': [{'POD': 'USCHS', 'Place': 'CHARLESTON, SC'}]},
    {'patterns': ['BOSTON'], 'destinations': [{'POD': 'USBOS', 'Place': 'BOSTON, MA'}]},
    
    # Gulf Ports - Houston/Mobile split
    {'patterns': ['HOUSTON/MOBILE', 'HOUSTON MOBILE', 'HOUSTON'], 
     'destinations': [
         {'POD': 'USHOU', 'Place': 'HOUSTON, TX'},
         {'POD': 'USMOB', 'Place': 'MOBILE, AL'}
     ]},
    
    # Baltimore/Miami split
    {'patterns': ['BALTIMORE/MIAMI', 'BALTIMORE MIAMI'], 
     'destinations': [
         {'POD': 'USBAL', 'Place': 'BALTIMORE, MD'},
         {'POD': 'USMIA', 'Place': 'MIAMI, FL'}
     ]},
    
    # Canada - Vancouver direct
    {'patterns': ['VANCOUVER'], 'destinations': [{'POD': 'CAVAN', 'Place': 'VANCOUVER, BC'}]},
    
    # Canada - Halifax direct  
    {'patterns': ['HALIFAX'], 'destinations': [{'POD': 'CAHAL', 'Place': 'HALIFAX, NS'}]},
    
    # Canada - Via Vancouver (Toronto/Montreal)
    {'patterns': ['TOR/MTL VIA VAN', 'TORIMTL VIA VAN', 'TOR MTL VIA VAN', 'TORONTO VIA VAN', 'MONTREAL VIA VAN'],
     'destinations': [
         {'POD': 'CAVAN', 'Place': 'TORONTO, ON'},
         {'POD': 'CAVAN', 'Place': 'MONTREAL, QC'}
     ]},
    
    # Canada - Via Halifax (Toronto/Montreal)
    {'patterns': ['TOR/MTL VIA HAL', 'TORIMTL VIA HAL', 'TOR MTL VIA HAL', 'TORONTO VIA HAL', 'MONTREAL VIA HAL'],
     'destinations': [
         {'POD': 'CAHAL', 'Place': 'TORONTO, ON'},
         {'POD': 'CAHAL', 'Place': 'MONTREAL, QC'}
     ]},
    
    # Inland via LA/LB - Chicago
    {'patterns': ['CHICAGO VIA LA', 'CHICAGO VIA LALB', 'CHICAGO VIA LA/LB', 'CHICAGO'],
     'destinations': [{'POD': 'USLAX/USLGB', 'Place': 'CHICAGO, IL'}]},
    
    # Inland via LA/LB - Kansas City (EXTRA - inherits Chicago surcharges)
    {'patterns': ['KANSAS CITY', 'KANSAS VIA LA', 'KANSAS CITY VIA LA/LB', 'KANSAS'],
     'destinations': [{'POD': 'USLAX/USLGB', 'Place': 'KANSAS CITY, KS', 'surcharge_from': 'CHICAGO'}]},
    
    # Gulf extras (inherit Houston surcharges)
    {'patterns': ['TAMPA'], 
     'destinations': [{'POD': 'USTPA', 'Place': 'TAMPA, FL', 'surcharge_from': 'HOUSTON'}]},
    {'patterns': ['NEW ORLEANS', 'NEWORLEANS', 'NEW O', 'NEWO', 'N ORLEANS', 'NOLA'], 
     'destinations': [{'POD': 'USMSY', 'Place': 'NEW ORLEANS, LA', 'surcharge_from': 'HOUSTON'}]},
]


def extract_with_easyocr(image_path, template):
    """Extract pricing data using EasyOCR"""
    import easyocr
    
    print(f"      > Initializing EasyOCR...")
    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    
    print(f"      > Running OCR on image...")
    result = reader.readtext(image_path)
    
    # Extract text and positions
    text_data = []
    for detection in result:
        bbox = detection[0]
        text = detection[1]
        conf = detection[2]
        x = (bbox[0][0] + bbox[2][0]) / 2
        y = (bbox[0][1] + bbox[2][1]) / 2
        text_data.append({'text': text, 'x': x, 'y': y, 'confidence': conf})
    
    print(f"      > Extracted {len(text_data)} text blocks")
    
    # Parse based on carrier
    if template and template.carrier == 'COSCO':
        pricing_rows = parse_cosco_reefer_table(text_data, template, image_path)
    elif template and template.carrier == 'WHL':
        pricing_rows = parse_whl_dry_table(text_data, template, image_path)
    else:
        pricing_rows = []
    
    return pricing_rows


def parse_cosco_reefer_table(text_data, template, image_path):
    """
    Parse COSCO Reefer table - outputs 23 rows per POL with proper POD/PlaceOfDelivery
    """
    # Sort by Y position
    text_data = sorted(text_data, key=lambda x: x['y'])
    
    # Extract dates from "EFFECTIVE FROM 26 JAN - 28 FEB"
    eff_date, exp_date = extract_dates_from_text(text_data)
    print(f"      > Detected validity: {eff_date} to {exp_date}")
    
    # Group by rows
    rows = group_by_rows(text_data, y_threshold=20)
    print(f"      > Found {len(rows)} potential rows")
    
    pricing_rows = []
    
    for row in rows:
        row = sorted(row, key=lambda x: x['x'])
        
        # Skip headers and footers
        row_text = ' '.join([item['text'] for item in row]).upper()
        if 'POL' in row_text and 'POD' in row_text:
            continue
        if 'EFFECTIVE' in row_text or 'SUBJECT' in row_text:
            continue
        
        if len(row) < 3:
            continue
        
        try:
            # Extract POL
            pol_text = row[0]['text']
            pol = normalize_pol(pol_text)
            
            # Extract POD text
            pod_text = row[1]['text'].strip()
            
            # Skip if POD looks like a price
            if parse_price(pod_text) is not None:
                print(f"      ! Skipping: POD '{pod_text}' looks like price")
                continue
            
            # Extract prices
            prices = []
            for item in row[2:]:
                price = parse_price(item['text'])
                if price:
                    prices.append(price)
            
            if not prices:
                continue
            
            # Match POD to destination master list
            destinations = match_destination(pod_text)
            
            if not destinations:
                print(f"      ! Unknown destination: '{pod_text}'")
                # Create single row for unknown
                destinations = [{'POD': pod_text[:5].upper(), 'Place': pod_text}]
            
            # Create pricing rows for each destination
            for dest in destinations:
                # 40RF price
                if len(prices) >= 1:
                    row_data = {
                        'POL': pol,
                        'POD': dest['POD'],
                        'PlaceOfDelivery': dest['Place'],
                        'Carrier': 'COSCO',
                        'Commodity': 'REEFER',
                        'Eff': eff_date,
                        'Exp': exp_date,
                        'Charge_Name': 'Base Ocean Freight',
                        'Container_Type': '40RF',
                        'Amount': prices[0],
                        'Note': dest.get('surcharge_from', ''),
                        'Source_File': os.path.basename(image_path)
                    }
                    pricing_rows.append(row_data)
                
                # 20RF price
                if len(prices) >= 2:
                    row_data = {
                        'POL': pol,
                        'POD': dest['POD'],
                        'PlaceOfDelivery': dest['Place'],
                        'Carrier': 'COSCO',
                        'Commodity': 'REEFER',
                        'Eff': eff_date,
                        'Exp': exp_date,
                        'Charge_Name': 'Base Ocean Freight',
                        'Container_Type': '20RF',
                        'Amount': prices[1],
                        'Note': dest.get('surcharge_from', ''),
                        'Source_File': os.path.basename(image_path)
                    }
                    pricing_rows.append(row_data)
        
        except Exception as e:
            print(f"      ! Error parsing row: {e}")
            continue
    
    print(f"      > Parsed {len(pricing_rows)} pricing rows")
    return pricing_rows


def match_destination(pod_text):
    """Match OCR pod text to destination master list"""
    pod_upper = pod_text.upper().strip()
    
    for entry in COSCO_DESTINATION_MASTER:
        for pattern in entry['patterns']:
            if pattern in pod_upper or pod_upper in pattern:
                return entry['destinations']
    
    # Fuzzy match - check if any pattern word is in the text
    for entry in COSCO_DESTINATION_MASTER:
        for pattern in entry['patterns']:
            pattern_words = pattern.split()
            if any(word in pod_upper for word in pattern_words if len(word) > 3):
                return entry['destinations']
    
    return None


def parse_whl_dry_table(text_data, template, image_path):
    """Parse WHL Dry table structure"""
    print(f"      ! WHL parsing not yet implemented")
    return []


def group_by_rows(text_data, y_threshold=20):
    """Group text blocks into rows based on Y position"""
    if not text_data:
        return []
    
    rows = []
    current_row = [text_data[0]]
    current_y = text_data[0]['y']
    
    for item in text_data[1:]:
        if abs(item['y'] - current_y) < y_threshold:
            current_row.append(item)
        else:
            rows.append(current_row)
            current_row = [item]
            current_y = item['y']
    
    if current_row:
        rows.append(current_row)
    
    return rows


def normalize_pol(pol_text):
    """Normalize POL to HCM, HPH, or DAD"""
    if not pol_text:
        return 'HCM'
    
    text = pol_text.upper().strip()
    
    if 'HPH' in text or 'HAI PHONG' in text:
        return 'HPH'
    if 'DAD' in text or 'DA NANG' in text:
        return 'DAD'
    if text.startswith('HCM') or text.startswith('HCW') or text.startswith('HC'):
        return 'HCM'
    if 'SGN' in text:
        return 'HCM'
    
    return 'HCM'


def parse_price(text):
    """Extract numeric price from text"""
    if not text:
        return None
    
    text = re.sub(r'[^\d.]', '', text)
    
    try:
        price = float(text)
        if 100 <= price <= 10000:
            return price
    except:
        pass
    
    return None


def extract_dates_from_text(text_data):
    """
    Extract dates from COSCO 'EFFECTIVE FROM 26 JAN - 28 FEB' format
    Handles: 26JAN-28FEB, 26 JAN - 28 FEB, 26JAN - 28FEB, etc.
    """
    all_text = ' '.join([item['text'] for item in text_data])
    all_text_upper = all_text.upper()
    
    month_map = {
        'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
        'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
        'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
    }
    
    year = '2026'
    
    # Multiple patterns for COSCO date format
    # Pattern 1: "26JAN-28FEB" or "26JAN - 28FEB" (compact, most common in COSCO)
    patterns = [
        r'(\d{1,2})\s*JAN\s*[-–]\s*(\d{1,2})\s*FEB',  # JAN-FEB specific
        r'(\d{1,2})\s*FEB\s*[-–]\s*(\d{1,2})\s*MAR',  # FEB-MAR
        r'(\d{1,2})\s*([A-Z]{3})\s*[-–]\s*(\d{1,2})\s*([A-Z]{3})',  # Generic DDMON-DDMON
    ]
    
    # Try JAN-FEB pattern first (most common for COSCO)
    jan_feb = re.search(r'(\d{1,2})\s*JAN\s*[-–]\s*(\d{1,2})\s*FEB', all_text_upper)
    if jan_feb:
        start_day = jan_feb.group(1).zfill(2)
        end_day = jan_feb.group(2).zfill(2)
        print(f"      > Date: {start_day} JAN - {end_day} FEB")
        return f"{year}-01-{start_day}", f"{year}-02-{end_day}"
    
    # Try FEB-MAR pattern
    feb_mar = re.search(r'(\d{1,2})\s*FEB\s*[-–]\s*(\d{1,2})\s*MAR', all_text_upper)
    if feb_mar:
        start_day = feb_mar.group(1).zfill(2)
        end_day = feb_mar.group(2).zfill(2)
        print(f"      > Date: {start_day} FEB - {end_day} MAR")
        return f"{year}-02-{start_day}", f"{year}-03-{end_day}"
    
    # Generic pattern: DDMON-DDMON
    generic = re.search(r'(\d{1,2})\s*([A-Z]{3})\s*[-–]\s*(\d{1,2})\s*([A-Z]{3})', all_text_upper)
    if generic:
        start_day = generic.group(1).zfill(2)
        start_month = month_map.get(generic.group(2), '01')
        end_day = generic.group(3).zfill(2)
        end_month = month_map.get(generic.group(4), '01')
        print(f"      > Date: {start_day}/{start_month} - {end_day}/{end_month}")
        return f"{year}-{start_month}-{start_day}", f"{year}-{end_month}-{end_day}"
    
    # Fallback: Look for separate date mentions
    for month_abbr, month_num in month_map.items():
        match = re.search(rf'(\d{{1,2}})\s*{month_abbr}', all_text_upper)
        if match:
            day = match.group(1).zfill(2)
            # Find second date
            remaining = all_text_upper[match.end():]
            for m2_abbr, m2_num in month_map.items():
                m2 = re.search(rf'(\d{{1,2}})\s*{m2_abbr}', remaining)
                if m2:
                    end_day = m2.group(1).zfill(2)
                    print(f"      > Date fallback: {day}/{month_num} - {end_day}/{m2_num}")
                    return f"{year}-{month_num}-{day}", f"{year}-{m2_num}-{end_day}"
    
    # Last resort: Use current date
    print(f"      ! No date found, using current date")
    today = datetime.now()
    return today.strftime('%Y-%m-%d'), "2026-02-28"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        from OCR_Engine.templates.cosco_reefer import CoscoReeferTemplate
        template = CoscoReeferTemplate()
        result = extract_with_easyocr(image_path, template)
        
        print(f"\n=== EXTRACTED {len(result)} ROWS ===")
        for row in result:
            note = f" (surcharge from {row['Note']})" if row['Note'] else ""
            print(f"{row['POL']} -> {row['POD']} | {row['PlaceOfDelivery']} | {row['Container_Type']}: ${row['Amount']}{note}")
