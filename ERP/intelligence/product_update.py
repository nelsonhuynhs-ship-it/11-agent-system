"""
Market Intelligence - Product Update Parser
Parses weekly product updates from Word documents
"""

import os
import re
from docx import Document
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Carrier keywords for detection
CARRIERS = ['HPL', 'ONE', 'YML', 'MSC', 'CMA', 'COSCO', 'ZIM', 'WHL', 'EMC']

def parse_product_update(filepath):
    """
    Parse Product Update Word document
    Returns structured dictionary
    """
    doc = Document(filepath)
    
    result = {
        'week': '',
        'special_notes': [],
        'space_situation': {},
        'equipment': {},
        'raw_text': ''
    }
    
    current_section = None
    current_carrier = None
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
            
        result['raw_text'] += text + '\n'
        
        # Detect week
        if 'Product update' in text:
            match = re.search(r'W(\d+)/(\d+)', text)
            if match:
                result['week'] = f"W{match.group(1)}-{match.group(2)}"
        
        # Detect sections
        if text == 'SPECIAL NOTE':
            current_section = 'special_note'
            continue
        elif text == 'SPACE SITUATION':
            current_section = 'space'
            continue
        elif text == 'EQUIPMENT':
            current_section = 'equipment'
            continue
        
        # Parse content based on section
        if current_section == 'special_note':
            if text not in ['SPACE SITUATION', 'EQUIPMENT']:
                result['special_notes'].append(text)
        
        elif current_section == 'space':
            # Check if this is a carrier header
            carrier_match = None
            for c in CARRIERS:
                if text.upper().startswith(c):
                    carrier_match = c
                    break
            
            if carrier_match:
                current_carrier = carrier_match
                if current_carrier not in result['space_situation']:
                    result['space_situation'][current_carrier] = {
                        'status': 'UNKNOWN',
                        'notes': []
                    }
                # Parse status from first line
                if 'full' in text.lower():
                    result['space_situation'][current_carrier]['status'] = 'FULL'
                elif 'open' in text.lower() or 'chưa có dấu hiệu full' in text.lower():
                    result['space_situation'][current_carrier]['status'] = 'OPEN'
                result['space_situation'][current_carrier]['notes'].append(text)
            elif current_carrier and text:
                result['space_situation'][current_carrier]['notes'].append(text)
        
        elif current_section == 'equipment':
            for c in CARRIERS:
                if text.upper().startswith(c):
                    # Extract equipment info
                    result['equipment'][c] = {
                        'note': text,
                        'quality': 'BAD' if 'xấu' in text.lower() else 'GOOD' if 'đẹp' in text.lower() else 'NORMAL'
                    }
                    break
    
    return result


def get_carrier_summary(update_data, carrier):
    """Get summary for specific carrier"""
    space = update_data.get('space_situation', {}).get(carrier, {})
    equip = update_data.get('equipment', {}).get(carrier, {})
    
    status = space.get('status', '-')
    notes = space.get('notes', [])
    equip_note = equip.get('note', '')
    
    return {
        'space': status,
        'notes': notes[:2],  # First 2 notes
        'equipment': equip_note
    }


def format_for_quote(update_data, carriers_in_quote):
    """
    Format product update for quote display
    Only include carriers that appear in the quote
    """
    lines = []
    
    week = update_data.get('week', 'Unknown')
    lines.append(f"📊 MARKET INTELLIGENCE ({week}):")
    
    for carrier in carriers_in_quote:
        carrier_upper = carrier.upper()
        summary = get_carrier_summary(update_data, carrier_upper)
        
        if summary['space'] != '-':
            line = f"• {carrier_upper}: Space {summary['space']}"
            if summary['notes']:
                # Add first short note
                first_note = summary['notes'][0]
                if len(first_note) > 50:
                    first_note = first_note[:47] + "..."
                line += f" | {first_note}"
            lines.append(line)
    
    # Add equipment warnings
    for carrier in carriers_in_quote:
        carrier_upper = carrier.upper()
        equip = update_data.get('equipment', {}).get(carrier_upper, {})
        if equip.get('quality') == 'BAD':
            lines.append(f"⚠️ {carrier_upper} Equipment: {equip.get('note', '')[:50]}")
    
    return '\n'.join(lines)


# Test
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    test_file = os.path.join(BASE_DIR, "Product update W03.docx")
    if os.path.exists(test_file):
        data = parse_product_update(test_file)
        print(f"Week: {data['week']}")
        print(f"\nSpecial Notes: {len(data['special_notes'])}")
        for note in data['special_notes'][:3]:
            print(f"  - {note[:80]}...")
        print(f"\nSpace Situation:")
        for carrier, info in data['space_situation'].items():
            print(f"  {carrier}: {info['status']}")
        print(f"\nEquipment:")
        for carrier, info in data['equipment'].items():
            print(f"  {carrier}: {info['quality']}")
        
        print("\n" + "="*50)
        print("Quote Format (for ONE, CMA):")
        print(format_for_quote(data, ['ONE', 'CMA']))
