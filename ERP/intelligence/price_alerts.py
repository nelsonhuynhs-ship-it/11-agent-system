"""
Price Alert Engine - Monitor pricing changes and generate alerts
Compares CRM quotes with current Pricing Engine data
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

print("=" * 70)
print("PRICE ALERT ENGINE - Integration Layer")
print("=" * 70)

# ============================================================
# CONFIGURATION
# ============================================================
PRICING_FILE = '../Pricing_Engine/MasterFullPricing.xlsx'
CRM_FILE = '../data/CRM_Master.xlsx'
# Auto-detect: ERP/intelligence/this_file.py → intelligence/ → ERP/ → Engine_test/
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Data')
PARQUET_FILE = os.path.join(DATA_DIR, 'Cleaned_Master_History.parquet')

# Alert thresholds
BETTER_PRICE_THRESHOLD = 50  # Alert if price drops by $50+
PRICE_INCREASE_THRESHOLD = 50  # Alert if price rises by $50+
ALTERNATIVE_SAVINGS_THRESHOLD = 100  # Alert if alternative carrier $100+ cheaper
STALE_QUOTE_DAYS = 3  # Alert if quote older than 3 days

# ============================================================
# LOAD DATA
# ============================================================
print("\n[1/5] Loading data...")

# Load CRM quotes
try:
    df_quotes = pd.read_excel(CRM_FILE, sheet_name='Quotes')
    print(f"  -> Loaded {len(df_quotes)} quotes from CRM")
except Exception as e:
    print(f"  -> Error loading CRM: {e}")
    sys.exit(1)

# Load current pricing from Parquet
try:
    df_pricing = pd.read_parquet(PARQUET_FILE)
    print(f"  -> Loaded {len(df_pricing):,} pricing records")
    
    # Get only latest prices (most recent Eff date for each route/carrier/container)
    df_pricing['Eff'] = pd.to_datetime(df_pricing['Eff'])
    df_pricing_latest = df_pricing.sort_values('Eff', ascending=False).groupby(
        ['POL', 'POD', 'Carrier', 'Commodity', 'Container_Type', 'Charge_Name']
    ).first().reset_index()
    
    print(f"  -> Filtered to {len(df_pricing_latest):,} latest prices")
except Exception as e:
    print(f"  -> Error loading pricing: {e}")
    sys.exit(1)

# ============================================================
# FILTER ACTIVE QUOTES
# ============================================================
print("\n[2/5] Filtering active quotes...")

# Only check quotes that are still active (Quoted or Follow status)
active_statuses = ['Inquiry', 'Quoted', 'Follow']
df_active_quotes = df_quotes[df_quotes['Pipeline_Status'].isin(active_statuses)].copy()

print(f"  -> Found {len(df_active_quotes)} active quotes")

if len(df_active_quotes) == 0:
    print("\n[INFO] No active quotes to check. Exiting.")
    sys.exit(0)

# Convert dates
df_active_quotes['Quote_Date'] = pd.to_datetime(df_active_quotes['Quote_Date'])

# ============================================================
# GENERATE ALERTS
# ============================================================
print("\n[3/5] Analyzing quotes and generating alerts...")

alerts = []
today = datetime.now()

for idx, quote in df_active_quotes.iterrows():
    quote_id = quote['Quote_ID']
    customer = quote['Customer_ID']
    pol = quote['POL']
    pod = quote['POD']
    carrier = quote['Carrier']
    container_type = quote['Container_Type']
    quoted_price = quote.get('Ocean_Freight', 0)
    quote_date = quote['Quote_Date']
    
    # Skip if missing critical data
    if pd.isna(pol) or pd.isna(pod) or pd.isna(carrier):
        continue
    
    # --- ALERT 1: Better Price (Cost Decreased) ---
    # Find current price for same route/carrier/container
    current_price = df_pricing_latest[
        (df_pricing_latest['POL'] == pol) &
        (df_pricing_latest['POD'] == pod) &
        (df_pricing_latest['Carrier'].str.contains(carrier, case=False, na=False)) &
        (df_pricing_latest['Container_Type'] == container_type) &
        (df_pricing_latest['Charge_Name'] == 'Base Ocean Freight')
    ]
    
    if not current_price.empty:
        current_cost = current_price['Amount'].iloc[0]
        
        # Assume original cost was similar to quoted price (need to track this in CRM)
        # For now, estimate: if quoted_price exists, assume 10% margin
        if quoted_price > 0:
            estimated_original_cost = quoted_price * 0.9  # Assume 10% margin
            cost_change = current_cost - estimated_original_cost
            
            # Alert if price dropped significantly
            if cost_change < -BETTER_PRICE_THRESHOLD:
                new_profit = quoted_price - current_cost
                new_margin = (new_profit / current_cost * 100) if current_cost > 0 else 0
                
                alerts.append({
                    'Alert_Type': 'BETTER_PRICE',
                    'Priority': 'HIGH',
                    'Quote_ID': quote_id,
                    'Customer_ID': customer,
                    'Route': f"{pol}-{pod}",
                    'Carrier': carrier,
                    'Container_Type': container_type,
                    'Quoted_Price': quoted_price,
                    'Old_Cost': estimated_original_cost,
                    'New_Cost': current_cost,
                    'Savings': abs(cost_change),
                    'New_Profit': new_profit,
                    'New_Margin': f"{new_margin:.1f}%",
                    'Action': 'Re-quote customer or increase profit margin',
                    'Alert_Date': today
                })
            
            # Alert if price increased significantly
            elif cost_change > PRICE_INCREASE_THRESHOLD:
                alerts.append({
                    'Alert_Type': 'PRICE_INCREASE',
                    'Priority': 'HIGH',
                    'Quote_ID': quote_id,
                    'Customer_ID': customer,
                    'Route': f"{pol}-{pod}",
                    'Carrier': carrier,
                    'Container_Type': container_type,
                    'Quoted_Price': quoted_price,
                    'Old_Cost': estimated_original_cost,
                    'New_Cost': current_cost,
                    'Increase': cost_change,
                    'Action': '⚠️ Caution: Cost increased, quote may be unprofitable',
                    'Alert_Date': today
                })
    
    # --- ALERT 2: Alternative Carrier (Cheaper Option) ---
    # Find all carriers for same route/container
    alternative_carriers = df_pricing_latest[
        (df_pricing_latest['POL'] == pol) &
        (df_pricing_latest['POD'] == pod) &
        (~df_pricing_latest['Carrier'].str.contains(carrier, case=False, na=False)) &
        (df_pricing_latest['Container_Type'] == container_type) &
        (df_pricing_latest['Charge_Name'] == 'Base Ocean Freight')
    ]
    
    if not alternative_carriers.empty and not current_price.empty:
        current_cost = current_price['Amount'].iloc[0]
        
        for _, alt in alternative_carriers.iterrows():
            alt_carrier = alt['Carrier']
            alt_cost = alt['Amount']
            
            # Alert if alternative is significantly cheaper
            if current_cost - alt_cost > ALTERNATIVE_SAVINGS_THRESHOLD:
                alerts.append({
                    'Alert_Type': 'ALTERNATIVE_CARRIER',
                    'Priority': 'MEDIUM',
                    'Quote_ID': quote_id,
                    'Customer_ID': customer,
                    'Route': f"{pol}-{pod}",
                    'Current_Carrier': carrier,
                    'Alt_Carrier': alt_carrier,
                    'Container_Type': container_type,
                    'Current_Cost': current_cost,
                    'Alt_Cost': alt_cost,
                    'Savings': current_cost - alt_cost,
                    'Action': f"Consider switching to {alt_carrier} for better margin",
                    'Alert_Date': today
                })
    
    # --- ALERT 3: Stale Quote (No Response) ---
    days_old = (today - quote_date).days
    if days_old >= STALE_QUOTE_DAYS:
        alerts.append({
            'Alert_Type': 'STALE_QUOTE',
            'Priority': 'LOW',
            'Quote_ID': quote_id,
            'Customer_ID': customer,
            'Route': f"{pol}-{pod}",
            'Carrier': carrier,
            'Quote_Date': quote_date.strftime('%Y-%m-%d'),
            'Days_Old': days_old,
            'Action': 'Follow up with customer',
            'Alert_Date': today
        })

print(f"  -> Generated {len(alerts)} alerts")

# ============================================================
# SAVE ALERTS
# ============================================================
print("\n[4/5] Saving alerts...")

if len(alerts) > 0:
    df_alerts = pd.DataFrame(alerts)
    
    # Save to Excel
    alert_file = '../data/Price_Alerts.xlsx'
    df_alerts.to_excel(alert_file, index=False)
    print(f"  -> Saved to {alert_file}")
    
    # Also append to CRM (if Price_Alerts sheet exists)
    try:
        with pd.ExcelWriter(CRM_FILE, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
            # Try to append, if sheet doesn't exist, create it
            try:
                existing = pd.read_excel(CRM_FILE, sheet_name='Price_Alerts')
                df_combined = pd.concat([existing, df_alerts], ignore_index=True)
                df_combined.to_excel(writer, sheet_name='Price_Alerts', index=False)
                print(f"  -> Appended to CRM Price_Alerts sheet")
            except:
                df_alerts.to_excel(writer, sheet_name='Price_Alerts', index=False)
                print(f"  -> Created new Price_Alerts sheet in CRM")
    except Exception as e:
        print(f"  -> Could not update CRM: {e}")
else:
    print("  -> No alerts to save")

# ============================================================
# DISPLAY SUMMARY
# ============================================================
print("\n[5/5] Alert Summary")
print("=" * 70)

if len(alerts) > 0:
    # Group by alert type
    alert_counts = df_alerts['Alert_Type'].value_counts()
    
    for alert_type, count in alert_counts.items():
        print(f"\n{alert_type}: {count} alerts")
        
        type_alerts = df_alerts[df_alerts['Alert_Type'] == alert_type]
        
        for _, alert in type_alerts.head(3).iterrows():  # Show first 3 of each type
            print(f"  - Quote {alert['Quote_ID']}: {alert.get('Action', 'N/A')}")
            if 'Savings' in alert:
                print(f"    Savings: ${alert['Savings']:.0f}")
    
    print(f"\n{'='*70}")
    print(f"Total Alerts: {len(alerts)}")
    print(f"HIGH Priority: {len(df_alerts[df_alerts['Priority'] == 'HIGH'])}")
    print(f"MEDIUM Priority: {len(df_alerts[df_alerts['Priority'] == 'MEDIUM'])}")
    print(f"LOW Priority: {len(df_alerts[df_alerts['Priority'] == 'LOW'])}")
else:
    print("\n✓ No alerts - All quotes are current and competitive")

print("\n" + "=" * 70)
print("PRICE ALERT ENGINE COMPLETE")
print("=" * 70)
