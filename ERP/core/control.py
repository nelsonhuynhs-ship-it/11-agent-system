"""
ERP Master Control - Single point of control for entire system
Anh chỉ cần chạy file này để thao tác toàn bộ hệ thống

Updated: 16 Mar 2026 — Post-refactor (Phase 6A)
All paths now reference ERP/ subdirectories instead of legacy CRM/, Jobs/, Integration/
"""

import os
import sys

# Base directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ERP_DIR = os.path.dirname(SCRIPT_DIR)  # ERP/
ENGINE_DIR = os.path.dirname(ERP_DIR)  # Engine_test/
ERP_DATA = os.path.join(ERP_DIR, "data")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def show_menu():
    clear_screen()
    print("=" * 70)
    print("         LOGISTICS ERP SYSTEM - MASTER CONTROL")
    print("=" * 70)
    print()
    print("PRICING ENGINE:")
    print("  1. Load new pricing files (FAK/FIX/SCFI)")
    print("  2. Generate pricing dashboard")
    print()
    print("CRM:")
    print("  3. Open CRM Master (Excel)")
    print("  4. Analyze customer relationships")
    print("  5. View CRM dashboard")
    print()
    print("INTELLIGENCE:")
    print("  6. Run daily sync (Price alerts + Profit analysis)")
    print("  7. Check price alerts")
    print("  8. View profit analysis")
    print()
    print("JOBS:")
    print("  9. Open Jobs Master (Excel)")
    print(" 10. Create job from won quote")
    print(" 11. Check ETA alerts")
    print(" 12. Record delay")
    print(" 13. Generate carrier performance report")
    print()
    print("REPORTS:")
    print(" 14. Full system report (All modules)")
    print()
    print(" 0. Exit")
    print()
    print("=" * 70)

def run_pricing_loader():
    print("\n[PRICING ENGINE] Loading new pricing files...")
    pe_dir = os.path.join(ENGINE_DIR, "Pricing_Engine")
    os.system(f'python "{os.path.join(pe_dir, "master_loader_v1.py")}"')
    input("\nPress Enter to continue...")

def run_pricing_dashboard():
    print("\n[PRICING ENGINE] Generating dashboard...")
    pe_dir = os.path.join(ENGINE_DIR, "Pricing_Engine")
    os.system(f'python "{os.path.join(pe_dir, "create_master_dashboard.py")}"')
    input("\nPress Enter to continue...")

def open_crm():
    print("\n[CRM] Opening CRM Master...")
    crm_file = os.path.join(ERP_DATA, "CRM_Master.xlsx")
    os.system(f'start "" "{crm_file}"')
    input("\nPress Enter to continue...")

def analyze_relationships():
    print("\n[CRM] Analyzing customer relationships...")
    crm_script = os.path.join(ERP_DIR, "crm", "relationships.py")
    os.system(f'python "{crm_script}"')
    input("\nPress Enter to continue...")

def view_crm_dashboard():
    print("\n[CRM] Opening CRM Dashboard...")
    crm_file = os.path.join(ERP_DATA, "CRM_Master.xlsx")
    os.system(f'start "" "{crm_file}"')
    print("  -> Go to 'Dashboard' sheet")
    print("  -> Use filter in cell C5 to select month")
    input("\nPress Enter to continue...")

def run_daily_sync():
    print("\n[INTELLIGENCE] Running daily sync...")
    sync_script = os.path.join(ERP_DIR, "intelligence", "daily_sync.py")
    os.system(f'python "{sync_script}"')
    input("\nPress Enter to continue...")

def check_price_alerts():
    print("\n[INTELLIGENCE] Checking price alerts...")
    alert_script = os.path.join(ERP_DIR, "intelligence", "price_alerts.py")
    os.system(f'python "{alert_script}"')
    alert_file = os.path.join(ERP_DATA, "Price_Alerts.xlsx")
    print(f"\n  -> Opening {alert_file}...")
    os.system(f'start "" "{alert_file}"')
    input("\nPress Enter to continue...")

def view_profit_analysis():
    print("\n[INTELLIGENCE] Analyzing profitability...")
    profit_script = os.path.join(ERP_DIR, "intelligence", "profit_calculator.py")
    os.system(f'python "{profit_script}"')
    profit_file = os.path.join(ERP_DATA, "Profit_Analysis.xlsx")
    print(f"\n  -> Opening {profit_file}...")
    os.system(f'start "" "{profit_file}"')
    input("\nPress Enter to continue...")

def open_jobs():
    print("\n[JOBS] Opening Jobs Master...")
    jobs_file = os.path.join(ERP_DATA, "Jobs_Master.xlsx")
    os.system(f'start "" "{jobs_file}"')
    input("\nPress Enter to continue...")

def create_job():
    print("\n[JOBS] Create job from won quote")
    quote_id = input("Enter Quote ID: ")
    job_script = os.path.join(ERP_DIR, "jobs", "create_from_quote.py")
    os.system(f'python "{job_script}" {quote_id}')
    input("\nPress Enter to continue...")

def check_eta_alerts():
    print("\n[JOBS] Checking ETA alerts...")
    eta_script = os.path.join(ERP_DIR, "jobs", "eta_alerts.py")
    os.system(f'python "{eta_script}"')
    input("\nPress Enter to continue...")

def record_delay():
    print("\n[JOBS] Record shipment delay")
    job_id = input("Enter Job ID: ")
    new_etd = input("Enter new ETD (YYYY-MM-DD): ")
    delay_script = os.path.join(ERP_DIR, "jobs", "delay_tracker.py")
    os.system(f'python "{delay_script}" {job_id} {new_etd}')
    input("\nPress Enter to continue...")

def carrier_performance():
    print("\n[JOBS] Generating carrier performance report...")
    perf_script = os.path.join(ERP_DIR, "jobs", "carrier_performance.py")
    os.system(f'python "{perf_script}"')
    perf_file = os.path.join(ERP_DATA, "Carrier_Performance_Report.xlsx")
    print(f"\n  -> Opening {perf_file}...")
    os.system(f'start "" "{perf_file}"')
    input("\nPress Enter to continue...")

def full_report():
    print("\n[FULL SYSTEM REPORT]")
    print("=" * 70)
    
    import pandas as pd
    
    # Pricing stats
    print("\nPRICING ENGINE:")
    print("  - Database: 10M+ pricing records (Parquet)")
    print(f"  - File: Pricing_Engine/data/Cleaned_Master_History.parquet")
    
    # CRM stats
    print("\nCRM:")
    crm_file = os.path.join(ERP_DATA, "CRM_Master.xlsx")
    try:
        df_customers = pd.read_excel(crm_file, sheet_name='Customers')
        df_quotes = pd.read_excel(crm_file, sheet_name='Quotes')
        print(f"  - Customers: {len(df_customers)}")
        print(f"  - Quotes: {len(df_quotes)}")
        print(f"  - File: ERP/data/CRM_Master.xlsx")
    except:
        print("  - Error loading CRM data")
    
    # Jobs stats
    print("\nJOBS:")
    jobs_file = os.path.join(ERP_DATA, "Jobs_Master.xlsx")
    try:
        df_jobs = pd.read_excel(jobs_file, sheet_name='Active_Jobs')
        total_profit = df_jobs['Profit'].sum()
        print(f"  - Active Jobs: {len(df_jobs)}")
        print(f"  - Total Profit: ${total_profit:,.2f}")
        print(f"  - File: ERP/data/Jobs_Master.xlsx")
    except:
        print("  - Error loading Jobs data")
    
    print("\n" + "=" * 70)
    input("\nPress Enter to continue...")

def main():
    while True:
        show_menu()
        choice = input("Select option (0-14): ").strip()
        
        if choice == '0':
            print("\nExiting ERP System. Goodbye!")
            break
        elif choice == '1':
            run_pricing_loader()
        elif choice == '2':
            run_pricing_dashboard()
        elif choice == '3':
            open_crm()
        elif choice == '4':
            analyze_relationships()
        elif choice == '5':
            view_crm_dashboard()
        elif choice == '6':
            run_daily_sync()
        elif choice == '7':
            check_price_alerts()
        elif choice == '8':
            view_profit_analysis()
        elif choice == '9':
            open_jobs()
        elif choice == '10':
            create_job()
        elif choice == '11':
            check_eta_alerts()
        elif choice == '12':
            record_delay()
        elif choice == '13':
            carrier_performance()
        elif choice == '14':
            full_report()
        else:
            print("\nInvalid option. Please try again.")
            input("\nPress Enter to continue...")

if __name__ == '__main__':
    main()
