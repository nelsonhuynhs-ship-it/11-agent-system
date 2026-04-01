# -*- coding: utf-8 -*-
"""
hdl_rules.py — HDL (Handling Fee) Rules per Carrier
=====================================================
Encodes HDL fee deduction rules for rate normalization.
Source: System rules + CARRIER_CONVENTIONS.md

HDL = Handling fee charged by forwarder, embedded in quoted rates.
normalize_rate() strips HDL from the raw rate to get the pure ocean freight.
"""

from __future__ import annotations

from typing import Optional

from .schema import NormalizedRate

__all__ = ["HDL_RULES", "normalize_rate"]


# ──────────────────────────────────────────────────────────────────────────────
# HDL RULES PER CARRIER
# ──────────────────────────────────────────────────────────────────────────────
# Structure: carrier -> { rate_type -> hdl_fee_or_dict, CAR_COM -> value }
#
# Special keys:
#   "DEFAULT"    : fallback HDL fee if rate_type not matched
#   "CAR_COM"    : carrier commission (per container)
#   Container-specific rules use nested dict: {"20": X, "40": Y}

HDL_RULES: dict[str, dict] = {
    "HPL": {
        "FAK": 20,
        "SCFI": 10,
        "FIX": {"20GP": 20, "40GP": 30, "40HQ": 30, "45HQ": 30},
        "CAR_COM": 35,
    },
    "ONE": {
        "FAK": 20,
        "DEFAULT": 20,
        "CAR_COM": 35,
    },
    "YML": {
        "FAK": 20,
        "FIX": 300,
        "CAR_COM": 35,
    },
    "MSC": {
        "FAK": 25,
        "DEFAULT": 25,
        "CAR_COM": 35,
    },
    "MSK": {
        "FAK": 25,
        "DEFAULT": 25,
        "CAR_COM": 35,
    },
    "CMA": {
        "FAK": 15,
        "FIX_TP_PD": 0,    # FIX TP-PD has no HDL
        "FIX": 15,
        "CAR_COM": 35,
    },
    "COSCO": {
        "DRY": 25,
        "REEFER": 100,
        "DEFAULT": 25,
        "CAR_COM": 10,
    },
    "ZIM": {
        "FAK": 30,
        "DEFAULT": 30,
        "CAR_COM": 10,
    },
    "WHL": {
        "HCM": 25,
        "HPH": {"CAR_COM": 35, "HDL": 25},
        "UIH": {"CAR_COM": 35, "HDL": 25},
        "DAD": {"CAR_COM": 35, "HDL": 25},
        "DEFAULT": 25,
        "CAR_COM_HCM": 10,
        "CAR_COM": 35,
    },
    "HMM": {
        "FAK": 40,
        "FIX": 100,
        "DEFAULT": 40,
        "CAR_COM": 35,
    },
    "EMC": {
        "FAK": 25,
        "DEFAULT": 25,
        "CAR_COM": 35,
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# NORMALIZATION FUNCTION
# ──────────────────────────────────────────────────────────────────────────────

def _get_hdl_fee(
    carrier: str,
    rate_type: str,
    container_type: str,
    pol: str,
) -> float:
    """Resolve HDL fee for a specific carrier/rate_type/container/pol combo."""
    carrier_upper = carrier.upper().strip()
    rate_upper = rate_type.upper().strip() if rate_type else "FAK"
    ct_upper = container_type.upper().strip() if container_type else "40HQ"
    pol_upper = pol.upper().strip() if pol else ""

    rules = HDL_RULES.get(carrier_upper)
    if rules is None:
        return 0.0

    # Special: WHL has POL-specific rules
    if carrier_upper == "WHL":
        if pol_upper in ("HCM", "SGN"):
            return float(rules.get("HCM", rules.get("DEFAULT", 0)))
        elif pol_upper in ("HPH", "UIH", "DAD"):
            port_rules = rules.get(pol_upper, {})
            if isinstance(port_rules, dict):
                return float(port_rules.get("HDL", rules.get("DEFAULT", 0)))

    # Special: COSCO has commodity-based rules (REEFER vs DRY)
    if carrier_upper == "COSCO":
        if "RF" in ct_upper or "REEFER" in ct_upper:
            return float(rules.get("REEFER", rules.get("DEFAULT", 0)))
        return float(rules.get("DRY", rules.get("DEFAULT", 0)))

    # Special: CMA FIX TP-PD (no HDL)
    if carrier_upper == "CMA" and "TP" in rate_upper and "PD" in rate_upper:
        return float(rules.get("FIX_TP_PD", 0))

    # Standard lookup: rate_type first, then DEFAULT
    fee = rules.get(rate_upper)
    if fee is None:
        fee = rules.get("DEFAULT", 0)

    # Container-specific rules (e.g., HPL FIX: {"20GP": 20, "40GP": 30})
    if isinstance(fee, dict):
        return float(fee.get(ct_upper, fee.get("40HQ", fee.get("40GP", 0))))

    return float(fee)


def _get_carrier_commission(carrier: str, pol: str = "") -> float:
    """Resolve carrier commission for a carrier/POL."""
    carrier_upper = carrier.upper().strip()
    pol_upper = pol.upper().strip() if pol else ""

    rules = HDL_RULES.get(carrier_upper)
    if rules is None:
        return 0.0

    # WHL: HCM has different CAR_COM
    if carrier_upper == "WHL" and pol_upper in ("HCM", "SGN"):
        return float(rules.get("CAR_COM_HCM", rules.get("CAR_COM", 0)))

    return float(rules.get("CAR_COM", 0))


def normalize_rate(
    carrier: str,
    rate_type: str,
    amount: float,
    container_type: str = "40HQ",
    pol: str = "HCM",
) -> NormalizedRate:
    """
    Normalize a freight rate by stripping HDL fee.

    Args:
        carrier: Carrier code (e.g., "HPL", "ONE")
        rate_type: Rate basis (e.g., "FAK", "FIX", "SCFI")
        amount: Raw quoted amount (USD)
        container_type: Container type (e.g., "20GP", "40HQ")
        pol: Port of Loading (e.g., "HCM", "HPH")

    Returns:
        NormalizedRate with hdl_fee stripped from raw_amount.
    """
    hdl_fee = _get_hdl_fee(carrier, rate_type, container_type, pol)
    car_com = _get_carrier_commission(carrier, pol)

    normalized = amount - hdl_fee
    if normalized < 0:
        normalized = amount  # Safety: never go negative

    # Determine rate_basis
    rate_upper = (rate_type or "FAK").upper().strip()
    if rate_upper in ("FAK", "FIX", "SCFI"):
        rate_basis = rate_upper
    elif "FIX" in rate_upper:
        rate_basis = "FIX"
    elif "SCFI" in rate_upper:
        rate_basis = "SCFI"
    else:
        rate_basis = "FAK"

    return NormalizedRate(
        raw_amount=amount,
        normalized_amount=normalized,
        hdl_fee=hdl_fee,
        carrier_commission=car_com,
        rate_basis=rate_basis,
        surcharge_included=hdl_fee > 0,
        carrier=carrier.upper().strip(),
        container_type=container_type.upper().strip(),
        pol=pol.upper().strip(),
    )
