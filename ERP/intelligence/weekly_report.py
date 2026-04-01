"""
WEEKLY MARKET REPORT - 4C Framework
Costing | Capacity | Challenge | Change

Kết hợp: Pricing + Product Update + Schedule
Output: Report toàn diện cho Sales review mỗi thứ 2
"""

import os
import sys
import pandas as pd
from datetime import datetime, date

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRICING_FILE = os.path.join(BASE_DIR, "Pricing_Engine", "MasterFullPricing.xlsx")

# Region mapping
REGIONS = {
    'USWC': ['USLAX', 'USLGB', 'USOAK', 'USSEA', 'USTAC'],
    'USEC': ['USNYC', 'USSAV', 'USCHS', 'USJAX', 'USORF', 'USBOS', 'USPHL'],
    'USGULF': ['USHOU', 'USMSY', 'USMOB', 'USTPA', 'USTIW'],
    'CANADA': ['CAVAN', 'CAHAL', 'CATOR', 'CAMTR'],
}

INLAND_CITIES = ['KANSAS', 'DENVER', 'DALLAS', 'CINCINNATI', 'CHICAGO', 'ATLANTA', 'MEMPHIS']

CARRIERS_FOCUS = ['ONE', 'HPL', 'CMA', 'MSC', 'COSCO', 'YML', 'ZIM', 'EMC']

COMMODITY_TYPES = {
    'FAK': ['FAK'],
    'FIX': ['FIX', '990104', 'NAC'],
    'REEFER': ['REEFER'],
    'SHORT_TERM': ['SHORT TERM', 'GDSM', 'GDS'],
}


def load_pricing_data():
    """Load current pricing from MasterFullPricing"""
    if not os.path.exists(PRICING_FILE):
        print(f"⚠️ Pricing file not found: {PRICING_FILE}")
        return pd.DataFrame()
    
    df = pd.read_excel(PRICING_FILE, sheet_name='Master')
    return df


def load_old_rate():
    """Load historical rates for comparison"""
    if not os.path.exists(PRICING_FILE):
        return pd.DataFrame()
    
    try:
        df = pd.read_excel(PRICING_FILE, sheet_name='Recent_History')
        return df
    except:
        return pd.DataFrame()


def get_region(pod):
    """Determine region from POD code"""
    if not pod:
        return 'OTHER'
    pod = str(pod).upper()
    for region, codes in REGIONS.items():
        if pod in codes or any(pod.startswith(c[:2]) for c in codes):
            return region
    return 'OTHER'


def get_commodity_group(commodity):
    """Group commodity types"""
    if not commodity:
        return 'OTHER'
    comm = str(commodity).upper()
    for group, keywords in COMMODITY_TYPES.items():
        if any(kw in comm for kw in keywords):
            return group
    return 'OTHER'


def check_inland(place):
    """Check if destination is inland"""
    if not place:
        return False
    place_upper = str(place).upper()
    return any(city in place_upper for city in INLAND_CITIES)


def analyze_costing(df):
    """Analyze current pricing - COSTING section"""
    results = {}
    
    # Filter HCM and HPH origins
    df_origin = df[df['POL'].isin(['HCM', 'HPH'])]
    
    for region in ['USWC', 'USEC', 'USGULF', 'CANADA']:
        results[region] = {}
        
        # Filter by region
        df_region = df_origin[df_origin['POD'].apply(lambda x: get_region(x) == region)]
        
        for carrier in CARRIERS_FOCUS:
            df_carrier = df_region[df_region['Carrier'] == carrier]
            if df_carrier.empty:
                continue
            
            carrier_data = {}
            for comm_group in ['FAK', 'FIX', 'REEFER', 'SHORT_TERM']:
                df_comm = df_carrier[df_carrier['Commodity'].apply(lambda x: get_commodity_group(x) == comm_group)]
                if df_comm.empty:
                    continue
                
                # Get min price for 40HQ
                price_40hq = df_comm['40HQ'].dropna()
                if not price_40hq.empty:
                    carrier_data[comm_group] = {
                        'min': int(price_40hq.min()),
                        'max': int(price_40hq.max()),
                        'count': len(price_40hq)
                    }
            
            if carrier_data:
                results[region][carrier] = carrier_data
    
    # Inland analysis
    results['INLAND'] = {}
    df_inland = df_origin[df_origin['Place'].apply(check_inland)]
    
    for carrier in CARRIERS_FOCUS:
        df_carrier = df_inland[df_inland['Carrier'] == carrier]
        if df_carrier.empty:
            continue
        
        price_40hq = df_carrier['40HQ'].dropna()
        if not price_40hq.empty:
            # Group by city
            for city in INLAND_CITIES:
                df_city = df_carrier[df_carrier['Place'].str.upper().str.contains(city, na=False)]
                if not df_city.empty:
                    city_price = df_city['40HQ'].dropna()
                    if not city_price.empty:
                        if city not in results['INLAND']:
                            results['INLAND'][city] = {}
                        results['INLAND'][city][carrier] = {
                            'min': int(city_price.min()),
                            'max': int(city_price.max())
                        }
    
    return results


def analyze_capacity(product_data, schedule_data):
    """Analyze capacity - space, equipment, blanks"""
    results = {
        'space': {},
        'equipment': {},
        'blanks': {}
    }
    
    # Space from product update
    if product_data:
        for carrier, info in product_data.get('space_situation', {}).items():
            results['space'][carrier] = info.get('status', 'UNKNOWN')
        
        for carrier, info in product_data.get('equipment', {}).items():
            results['equipment'][carrier] = info.get('quality', 'NORMAL')
    
    # Blanks from schedule
    if schedule_data:
        for week, count in schedule_data.get('blanks_by_week', {}).items():
            results['blanks'][week] = count
    
    return results


def analyze_changes(df_current, df_old):
    """Analyze week-over-week changes"""
    results = {}
    
    if df_current.empty or df_old.empty:
        return results
    
    # Get latest and previous rates for comparison
    for region in ['USWC', 'USEC', 'USGULF']:
        results[region] = {}
        
        for carrier in ['ONE', 'HPL', 'CMA']:
            # Current average
            curr = df_current[
                (df_current['Carrier'] == carrier) & 
                (df_current['POD'].apply(lambda x: get_region(x) == region))
            ]['40HQ'].dropna()
            
            # Previous average
            prev = df_old[
                (df_old['Carrier'] == carrier) & 
                (df_old['POD'].apply(lambda x: get_region(x) == region))
            ]['40HQ'].dropna()
            
            if not curr.empty and not prev.empty:
                curr_avg = curr.mean()
                prev_avg = prev.mean()
                delta = curr_avg - prev_avg
                pct = (delta / prev_avg * 100) if prev_avg else 0
                
                results[region][carrier] = {
                    'current': int(curr_avg),
                    'previous': int(prev_avg),
                    'delta': int(delta),
                    'pct': round(pct, 1)
                }
    
    return results


def generate_report():
    """Generate comprehensive 4C Market Report"""
    
    print("="*80)
    print("📊 WEEKLY MARKET REPORT - 4C FRAMEWORK")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} (Week {datetime.now().isocalendar()[1]})")
    print("   Origin: HCM, HPH → USA, Canada")
    print("="*80)
    
    # Load data
    print("\n⏳ Loading data...")
    df_current = load_pricing_data()
    df_old = load_old_rate()
    
    # Load product update and schedule from history
    product_data = None
    schedule_data = None
    try:
        from market_history import load_history
        history = load_history()
        
        # Get latest product update
        if history['product_updates']:
            latest_week = sorted(history['product_updates'].keys())[-1]
            product_data = history['product_updates'][latest_week]
        
        # Get latest schedule
        if history['schedules']:
            latest_sched = sorted(history['schedules'].keys())[-1]
            schedule_data = history['schedules'][latest_sched]
    except:
        pass
    
    # ========== 1. COSTING ==========
    print("\n" + "="*80)
    print("💰 1. COSTING - Mức giá hiện tại (40HQ)")
    print("="*80)
    
    costing = analyze_costing(df_current)
    
    for region in ['USWC', 'USEC', 'USGULF', 'CANADA']:
        if region not in costing or not costing[region]:
            continue
        
        print(f"\n📍 {region}:")
        print("-"*60)
        print(f"{'Carrier':<8} {'FAK':<15} {'FIX':<15} {'REEFER':<15} {'SHORT':<15}")
        print("-"*60)
        
        for carrier, data in costing[region].items():
            fak = f"${data.get('FAK', {}).get('min', '-'):,}" if 'FAK' in data else "-"
            fix = f"${data.get('FIX', {}).get('min', '-'):,}" if 'FIX' in data else "-"
            rf = f"${data.get('REEFER', {}).get('min', '-'):,}" if 'REEFER' in data else "-"
            short = f"${data.get('SHORT_TERM', {}).get('min', '-'):,}" if 'SHORT_TERM' in data else "-"
            print(f"{carrier:<8} {fak:<15} {fix:<15} {rf:<15} {short:<15}")
    
    # Inland
    if costing.get('INLAND'):
        print(f"\n📍 INLAND CITIES:")
        print("-"*60)
        for city, carriers in costing['INLAND'].items():
            carrier_str = " | ".join([f"{c}: ${v['min']:,}" for c, v in list(carriers.items())[:3]])
            print(f"   {city}: {carrier_str}")
    
    # ========== 2. CAPACITY ==========
    print("\n" + "="*80)
    print("📦 2. CAPACITY - Space, Equipment, Sailings")
    print("="*80)
    
    capacity = analyze_capacity(product_data, schedule_data)
    
    # Space Status
    print("\n🚢 Space Status:")
    for carrier in CARRIERS_FOCUS:
        status = capacity['space'].get(carrier, 'N/A')
        emoji = "🔴" if status == 'FULL' else "🟢" if status == 'OPEN' else "🟡"
        print(f"   {emoji} {carrier}: {status}")
    
    # Equipment
    print("\n🔧 Equipment:")
    for carrier, quality in capacity['equipment'].items():
        emoji = "✅" if quality == 'GOOD' else "⚠️" if quality == 'BAD' else "➖"
        print(f"   {emoji} {carrier}: {quality}")
    
    # Blank Sailings
    print("\n⚓ Sailing Schedule (Blanks per week):")
    for week, count in sorted(capacity['blanks'].items()):
        bar = "█" * min(count, 20)
        status = "TIGHT" if count >= 10 else "NORMAL" if count >= 3 else "OPEN"
        emoji = "🔴" if status == 'TIGHT' else "🟡" if status == 'NORMAL' else "🟢"
        print(f"   {emoji} {week}: {count:2d} blanks {bar}")
    
    # ========== 3. CHALLENGE ==========
    print("\n" + "="*80)
    print("⚠️ 3. CHALLENGE - Rủi ro và Thách thức")
    print("="*80)
    
    if product_data:
        print("\n🔔 Special Notes từ Product:")
        for note in product_data.get('special_notes', [])[:5]:
            print(f"   • {note[:100]}...")
    
    # Identify challenges
    print("\n🚨 Key Challenges:")
    full_carriers = [c for c, s in capacity['space'].items() if s == 'FULL']
    if full_carriers:
        print(f"   • FULL Space: {', '.join(full_carriers)} → Book sớm hoặc alternative")
    
    bad_equip = [c for c, q in capacity['equipment'].items() if q == 'BAD']
    if bad_equip:
        print(f"   • Equipment xấu: {', '.join(bad_equip)} → Kiểm tra rỗng trước khi lấy")
    
    tight_weeks = [w for w, c in capacity['blanks'].items() if c >= 10]
    if tight_weeks:
        print(f"   • Tight weeks: {', '.join(tight_weeks)} → Push booking sớm")
    
    # ========== 4. CHANGE ==========
    print("\n" + "="*80)
    print("📈 4. CHANGE - Biến động giá vs Kỳ trước")
    print("="*80)
    
    try:
        changes = analyze_changes(df_current, df_old)
        
        if not changes:
            print("\n   ⚠️ Chưa có dữ liệu so sánh kỳ trước")
        else:
            for region in ['USWC', 'USEC', 'USGULF']:
                if region not in changes or not changes[region]:
                    continue
                
                print(f"\n📍 {region}:")
                for carrier, data in changes[region].items():
                    delta = data['delta']
                    pct = data['pct']
                    arrow = "▲" if delta > 0 else "▼" if delta < 0 else "→"
                    color_note = "(Tăng)" if delta > 0 else "(Giảm)" if delta < 0 else "(Ổn định)"
                    print(f"   {carrier}: ${data['current']:,} {arrow} ${abs(delta):,} ({pct:+.1f}%) {color_note}")
    except Exception as e:
        print(f"\n   ⚠️ Chưa có dữ liệu so sánh: {str(e)[:50]}")
    
    # ========== SUMMARY ==========
    print("\n" + "="*80)
    print("📋 EXECUTIVE SUMMARY")
    print("="*80)
    
    print("\n💡 Recommendations:")
    if full_carriers:
        print(f"   1. Carriers FULL ({', '.join(full_carriers)}): Ưu tiên alternatives hoặc book trước 2 tuần")
    if tight_weeks:
        print(f"   2. Weeks TIGHT ({', '.join(tight_weeks)}): Khuyên khách confirm sớm, expect giá tăng")
    if bad_equip:
        print(f"   3. Equipment issues ({', '.join(bad_equip)}): Cảnh báo khách check rỗng")
    
    print("\n" + "="*80)
    print("END OF WEEKLY MARKET REPORT")
    print("="*80)


if __name__ == "__main__":
    generate_report()
