"""
Quote Matcher - Match CRM quotes with current Pricing Engine data
Get exact pricing for quote validation
"""

import pandas as pd
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def get_price_from_pricing_engine(pol, pod, carrier, container_type, contract_type='FAK'):
    """
    Get current price from Pricing Engine
    
    Args:
        pol: Port of Loading
        pod: Port of Discharge
        carrier: Carrier name
        container_type: Container type (20GP, 40HQ, etc.)
        contract_type: FAK/FIX/SCFI (default FAK)
    
    Returns:
        dict with price info or None if not found
    """
    
    # Auto-detect: ERP/intelligence/this_file.py → intelligence/ → ERP/ → Engine_test/
    DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'Data')
    PARQUET_FILE = os.path.join(DATA_DIR, 'Cleaned_Master_History.parquet')
    
    try:
        # Load pricing data
        df = pd.read_parquet(PARQUET_FILE)
        
        # Filter for latest prices
        df['Eff'] = pd.to_datetime(df['Eff'])
        
        # Match route, carrier, container
        matches = df[
            (df['POL'] == pol) &
            (df['POD'] == pod) &
            (df['Carrier'].str.contains(carrier, case=False, na=False)) &
            (df['Container_Type'] == container_type) &
            (df['Commodity'].str.contains(contract_type, case=False, na=False))
        ]
        
        if matches.empty:
            return None
        
        # Get latest price
        latest = matches.sort_values('Eff', ascending=False).iloc[0]
        
        # Get base ocean freight
        base_freight = matches[
            (matches['Charge_Name'] == 'Base Ocean Freight')
        ].sort_values('Eff', ascending=False)
        
        if not base_freight.empty:
            base_amount = base_freight.iloc[0]['Amount']
        else:
            base_amount = 0
        
        # Get all surcharges
        surcharges = matches[
            (matches['Charge_Name'] != 'Base Ocean Freight')
        ].groupby('Charge_Name')['Amount'].first().to_dict()
        
        return {
            'POL': pol,
            'POD': pod,
            'Carrier': latest['Carrier'],
            'Container_Type': container_type,
            'Contract_Type': contract_type,
            'Base_Ocean_Freight': base_amount,
            'Surcharges': surcharges,
            'Total_Cost': base_amount + sum(surcharges.values()),
            'Effective_Date': latest['Eff'].strftime('%Y-%m-%d'),
            'Valid_Until': latest['Exp'].strftime('%Y-%m-%d') if pd.notna(latest['Exp']) else 'N/A'
        }
        
    except Exception as e:
        print(f"Error getting price: {e}")
        return None


def match_quote_with_pricing(quote_id=None):
    """
    Match a specific quote or all active quotes with current pricing
    
    Args:
        quote_id: Specific quote ID to match, or None for all active quotes
    
    Returns:
        DataFrame with matched quotes and current pricing
    """
    
    CRM_FILE = '../data/CRM_Master.xlsx'
    
    try:
        # Load quotes
        df_quotes = pd.read_excel(CRM_FILE, sheet_name='Quotes')
        
        # Filter active quotes
        active_statuses = ['Inquiry', 'Quoted', 'Follow']
        df_active = df_quotes[df_quotes['Pipeline_Status'].isin(active_statuses)].copy()
        
        if quote_id:
            df_active = df_active[df_active['Quote_ID'] == quote_id]
        
        if df_active.empty:
            print("No active quotes found")
            return pd.DataFrame()
        
        # Match each quote with current pricing
        results = []
        
        for idx, quote in df_active.iterrows():
            pol = quote['POL']
            pod = quote['POD']
            carrier = quote['Carrier']
            container_type = quote['Container_Type']
            
            # Skip if missing data
            if pd.isna(pol) or pd.isna(pod) or pd.isna(carrier):
                continue
            
            # Get current price
            price_info = get_price_from_pricing_engine(
                pol=pol,
                pod=pod,
                carrier=carrier,
                container_type=container_type
            )
            
            if price_info:
                results.append({
                    'Quote_ID': quote['Quote_ID'],
                    'Customer_ID': quote['Customer_ID'],
                    'Quote_Date': quote['Quote_Date'],
                    'Route': f"{pol}-{pod}",
                    'Carrier': carrier,
                    'Container_Type': container_type,
                    'Quoted_Price': quote.get('Ocean_Freight', 0),
                    'Current_Cost': price_info['Total_Cost'],
                    'Base_Freight': price_info['Base_Ocean_Freight'],
                    'Surcharges_Total': sum(price_info['Surcharges'].values()),
                    'Price_Date': price_info['Effective_Date'],
                    'Valid_Until': price_info['Valid_Until'],
                    'Status': quote['Pipeline_Status']
                })
        
        return pd.DataFrame(results)
        
    except Exception as e:
        print(f"Error matching quotes: {e}")
        return pd.DataFrame()


if __name__ == '__main__':
    print("=" * 70)
    print("QUOTE MATCHER - Match Quotes with Current Pricing")
    print("=" * 70)
    
    # Match all active quotes
    df_matched = match_quote_with_pricing()
    
    if not df_matched.empty:
        print(f"\nMatched {len(df_matched)} quotes with current pricing:\n")
        print(df_matched[['Quote_ID', 'Route', 'Carrier', 'Quoted_Price', 'Current_Cost']].to_string(index=False))
        
        # Save results
        output_file = '../data/Quote_Price_Matches.xlsx'
        df_matched.to_excel(output_file, index=False)
        print(f"\n✓ Saved to {output_file}")
    else:
        print("\nNo quotes to match")
