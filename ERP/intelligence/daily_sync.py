"""
Daily Sync - Automated daily synchronization between systems
Runs price alerts, quote matching, and profit analysis
"""

import pandas as pd
import sys
import os
from datetime import datetime

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import our integration modules
from price_alerts import *
from quote_matcher import match_quote_with_pricing
from profit_calculator import analyze_quote_profitability

print("=" * 70)
print("DAILY SYNC - Integration Layer")
print(f"Run Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# ============================================================
# STEP 1: Match Quotes with Current Pricing
# ============================================================
print("\n[STEP 1/4] Matching quotes with current pricing...")

try:
    df_matched = match_quote_with_pricing()
    
    if not df_matched.empty:
        print(f"  ✓ Matched {len(df_matched)} quotes")
        
        # Save matched quotes
        output_file = '../data/Daily_Quote_Matches.xlsx'
        df_matched.to_excel(output_file, index=False)
        print(f"  ✓ Saved to {output_file}")
    else:
        print("  → No active quotes to match")
        
except Exception as e:
    print(f"  ✗ Error: {e}")

# ============================================================
# STEP 2: Analyze Profitability
# ============================================================
print("\n[STEP 2/4] Analyzing quote profitability...")

try:
    df_profit = analyze_quote_profitability()
    
    if not df_profit.empty:
        total_profit = df_profit['Profit_Amount'].sum()
        avg_profit = df_profit['Profit_Amount'].mean()
        
        print(f"  ✓ Analyzed {len(df_profit)} quotes")
        print(f"  → Total Profit: ${total_profit:,.2f}")
        print(f"  → Average Profit: ${avg_profit:,.2f}")
        
        # Save profit analysis
        output_file = '../data/Daily_Profit_Analysis.xlsx'
        df_profit.to_excel(output_file, index=False)
        print(f"  ✓ Saved to {output_file}")
    else:
        print("  → No quotes to analyze")
        
except Exception as e:
    print(f"  ✗ Error: {e}")

# ============================================================
# STEP 3: Generate Price Alerts
# ============================================================
print("\n[STEP 3/4] Generating price alerts...")

# This will run the price_alert_engine.py logic
# (Already imported and will execute when we run the main script)

print("  → Running price alert engine...")
print("  → (See price_alert_engine output above)")

# ============================================================
# STEP 4: Generate Summary Report
# ============================================================
print("\n[STEP 4/4] Generating daily summary...")

try:
    # Load all generated files
    summary = {
        'Sync_Date': datetime.now().strftime('%Y-%m-%d'),
        'Sync_Time': datetime.now().strftime('%H:%M:%S'),
        'Quotes_Matched': len(df_matched) if not df_matched.empty else 0,
        'Quotes_Analyzed': len(df_profit) if not df_profit.empty else 0,
        'Total_Profit': df_profit['Profit_Amount'].sum() if not df_profit.empty else 0,
        'Alerts_Generated': len(alerts) if 'alerts' in locals() else 0
    }
    
    # Save summary
    df_summary = pd.DataFrame([summary])
    summary_file = '../data/Daily_Sync_Summary.xlsx'
    
    # Append to existing summary file
    try:
        existing = pd.read_excel(summary_file)
        df_combined = pd.concat([existing, df_summary], ignore_index=True)
        df_combined.to_excel(summary_file, index=False)
    except:
        df_summary.to_excel(summary_file, index=False)
    
    print(f"  ✓ Summary saved to {summary_file}")
    
    # Display summary
    print(f"\n{'='*70}")
    print("DAILY SYNC SUMMARY")
    print("=" * 70)
    print(f"Date: {summary['Sync_Date']}")
    print(f"Time: {summary['Sync_Time']}")
    print(f"Quotes Matched: {summary['Quotes_Matched']}")
    print(f"Quotes Analyzed: {summary['Quotes_Analyzed']}")
    print(f"Total Profit: ${summary['Total_Profit']:,.2f}")
    print(f"Alerts Generated: {summary['Alerts_Generated']}")
    
except Exception as e:
    print(f"  ✗ Error generating summary: {e}")

print("\n" + "=" * 70)
print("DAILY SYNC COMPLETE")
print("=" * 70)
print("\nNext Steps:")
print("  1. Review alerts in ERP/data/Price_Alerts.xlsx")
print("  2. Check profit analysis in ERP/data/Daily_Profit_Analysis.xlsx")
print("  3. Follow up on high-priority alerts")
print("  4. Update CRM quotes as needed")
