# -*- coding: utf-8 -*-
"""
freetime_formatter.py — Sprint Reorg Phase 3
Freetime intent detection + response formatting.
Reads rules from carrier_rules.json (no hardcoding).

Exports:
  _is_freetime_query(text) -> bool
  _is_price_query(text)    -> bool   (depends on freetime check)
  get_freetime_summary(carrier, container, pol) -> str
  format_freetime_answer(text, rules) -> str
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

_THIS_DIR   = os.path.dirname(os.path.abspath(__file__))

# ── Intent keyword sets ───────────────────────────────────────────────────────

_FREETIME_KW = {
    'FREETIME', 'FREE TIME', 'DEM', 'DET', 'DETENTION', 'DEMURRAGE',
    'CAM DIEN', 'CẮM ĐIỆN', 'POWER CHARGE', 'POWER', 'REEFER CHARGE',
    'MIEN PHI', 'MIỄN PHÍ', 'BAO NHIEU NGAY', 'BAO NHIÊU NGÀY',
    'NGAY MIEN', 'NGÀY MIỄN', 'STORAGE', 'FREE DAY',
}

_FREETIME_CARRIERS = {
    'ONE', 'YML', 'CMA', 'MSC', 'MSK', 'MAERSK', 'HPL', 'HMM',
    'ZIM', 'EMC', 'COSCO', 'WHL', 'OOCL',
}

_PRICE_STRONG_KW = {
    'GIÁ', 'QUOTE', 'RATE', 'BAO NHIÊU TIỀN', 'BAO NHIEU TIEN', 'PRICE',
}

_PRICE_KW = [
    'GIÁ', 'QUOTE', 'RATE', 'PRICE', 'BAO NHIÊU', 'GIA BAO', 'CHO GIA',
    'HPH', 'HCM', 'DAD', 'UIH', 'VUT',
    'LAX', 'NYC', 'CHICAGO', 'HOUSTON', 'DALLAS', 'ATLANTA', 'DENVER',
    'SEATTLE', 'PORTLAND', 'BOSTON', 'MIAMI', 'TORONTO', 'VANCOUVER',
    'EL PASO', 'MEMPHIS', 'KANSAS', 'NEWARK', 'NORFOLK', 'SAVANNAH',
    'SOC', 'COC', 'CONT', 'CONTAINER', '20GP', '40GP', '40HQ', '40HC',
    '20HQ', 'FCL', 'LCL',
]


# ── Intent detectors ──────────────────────────────────────────────────────────

def _is_freetime_query(text: str) -> bool:
    """True if message is asking ONLY about freetime/DEM/DET, not price."""
    t = text.upper()
    has_freetime = any(kw in t for kw in _FREETIME_KW)
    if not has_freetime:
        return False
    # If user also mentions price keywords → let price engine handle
    price_strong = any(kw in t for kw in _PRICE_STRONG_KW)
    return not price_strong


def _is_price_query(text: str) -> bool:
    """True if free text is a price/rate query (and NOT freetime-only)."""
    if _is_freetime_query(text):
        return False
    t = text.upper()
    return any(kw in t for kw in _PRICE_KW)


# ── Freetime per-carrier summary ──────────────────────────────────────────────

def get_freetime_summary(carrier: str, container: str, rules: dict, pol: str = "HPH") -> str:
    """
    Return freetime summary string for one carrier.

    Args:
        carrier   : e.g. 'CMA'
        container : e.g. '40HQ'
        rules     : full carrier_rules dict (already loaded by caller)
        pol       : Point of Loading — reserved for future per-POL logic
    """
    try:
        c_key = carrier.upper()
        rule  = rules.get(c_key)

        if not isinstance(rule, dict):
            for k, v in rules.items():
                if isinstance(v, dict) and (k in c_key or c_key in k) and k != "_meta":
                    rule = v
                    break

        if not isinstance(rule, dict):
            return ""

        is_reefer = any(x in container.upper() for x in ["RF", "REEFER"])
        cargo_key = "reefer" if is_reefer else "dry"
        cargo     = rule.get(cargo_key)
        if not isinstance(cargo, dict):
            cargo = rule.get("dry")
        if not isinstance(cargo, dict):
            return ""

        parts        = []
        combined_flag = cargo.get("combined")
        det_days      = cargo.get("det_days")
        dem_days      = cargo.get("dem_days")
        basis         = cargo.get("basis") or cargo.get("det_basis", "")

        if combined_flag is True and det_days:
            scope = basis.replace("_", " ") if basis else ""
            parts.append(f"DEM+DET {det_days}d combined" + (f" ({scope})" if scope else ""))
        else:
            det_basis = cargo.get("det_basis", "")
            dem_basis = cargo.get("dem_basis", "")
            if det_days:
                s = det_basis.replace("_", " ") if det_basis else ""
                parts.append(f"DET {det_days}d" + (f" ({s})" if s else ""))
            if dem_days:
                s = dem_basis.replace("_", " ") if dem_basis else ""
                parts.append(f"DEM {dem_days}d" + (f" ({s})" if s else ""))

        # Power charge (reefer)
        if is_reefer:
            pc = rule.get("power_charge")
            if isinstance(pc, dict):
                free_h = pc.get("free_hours")
                free_d = pc.get("free_days")
                if free_h:
                    parts.append(f"Power charge: {free_h}h free")
                elif free_d:
                    parts.append(f"Power charge: {free_d}d free")

        return " | ".join(parts) if parts else ""

    except Exception as exc:
        logger.warning(f"get_freetime_summary error for {carrier}: {exc}")
        return ""


# ── Full freetime answer formatter ────────────────────────────────────────────

def format_freetime_answer(text: str, rules: dict) -> str:
    """
    Generate a direct freetime answer from carrier_rules dict.
    Detects carrier + cargo type from the query text.

    Args:
        text  : user message
        rules : full carrier_rules dict (already loaded by caller)
    """
    t = text.upper()

    # Detect which carriers user is asking about
    target_carriers = []
    for ck in _FREETIME_CARRIERS:
        if ck in t and ck in rules:
            target_carriers.append(ck)
    if not target_carriers:
        target_carriers = [k for k in rules if k != "_meta"]

    is_reefer  = any(kw in t for kw in ['LANH', 'LẠNH', 'REEFER', 'RF', 'POWER', 'CAM DIEN', 'CẮM ĐIỆN'])
    cargo_label = "Reefer" if is_reefer else "Dry"
    cargo_key   = "reefer" if is_reefer else "dry"

    lines = [f"Freetime at POL (Vietnam) — {cargo_label} Containers", "\u2500" * 42]

    for ck in target_carriers:
        rule = rules.get(ck)
        if not isinstance(rule, dict):
            continue
        name     = rule.get("name", ck)
        cargo    = rule.get(cargo_key)
        if not isinstance(cargo, dict):
            cargo = rule.get("dry", {})

        combined_flag = cargo.get("combined")
        det_days  = cargo.get("det_days")
        dem_days  = cargo.get("dem_days")
        det_basis = cargo.get("det_basis") or cargo.get("basis", "")
        dem_basis = cargo.get("dem_basis", "")

        lines.append("")
        lines.append(f"{ck} — {name}:")
        if combined_flag is True and det_days:
            b = det_basis.replace("_", " ") if det_basis else ""
            lines.append(f"  DEM+DET: {det_days} days combined" + (f" ({b})" if b else ""))
        else:
            if det_days:
                b = det_basis.replace("_", " ") if det_basis else ""
                lines.append(f"  DET: {det_days} days" + (f" ({b})" if b else ""))
            if dem_days:
                b = dem_basis.replace("_", " ") if dem_basis else ""
                lines.append(f"  DEM: {dem_days} days" + (f" ({b})" if b else ""))

        # Power charge
        pc = rule.get("power_charge")
        if isinstance(pc, dict) and (is_reefer or any(kw in t for kw in ['POWER', 'CAM', 'CẮM'])):
            free_h = pc.get("free_hours")
            free_d = pc.get("free_days")
            basis  = pc.get("basis", "")
            if free_h:
                lines.append(f"  Power charge: {free_h}h free" + (f" ({basis})" if basis else ""))
            elif free_d:
                lines.append(f"  Power charge: {free_d} days free" + (f" ({basis})" if basis else ""))

        note = cargo.get("note", "")
        if note:
            lines.append(f"  Note: {note}")

    lines.append("")
    lines.append("\u2500" * 42)
    lines.append("Nguon: FREE TIME AT ORIGIN 2025.xlsx (updated 2026-03-09)")
    return "\n".join(lines)
