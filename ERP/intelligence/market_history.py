"""
Market History Manager
- Parse and store market data permanently
- Query historical data by week
- Data survives file deletion
"""

import os
import sys
import json
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "market_history.json")

def load_history():
    """Load existing history or create new"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'product_updates': {},  # week -> data
        'schedules': {},        # week -> data
        'last_updated': None
    }


def save_history(history):
    """Save history to JSON"""
    history['last_updated'] = datetime.now().isoformat()
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"✅ History saved to {HISTORY_FILE}")


def import_product_update(filepath):
    """Import product update file into history"""
    from market_intelligence.product_update import parse_product_update
    
    data = parse_product_update(filepath)
    week = data['week']
    
    if not week:
        print("❌ Could not detect week from file")
        return False
    
    history = load_history()
    
    # Store parsed data
    history['product_updates'][week] = {
        'imported_at': datetime.now().isoformat(),
        'source_file': os.path.basename(filepath),
        'special_notes': data['special_notes'],
        'space_situation': data['space_situation'],
        'equipment': data['equipment']
    }
    
    save_history(history)
    print(f"✅ Imported Product Update {week}")
    return True


def import_schedule(filepath, week=None):
    """Import schedule file into history"""
    from market_intelligence.sailing_schedule import parse_schedule, get_week_summary
    
    data = parse_schedule(filepath)
    
    # Auto-detect week from file or use provided
    if not week:
        # Use first week in schedule
        week = data['weeks'][0] if data['weeks'] else 'UNKNOWN'
    
    history = load_history()
    
    # Store summary data (not full sailings to save space)
    week_summary = get_week_summary(data)
    blanks = data['blanks_by_week']
    
    history['schedules'][week] = {
        'imported_at': datetime.now().isoformat(),
        'source_file': os.path.basename(filepath),
        'weeks_covered': data['weeks'],
        'week_summary': week_summary,
        'blanks_by_week': {w: len(b) for w, b in blanks.items()},
        'blanks_detail': {w: [{'pod': x['pod'], 'service': x['service']} for x in b[:10]] 
                          for w, b in blanks.items()}
    }
    
    save_history(history)
    print(f"✅ Imported Schedule (weeks: {', '.join(data['weeks'])})")
    return True


def get_week_data(week):
    """Get all data for a specific week"""
    history = load_history()
    
    result = {
        'week': week,
        'product_update': history['product_updates'].get(week),
        'schedule': None
    }
    
    # Find schedule that covers this week
    for sched_week, sched_data in history['schedules'].items():
        if week in sched_data.get('weeks_covered', []):
            result['schedule'] = sched_data
            break
    
    return result


def list_available_weeks():
    """List all available weeks in history"""
    history = load_history()
    
    product_weeks = set(history['product_updates'].keys())
    schedule_weeks = set()
    for sched_data in history['schedules'].values():
        schedule_weeks.update(sched_data.get('weeks_covered', []))
    
    all_weeks = sorted(product_weeks | schedule_weeks)
    return all_weeks


def query_carrier_history(carrier, weeks=None):
    """Query carrier status across weeks"""
    history = load_history()
    
    carrier = carrier.upper()
    result = []
    
    for week, data in sorted(history['product_updates'].items()):
        if weeks and week not in weeks:
            continue
        
        space = data.get('space_situation', {}).get(carrier, {})
        equip = data.get('equipment', {}).get(carrier, {})
        
        result.append({
            'week': week,
            'space_status': space.get('status', '-'),
            'equipment': equip.get('quality', '-'),
            'notes': space.get('notes', [])[:1]
        })
    
    return result


def print_history_summary():
    """Print summary of stored history"""
    history = load_history()
    
    print("="*60)
    print("📚 MARKET HISTORY DATABASE")
    print(f"   Last updated: {history.get('last_updated', 'Never')}")
    print("="*60)
    
    print(f"\n📋 Product Updates: {len(history['product_updates'])} weeks")
    for week in sorted(history['product_updates'].keys()):
        data = history['product_updates'][week]
        carriers = list(data.get('space_situation', {}).keys())
        print(f"   • {week}: {len(carriers)} carriers | {data.get('source_file', '-')}")
    
    print(f"\n⚓ Schedules: {len(history['schedules'])} imports")
    for week, data in sorted(history['schedules'].items()):
        weeks = data.get('weeks_covered', [])
        total_blanks = sum(data.get('blanks_by_week', {}).values())
        print(f"   • {week}: covers {len(weeks)} weeks, {total_blanks} blanks | {data.get('source_file', '-')}")
    
    print("\n" + "="*60)


# CLI Interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python market_history.py import-product <file.docx>")
        print("  python market_history.py import-schedule <file.xlsx>")
        print("  python market_history.py list")
        print("  python market_history.py query <week>")
        print("  python market_history.py carrier <carrier_code>")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "import-product" and len(sys.argv) > 2:
        import_product_update(sys.argv[2])
    
    elif cmd == "import-schedule" and len(sys.argv) > 2:
        import_schedule(sys.argv[2])
    
    elif cmd == "list":
        print_history_summary()
    
    elif cmd == "query" and len(sys.argv) > 2:
        week = sys.argv[2].upper()
        data = get_week_data(week)
        print(f"\n📊 Data for {week}:")
        if data['product_update']:
            print(f"   Product Update: ✅")
            space = data['product_update'].get('space_situation', {})
            for c, v in space.items():
                print(f"      {c}: {v.get('status', '-')}")
        else:
            print(f"   Product Update: ❌ Not found")
        
        if data['schedule']:
            print(f"   Schedule: ✅")
            blanks = data['schedule'].get('blanks_by_week', {}).get(week, 0)
            print(f"      Blanks: {blanks}")
        else:
            print(f"   Schedule: ❌ Not found")
    
    elif cmd == "carrier" and len(sys.argv) > 2:
        carrier = sys.argv[2].upper()
        history = query_carrier_history(carrier)
        print(f"\n📊 {carrier} History:")
        for h in history:
            print(f"   {h['week']}: Space={h['space_status']}, Equip={h['equipment']}")
    
    else:
        print("Unknown command")
