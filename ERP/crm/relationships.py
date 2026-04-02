"""
CRM Relationship Analyzer
Analyzes Shipper-Cnee relationships to identify sales opportunities
"""

import pandas as pd
import openpyxl

print("=" * 70)
print("CRM RELATIONSHIP ANALYZER")
print("=" * 70)

# Load CRM data
crm_file = 'CRM_Master.xlsx'

print(f"\nLoading {crm_file}...")

df_customers = pd.read_excel(crm_file, sheet_name='Customers')
df_relationships = pd.read_excel(crm_file, sheet_name='Shipper_Cnee_Relationships')

print(f"  -> Loaded {len(df_customers)} customers")
print(f"  -> Loaded {len(df_relationships)} relationships")

# ============================================================
# ANALYSIS 1: Shipper Analysis
# ============================================================
print("\n" + "=" * 70)
print("SHIPPER ANALYSIS - Who are they selling to?")
print("=" * 70)

shippers = df_customers[df_customers['Customer_Type'] == 'Shipper']

for _, shipper in shippers.iterrows():
    shipper_id = shipper['Customer_ID']
    shipper_name = shipper['Company_Name']
    
    # Find all Cnees this Shipper sells to
    cnee_relationships = df_relationships[df_relationships['Shipper_ID'] == shipper_id]
    
    print(f"\n{shipper_name} ({shipper_id})")
    print(f"  Country: {shipper['Country']}")
    print(f"  Selling to {len(cnee_relationships)} Cnee(s):")
    
    if len(cnee_relationships) > 0:
        for _, rel in cnee_relationships.iterrows():
            print(f"    - {rel['Cnee_Name']} ({rel['Cnee_ID']})")
            print(f"      Commodity: {rel['Commodity']}")
            print(f"      Route: {rel['Typical_Route']}")
            print(f"      Frequency: {rel['Frequency']}")
            print(f"      Last Shipment: {rel['Last_Shipment']}")
    else:
        print("    ** NO CNEE RELATIONSHIPS YET - SALES OPPORTUNITY! **")
    
    # Find potential Cnees (Cnees not yet buying from this Shipper)
    all_cnees = df_customers[df_customers['Customer_Type'] == 'Cnee']
    current_cnee_ids = cnee_relationships['Cnee_ID'].tolist()
    potential_cnees = all_cnees[~all_cnees['Customer_ID'].isin(current_cnee_ids)]
    
    if len(potential_cnees) > 0:
        print(f"\n  POTENTIAL NEW CNEES ({len(potential_cnees)}):")
        for _, cnee in potential_cnees.iterrows():
            print(f"    - {cnee['Company_Name']} ({cnee['Customer_ID']}) - {cnee['Country']}")

# ============================================================
# ANALYSIS 2: Cnee Analysis
# ============================================================
print("\n" + "=" * 70)
print("CNEE ANALYSIS - Who are they buying from?")
print("=" * 70)

cnees = df_customers[df_customers['Customer_Type'] == 'Cnee']

for _, cnee in cnees.iterrows():
    cnee_id = cnee['Customer_ID']
    cnee_name = cnee['Company_Name']
    
    # Find all Shippers this Cnee buys from
    shipper_relationships = df_relationships[df_relationships['Cnee_ID'] == cnee_id]
    
    print(f"\n{cnee_name} ({cnee_id})")
    print(f"  Country: {cnee['Country']}")
    print(f"  Buying from {len(shipper_relationships)} Shipper(s):")
    
    if len(shipper_relationships) > 0:
        for _, rel in shipper_relationships.iterrows():
            print(f"    - {rel['Shipper_Name']} ({rel['Shipper_ID']})")
            print(f"      Commodity: {rel['Commodity']}")
            print(f"      Route: {rel['Typical_Route']}")
            print(f"      Frequency: {rel['Frequency']}")
            print(f"      Last Shipment: {rel['Last_Shipment']}")
    else:
        print("    ** NO SHIPPER RELATIONSHIPS YET - SALES OPPORTUNITY! **")
    
    # Find potential Shippers (Shippers not yet selling to this Cnee)
    all_shippers = df_customers[df_customers['Customer_Type'] == 'Shipper']
    current_shipper_ids = shipper_relationships['Shipper_ID'].tolist()
    potential_shippers = all_shippers[~all_shippers['Customer_ID'].isin(current_shipper_ids)]
    
    if len(potential_shippers) > 0:
        print(f"\n  POTENTIAL NEW SHIPPERS ({len(potential_shippers)}):")
        for _, shipper in potential_shippers.iterrows():
            print(f"    - {shipper['Company_Name']} ({shipper['Customer_ID']}) - {shipper['Country']}")

# ============================================================
# ANALYSIS 3: Summary Statistics
# ============================================================
print("\n" + "=" * 70)
print("SUMMARY STATISTICS")
print("=" * 70)

total_customers = len(df_customers)
total_coloaders = len(df_customers[df_customers['Customer_Type'] == 'Coloader'])
total_shippers = len(df_customers[df_customers['Customer_Type'] == 'Shipper'])
total_cnees = len(df_customers[df_customers['Customer_Type'] == 'Cnee'])

print(f"\nTotal Customers: {total_customers}")
print(f"  - Coloaders: {total_coloaders}")
print(f"  - Shippers: {total_shippers}")
print(f"  - Cnees: {total_cnees}")

print(f"\nTotal Relationships: {len(df_relationships)}")

# Average relationships per Shipper
avg_cnees_per_shipper = len(df_relationships) / total_shippers if total_shippers > 0 else 0
print(f"  - Avg Cnees per Shipper: {avg_cnees_per_shipper:.1f}")

# Average relationships per Cnee
avg_shippers_per_cnee = len(df_relationships) / total_cnees if total_cnees > 0 else 0
print(f"  - Avg Shippers per Cnee: {avg_shippers_per_cnee:.1f}")

# Commodity breakdown
print(f"\nCommodity Breakdown:")
commodity_counts = df_relationships['Commodity'].value_counts()
for commodity, count in commodity_counts.items():
    print(f"  - {commodity}: {count} relationships")

# Route breakdown
print(f"\nTop Routes:")
route_counts = df_relationships['Typical_Route'].value_counts().head(5)
for route, count in route_counts.items():
    print(f"  - {route}: {count} relationships")

print("\n" + "=" * 70)
print("ANALYSIS COMPLETE!")
print("=" * 70)
print("\nACTION ITEMS:")
print("1. Contact Shippers with no Cnee relationships")
print("2. Contact Cnees with no Shipper relationships")
print("3. Cross-sell: Introduce Shippers to new Cnees")
print("4. Cross-sell: Introduce Cnees to new Shippers")
print("5. Focus on high-volume commodities and routes")
