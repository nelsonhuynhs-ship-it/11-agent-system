"""
ETA Alert System - Generate alerts for approaching shipments
"""

import pandas as pd
from datetime import datetime, timedelta

print("=" * 70)
print("ETA ALERT SYSTEM - Shipment Arrival Alerts")
print("=" * 70)

JOBS_FILE = 'Jobs_Master.xlsx'

# ============================================================
# LOAD ACTIVE JOBS
# ============================================================
print("\n[1/3] Loading active jobs...")

try:
    df_jobs = pd.read_excel(JOBS_FILE, sheet_name='Active_Jobs')
    print(f"  -> Loaded {len(df_jobs)} jobs")
except Exception as e:
    print(f"  -> Error: {e}")
    print("  -> No active jobs found")
    exit(0)

# Filter jobs with ETA
df_jobs['ETA'] = pd.to_datetime(df_jobs['ETA'], errors='coerce')
df_with_eta = df_jobs[df_jobs['ETA'].notna()].copy()

print(f"  -> {len(df_with_eta)} jobs with ETA")

if len(df_with_eta) == 0:
    print("\n[INFO] No jobs with ETA to check")
    exit(0)

# ============================================================
# GENERATE ALERTS
# ============================================================
print("\n[2/3] Generating ETA alerts...")

today = datetime.now()
alerts = []

for idx, job in df_with_eta.iterrows():
    eta = job['ETA']
    days_until = (eta - today).days
    
    # Alert 1: 7 days before ETA
    if days_until == 7:
        alerts.append({
            'Alert_Date': today.strftime('%Y-%m-%d'),
            'Job_ID': job['Job_ID'],
            'Customer': job['Customer_Name'],
            'Routing': job['Routing'],
            'ETA': eta.strftime('%Y-%m-%d'),
            'Days_Until_Arrival': 7,
            'Alert_Type': 'ETA_WARNING',
            'Action_Required': 'Track container, prepare customs clearance documents',
            'Status': 'Pending'
        })
    
    # Alert 2: 5 days before ETA - Payment reminder
    if days_until == 5:
        alerts.append({
            'Alert_Date': today.strftime('%Y-%m-%d'),
            'Job_ID': job['Job_ID'],
            'Customer': job['Customer_Name'],
            'Routing': job['Routing'],
            'ETA': eta.strftime('%Y-%m-%d'),
            'Days_Until_Arrival': 5,
            'Alert_Type': 'PAYMENT_REMINDER',
            'Action_Required': f"Remind customer to arrange payment (${job['Selling_Rate']:,.0f})",
            'Status': 'Pending'
        })
    
    # Alert 3: 3 days before ETA - Urgent
    if days_until == 3:
        alerts.append({
            'Alert_Date': today.strftime('%Y-%m-%d'),
            'Job_ID': job['Job_ID'],
            'Customer': job['Customer_Name'],
            'Routing': job['Routing'],
            'ETA': eta.strftime('%Y-%m-%d'),
            'Days_Until_Arrival': 3,
            'Alert_Type': 'ETA_URGENT',
            'Action_Required': 'Confirm delivery arrangement, book trucking if door delivery',
            'Status': 'Pending'
        })
    
    # Alert 4: Door delivery - 3 days before
    if job['Door_Delivery'] == 'Yes' and days_until == 3:
        alerts.append({
            'Alert_Date': today.strftime('%Y-%m-%d'),
            'Job_ID': job['Job_ID'],
            'Customer': job['Customer_Name'],
            'Routing': job['Routing'],
            'ETA': eta.strftime('%Y-%m-%d'),
            'Days_Until_Arrival': 3,
            'Alert_Type': 'DOOR_DELIVERY',
            'Action_Required': f"Schedule trucking to {job['Door_Address']}",
            'Status': 'Pending'
        })
    
    # Alert 5: SI missing - 5 days before ETD
    if pd.notna(job.get('ETD')):
        etd = pd.to_datetime(job['ETD'])
        days_until_etd = (etd - today).days
        
        if days_until_etd == 5 and pd.isna(job.get('SI_Received')):
            alerts.append({
                'Alert_Date': today.strftime('%Y-%m-%d'),
                'Job_ID': job['Job_ID'],
                'Customer': job['Customer_Name'],
                'Routing': job['Routing'],
                'ETA': eta.strftime('%Y-%m-%d'),
                'Days_Until_Arrival': days_until,
                'Alert_Type': 'SI_MISSING',
                'Action_Required': 'Follow up with customer for SI document',
                'Status': 'Pending'
            })

print(f"  -> Generated {len(alerts)} alerts")

# ============================================================
# SAVE ALERTS
# ============================================================
print("\n[3/3] Saving alerts...")

if len(alerts) > 0:
    df_alerts = pd.DataFrame(alerts)
    
    # Save to Jobs_Master.xlsx
    try:
        with pd.ExcelWriter(JOBS_FILE, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
            df_alerts.to_excel(writer, sheet_name='ETA_Alerts', index=False)
        
        print(f"  -> Saved to {JOBS_FILE} (ETA_Alerts sheet)")
    except Exception as e:
        print(f"  -> Error saving: {e}")
    
    # Display summary
    print("\n" + "=" * 70)
    print("ALERT SUMMARY")
    print("=" * 70)
    
    alert_counts = df_alerts['Alert_Type'].value_counts()
    
    for alert_type, count in alert_counts.items():
        print(f"\n{alert_type}: {count} alerts")
        
        type_alerts = df_alerts[df_alerts['Alert_Type'] == alert_type]
        for _, alert in type_alerts.head(3).iterrows():
            print(f"  - {alert['Customer']}: {alert['Action_Required']}")
    
    print(f"\n{'='*70}")
    print(f"Total Alerts: {len(alerts)}")
else:
    print("  -> No alerts to save")
    print("\n[INFO] No shipments approaching ETA")

print("\n" + "=" * 70)
print("ETA ALERT SYSTEM COMPLETE")
print("=" * 70)
