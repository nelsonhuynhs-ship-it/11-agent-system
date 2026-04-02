"""
Analyze Shipments.xlsx structure
"""
import pandas as pd
import openpyxl

file = 'Shipments.xlsx'

# Load workbook
wb = openpyxl.load_workbook(file)
print("=" * 70)
print("SHIPMENTS.XLSX ANALYSIS")
print("=" * 70)

print(f"\nSheets: {wb.sheetnames}")

# Analyze Jan 2026 sheet
df = pd.read_excel(file, sheet_name='Jan 2026')

print(f"\n=== JAN 2026 DATA ===")
print(f"Total shipments: {len(df)}")
print(f"Unique customers: {df['Customer'].nunique()}")

print(f"\n=== COLUMNS ({len(df.columns)}) ===")
for i, col in enumerate(df.columns, 1):
    print(f"{i:2d}. {col}")

print(f"\n=== SAMPLE DATA (First 3 rows) ===")
print(df.head(3).to_string())

print(f"\n=== STATUS VALUES ===")
print(df['Status'].value_counts())

print(f"\n=== CUSTOMER TYPES ===")
print(df['Customer Type'].value_counts())

print(f"\n=== CONTAINER TYPES ===")
print(df['Container Type'].value_counts())

print(f"\n=== CARRIERS ===")
print(df['Carrier'].value_counts())

print(f"\n=== DELAY ANALYSIS ===")
print(f"Shipments with delays: {df['Delay_Log'].notna().sum()}")
if df['Delay_Log'].notna().any():
    print("Delay examples:")
    print(df[df['Delay_Log'].notna()][['Customer', 'Routing', 'ETD', 'Etd_Original', 'Delay_Log']].head())

print(f"\n=== PROFIT ANALYSIS ===")
print(f"Total profit: ${df['Profit'].sum():,.2f}")
print(f"Average profit per shipment: ${df['Profit'].mean():,.2f}")
print(f"Total volume: {df['Volume'].sum()}")
