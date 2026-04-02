"""
Delay Tracker - Track and log shipment delays
"""

import pandas as pd
from datetime import datetime
import sys

def record_delay(job_id, new_etd):
    """
    Record delay for a job
    
    Args:
        job_id: Job ID
        new_etd: New ETD date (YYYY-MM-DD format)
    """
    
    JOBS_FILE = 'Jobs_Master.xlsx'
    
    try:
        # Load active jobs
        df_jobs = pd.read_excel(JOBS_FILE, sheet_name='Active_Jobs')
        
        # Find job
        job_idx = df_jobs[df_jobs['Job_ID'] == job_id].index
        
        if len(job_idx) == 0:
            print(f"Error: Job {job_id} not found")
            return False
        
        job_idx = job_idx[0]
        job = df_jobs.loc[job_idx]
        
        # Parse dates
        new_etd = pd.to_datetime(new_etd)
        current_etd = pd.to_datetime(job['ETD']) if pd.notna(job['ETD']) else None
        original_etd = pd.to_datetime(job['ETD_Original']) if pd.notna(job['ETD_Original']) else current_etd
        
        if current_etd is None:
            print("Error: Job has no current ETD")
            return False
        
        # Calculate delay
        delay_days = (new_etd - current_etd).days
        
        if delay_days <= 0:
            print("Error: New ETD is not later than current ETD")
            return False
        
        # Update delay count
        delay_count = job['Delay_Count'] if pd.notna(job['Delay_Count']) else 0
        delay_count += 1
        
        # Update delay log
        delay_log = job['Delay_Log'] if pd.notna(job['Delay_Log']) else ''
        
        if delay_log:
            delay_log += f" -> {new_etd.strftime('%d%b').upper()}(+{delay_days})"
        else:
            if original_etd:
                delay_log = f"{original_etd.strftime('%d%b').upper()} -> {new_etd.strftime('%d%b').upper()}(+{delay_days})"
            else:
                delay_log = f"{current_etd.strftime('%d%b').upper()} -> {new_etd.strftime('%d%b').upper()}(+{delay_days})"
        
        # Update job
        df_jobs.loc[job_idx, 'ETD'] = new_etd
        df_jobs.loc[job_idx, 'Delay_Count'] = delay_count
        df_jobs.loc[job_idx, 'Delay_Log'] = delay_log
        df_jobs.loc[job_idx, 'Last_Updated'] = datetime.now().strftime('%Y-%m-%d')
        
        # Update ETA (assume same transit time)
        if pd.notna(job['ETA']):
            current_eta = pd.to_datetime(job['ETA'])
            transit_days = (current_eta - current_etd).days
            new_eta = new_etd + pd.Timedelta(days=transit_days)
            df_jobs.loc[job_idx, 'ETA'] = new_eta
        
        # Save to Excel
        with pd.ExcelWriter(JOBS_FILE, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
            df_jobs.to_excel(writer, sheet_name='Active_Jobs', index=False)
        
        # Add to Delay_Tracking sheet
        delay_record = {
            'Job_ID': job_id,
            'Customer': job['Customer_Name'],
            'Routing': job['Routing'],
            'Carrier': job['Carrier'],
            'ETD_Original': original_etd.strftime('%Y-%m-%d') if original_etd else '',
            'ETD_Current': new_etd.strftime('%Y-%m-%d'),
            'Delay_Count': delay_count,
            'Delay_Days': delay_days,
            'Delay_Log': delay_log,
            'Impact': 'HIGH' if delay_days > 7 else 'MEDIUM' if delay_days > 3 else 'LOW'
        }
        
        try:
            df_delay_tracking = pd.read_excel(JOBS_FILE, sheet_name='Delay_Tracking')
        except:
            df_delay_tracking = pd.DataFrame()
        
        df_new_delay = pd.DataFrame([delay_record])
        df_combined = pd.concat([df_delay_tracking, df_new_delay], ignore_index=True)
        
        with pd.ExcelWriter(JOBS_FILE, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
            df_combined.to_excel(writer, sheet_name='Delay_Tracking', index=False)
        
        print("\n" + "=" * 70)
        print("DELAY RECORDED SUCCESSFULLY")
        print("=" * 70)
        print(f"\nJob ID: {job_id}")
        print(f"Customer: {job['Customer_Name']}")
        print(f"Routing: {job['Routing']}")
        print(f"Carrier: {job['Carrier']}")
        print(f"\nOld ETD: {current_etd.strftime('%Y-%m-%d')}")
        print(f"New ETD: {new_etd.strftime('%Y-%m-%d')}")
        print(f"Delay: {delay_days} days")
        print(f"\nTotal Delays: {delay_count}")
        print(f"Delay Log: {delay_log}")
        print(f"Impact: {delay_record['Impact']}")
        
        if pd.notna(job['ETA']):
            print(f"\nNew ETA: {df_jobs.loc[job_idx, 'ETA']}")
        
        print("\n" + "=" * 70)
        
        return True
        
    except Exception as e:
        print(f"Error recording delay: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("=" * 70)
    print("DELAY TRACKER - Record Shipment Delays")
    print("=" * 70)
    
    # Get job ID
    if len(sys.argv) > 1:
        job_id = sys.argv[1]
    else:
        job_id = input("\nEnter Job ID: ")
    
    # Get new ETD
    if len(sys.argv) > 2:
        new_etd = sys.argv[2]
    else:
        new_etd = input("Enter new ETD (YYYY-MM-DD): ")
    
    # Record delay
    success = record_delay(job_id, new_etd)
    
    if success:
        print("\nDelay recorded and saved to Jobs_Master.xlsx")
    else:
        print("\nFailed to record delay")
