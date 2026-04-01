# -*- coding: utf-8 -*-
"""
Real OCR Implementation with PaddleOCR
Extracts actual pricing data from images
"""

import os
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

def extract_with_paddleocr(image_path, template):
    """
    Extract pricing data using PaddleOCR
    """
    from paddleocr import PaddleOCR
    
    print(f"      > Initializing PaddleOCR...")
    
    # Initialize OCR (removed show_log parameter)
    ocr = PaddleOCR(use_angle_cls=True, lang='en')
    
    print(f"      > Running OCR on image...")
    
    # Run OCR (removed cls parameter)
    result = ocr.ocr(image_path)
    
    # Extract text and positions
    text_data = []
    for line in result[0]:
        bbox = line[0]  # Bounding box
        text = line[1][0]  # Text
        conf = line[1][1]  # Confidence
        
        # Get position (top-left corner)
        x = bbox[0][0]
        y = bbox[0][1]
        
        text_data.append({
            'text': text,
            'x': x,
            'y': y,
            'confidence': conf
        })
    
    print(f"      > Extracted {len(text_data)} text blocks")
    
    # Parse into pricing rows
    pricing_rows = parse_cosco_reefer_table(text_data, template, image_path)
    
    return pricing_rows


def parse_cosco_reefer_table(text_data, template, image_path):
    """
    Parse COSCO Reefer table structure
    
    Expected format:
    POL              | POD           | 40RQ (spot) | 20RF (spot)
    HCM/Cai Mep/     | LGB/LA       | 2200        | 2600
    HCM/Cai Mep/     | Seattle      | 2200        | 2600
    ...
    """
    
    # Sort by Y position (top to bottom), then X (left to right)
    text_data = sorted(text_data, key=lambda x: (x['y'], x['x']))
    
    # Find header row (contains "POL", "POD", "40RQ", "20RF")
    header_idx = None
    for i, item in enumerate(text_data):
        text = item['text'].upper()
        if 'POL' in text or 'POD' in text:
            header_idx = i
            break
    
    if header_idx is None:
        print(f"      ! Warning: Could not find table header")
        return []
    
    # Group text by rows (similar Y positions)
    rows = group_by_rows(text_data[header_idx+1:])
    
    print(f"      > Found {len(rows)} data rows")
    
    # Parse each row
    pricing_rows = []
    
    for row in rows:
        try:
            # Sort by X position (left to right)
            row = sorted(row, key=lambda x: x['x'])
            
            # Extract fields
            if len(row) < 4:
                continue
            
            pol_text = row[0]['text']
            pod_text = row[1]['text']
            price_40rq = row[2]['text']
            price_20rf = row[3]['text'] if len(row) > 3 else None
            
            # Clean POL
            pol = template.parse_pol(pol_text) if template else pol_text.split('/')[0].strip()
            
            # Clean POD
            pod = template.parse_pod(pod_text) if template else pod_text.strip()
            
            # Parse prices
            price_40 = parse_price(price_40rq)
            price_20 = parse_price(price_20rf) if price_20rf else None
            
            # Get dates from image (look for "EFFECTIVE DATE")
            eff_date, exp_date = extract_dates_from_text(text_data)
            
            # Create pricing rows
            if price_40:
                pricing_rows.append({
                    'POL': pol,
                    'POD': map_pod_code(pod),
                    'Place': pod,
                    'Carrier': template.carrier if template else 'COSCO',
                    'Commodity': 'FAK',
                    'Eff': eff_date,
                    'Exp': exp_date,
                    'Charge_Name': 'Base Ocean Freight',
                    'Container_Type': '40RF',
                    'Amount': price_40,
                    'Note': '',
                    'Source_File': os.path.basename(image_path)
                })
            
            if price_20:
                pricing_rows.append({
                    'POL': pol,
                    'POD': map_pod_code(pod),
                    'Place': pod,
                    'Carrier': template.carrier if template else 'COSCO',
                    'Commodity': 'FAK',
                    'Eff': eff_date,
                    'Exp': exp_date,
                    'Charge_Name': 'Base Ocean Freight',
                    'Container_Type': '20RF',
                    'Amount': price_20,
                    'Note': '',
                    'Source_File': os.path.basename(image_path)
                })
        
        except Exception as e:
            print(f"      ! Error parsing row: {e}")
            continue
    
    return pricing_rows


def group_by_rows(text_data, y_threshold=15):
    """
    Group text blocks into rows based on Y position
    """
    if not text_data:
        return []
    
    rows = []
    current_row = [text_data[0]]
    current_y = text_data[0]['y']
    
    for item in text_data[1:]:
        if abs(item['y'] - current_y) < y_threshold:
            # Same row
            current_row.append(item)
        else:
            # New row
            rows.append(current_row)
            current_row = [item]
            current_y = item['y']
    
    # Add last row
    if current_row:
        rows.append(current_row)
    
    return rows


def parse_price(text):
    """
    Extract numeric price from text
    """
    if not text:
        return None
    
    # Remove non-numeric characters except decimal point
    text = re.sub(r'[^\d.]', '', text)
    
    try:
        return float(text)
    except:
        return None


def extract_dates_from_text(text_data):
    """
    Extract effective and expiry dates from text
    
    Look for patterns like:
    - "EFFECTIVE DATE 15-21 JAN"
    - "15-21 JAN"
    """
    
    # Combine all text
    all_text = ' '.join([item['text'] for item in text_data])
    
    # Look for date pattern
    date_pattern = r'(\d{1,2})-(\d{1,2})\s+(\w+)'
    match = re.search(date_pattern, all_text, re.IGNORECASE)
    
    if match:
        start_day = match.group(1)
        end_day = match.group(2)
        month = match.group(3).upper()
        
        # Map month to number
        month_map = {
            'JAN': '01', 'FEB': '02', 'MAR': '03', 'APR': '04',
            'MAY': '05', 'JUN': '06', 'JUL': '07', 'AUG': '08',
            'SEP': '09', 'OCT': '10', 'NOV': '11', 'DEC': '12'
        }
        
        month_num = month_map.get(month[:3], '01')
        year = '2026'  # Current year
        
        eff_date = f"{year}-{month_num}-{start_day.zfill(2)}"
        exp_date = f"{year}-{month_num}-{end_day.zfill(2)}"
        
        return eff_date, exp_date
    
    # Default dates
    return '2026-01-22', '2026-01-28'


def map_pod_code(pod_name):
    """
    Map POD name to standard code
    """
    pod_map = {
        'LGB/LA': 'USLAX',
        'LGB': 'USLGB',
        'LA': 'USLAX',
        'Seattle': 'USSEA',
        'Tacoma': 'USTIW',
        'Oakland': 'USOAK',
        'New York': 'USNYC',
        'Norfolk': 'USNFK',
        'Savannah': 'USSAV',
        'Charleston': 'USCHS',
        'Houston': 'USHOU',
        'Mobile': 'USMOB',
        'Boston': 'USBOS',
        'Baltimore': 'USBAL',
        'Miami': 'USMIA',
        'New Orleans': 'USMSY',
        'Tampa': 'USTPA',
        'Chicago': 'USCHI',
        'Dallas': 'USDAL',
        'Kansas': 'USKCK',
        'Vancouver': 'CAVAN',
        'Halifax': 'CAHAL',
        'Toronto': 'CATOR',
        'Montreal': 'CAMTR'
    }
    
    # Try exact match first
    if pod_name in pod_map:
        return pod_map[pod_name]
    
    # Try partial match
    for key, value in pod_map.items():
        if key.lower() in pod_name.lower():
            return value
    
    # Return as-is if no match
    return pod_name.upper()


if __name__ == "__main__":
    # Test
    import sys
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        
        from OCR_Engine.templates.cosco_reefer import CoscoReeferTemplate
        template = CoscoReeferTemplate()
        
        result = extract_with_paddleocr(image_path, template)
        
        print(f"\n=== EXTRACTED {len(result)} ROWS ===")
        for row in result:
            print(f"{row['POL']} -> {row['POD']} | {row['Container_Type']}: ${row['Amount']}")
