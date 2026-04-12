"""
arb_engine.py — ARB cross-origin pricing for third-country POLs.
Combines base rates from HCM with ARB surcharges for Thailand/China/Cambodia ports.
"""
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from .pricing_engine import get_active_rates, _normalize_container

DATA_DIR = Path(os.environ.get("NELSON_DATA_DIR", "/opt/nelson/data"))
ARB_CONFIG = DATA_DIR / "pricing" / "arb_rates.yaml"


def _load_arb() -> dict:
    with open(ARB_CONFIG) as f:
        return yaml.safe_load(f) or {}


def list_available_origins() -> list[str]:
    """List all ports with ARB data configured."""
    return list(_load_arb().keys())


def get_arb(
    origin_port: str,
    carrier: str,
    container: str = "40HQ",
    pod_region: str = None,
    rate_type: str = "FAK",
) -> Optional[float]:
    """Get ARB surcharge for a port/carrier/container combination."""
    arb_data = _load_arb()
    port_key = origin_port.lower().replace(" ", "_")
    container_norm = _normalize_container(container)

    port_arb = arb_data.get(port_key)
    if not port_arb:
        return None

    carrier_arb = port_arb.get(carrier.upper())
    if not carrier_arb:
        return None

    rate_arb = carrier_arb.get(rate_type.upper())
    if rate_arb is None:
        return None

    # If rate_arb is a dict with region keys (e.g., CMA FAK has PSW, PNW, etc.)
    if isinstance(rate_arb, dict):
        first_val = next(iter(rate_arb.values()))
        if isinstance(first_val, dict):
            # Nested: rate_arb = {PSW: {20GP: 180, 40HQ: 200}, ...}
            if pod_region and pod_region.upper() in {k.upper(): k for k in rate_arb}:
                region_key = next(k for k in rate_arb if k.upper() == pod_region.upper())
                region_rates = rate_arb[region_key]
                return region_rates.get(container_norm)
            # No region specified — return first available
            region_rates = first_val
            return region_rates.get(container_norm)
        else:
            # Flat: rate_arb = {20GP: 80, 40HQ: 100}
            return rate_arb.get(container_norm)

    return None


def get_cross_origin_rate(
    origin_port: str,
    pod: str,
    carrier: str = None,
    container: str = "40HQ",
    pod_region: str = None,
    rate_type: str = "FAK",
) -> pd.DataFrame:
    """
    Get combined rate: base HCM rate + ARB surcharge for origin port.
    Example: Lat Krabang → LAX = HCM → LAX base + ARB(Lat Krabang)
    """
    base_rates = get_active_rates(
        pol="HCM", pod=pod, carrier=carrier, container=container, rate_type=rate_type
    )

    if base_rates.empty:
        return pd.DataFrame()

    arb_data = _load_arb()
    results = []

    for _, row in base_rates.iterrows():
        arb_amount = get_arb(
            origin_port, row["Carrier"], container, pod_region, rate_type
        )
        if arb_amount is not None:
            combined = row.copy()
            combined["POL"] = origin_port.upper()
            combined["Base_Amount"] = combined["Amount"]
            combined["ARB"] = arb_amount
            combined["Amount"] = round(combined["Amount"] + arb_amount, 2)
            combined["Note"] = f"Base HCM + ARB {origin_port}"
            results.append(combined)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("Amount").head(20)
