"""
Profit Calculator - Calculate profit margins and opportunities
"""

import pandas as pd
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def calculate_profit(selling_price, buying_price):
    """
    Calculate profit amount and margin
    
    Args:
        selling_price: Price quoted to customer
        buying_price: Cost from carrier
    
    Returns:
        dict with profit metrics
    """
    profit_amount = selling_price - buying_price
    profit_margin = (profit_amount / buying_price * 100) if buying_price > 0 else 0
    
    return {
        'Profit_Amount': profit_amount,
        'Profit_Margin': profit_margin,
        'Markup': (profit_amount / buying_price * 100) if buying_price > 0 else 0
    }


def suggest_quote_price(cost, target_margin=10):
    """
    Suggest quote price based on cost and target margin
    
    Args:
        cost: Buying cost
        target_margin: Target profit margin % (default 10%)
    
    Returns:
        dict with suggested pricing
    """
    suggested_price = cost * (1 + target_margin/100)
    profit = suggested_price - cost
    
    return {
        'Cost': cost,
        'Target_Margin': f"{target_margin}%",
        'Suggested_Price': suggested_price,
        'Profit': profit
    }


def analyze_quote_profitability():
    """
    Analyze profitability of all quotes in CRM
    """
    
    CRM_FILE = '../data/CRM_Master.xlsx'
    
    try:
        # Load quotes
        df_quotes = pd.read_excel(CRM_FILE, sheet_name='Quotes')
        
        # Calculate profit for each quote
        results = []
        
        for idx, quote in df_quotes.iterrows():
            selling_price = quote.get('Total_Price', 0)
            ocean_freight = quote.get('Ocean_Freight', 0)
            
            # For now, assume ocean freight is the main cost
            # In full implementation, would get actual cost from pricing engine
            if selling_price > 0 and ocean_freight > 0:
                profit_metrics = calculate_profit(selling_price, ocean_freight)
                
                results.append({
                    'Quote_ID': quote['Quote_ID'],
                    'Customer_ID': quote['Customer_ID'],
                    'Route': f"{quote['POL']}-{quote['POD']}",
                    'Carrier': quote['Carrier'],
                    'Selling_Price': selling_price,
                    'Cost': ocean_freight,
                    'Profit_Amount': profit_metrics['Profit_Amount'],
                    'Profit_Margin': f"{profit_metrics['Profit_Margin']:.1f}%",
                    'Status': quote['Pipeline_Status']
                })
        
        return pd.DataFrame(results)
        
    except Exception as e:
        print(f"Error analyzing profitability: {e}")
        return pd.DataFrame()


def calculate_profit_opportunity(quoted_price, old_cost, new_cost):
    """
    Calculate profit opportunity when cost changes
    
    Args:
        quoted_price: Original quoted price
        old_cost: Original cost
        new_cost: New (current) cost
    
    Returns:
        dict with opportunity analysis
    """
    
    old_profit = quoted_price - old_cost
    old_margin = (old_profit / old_cost * 100) if old_cost > 0 else 0
    
    new_profit = quoted_price - new_cost
    new_margin = (new_profit / new_cost * 100) if new_cost > 0 else 0
    
    profit_increase = new_profit - old_profit
    margin_increase = new_margin - old_margin
    
    # Calculate alternative: re-quote at lower price
    # Keep same profit amount, reduce price
    alternative_price = new_cost + old_profit
    customer_savings = quoted_price - alternative_price
    
    return {
        'Original': {
            'Quoted_Price': quoted_price,
            'Cost': old_cost,
            'Profit': old_profit,
            'Margin': f"{old_margin:.1f}%"
        },
        'Current': {
            'Quoted_Price': quoted_price,
            'Cost': new_cost,
            'Profit': new_profit,
            'Margin': f"{new_margin:.1f}%"
        },
        'Opportunity': {
            'Profit_Increase': profit_increase,
            'Margin_Increase': f"{margin_increase:.1f}%",
            'Alternative_Price': alternative_price,
            'Customer_Savings': customer_savings
        },
        'Recommendation': 'Keep price, increase profit' if profit_increase > 50 else 'Re-quote to customer'
    }


if __name__ == '__main__':
    print("=" * 70)
    print("PROFIT CALCULATOR - Analyze Quote Profitability")
    print("=" * 70)
    
    # Analyze all quotes
    df_profit = analyze_quote_profitability()
    
    if not df_profit.empty:
        print(f"\nProfitability Analysis for {len(df_profit)} quotes:\n")
        print(df_profit[['Quote_ID', 'Route', 'Selling_Price', 'Cost', 'Profit_Amount', 'Profit_Margin']].to_string(index=False))
        
        # Summary stats
        print(f"\n{'='*70}")
        print(f"Total Profit: ${df_profit['Profit_Amount'].sum():,.2f}")
        print(f"Average Profit: ${df_profit['Profit_Amount'].mean():,.2f}")
        
        # Save results
        output_file = '../data/Profit_Analysis.xlsx'
        df_profit.to_excel(output_file, index=False)
        print(f"\n✓ Saved to {output_file}")
    else:
        print("\nNo quotes to analyze")
    
    # Example: Calculate opportunity
    print(f"\n{'='*70}")
    print("Example: Profit Opportunity Calculation")
    print("=" * 70)
    
    opportunity = calculate_profit_opportunity(
        quoted_price=1500,
        old_cost=1350,
        new_cost=1250
    )
    
    print(f"\nOriginal Quote:")
    print(f"  Price: ${opportunity['Original']['Quoted_Price']}")
    print(f"  Cost: ${opportunity['Original']['Cost']}")
    print(f"  Profit: ${opportunity['Original']['Profit']} ({opportunity['Original']['Margin']})")
    
    print(f"\nWith New Cost:")
    print(f"  Price: ${opportunity['Current']['Quoted_Price']} (unchanged)")
    print(f"  Cost: ${opportunity['Current']['Cost']}")
    print(f"  Profit: ${opportunity['Current']['Profit']} ({opportunity['Current']['Margin']})")
    
    print(f"\nOpportunity:")
    print(f"  Profit Increase: ${opportunity['Opportunity']['Profit_Increase']}")
    print(f"  Alternative: Re-quote at ${opportunity['Opportunity']['Alternative_Price']}")
    print(f"  Customer Saves: ${opportunity['Opportunity']['Customer_Savings']}")
    print(f"  Recommendation: {opportunity['Recommendation']}")
