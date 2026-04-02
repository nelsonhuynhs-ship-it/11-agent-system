"""
enrich_active_jobs.py
=====================
Enrich Active Jobs in ERP with Cost Breakdown and Booking Email links.

Cách dùng:
  python scripts/enrich_active_jobs.py

Hoạt động:
  1. Đọc Active Jobs từ ERP_Master.xlsm
  2. Lookup Basic Cost data từ MasterFullPricing.xlsx
  3. Tạo Cost Breakdown string cho mỗi job
  4. Tạo mailto: link cho booking request
  5. Ghi vào cột mới: Cost_Breakdown (AJ) + 📧 Request BKG (AK)

Lưu ý:
  - File ERP_Master.xlsm phải đóng trước khi chạy
"""

import os, sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# Add parent dir for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ERP_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from email_builder import (
    load_rules, build_mailto_link, build_cost_breakdown, get_container_category
)

# ── Paths ──
MASTER_FILE = os.path.join(ERP_DIR, "..", "Pricing_Engine", "data", "MasterFullPricing.xlsx")
ERP_FILE    = os.path.join(ERP_DIR, "data", "ERP_Master.xlsm")

# ── Active Jobs Layout ──
JOBS_HEADER_ROW = 7
JOBS_DATA_START = 8
# Existing columns A-AI (35 cols), new: AJ=Cost_Breakdown, AK=Email
COST_COL = 36   # AJ
EMAIL_COL = 37  # AK


def load_basic_cost():
    """Load Basic Cost data from MasterFullPricing as DataFrame."""
    print(f"[+] Loading Basic Cost: {MASTER_FILE}")
    df = pd.read_excel(MASTER_FILE, sheet_name="Basic Cost")
    print(f"    -> {len(df):,} rows, {len(df.columns)} columns")
    return df


def find_basic_cost_row(df_bc, carrier, pol, pod, container_type):
    """Find matching Basic Cost row for a job."""
    # Try exact match first
    mask = (
        (df_bc['Carrier'] == carrier) &
        (df_bc['POL'] == pol) &
        (df_bc['POD'] == pod)
    )
    matches = df_bc[mask]
    
    if matches.empty:
        # Try with just Carrier + POL
        mask = (df_bc['Carrier'] == carrier) & (df_bc['POL'] == pol)
        matches = df_bc[mask]
    
    if not matches.empty:
        return matches.iloc[0].to_dict()
    return None


def main():
    print("=" * 60)
    print("  ENRICH ACTIVE JOBS: Cost Breakdown + Email Links")
    print("=" * 60)
    
    # Check ERP file
    if not os.path.exists(ERP_FILE):
        print(f"[ERROR] ERP file not found: {ERP_FILE}")
        sys.exit(1)
    
    try:
        with open(ERP_FILE, 'r+b'):
            pass
    except PermissionError:
        print(f"\n[ERROR] ERP file is open in Excel. Please close it first.")
        sys.exit(1)
    
    # Load data
    df_bc = load_basic_cost()
    rules = load_rules()
    
    # Open ERP
    print(f"\n[+] Opening ERP: {ERP_FILE}")
    wb = openpyxl.load_workbook(ERP_FILE, keep_vba=True)
    
    # Find Active Jobs sheet
    jobs_sheet = None
    for sn in wb.sheetnames:
        if 'Active Jobs' in sn:
            jobs_sheet = sn
            break
    
    if not jobs_sheet:
        print("[ERROR] Active Jobs sheet not found")
        wb.close()
        sys.exit(1)
    
    ws = wb[jobs_sheet]
    print(f"    -> Sheet: '{jobs_sheet}'")
    print(f"    -> {ws.max_row - JOBS_DATA_START + 1} jobs")
    
    # Add new headers
    header_font = Font(bold=True, color="FFFFFF", size=10, name="Segoe UI")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    ws.cell(JOBS_HEADER_ROW, COST_COL, "Cost_Breakdown")
    ws.cell(JOBS_HEADER_ROW, COST_COL).font = header_font
    ws.cell(JOBS_HEADER_ROW, COST_COL).fill = header_fill
    ws.cell(JOBS_HEADER_ROW, COST_COL).alignment = center
    
    ws.cell(JOBS_HEADER_ROW, EMAIL_COL, "📧 Request BKG")
    ws.cell(JOBS_HEADER_ROW, EMAIL_COL).font = header_font
    ws.cell(JOBS_HEADER_ROW, EMAIL_COL).fill = header_fill
    ws.cell(JOBS_HEADER_ROW, EMAIL_COL).alignment = center
    
    # Set column widths
    ws.column_dimensions['AJ'].width = 40
    ws.column_dimensions['AK'].width = 18
    
    # Read existing headers to map column indices
    headers = {}
    for c in range(1, 36):
        v = ws.cell(JOBS_HEADER_ROW, c).value
        if v:
            headers[v] = c
    
    # Process each job row
    enriched = 0
    email_count = 0
    
    for r in range(JOBS_DATA_START, ws.max_row + 1):
        # Read job data
        job_id = ws.cell(r, headers.get('Job_ID', 1)).value
        if not job_id:
            continue
        
        carrier = ws.cell(r, headers.get('Carrier', 14)).value or ""
        pol = ""
        routing = ws.cell(r, headers.get('Routing', 6)).value or ""
        if "-" in routing:
            pol = routing.split("-")[0].strip()
            pod_part = routing.split("-", 1)[1].strip()
        else:
            pod_part = ""
        
        container_type = ws.cell(r, headers.get('Container_Type', 16)).value or ""
        customer = ws.cell(r, headers.get('Customer_Name', 4)).value or ""
        quantity = ws.cell(r, headers.get('Quantity', 17)).value or 1
        contract_type = ws.cell(r, headers.get('Contract_Type', 15)).value or ""
        
        # Lookup Place from POD/routing  
        # (Active Jobs has Routing like "HCM-SEATTLE", need to find Place)
        
        # Find matching Basic Cost row
        bc_row = find_basic_cost_row(df_bc, carrier, pol, pod_part, container_type)
        
        # Build cost breakdown
        if bc_row:
            job_data_for_cost = {"Container_Type": container_type}
            breakdown = build_cost_breakdown(job_data_for_cost, bc_row)
            if breakdown:
                ws.cell(r, COST_COL, breakdown)
                ws.cell(r, COST_COL).font = Font(size=9, name="Consolas")
                ws.cell(r, COST_COL).alignment = Alignment(wrap_text=True, vertical="top")
                enriched += 1
        
        # Build email link
        job_data_for_email = {
            "Customer_Name": customer,
            "POL": pol,
            "POD": pod_part,
            "Place": bc_row.get("Place", pod_part) if bc_row else pod_part,
            "Carrier": carrier,
            "Container_Type": container_type,
            "Quantity": quantity,
            "Contract_No": contract_type,
        }
        cost_data_for_email = {}
        if bc_row:
            cost_data_for_email = {
                "Contract": bc_row.get("Contract", ""),
                "Group_Rate": bc_row.get("Group Rate", ""),
            }
        
        mailto = build_mailto_link(job_data_for_email, cost_data_for_email, rules)
        
        # Write as hyperlink
        cell = ws.cell(r, EMAIL_COL, "📧 Send")
        cell.hyperlink = mailto
        cell.font = Font(color="0563C1", underline="single", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        email_count += 1
    
    # Save
    print(f"\n    -> Saving ERP file...")
    wb.save(ERP_FILE)
    print(f"\n[SUCCESS] Active Jobs enriched!")
    print(f"  -> {enriched} jobs with Cost Breakdown")
    print(f"  -> {email_count} email links added")
    print(f"  -> Columns: AJ (Cost_Breakdown), AK (📧 Request BKG)")
    wb.close()


if __name__ == "__main__":
    main()
