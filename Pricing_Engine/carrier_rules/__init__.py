# -*- coding: utf-8 -*-
"""
Pricing_Engine/carrier_rules/__init__.py
=========================================
Loader for per-carrier rule JSON files.

Canonical location: D:/OneDrive/NelsonData/pricing/carrier_rules/
Fallback: Pricing_Engine/carrier_rules/ (repo local copies)

API:
    load_carrier(code: str) -> dict
        Load {CARRIER}.json merged with _common.json.
        Returns merged dict: common rules + carrier-specific overrides.

    load_all() -> dict[str, dict]
        Load all known carriers. Returns {code: merged_dict}.

    get_puc_carriers() -> set[str]
        Return set of carrier codes where puc_handling.strip_from_soc_tof == True.

    get_commodity_shortcuts(code: str) -> dict
        Return commodity_shortcuts for carrier + universal commodity_shortcuts_universal.

    get_note_shortcuts(code: str) -> dict
        Return note_shortcuts for carrier.

Module-level cache: files loaded once per process. Call clear_cache() to reset.
"""
from __future__ import annotations

import os
import json
import copy
import sys
from typing import Optional

# ── Path resolution ────────────────────────────────────────────────────────
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT  = os.path.dirname(os.path.dirname(_MODULE_DIR))  # Engine_test/

def _resolve_carrier_rules_dir() -> str:
    """Resolve canonical carrier_rules dir: OneDrive first, repo local second."""
    try:
        sys.path.insert(0, _REPO_ROOT)
        from shared import paths as sp
        onedrive = os.path.join(str(sp.PRICING_DATA), "carrier_rules")
        if os.path.isdir(onedrive):
            return onedrive
    except Exception:
        pass
    # Fallback 1: explicit OneDrive path
    fallback_od = "D:/OneDrive/NelsonData/pricing/carrier_rules"
    if os.path.isdir(fallback_od):
        return fallback_od
    # Fallback 2: repo-local (for CI / offline use)
    return _MODULE_DIR


CARRIER_RULES_DIR: str = _resolve_carrier_rules_dir()

KNOWN_CARRIERS = frozenset([
    "ONE", "ZIM", "CMA", "HPL", "YML",
    "MSC", "COSCO", "EMC", "WHL", "MSK", "EMF"
])

# Module-level cache
_cache: dict[str, dict] = {}
_common_cache: Optional[dict] = None


def clear_cache() -> None:
    """Clear the module-level cache. Call after updating JSON files."""
    global _cache, _common_cache
    _cache.clear()
    _common_cache = None


def _load_json_file(path: str) -> dict:
    """Load a JSON file. Returns {} on error with a warning."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [carrier_rules] WARN: failed to load {path}: {e}")
        return {}


def _load_common() -> dict:
    """Load _common.json (cached)."""
    global _common_cache
    if _common_cache is None:
        path = os.path.join(CARRIER_RULES_DIR, "_common.json")
        _common_cache = _load_json_file(path)
    return _common_cache


def _merge(common: dict, carrier_specific: dict) -> dict:
    """Deep merge: carrier-specific values override common values."""
    result = copy.deepcopy(common)
    for key, val in carrier_specific.items():
        if isinstance(val, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def load_carrier(code: str) -> dict:
    """Load carrier JSON merged with _common.json.

    Args:
        code: Carrier code (e.g. 'ONE', 'CMA'). Case-insensitive.

    Returns:
        Merged dict with _common.json as base, carrier-specific on top.
        Returns _common.json only (with warning) if carrier file not found.

    Example:
        rule = load_carrier('ONE')
        puc_carriers_flag = rule['puc_handling']['strip_from_soc_tof']  # True
        shortcuts = rule.get('commodity_shortcuts', {})
    """
    code = code.upper().strip()

    if code in _cache:
        return _cache[code]

    common = _load_common()
    carrier_path = os.path.join(CARRIER_RULES_DIR, f"{code}.json")

    if not os.path.exists(carrier_path):
        print(f"  [carrier_rules] WARN: no rule file for carrier '{code}' at {carrier_path}")
        result = copy.deepcopy(common)
        result["carrier_code"] = code
        result["_missing"] = True
    else:
        carrier_data = _load_json_file(carrier_path)
        result = _merge(common, carrier_data)

    _cache[code] = result
    return result


def load_all() -> dict[str, dict]:
    """Load all known carriers.

    Returns:
        Dict keyed by carrier code: {'ONE': {...}, 'CMA': {...}, ...}
    """
    result: dict[str, dict] = {}
    for code in KNOWN_CARRIERS:
        result[code] = load_carrier(code)
    return result


def get_puc_carriers() -> set[str]:
    """Return set of carrier codes where puc_handling.strip_from_soc_tof == True.

    Replaces the hardcoded PUC_CARRIERS set in master_loader_v2.py.

    Returns:
        e.g. {'CMA', 'ONE', 'YML', 'HPL'}
    """
    all_rules = load_all()
    return {
        code
        for code, rules in all_rules.items()
        if rules.get("puc_handling", {}).get("strip_from_soc_tof", False)
    }


def get_commodity_shortcuts(code: str) -> dict:
    """Return commodity shortcut map for a carrier (carrier-specific only, not universal).

    Universal shortcuts (FAK INCL/EXCL GARMENT) are in _common.json
    under commodity_shortcuts_universal. This returns carrier-specific shortcuts.

    Args:
        code: Carrier code

    Returns:
        Dict of {pattern_or_keyword: canonical_label}
    """
    rules = load_carrier(code)
    shortcuts = rules.get("commodity_shortcuts", {})
    # Filter out meta keys starting with _
    return {k: v for k, v in shortcuts.items() if not k.startswith("_")}


def get_universal_commodity_shortcuts() -> dict:
    """Return universal commodity shortcuts applicable to all carriers."""
    common = _load_common()
    raw = common.get("commodity_shortcuts_universal", {})
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def get_note_shortcuts(code: str) -> dict:
    """Return note shortcut rules for a carrier.

    Args:
        code: Carrier code

    Returns:
        Dict of note shortcut rules for this carrier
    """
    rules = load_carrier(code)
    shortcuts = rules.get("note_shortcuts", {})
    return {k: v for k, v in shortcuts.items() if not k.startswith("_")}


def get_soc_routing_rules() -> dict:
    """Return the universal SOC/routing block from _common.json."""
    common = _load_common()
    return common.get("note_shortcuts_soc_routing", {})


def get_booking_template(code: str) -> dict:
    """Return booking template for a carrier (common + carrier overrides).

    Args:
        code: Carrier code

    Returns:
        Booking template dict with carrier-specific overrides applied
    """
    rules = load_carrier(code)
    return rules.get("booking_template", {})


if __name__ == "__main__":
    # Quick smoke test
    print(f"Carrier rules dir: {CARRIER_RULES_DIR}")
    print(f"\nPUC carriers: {get_puc_carriers()}")
    print(f"\nONE commodity shortcuts: {get_commodity_shortcuts('ONE')}")
    print(f"\nZIM note shortcuts (keys): {list(get_note_shortcuts('ZIM').keys())}")
    print(f"\nCMA booking template extra_fields: {get_booking_template('CMA').get('extra_fields', {})}")
    print("\nAll carriers:")
    for code in sorted(KNOWN_CARRIERS):
        rule = load_carrier(code)
        soc = rule.get("puc_handling", {}).get("strip_from_soc_tof", False)
        print(f"  {code:8s} SOC={soc}")
