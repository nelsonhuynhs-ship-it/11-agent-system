"""
Market Intelligence - Sailing Schedule Parser
Detect blank sailings and space availability
"""

import os
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def parse_schedule(filepath):
    """
    Parse sailing schedule Excel file
    Returns structured data with blank sailing detection
    """
    df = pd.read_excel(filepath, sheet_name='Sheet1', header=None)
    
    # First row contains week headers
    # First few columns: GROUP, SERVICE, POD
    # Remaining columns: Week sailing info
    
    result = {
        'weeks': [],
        'sailings': [],
        'blanks_by_pod': {},
        'blanks_by_week': {}
    }
    
    # Parse header row for week info
    header_row = df.iloc[0]
    week_cols = {}
    for col_idx, val in enumerate(header_row):
        if val and 'W0' in str(val):
            # Extract week number: W04 (25 JAN-31 JAN)
            week_match = str(val).split('(')[0].strip()
            week_cols[col_idx] = week_match
            result['weeks'].append(week_match)
    
    # Parse data rows
    current_group = None
    for row_idx in range(1, len(df)):
        row = df.iloc[row_idx]
        
        # Get group (if present)
        if pd.notna(row[0]) and row[0]:
            current_group = str(row[0]).strip()
        
        service = str(row[1]).strip() if pd.notna(row[1]) else ""
        pod = str(row[2]).strip() if pd.notna(row[2]) else ""
        
        if not service:
            continue
        
        # Parse each week column
        for col_idx, week in week_cols.items():
            cell_val = str(row[col_idx]) if pd.notna(row[col_idx]) else ""
            
            is_blank = 'BLANK' in cell_val.upper()
            
            sailing_info = {
                'group': current_group,
                'service': service,
                'pod': pod,
                'week': week,
                'vessel': cell_val if not is_blank else None,
                'is_blank': is_blank
            }
            result['sailings'].append(sailing_info)
            
            # Track blanks by POD
            if is_blank:
                if pod not in result['blanks_by_pod']:
                    result['blanks_by_pod'][pod] = {}
                if week not in result['blanks_by_pod'][pod]:
                    result['blanks_by_pod'][pod][week] = []
                result['blanks_by_pod'][pod][week].append(service)
                
                # Track blanks by week
                if week not in result['blanks_by_week']:
                    result['blanks_by_week'][week] = []
                result['blanks_by_week'][week].append({
                    'service': service,
                    'pod': pod,
                    'group': current_group
                })
    
    return result


def get_blank_sailing_alert(schedule_data, pod_filter=None):
    """
    Generate blank sailing alerts for specific POD or all PODs
    """
    alerts = []
    
    blanks_by_pod = schedule_data.get('blanks_by_pod', {})
    
    for pod, weeks in blanks_by_pod.items():
        if pod_filter and pod_filter.upper() not in pod.upper():
            continue
            
        for week, services in weeks.items():
            if len(services) >= 2:
                # Multiple blanks = TIGHT space
                signal = "🔴 TIGHT"
            else:
                signal = "🟡 NORMAL"
            
            alerts.append({
                'pod': pod,
                'week': week,
                'signal': signal,
                'blank_count': len(services),
                'services': services
            })
    
    # Sort by week
    alerts.sort(key=lambda x: x['week'])
    
    return alerts


def format_sailing_for_quote(schedule_data, pods_in_quote):
    """
    Format sailing schedule alerts for quote display
    Only include PODs that appear in the quote
    """
    lines = []
    lines.append("⚓ SAILING UPDATE:")
    
    for pod in pods_in_quote:
        pod_upper = pod.upper()
        alerts = get_blank_sailing_alert(schedule_data, pod_upper)
        
        if alerts:
            for alert in alerts[:2]:  # Max 2 alerts per POD
                services_str = " + ".join(alert['services'][:3])
                if alert['blank_count'] >= 2:
                    lines.append(f"• {alert['week']} {pod}: {services_str} BLANK → Book sớm")
                else:
                    lines.append(f"• {alert['week']} {pod}: {services_str} blank")
    
    if len(lines) == 1:
        lines.append("• All services sailing normally")
    
    return '\n'.join(lines)


def get_week_summary(schedule_data):
    """Get summary of blanks by week"""
    summary = {}
    for week in schedule_data.get('weeks', []):
        blanks = schedule_data.get('blanks_by_week', {}).get(week, [])
        summary[week] = {
            'total_blanks': len(blanks),
            'status': 'TIGHT' if len(blanks) >= 5 else 'NORMAL' if len(blanks) >= 2 else 'OPEN'
        }
    return summary


# Test
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    test_file = os.path.join(BASE_DIR, "Schedule.xlsx")
    if os.path.exists(test_file):
        data = parse_schedule(test_file)
        
        print(f"Weeks: {data['weeks']}")
        print(f"\nTotal sailings: {len(data['sailings'])}")
        
        print(f"\nBlanks by Week:")
        for week, blanks in data['blanks_by_week'].items():
            print(f"  {week}: {len(blanks)} blanks")
        
        print(f"\nBlanks by POD:")
        for pod, weeks in list(data['blanks_by_pod'].items())[:5]:
            for week, services in weeks.items():
                print(f"  {pod} {week}: {services}")
        
        print("\n" + "="*50)
        print("Alerts for LAX:")
        alerts = get_blank_sailing_alert(data, 'LAX')
        for a in alerts:
            print(f"  {a['week']}: {a['signal']} - {a['services']}")
        
        print("\n" + "="*50)
        print("Quote Format (for USLAX, USOAK):")
        print(format_sailing_for_quote(data, ['USLAX', 'USOAK']))
