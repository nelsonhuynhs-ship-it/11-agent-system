"""
Add More Sample Data to CRM - For Dashboard Demo
Adds more quotes across multiple months and updates shipment dates
"""

import pandas as pd
import openpyxl
from datetime import datetime, timedelta
import random

print("=" * 70)
print("Adding More Sample Data to CRM_Master.xlsx")
print("=" * 70)

# Load existing data
crm_file = 'CRM_Master.xlsx'
wb = openpyxl.load_workbook(crm_file)

# ============================================================
# ADD MORE QUOTES (Multiple months)
# ============================================================
print("\n[1/3] Adding more quotes across multiple months...")

ws_quotes = wb['Quotes']

# Generate quotes for last 3 months
today = datetime.now()
months_ago_3 = today - timedelta(days=90)
months_ago_2 = today - timedelta(days=60)
months_ago_1 = today - timedelta(days=30)

additional_quotes = [
    # November 2025
    ['Q2025101', '2025-11-05', 'C002', 'Shipper', 'HCM', 'USLAX', 'Los Angeles', 'ONE', 
     'Furniture', '9403', '40HQ', 3, 1600, 1850, '2025-11-12', 'Won', 'Good price', 
     'Regular customer', 'Nelson', '2025-11-05'],
    
    ['Q2025102', '2025-11-10', 'C004', 'Shipper', 'BKK', 'USNYC', 'New York', 'YML', 
     'Textile', '5208', '40GP', 2, 1450, 1700, '2025-11-17', 'Lost', 'Price too high', 
     'Customer went with competitor', 'Nelson', '2025-11-10'],
    
    ['Q2025103', '2025-11-15', 'C001', 'Coloader', 'HCM', 'USSEA', 'Seattle', 'HPL', 
     'General Cargo', '', '40GP', 1, 1300, 1500, '2025-11-22', 'Won', 'Best rate', 
     'Quick turnaround', 'Nelson', '2025-11-15'],
    
    # December 2025
    ['Q2025201', '2025-12-03', 'C003', 'Cnee', 'HCM', 'USNYC', 'New York', 'ONE', 
     'Furniture', '9403', '40HQ', 5, 1550, 1800, '2025-12-10', 'Won', 'Volume discount', 
     'Large shipment', 'Nelson', '2025-12-03'],
    
    ['Q2025202', '2025-12-08', 'C002', 'Shipper', 'HCM', 'USLAX', 'Los Angeles', 'YML', 
     'Furniture', '9403', '40HQ', 2, 1500, 1750, '2025-12-15', 'Follow', '', 
     'Waiting for customer decision', 'Nelson', '2025-12-08'],
    
    ['Q2025203', '2025-12-12', 'C005', 'Cnee', 'BKK', 'CATOR', 'Toronto', 'HPL', 
     'Textile', '5208', '40GP', 3, 1400, 1650, '2025-12-19', 'Won', 'Reliable service', 
     'Repeat customer', 'Nelson', '2025-12-12'],
    
    ['Q2025204', '2025-12-18', 'C006', 'Shipper', 'KUL', 'USLAX', 'Los Angeles', 'ONE', 
     'Electronics', '8517', '40HQ', 4, 1650, 1900, '2025-12-25', 'Lost', 'Transit time', 
     'Customer needed faster service', 'Nelson', '2025-12-18'],
    
    ['Q2025205', '2025-12-22', 'C001', 'Coloader', 'HCM', 'USNYC', 'New York', 'YML', 
     'General Cargo', '', '40GP', 1, 1350, 1550, '2025-12-29', 'Won', 'Competitive', 
     'Good relationship', 'Nelson', '2025-12-22'],
    
    # January 2026
    ['Q2026004', '2026-01-05', 'C002', 'Shipper', 'HCM', 'USNYC', 'New York', 'HPL', 
     'Furniture', '9403', '40HQ', 2, 1480, 1730, '2026-01-12', 'Quoted', '', 
     'Pending customer response', 'Nelson', '2026-01-05'],
    
    ['Q2026005', '2026-01-08', 'C004', 'Shipper', 'BKK', 'USLAX', 'Los Angeles', 'ONE', 
     'Textile', '5208', '40GP', 3, 1520, 1770, '2026-01-15', 'Follow', '', 
     'Following up with customer', 'Nelson', '2026-01-08'],
    
    ['Q2026006', '2026-01-12', 'C003', 'Cnee', 'HCM', 'USSEA', 'Seattle', 'YML', 
     'Furniture', '9403', '40HQ', 4, 1430, 1680, '2026-01-19', 'Won', 'Best service', 
     'Fast booking', 'Nelson', '2026-01-12'],
    
    ['Q2026007', '2026-01-15', 'C007', 'Coloader', 'HCM', 'USLAX', 'Los Angeles', 'HPL', 
     'General Cargo', '', '40GP', 1, 1280, 1480, '2026-01-22', 'Quoted', '', 
     'New inquiry', 'Nelson', '2026-01-15'],
    
    ['Q2026008', '2026-01-18', 'C005', 'Cnee', 'BKK', 'USNYC', 'New York', 'ONE', 
     'Textile', '5208', '40GP', 2, 1460, 1710, '2026-01-25', 'Follow', '', 
     'Price negotiation ongoing', 'Nelson', '2026-01-18'],
]

for quote in additional_quotes:
    ws_quotes.append(quote)

print(f"  -> Added {len(additional_quotes)} quotes")

# ============================================================
# UPDATE SHIPMENT DATES (Some old, some recent)
# ============================================================
print("\n[2/3] Updating shipment dates...")

ws_relationships = wb['Shipper_Cnee_Relationships']

# Update some relationships to be old (trigger alerts)
# Row 2: R001 - Make it 45 days old
ws_relationships['I2'] = (today - timedelta(days=45)).strftime('%Y-%m-%d')

# Row 3: R002 - Make it 65 days old (HIGH RISK)
ws_relationships['I3'] = (today - timedelta(days=65)).strftime('%Y-%m-%d')

# Row 4: R003 - Keep recent
ws_relationships['I4'] = (today - timedelta(days=10)).strftime('%Y-%m-%d')

# Row 5: R004 - Keep recent
ws_relationships['I5'] = (today - timedelta(days=5)).strftime('%Y-%m-%d')

# Row 6: R005 - Make it 35 days old (MEDIUM RISK)
ws_relationships['I6'] = (today - timedelta(days=35)).strftime('%Y-%m-%d')

print("  -> Updated 5 shipment dates (some old for alert demo)")

# ============================================================
# SAVE
# ============================================================
print("\n[3/3] Saving updated CRM_Master.xlsx...")

wb.save(crm_file)

print("\n" + "=" * 70)
print("SUCCESS! Updated CRM_Master.xlsx")
print("=" * 70)
print("\nAdded:")
print(f"  - {len(additional_quotes)} quotes across 3 months (Nov, Dec, Jan)")
print("  - Updated shipment dates (some old to trigger alerts)")
print("\nNow run: python create_crm_dashboard.py")
print("  -> Will show monthly tracking")
print("  -> Will show inactive customer alerts")
