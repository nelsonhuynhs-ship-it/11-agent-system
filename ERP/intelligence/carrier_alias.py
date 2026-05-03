"""
carrier_alias.py — Carrier name normalization for Price Watch matching.
=======================================================================
Centralizes carrier alias lookup so price_watch.py, forecast_pipeline.py,
and any other modules can resolve raw carrier strings to canonical codes.

Usage:
    from ERP.intelligence.carrier_alias import normalize_carrier, CARRIER_ALIAS
    canonical = normalize_carrier("YANG MING LINE")  # -> "YML"
"""
from __future__ import annotations

CARRIER_ALIAS: dict[str, set[str]] = {
    "ONE":       {"ONE", "OCEAN NETWORK EXPRESS"},
    "YML":       {"YML", "YANG MING", "YM"},
    "WHL":       {"WHL", "WAN HAI"},
    "CMA":       {"CMA", "CMA-CGM", "CMA CGM"},
    "MSC":       {"MSC", "MEDITERRANEAN SHIPPING"},
    "MAERSK":    {"MAERSK", "MSK", "AP MOLLER"},
    "HAPAG":     {"HAPAG", "HAPAG-LLOYD", "HLC"},
    "COSCO":     {"COSCO", "CHINA OCEAN SHIPPING", "COSCO SHIPPING"},
    "EVERGREEN": {"EVERGREEN", "EMC", "EGL", "EVERGREEN LINE"},
    "ZIM":       {"ZIM"},
    "OOCL":      {"OOCL", "ORIENT OVERSEAS"},
}


def normalize_carrier(raw: str) -> str:
    """Return canonical carrier code. Falls back to uppercase raw if no alias match.

    Examples:
        normalize_carrier("Yang Ming")          -> "YML"
        normalize_carrier("CMA-CGM")            -> "CMA"
        normalize_carrier("HAPAG-LLOYD")        -> "HAPAG"
        normalize_carrier("UNKNOWN CARRIER X")  -> "UNKNOWN CARRIER X"
    """
    if not raw:
        return ""
    upper = raw.upper().strip()
    for canonical, aliases in CARRIER_ALIAS.items():
        if any(a in upper for a in aliases):
            return canonical
    return upper
