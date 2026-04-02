"""
Carrier Performance Report - Analyze carrier reliability and profitability
"""

import pandas as pd
from datetime import datetime

print("=" * 70)
print("CARRIER PERFORMANCE REPORT")
print("=" * 70)

JOBS_FILE = 'Jobs_Master.xlsx'

# ============================================================
# LOAD DATA
# ============================================================
print("\n[1/3] Loading job data...")

try:
    # Load both active and completed jobs
    df_active = pd.read_excel(JOBS_FILE, sheet_name='Active_Jobs')
    print(f"  -> Loaded {len(df_active)} active jobs")
except:
    df_active = pd.DataFrame()
    print("  -> No active jobs")

try:
    df_completed = pd.read_excel(JOBS_FILE, sheet_name='Completed_Jobs')
    print(f"  -> Loaded {len(df_completed)} completed jobs")
except:
    df_completed = pd.DataFrame()
    print("  -> No completed jobs")

# Combine all jobs
df_all_jobs = pd.concat([df_active, df_completed], ignore_index=True)

if len(df_all_jobs) == 0:
    print("\n[INFO] No jobs to analyze")
    exit(0)

print(f"  -> Total jobs: {len(df_all_jobs)}")

# ============================================================
# ANALYZE BY CARRIER
# ============================================================
print("\n[2/3] Analyzing carrier performance...")

carrier_stats = []

for carrier in df_all_jobs['Carrier'].dropna().unique():
    carrier_jobs = df_all_jobs[df_all_jobs['Carrier'] == carrier]
    
    total_shipments = len(carrier_jobs)
    
    # Count on-time vs delayed
    on_time = len(carrier_jobs[carrier_jobs['Delay_Count'].fillna(0) == 0])
    delayed = total_shipments - on_time
    
    on_time_rate = (on_time / total_shipments * 100) if total_shipments > 0 else 0
    
    # Average delay days
    avg_delay = carrier_jobs['Delay_Count'].fillna(0).mean()
    
    # Total profit
    total_profit = carrier_jobs['Profit'].fillna(0).sum()
    
    # Recommendation
    if on_time_rate >= 95:
        recommendation = "Excellent - Highly Recommend"
    elif on_time_rate >= 85:
        recommendation = "Good - Recommend"
    elif on_time_rate >= 70:
        recommendation = "Average - Use with caution"
    else:
        recommendation = "Poor - Not recommended"
    
    carrier_stats.append({
        'Carrier': carrier,
        'Total_Shipments': total_shipments,
        'On_Time_Shipments': on_time,
        'Delayed_Shipments': delayed,
        'On_Time_Rate': f"{on_time_rate:.1f}%",
        'Avg_Delay_Days': f"{avg_delay:.1f}",
        'Total_Profit': f"${total_profit:,.2f}",
        'Recommendation': recommendation
    })

df_carrier_perf = pd.DataFrame(carrier_stats)

# Sort by on-time rate
df_carrier_perf['On_Time_Rate_Num'] = df_carrier_perf['On_Time_Rate'].str.rstrip('%').astype(float)
df_carrier_perf = df_carrier_perf.sort_values('On_Time_Rate_Num', ascending=False)
df_carrier_perf = df_carrier_perf.drop('On_Time_Rate_Num', axis=1)

print(f"  -> Analyzed {len(df_carrier_perf)} carriers")

# ============================================================
# SAVE REPORT
# ============================================================
print("\n[3/3] Saving report...")

# Save to Jobs_Master.xlsx
with pd.ExcelWriter(JOBS_FILE, mode='a', if_sheet_exists='overlay', engine='openpyxl') as writer:
    df_carrier_perf.to_excel(writer, sheet_name='Carrier_Performance', index=False)

print(f"  -> Saved to {JOBS_FILE} (Carrier_Performance sheet)")

# Also save standalone report
report_file = 'Carrier_Performance_Report.xlsx'
df_carrier_perf.to_excel(report_file, index=False)
print(f"  -> Saved to {report_file}")

# Display report
print("\n" + "=" * 70)
print("CARRIER PERFORMANCE REPORT")
print("=" * 70)
print()
print(df_carrier_perf.to_string(index=False))

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total Carriers: {len(df_carrier_perf)}")
print(f"Total Shipments: {df_all_jobs['Carrier'].notna().sum()}")

# Best carrier
if len(df_carrier_perf) > 0:
    best = df_carrier_perf.iloc[0]
    print(f"\nBest Carrier: {best['Carrier']}")
    print(f"  On-Time Rate: {best['On_Time_Rate']}")
    print(f"  Total Shipments: {best['Total_Shipments']}")
    print(f"  Recommendation: {best['Recommendation']}")

print("\n" + "=" * 70)
print("CARRIER PERFORMANCE REPORT COMPLETE")
print("=" * 70)
