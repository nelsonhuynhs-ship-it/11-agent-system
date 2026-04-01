"""
Market Brief Dashboard - Internal Sales Tool
Hiển thị thông tin thị trường cho Sales trước khi báo giá
KHÔNG hiển thị cho khách hàng
"""

import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from market_intelligence.product_update import parse_product_update, get_carrier_summary
from market_intelligence.sailing_schedule import parse_schedule, get_blank_sailing_alert, get_week_summary

def find_latest_files():
    """Find latest Product Update and Schedule files"""
    product_file = None
    schedule_file = None
    
    # Look for Product update files
    for f in os.listdir(BASE_DIR):
        if f.lower().startswith('product update') and f.endswith('.docx'):
            product_file = os.path.join(BASE_DIR, f)
        if f.lower() == 'schedule.xlsx':
            schedule_file = os.path.join(BASE_DIR, f)
    
    return product_file, schedule_file


def generate_market_brief():
    """Generate market brief report for Sales"""
    
    print("="*70)
    print("📊 MARKET BRIEF - INTERNAL SALES KNOWLEDGE")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*70)
    
    product_file, schedule_file = find_latest_files()
    
    # ===== PRODUCT UPDATE SECTION =====
    if product_file:
        print(f"\n📋 PRODUCT UPDATE: {os.path.basename(product_file)}")
        print("-"*50)
        
        data = parse_product_update(product_file)
        print(f"Week: {data['week']}")
        
        # Special Notes (quan trọng nhất)
        if data['special_notes']:
            print("\n🔔 SPECIAL NOTES:")
            for note in data['special_notes'][:5]:
                print(f"   • {note[:100]}...")
        
        # Space by Carrier
        print("\n📦 SPACE SITUATION:")
        for carrier, info in data['space_situation'].items():
            status = info['status']
            emoji = "🔴" if status == "FULL" else "🟢" if status == "OPEN" else "🟡"
            print(f"   {emoji} {carrier}: {status}")
            if info['notes']:
                for note in info['notes'][:2]:
                    if len(note) > 80:
                        note = note[:77] + "..."
                    print(f"      └─ {note}")
        
        # Equipment
        if data['equipment']:
            print("\n🔧 EQUIPMENT STATUS:")
            for carrier, info in data['equipment'].items():
                quality = info['quality']
                emoji = "✅" if quality == "GOOD" else "⚠️" if quality == "BAD" else "➖"
                print(f"   {emoji} {carrier}: {info['note'][:60]}")
    else:
        print("\n⚠️ No Product Update file found!")
    
    # ===== SCHEDULE SECTION =====
    if schedule_file:
        print(f"\n\n⚓ SAILING SCHEDULE: {os.path.basename(schedule_file)}")
        print("-"*50)
        
        schedule = parse_schedule(schedule_file)
        
        # Week Summary
        week_summary = get_week_summary(schedule)
        print("\n📅 WEEK STATUS:")
        for week, info in week_summary.items():
            status = info['status']
            blanks = info['total_blanks']
            emoji = "🔴" if status == "TIGHT" else "🟢" if status == "OPEN" else "🟡"
            print(f"   {emoji} {week}: {status} ({blanks} blanks)")
        
        # Blank Sailing Alerts
        print("\n🚨 BLANK SAILING ALERTS:")
        all_alerts = get_blank_sailing_alert(schedule)
        
        # Group by week
        alerts_by_week = {}
        for alert in all_alerts:
            week = alert['week']
            if week not in alerts_by_week:
                alerts_by_week[week] = []
            alerts_by_week[week].append(alert)
        
        for week in sorted(alerts_by_week.keys()):
            alerts = alerts_by_week[week]
            tight_count = sum(1 for a in alerts if a['signal'] == '🔴 TIGHT')
            print(f"\n   {week}: {len(alerts)} routes affected ({tight_count} TIGHT)")
            
            for alert in alerts[:5]:  # Max 5 per week
                services = ", ".join(alert['services'][:2])
                if len(alert['services']) > 2:
                    services += f" +{len(alert['services'])-2} more"
                print(f"      {alert['signal']} {alert['pod'][:30]}: {services}")
    else:
        print("\n⚠️ No Schedule file found!")
    
    # ===== RECOMMENDATIONS =====
    print("\n\n" + "="*70)
    print("💡 RECOMMENDATIONS FOR SALES:")
    print("-"*50)
    
    if product_file:
        data = parse_product_update(product_file)
        full_carriers = [c for c, v in data['space_situation'].items() if v['status'] == 'FULL']
        open_carriers = [c for c, v in data['space_situation'].items() if v['status'] == 'OPEN']
        
        if full_carriers:
            print(f"   ⚠️ FULL Space: {', '.join(full_carriers)} → Book sớm, cân nhắc alternatives")
        if open_carriers:
            print(f"   ✅ OPEN Space: {', '.join(open_carriers)} → Negotiation room available")
    
    if schedule_file:
        schedule = parse_schedule(schedule_file)
        week_summary = get_week_summary(schedule)
        tight_weeks = [w for w, v in week_summary.items() if v['status'] == 'TIGHT']
        if tight_weeks:
            print(f"   🚨 TIGHT Weeks: {', '.join(tight_weeks)} → Push khách book sớm, expect rate increase")
    
    print("\n" + "="*70)
    print("END OF MARKET BRIEF")
    print("="*70)


if __name__ == "__main__":
    generate_market_brief()
