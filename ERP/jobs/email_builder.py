"""
generate_email_link.py
======================
Generate mailto: hyperlinks for booking request emails in Active Jobs.

Cách dùng:
  # From Python
  from generate_email_link import build_mailto_link
  link = build_mailto_link(job_data, basic_cost_data)
  
  # Standalone test
  python generate_email_link.py

Hoạt động:
  1. Đọc booking_rules.json cho template rules
  2. Match carrier × POL × container category
  3. Build email subject + body
  4. Return mailto: URL (can be used as hyperlink in Excel)
"""

import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')
from urllib.parse import quote


# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ERP_DIR = os.path.dirname(SCRIPT_DIR)
RULES_FILE = os.path.join(ERP_DIR, "config", "booking_rules.json")


def load_rules():
    """Load booking rules from JSON config."""
    with open(RULES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_container_category(container_type, rules):
    """Determine DRY or REEFER from container type."""
    cat_map = rules.get("container_category", {})
    return cat_map.get(container_type, "DRY")


def get_volume_string(quantity, container_type):
    """Format volume string like '1X20DC', '2X40HQ'."""
    qty = quantity or 1
    # Map container types to booking format
    cont_map = {
        "20GP": "20DC", "40GP": "40DC", "40HQ": "40HQ",
        "45HQ": "45HQ", "40NOR": "40NOR",
        "20RF": "20RF", "40RF": "40RF"
    }
    cont_code = cont_map.get(container_type, container_type)
    return f"{qty}X{cont_code}"


def build_email_body(job_data, cost_data, rules):
    """
    Build email body from job data and rules.
    
    job_data dict keys:
        Customer_Name, POL, POD, Place, Carrier, Container_Type,
        Quantity, Volume, Contract_No, Group_Rate, ETD
    
    cost_data dict keys (optional, from Basic Cost):
        Contract, Group_Rate
    """
    common = rules["common"]
    pol_cfg = rules["pol_config"].get(job_data.get("POL", ""), {})
    container_cat = get_container_category(job_data.get("Container_Type", "40HQ"), rules)
    carrier = job_data.get("Carrier", "")
    
    # Get carrier-specific rules
    carrier_rules = rules["carrier_rules"].get(carrier, rules["carrier_rules"]["_default"])
    cat_rules = carrier_rules.get(container_cat, carrier_rules.get("DRY", {}))
    
    # Build carrier display name
    carrier_display = cat_rules.get("carrier_display", carrier).replace("{carrier}", carrier)
    
    # Contract number with prefix
    contract = cost_data.get("Contract", job_data.get("Contract_No", ""))
    contract_prefix = cat_rules.get("contract_prefix", "")
    contract_display = f"{contract_prefix}{contract}" if contract else ""
    
    # Group rate
    group_rate = cost_data.get("Group_Rate", job_data.get("Group_Rate", ""))
    
    # POL full name
    pol_full = pol_cfg.get("pol_full_name", job_data.get("POL", ""))
    
    # Volume string
    volume = get_volume_string(job_data.get("Quantity"), job_data.get("Container_Type", "40HQ"))
    
    # Default GW
    default_gw = pol_cfg.get("default_gw", "17 TONS")
    
    # Place / FND/DEL
    place = job_data.get("Place", "")
    
    # Build body lines
    lines = []
    lines.append(common["greeting"])
    lines.append("")
    lines.append("Please help me release the booking as below info:")
    lines.append(f"•  Carrier: {carrier_display}")
    lines.append(f"•  Contract number: {contract_display}")
    if group_rate:
        lines.append(f"•  Group rate for USCA only (based on pricing's rate, if any): {group_rate}")
    lines.append(f"•  NAC (if any): Actual NAC")
    lines.append(f"•  POL: {pol_full}")
    lines.append(f"•  POD: {job_data.get('POD', '')}")
    lines.append(f"•  FND/DEL: {place}")
    lines.append(f"•  ETD: ")
    lines.append(f"•  CMD: ")
    lines.append(f"•  HS code: ")
    lines.append(f"•  Volume: {volume}")
    lines.append(f"•  Gross Weight per container (GW): {default_gw}")
    lines.append(f"•  Stuffing place: {common['stuffing_place']}")
    
    # POL-specific fields (HCM has MT pick up / Full return)
    mt_pickup = pol_cfg.get("mt_pickup")
    full_return = pol_cfg.get("full_return")
    if mt_pickup:
        lines.append(f"•  MT pick up: {mt_pickup}")
    if full_return:
        lines.append(f"•  Full return: {full_return}")
    
    lines.append(f"•  Special Remark: {common['special_remark']}")
    
    # Reefer-specific section
    if container_cat == "REEFER":
        lines.append(f"•  REEFER CONTAINER – {common['reefer_settings']}")
    
    lines.append("")
    lines.append(cat_rules.get("closing", "With warmest regards,"))
    
    return "\n".join(lines)


def build_subject(job_data, cost_data, rules):
    """Build email subject line."""
    carrier = job_data.get("Carrier", "")
    customer = job_data.get("Customer_Name", "")
    pol = job_data.get("POL", "")
    pod = job_data.get("POD", "")
    container = job_data.get("Container_Type", "")
    container_cat = get_container_category(container, rules)
    
    if container_cat == "REEFER":
        return f"BKG REQ RF - {customer} - {pol}-{pod} - {container} - {carrier}"
    else:
        return f"BKG REQ - {customer} - {pol}-{pod} - {container} - {carrier}"


def build_mailto_link(job_data, cost_data=None, rules=None):
    """
    Build complete mailto: link for booking request.
    
    Returns: mailto:URL string
    """
    if rules is None:
        rules = load_rules()
    if cost_data is None:
        cost_data = {}
    
    to_email = rules["common"].get("to_email", "")
    subject = build_subject(job_data, cost_data, rules)
    body = build_email_body(job_data, cost_data, rules)
    
    # Build mailto URL
    mailto = f"mailto:{to_email}?subject={quote(subject)}&body={quote(body)}"
    return mailto


def build_cost_breakdown(job_data, basic_cost_row):
    """
    Build cost breakdown string from Basic Cost data.
    
    basic_cost_row: dict with charge group columns from Basic Cost sheet
    Returns: formatted cost breakdown string
    """
    import math
    
    def is_valid(val):
        """Check if value is valid (not None, nan, 0, empty)."""
        if val is None or val == "" or val == 0:
            return False
        try:
            if isinstance(val, float) and math.isnan(val):
                return False
        except (TypeError, ValueError):
            pass
        if str(val).strip().lower() == "nan":
            return False
        return True
    
    if not basic_cost_row:
        return ""
    
    container = job_data.get("Container_Type", "40HQ")
    lines = []
    
    # BKG info
    contract = basic_cost_row.get("Contract", "")
    group_rate = basic_cost_row.get("Group Rate", "")
    contract_str = str(contract) if is_valid(contract) else ""
    group_str = str(group_rate) if is_valid(group_rate) else ""
    if contract_str or group_str:
        lines.append(f"BKG: SC={contract_str} | Group={group_str}")
    
    # Cost breakdown by charge group
    charge_groups = [
        ("O/F", "BASIC O/F"),
        ("ARB", "ARB/OLF"),
        ("ISPS", "ISPS/LSF/CMC"),
        ("PSS/PUC", "PSS/PUC"),
        ("OCS/LSS", "OCS/LSS/EFF/ITC/GFS/ SOC COST HDL FEE"),
        ("PCS/ACS", "PCS/ACS/AGS"),
        ("GRI", "GRI"),
        ("EIC/BAF", "EIC/GFS/BAF/FDI"),
        ("WHA/BCO", "WHA/BCO/BCD/CFC/EIC"),
        ("GARMENT", "GARMENT ADD ON"),
        ("PREMIUM", "PREMIUM ADD ON/HDL FEE US FOR SOC"),
    ]
    
    cost_parts = []
    for short_name, charge_prefix in charge_groups:
        col_name = f"{charge_prefix}_{container}"
        val = basic_cost_row.get(col_name)
        if is_valid(val):
            try:
                cost_parts.append(f"{short_name} ${float(val):,.0f}")
            except (ValueError, TypeError):
                pass
    
    if cost_parts:
        lines.append(f"COST: {' + '.join(cost_parts)}")
    
    # Handling fee
    hdl_col = f"HANDLING FEE FOR CARRIER_{container}"
    hdl_val = basic_cost_row.get(hdl_col)
    if is_valid(hdl_val):
        try:
            lines.append(f"HDL FEE: ${float(hdl_val):,.0f}")
        except (ValueError, TypeError):
            pass
    
    return "\n".join(lines)


# ── Test ──
if __name__ == "__main__":
    rules = load_rules()
    
    print("=" * 60)
    print("  EMAIL TEMPLATE TEST")
    print("=" * 60)
    
    # Test 1: HPH DRY
    print("\n--- Test 1: HPH + ONE SOC + DRY ---")
    job1 = {
        "Customer_Name": "WOODPECKER LUMBER",
        "POL": "HPH",
        "POD": "USTIW",
        "Place": "TACOMA, WA",
        "Carrier": "ONE",
        "Container_Type": "20GP",
        "Quantity": 1,
    }
    cost1 = {
        "Contract": "SHA0005N25",
        "Group_Rate": "990132 – (S1 - TPE9 - Group SOC Big 4)",
    }
    
    subject = build_subject(job1, cost1, rules)
    body = build_email_body(job1, cost1, rules)
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")
    
    # Test 2: HCM REEFER
    print("\n--- Test 2: HCM + ONE + REEFER ---")
    job2 = {
        "Customer_Name": "NAFOODS",
        "POL": "HCM",
        "POD": "USLAX",
        "Place": "LOS ANGELES, CA",
        "Carrier": "ONE",
        "Container_Type": "40RF",
        "Quantity": 2,
    }
    cost2 = {
        "Contract": "SHA0005N25",
        "Group_Rate": "01",
    }
    
    subject = build_subject(job2, cost2, rules)
    body = build_email_body(job2, cost2, rules)
    print(f"Subject: {subject}")
    print(f"Body:\n{body}")
    
    # Test 3: Cost breakdown
    print("\n--- Test 3: Cost Breakdown ---")
    bc_row = {
        "Contract": "25-4402",
        "Group Rate": "FAK EC",
        "BASIC O/F_40HQ": 4821,
        "ARB/OLF_40HQ": 600,
        "ISPS/LSF/CMC_40HQ": 14,
        "PSS/PUC_40HQ": 950,
        "HANDLING FEE FOR CARRIER_40HQ": 50,
    }
    breakdown = build_cost_breakdown({"Container_Type": "40HQ"}, bc_row)
    print(breakdown)
