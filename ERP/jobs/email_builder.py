"""
email_builder.py
================
Build mailto: hyperlinks for booking request emails in Active Jobs.

Reads config from `ERP/carrier_rules/booking_rules.json` (v2.0 schema).
Produces a subject + body + full mailto URL that can be written as a
hyperlink into Active Jobs col 28 (Request_BKG).

Public API:
    load_rules()                         → dict
    build_subject(job_data, rules)       → str
    build_email_body(job_data, rules)    → str
    build_mailto_link(job_data, rules=None) → str  (full mailto: URL)

Where `job_data` is a dict with these keys (strings/ints):
    Customer_Name, POL, POD, Place, Carrier, Container_Type,
    Quantity, Contract_No, Group_Rate, is_SOC  (optional)

Usage standalone:
    python ERP/jobs/email_builder.py
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import quote

sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ERP_DIR = os.path.dirname(SCRIPT_DIR)
RULES_FILE = os.path.join(ERP_DIR, "carrier_rules", "booking_rules.json")
DEFAULT_TO_EMAIL = "cus_team@pudongprime.vn"  # default; override in job_data["to_email"]


# ── Rules ──
def load_rules(path: str | None = None) -> dict:
    """Load booking_rules.json (v2.0)."""
    p = path or RULES_FILE
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Helpers ──
def _container_category(container_type: str, rules: dict) -> str:
    return rules.get("container_category", {}).get(container_type, "DRY")


def _container_display(container_type: str, rules: dict) -> str:
    return rules.get("container_display", {}).get(container_type, container_type)


def _volume_string(qty: int | None, container_type: str, rules: dict) -> str:
    q = qty or 1
    code = _container_display(container_type, rules)
    return f"{q}X{code}"


def _carrier_display(carrier: str, is_soc: bool) -> str:
    base = (carrier or "").strip()
    if is_soc:
        return f"{base} SOC"
    return base


# ── Builders ──
def build_subject(job_data: dict, rules: dict) -> str:
    sender = rules.get("sender", {}).get("name", "NELSON")
    carrier = str(job_data.get("Carrier", ""))
    is_soc = bool(job_data.get("is_SOC"))
    container = str(job_data.get("Container_Type", "40HQ"))
    qty = int(job_data.get("Quantity") or 1)
    customer = str(job_data.get("Customer_Name") or "")
    pol = str(job_data.get("POL", ""))
    pod = str(job_data.get("POD", ""))
    place = str(job_data.get("Place") or pod)

    # If place == pod, don't duplicate "place VIA pod" — use "pol-pod" instead
    if place.upper() == pod.upper() or not place:
        route_part = f"{pol}-{pod}".strip("- ")
    else:
        route_part = f"{pol}-{place} VIA {pod}".strip("- ")

    cont_code = _container_display(container, rules)
    vol = f"{qty}X{cont_code}"
    carrier_disp = _carrier_display(carrier, is_soc)

    parts = [f"{customer} BOOKING", route_part, vol, carrier_disp, sender]
    return " | ".join(p for p in parts if p)


def build_email_body(job_data: dict, rules: dict) -> str:
    pol = str(job_data.get("POL", ""))
    container = str(job_data.get("Container_Type", "40HQ"))
    carrier = str(job_data.get("Carrier", ""))
    category = _container_category(container, rules)
    is_soc = bool(job_data.get("is_SOC"))
    pol_cfg = rules.get("pol_config", {}).get(pol, {})

    greeting = rules.get("greeting", {}).get("text", "Dear Team,")
    closing = rules.get("closing", {}).get("text", "With warmest regards,")
    stuffing = rules.get("stuffing_place", "WAREHOUSE")
    special = rules.get("special_remark", {}).get("text", "")

    contract = str(job_data.get("Contract_No") or "").strip()
    contract_disp_tmpl = rules.get("contract_display", {}).get(
        category, rules.get("contract_display", {}).get("DRY", "{contract}")
    )
    contract_disp = contract_disp_tmpl.format(contract=contract) if contract else ""

    group_rate = str(job_data.get("Group_Rate") or "").strip()
    gr_cfg = rules.get("group_rate", {})
    gr_line_value = group_rate if group_rate else gr_cfg.get("if_empty", "N/A")

    nac_cfg = rules.get("nac", {})
    nac_value = str(job_data.get("NAC") or "").strip() or nac_cfg.get("default_text", "Actual NAC")

    pol_full = pol_cfg.get("pol_full_name", pol)
    default_gw = pol_cfg.get("default_gw", "17 TONS")
    place = str(job_data.get("Place") or "")
    volume = _volume_string(int(job_data.get("Quantity") or 1), container, rules)

    lines: list[str] = []
    lines.append(greeting)
    lines.append("")
    lines.append("Please help me release the booking as below info:")
    lines.append(f"•  Carrier: {_carrier_display(carrier, is_soc)}")
    if contract_disp:
        lines.append(f"•  Contract number: {contract_disp}")
    if gr_cfg.get("always_show", True):
        lines.append(f"•  {gr_cfg.get('label', 'Group rate')}: {gr_line_value}")
    if nac_cfg.get("always_show", True):
        lines.append(f"•  NAC (if any): {nac_value}")
    lines.append(f"•  POL: {pol_full}")
    lines.append(f"•  POD: {job_data.get('POD', '')}")
    lines.append(f"•  FND/DEL: {place}")
    lines.append(f"•  ETD: ")
    lines.append(f"•  CMD: ")
    lines.append(f"•  HS code: ")
    lines.append(f"•  Volume: {volume}")
    lines.append(f"•  Gross Weight per container (GW): {default_gw}")
    lines.append(f"•  Stuffing place: {stuffing}")

    if pol_cfg.get("show_mt_pickup"):
        mt = pol_cfg.get("mt_pickup", "")
        full_return = pol_cfg.get("full_return", "")
        if mt:
            lines.append(f"•  MT pick up: {mt}")
        if full_return:
            lines.append(f"•  Full return: {full_return}")

    # carrier-specific extras (e.g., CMA payment_term)
    carrier_extras = rules.get("carrier_specific_rules", {}).get(
        carrier, rules.get("carrier_specific_rules", {}).get("_default", {})
    )
    for k, v in carrier_extras.items():
        if k.startswith("_"):
            continue
        lines.append(f"•  {k.replace('_', ' ').title()}: {v}")

    if special:
        lines.append(f"•  Special Remark: {special}")

    if category == "REEFER":
        reefer = rules.get("reefer_section", {})
        temp = reefer.get("temperature", "-18°C")
        vent = reefer.get("ventilation", "CLOSED")
        humid = reefer.get("humidity", "NO")
        lines.append(f"•  REEFER CONTAINER – Temperature: {temp} | Ventilation: {vent} | Humidity: {humid}")

    lines.append("")
    lines.append(closing)
    return "\n".join(lines)


def build_mailto_link(job_data: dict, cost_data: dict | None = None,
                      rules: dict | None = None, to_email: str | None = None) -> str:
    """
    Build full mailto: URL for Excel hyperlink.

    cost_data (optional): {"Contract": ..., "Group_Rate": ...} — merged into job_data
        if the job_data doesn't provide Contract_No / Group_Rate.
    """
    if rules is None:
        rules = load_rules()
    if cost_data:
        job_data = {**job_data}  # shallow copy
        if not job_data.get("Contract_No") and cost_data.get("Contract"):
            job_data["Contract_No"] = cost_data["Contract"]
        if not job_data.get("Group_Rate") and cost_data.get("Group_Rate"):
            job_data["Group_Rate"] = cost_data["Group_Rate"]

    subject = build_subject(job_data, rules)
    body = build_email_body(job_data, rules)
    email = to_email or job_data.get("to_email") or DEFAULT_TO_EMAIL
    return f"mailto:{email}?subject={quote(subject)}&body={quote(body)}"


# ── Test ──
if __name__ == "__main__":
    rules = load_rules()

    print("=" * 64)
    print("  EMAIL BUILDER (v2.0 schema)")
    print("=" * 64)

    # Test 1: HPH DRY
    print("\n--- Test 1: HPH + ONE + 40HQ DRY ---")
    job1 = {
        "Customer_Name": "NAFOODS",
        "POL": "HPH", "POD": "USLGB", "Place": "LOS ANGELES, CA",
        "Carrier": "ONE", "Container_Type": "40HQ", "Quantity": 2,
        "Contract_No": "SHA0005N25",
        "Group_Rate": "990132 – (S1 - TPE9 - Group SOC Big 4)",
    }
    print("Subject:", build_subject(job1, rules))
    print("Body:")
    print(build_email_body(job1, rules))
    print("\nmailto URL (first 200 chars):")
    print(build_mailto_link(job1, rules=rules)[:200], "...")

    # Test 2: HCM REEFER
    print("\n--- Test 2: HCM + ONE + 40RF REEFER ---")
    job2 = {
        "Customer_Name": "NAFOODS", "POL": "HCM", "POD": "USLAX",
        "Place": "LOS ANGELES, CA", "Carrier": "ONE", "Container_Type": "40RF",
        "Quantity": 2, "Contract_No": "SHA0005N25",
    }
    print("Subject:", build_subject(job2, rules))
    print("Body:")
    print(build_email_body(job2, rules))

    # Test 3: CMA (extra payment_term from carrier_specific_rules)
    print("\n--- Test 3: HCM + CMA + 40GP (with payment_term extra) ---")
    job3 = {
        "Customer_Name": "TRAN ANH", "POL": "HCM", "POD": "USNYC",
        "Place": "NEW YORK, NY", "Carrier": "CMA", "Container_Type": "40GP",
        "Quantity": 1, "Contract_No": "CMA-SCFI-2026",
    }
    print("Subject:", build_subject(job3, rules))
    print("Body:")
    print(build_email_body(job3, rules))
