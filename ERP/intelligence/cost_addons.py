"""
cost_addons.py — Commission / Insurance / Trucking calculator
=============================================================
Feature 10 (Active Jobs v4): Compute KB (kick-back) splits, marine insurance
premium, and trucking fees for Nelson Freight shipments.

Public API
----------
  load_rules()                    -> dict
  commission_for(customer, gp, rules)  -> {client, carrier, tax, net_company}
  insurance_premium(cargo_value, cont_type, class_code, rules)  -> float
  trucking_fee(destination, cont_type, rules)  -> float
  compute_net_profit(job_row, rules)  -> dict

CLI
---
  python ERP/intelligence/cost_addons.py --demo
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_RULES_PATH = _HERE.parent / "data" / "commissions_rules.yaml"

_YAML_TEMPLATE = """\
default_commission_rate: 0.50

customer_commission:
  VIFON EXPORT: 0.40
  NAFOODS: 0.45
  SIRI: 0.50
  PANDA DAD: 0.50

insurance_rates:
  A:
    default: 0.0015
    REEFER: 0.0020
  B:
    default: 0.0010
  C:
    default: 0.0005

trucking:
  zones:
    CHICAGO, IL: 1800
    DENVER, CO: 1400
    SALT LAKE CITY, UT: 1600
    ATLANTA, GA: 2200
    HOUSTON, TX: 2000
    DALLAS, TX: 1900
    LOS ANGELES, CA: 0
    LONG BEACH, CA: 0
    NEW YORK, NY: 0
    SAVANNAH, GA: 0
  factor_20GP: 0.6
  factor_40HC: 1.0
  tthq_fee: 150

withholding_tax_rate: 0.03
"""


# ---------------------------------------------------------------------------
# Rule loader
# ---------------------------------------------------------------------------

def load_rules(path: str | Path | None = None) -> dict:
    """Load commissions_rules.yaml. Creates the file if missing."""
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("pyyaml is required: pip install pyyaml") from exc

    p = Path(path) if path else _RULES_PATH
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_YAML_TEMPLATE, encoding="utf-8")

    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Commission calculator
# ---------------------------------------------------------------------------

def commission_for(
    customer: str,
    gross_profit: float,
    rules: dict,
) -> dict[str, float]:
    """
    Compute KICK BACK split for one shipment.

    Nelson's formula
    ----------------
    kb_pool   = gross_profit * customer_rate   (default 50%)
    net_co    = gross_profit - kb_pool         (company keeps remainder)
    kb_client = kb_pool                        (full pool goes to client)
    kb_carrier = 0                             (carrier portion — manual/0 default)
    kb_tax    = net_co * withholding_tax_rate  (3% of company share)

    Returns
    -------
    {client, carrier, tax, net_company}  — all in USD
    """
    if gross_profit <= 0:
        return {"client": 0.0, "carrier": 0.0, "tax": 0.0, "net_company": 0.0}

    cust_map: dict = rules.get("customer_commission", {})
    rate = float(cust_map.get(customer.strip().upper() if customer else "", 0)
                 or rules.get("default_commission_rate", 0.50))

    wh_rate = float(rules.get("withholding_tax_rate", 0.03))

    kb_pool = gross_profit * rate
    net_co = gross_profit - kb_pool
    kb_client = kb_pool
    kb_carrier = 0.0
    kb_tax = net_co * wh_rate

    return {
        "client": round(kb_client, 2),
        "carrier": round(kb_carrier, 2),
        "tax": round(kb_tax, 2),
        "net_company": round(net_co - kb_tax, 2),
    }


# ---------------------------------------------------------------------------
# Insurance premium
# ---------------------------------------------------------------------------

_REEFER_TYPES = {"40RF", "20RF"}


def insurance_premium(
    cargo_value: float,
    cont_type: str,
    class_code: str,
    rules: dict,
) -> float:
    """
    Marine insurance premium = cargo_value × rate.

    class_code: 'A' | 'B' | 'C'
    cont_type:  e.g. '40RF', '40HC', '20GP'
    """
    if cargo_value <= 0:
        return 0.0

    cls_rules: dict = (rules.get("insurance_rates") or {}).get(
        class_code.upper(), {}
    )
    if not cls_rules:
        raise ValueError(f"Unknown insurance class: {class_code!r}. Use A/B/C.")

    cont_upper = (cont_type or "").strip().upper()
    if cont_upper in _REEFER_TYPES and "REEFER" in cls_rules:
        rate = float(cls_rules["REEFER"])
    else:
        rate = float(cls_rules.get("default", 0.0))

    return round(cargo_value * rate, 2)


# ---------------------------------------------------------------------------
# Trucking fee
# ---------------------------------------------------------------------------

_20GP_TYPES = {"20GP", "20DC", "20RF"}


def trucking_fee(
    destination: str,
    cont_type: str,
    rules: dict,
    *,
    cy_door: bool = True,
) -> float:
    """
    Return trucking cost (base + TTHQ) for CY-DOOR; 0 for CY-CY.

    destination: city string, e.g. 'CHICAGO, IL' or 'CHICAGO IL'
    cont_type:   '40HC', '20GP', etc.
    cy_door:     False forces CY-CY (no trucking regardless of destination)
    """
    if not cy_door:
        return 0.0

    truck_cfg: dict = rules.get("trucking", {})
    zones: dict = truck_cfg.get("zones", {})
    tthq: float = float(truck_cfg.get("tthq_fee", 150))

    dest_key = _normalize_dest(destination)
    base = _lookup_zone(dest_key, zones)

    if base == 0:
        # Port-direct or unknown — no trucking, no TTHQ
        return 0.0

    cont_upper = (cont_type or "").strip().upper()
    factor = float(
        truck_cfg.get("factor_20GP", 0.6)
        if cont_upper in _20GP_TYPES
        else truck_cfg.get("factor_40HC", 1.0)
    )
    return round(base * factor + tthq, 2)


def _normalize_dest(destination: str) -> str:
    """Normalise 'CHICAGO IL' or 'Chicago, IL' → 'CHICAGO, IL'."""
    if not destination:
        return ""
    d = destination.strip().upper()
    # Already has comma
    if "," in d:
        return d
    # Try splitting last word as state code
    parts = d.rsplit(None, 1)
    if len(parts) == 2 and len(parts[1]) == 2:
        return f"{parts[0]}, {parts[1]}"
    return d


def _lookup_zone(dest_key: str, zones: dict) -> float:
    """Exact then prefix match against zone keys."""
    if dest_key in zones:
        return float(zones[dest_key])
    for k, v in zones.items():
        if dest_key.startswith(k) or k.startswith(dest_key):
            return float(v)
    return 0.0


# ---------------------------------------------------------------------------
# Net profit integrator
# ---------------------------------------------------------------------------

def compute_net_profit(job_row: dict[str, Any], rules: dict) -> dict[str, float]:
    """
    Integrate commission + trucking + insurance into a single net-profit dict.

    Expected job_row keys (mirrors Active Jobs AJ_COL schema):
      CRM_ID, Quantity, Container_Type, Selling_Rate, Buying_Rate,
      Profit (pre-computed or 0), Status, SERVICE, Door_Address,
      cargo_value (optional, for insurance), insurance_class (optional)

    Returns
    -------
    {gross_profit, kb_client, kb_carrier, kb_tax, trucking, insurance,
     net_profit}
    """
    qty = int(job_row.get("Quantity") or 1)
    sell = float(job_row.get("Selling_Rate") or 0)
    buy = float(job_row.get("Buying_Rate") or 0)

    # Use stored Profit if present and non-zero, otherwise compute
    stored_profit = job_row.get("Profit")
    gross = float(stored_profit) if stored_profit else (sell - buy) * qty

    customer = str(job_row.get("CRM_ID") or "")
    cont_type = str(job_row.get("Container_Type") or "40HC")
    service = str(job_row.get("SERVICE") or "CY-CY").upper()
    door_addr = str(job_row.get("Door_Address") or "")
    status = str(job_row.get("Status") or "")

    # Commission — only for PAID shipments
    kb: dict[str, float]
    if status.upper() == "PAID":
        kb = commission_for(customer, gross, rules)
    else:
        kb = {"client": 0.0, "carrier": 0.0, "tax": 0.0, "net_company": 0.0}

    # Trucking — CY-DOOR only
    is_door = "DOOR" in service
    truck = trucking_fee(door_addr, cont_type, rules, cy_door=is_door)

    # Insurance — optional, requires cargo_value key
    cargo_val = float(job_row.get("cargo_value") or 0)
    ins_class = str(job_row.get("insurance_class") or "")
    ins = 0.0
    if cargo_val > 0 and ins_class:
        ins = insurance_premium(cargo_val, cont_type, ins_class, rules)

    # Net profit: gross − KB client payout − trucking cost − insurance premium
    net = gross - kb["client"] - truck - ins

    return {
        "gross_profit": round(gross, 2),
        "kb_client": kb["client"],
        "kb_carrier": kb["carrier"],
        "kb_tax": kb["tax"],
        "trucking": round(truck, 2),
        "insurance": round(ins, 2),
        "net_profit": round(net, 2),
    }


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------


def _run_demo() -> None:
    # load_rules() creates the YAML if missing, so this always succeeds
    rules = load_rules()

    print("=" * 60)
    print("cost_addons.py  -- DEMO scenarios")
    print("=" * 60)

    # Scenario 1: SIRI, 2x40HQ, paid, no insurance, CY-CY
    print("\n[S1] SIRI — 2x40HQ, gross $1,200, PAID, CY-CY")
    kb = commission_for("SIRI", 1200.0, rules)
    print(f"  KB client : ${kb['client']:>8.2f}")
    print(f"  KB carrier: ${kb['carrier']:>8.2f}")
    print(f"  KB tax    : ${kb['tax']:>8.2f}")
    print(f"  Net co.   : ${kb['net_company']:>8.2f}")

    # Scenario 2: NAFOODS 1x40RF, reefer insurance class A
    print("\n[S2] NAFOODS — 1x40RF, ICC-A, cargo $50,000")
    ins = insurance_premium(50_000, "40RF", "A", rules)
    print(f"  Premium   : ${ins:>8.2f}  (rate 0.20%)")

    # Scenario 3: CY-DOOR to Chicago, 40HC
    print("\n[S3] CY-DOOR — Chicago IL, 40HC")
    fee = trucking_fee("CHICAGO, IL", "40HC", rules, cy_door=True)
    print(f"  Trucking  : ${fee:>8.2f}  (base $1,800 + TTHQ $150)")

    # Full net profit for S3 with commission
    job = {
        "CRM_ID": "SIRI",
        "Quantity": 1,
        "Container_Type": "40HC",
        "Selling_Rate": 2000,
        "Buying_Rate": 800,
        "Profit": 1200.0,
        "Status": "PAID",
        "SERVICE": "CY-DOOR",
        "Door_Address": "CHICAGO, IL",
        "cargo_value": 0,
        "insurance_class": "",
    }
    print("\n[S3-full] compute_net_profit for SIRI CY-DOOR Chicago")
    result = compute_net_profit(job, rules)
    for k, v in result.items():
        print(f"  {k:<15}: ${v:>8.2f}")
    print("=" * 60)


def main() -> int:
    ap = argparse.ArgumentParser(description="Commission/Insurance/Trucking calculator")
    ap.add_argument("--demo", action="store_true", help="Print sample calculations")
    ap.add_argument("--rules", default=None, help="Path to commissions_rules.yaml")
    args = ap.parse_args()

    if args.demo:
        _run_demo()
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
