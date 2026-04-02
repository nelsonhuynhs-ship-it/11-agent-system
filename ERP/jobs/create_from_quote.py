"""
Create Job from Won Quote - Convert CRM quote to Job
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Import quote matcher to get current pricing
from intelligence.quote_matcher import get_price_from_pricing_engine

def generate_job_id():
    """Generate unique job ID"""
    today = datetime.now()
    return f"J{today.strftime('%Y%m%d')}{today.strftime('%H%M%S')}"


def create_job_from_quote(quote_id):
    """
    Create job from won CRM quote
    
    Args:
        quote_id: Quote ID from CRM
    
    Returns:
        dict with job details or None if error
    """
    
    CRM_FILE = '../data/CRM_Master.xlsx'
    JOBS_FILE = '../data/Jobs_Master.xlsx'
    
    try:
        # Load quote
        df_quotes = pd.read_excel(CRM_FILE, sheet_name='Quotes')
        quote = df_quotes[df_quotes['Quote_ID'] == quote_id]
        
        if quote.empty:
            print(f"Error: Quote {quote_id} not found")
            return None
        
        quote = quote.iloc[0]
        
        # Check if quote is won
        if quote['Pipeline_Status'] != 'Won':
            print(f"Error: Quote {quote_id} status is '{quote['Pipeline_Status']}', not 'Won'")
            return None
        
        # Load customer info
        df_customers = pd.read_excel(CRM_FILE, sheet_name='Customers')
        customer = df_customers[df_customers['Customer_ID'] == quote['Customer_ID']]
        
        if customer.empty:
            customer_name = 'Unknown'
            customer_type = 'Direct'
        else:
            customer_name = customer.iloc[0]['Company_Name']
            customer_type = customer.iloc[0]['Customer_Type']
        
        # Get current buying rate from Pricing Engine
        buying_rate = 0
        if not pd.isna(quote['POL']) and not pd.isna(quote['POD']) and not pd.isna(quote['Carrier']):
            price_info = get_price_from_pricing_engine(
                pol=quote['POL'],
                pod=quote['POD'],
                carrier=quote['Carrier'],
                container_type=quote['Container_Type']
            )
            
            if price_info:
                buying_rate = price_info['Total_Cost']
        
        # If no pricing found, use Ocean_Freight from quote
        if buying_rate == 0:
            buying_rate = quote.get('Ocean_Freight', 0)
        
        # Calculate profit
        selling_rate = quote.get('Total_Price', 0)
        profit = selling_rate - buying_rate
        profit_margin = (profit / buying_rate * 100) if buying_rate > 0 else 0
        
        # Create job
        job = {
            'Job_ID': generate_job_id(),
            'Quote_ID': quote_id,
            'Customer_ID': quote['Customer_ID'],
            'Customer_Name': customer_name,
            'Customer_Type': customer_type,
            'Routing': f"{quote['POL']}-{quote['POD']}",
            'Bkg_No': '',  # To be filled later
            'Hbl_No': '',  # To be filled later
            'ETD': '',  # To be filled later
            'ETD_Original': '',
            'ETA': '',  # To be filled later
            'ETA_Alert_Date': '',
            'ATA': '',
            'Carrier': quote['Carrier'],
            'Contract_Type': quote.get('Contract_Type', 'FAK'),
            'Container_Type': quote['Container_Type'],
            'Quantity': quote.get('Quantity', 1),
            'Volume': quote.get('Quantity', 1),
            'Selling_Rate': selling_rate,
            'Buying_Rate': buying_rate,
            'Profit': profit,
            'Profit_Margin': f"{profit_margin:.1f}%",
            'Status': 'Booking_Pending',
            'Delay_Count': 0,
            'Delay_Log': '',
            'Door_Delivery': 'No',
            'Door_Address': '',
            'Door_Status': '',
            'SI_Received': '',
            'CY_Cutoff': '',
            'Carrier_Com': 0,
            'Customer_Com': 0,
            'Notes': f"Created from Quote {quote_id}",
            'Created_Date': datetime.now().strftime('%Y-%m-%d'),
            'Last_Updated': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Save to Jobs_Master.xlsx
        try:
            df_jobs = pd.read_excel(JOBS_FILE, sheet_name='Active_Jobs')
        except:
            df_jobs = pd.DataFrame()
        
        df_new_job = pd.DataFrame([job])
        df_combined = pd.concat([df_jobs, df_new_job], ignore_index=True)
        
        with pd.ExcelWriter(JOBS_FILE, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
            df_combined.to_excel(writer, sheet_name='Active_Jobs', index=False)
        
        print(f"\nJob created successfully!")
        print(f"  Job ID: {job['Job_ID']}")
        print(f"  Customer: {customer_name}")
        print(f"  Route: {job['Routing']}")
        print(f"  Carrier: {job['Carrier']}")
        print(f"  Selling Rate: ${selling_rate:,.0f}")
        print(f"  Buying Rate: ${buying_rate:,.0f}")
        print(f"  Profit: ${profit:,.0f} ({profit_margin:.1f}%)")
        print(f"  Status: {job['Status']}")
        
        # Update quote status in CRM
        df_quotes.loc[df_quotes['Quote_ID'] == quote_id, 'Pipeline_Status'] = 'Job_Created'
        
        with pd.ExcelWriter(CRM_FILE, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
            df_quotes.to_excel(writer, sheet_name='Quotes', index=False)
        
        print(f"\nUpdated CRM quote status to 'Job_Created'")
        
        return job
        
    except Exception as e:
        print(f"Error creating job: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    print("=" * 70)
    print("CREATE JOB FROM WON QUOTE")
    print("=" * 70)
    
    # Check for command line argument
    if len(sys.argv) > 1:
        quote_id = sys.argv[1]
    else:
        quote_id = input("\nEnter Quote ID: ")
    
    job = create_job_from_quote(quote_id)
    
    if job:
        print("\n" + "=" * 70)
        print("SUCCESS - Job created and saved to Jobs_Master.xlsx")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Open Jobs_Master.xlsx")
        print("  2. Fill in Bkg_No, Hbl_No, ETD, ETA")
        print("  3. Update status as shipment progresses")
    else:
        print("\nFailed to create job")
