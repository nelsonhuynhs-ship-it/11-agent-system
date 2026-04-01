"""
customer_profiles.py — Sprint 7: Customer Deep Memory
Loads static customer profiles from 02_data_dictionary.md and merges
with dynamic rules from the SQLite database.

Profile fields:
  - preferred_lanes: list of inland destination keywords
  - commodity: typical cargo
  - priority: 'cheapest' | 'direct' | 'carrier:XXX'
  - behavior: free-text behavioral notes
"""
import os
import re
import logging

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# STATIC PROFILES (sourced from 02_data_dictionary.md §5)
# Sếp can extend this dict directly or via /remember command
# ─────────────────────────────────────────────────────────
STATIC_PROFILES = {
    "HML": {
        "preferred_lanes": ["DENVER", "EL PASO", "KANSAS"],
        "commodity": "Stone, Slabs (Đá)",
        "priority": "direct",
        "behavior": "Hàng nặng, hay quan tâm weight limit",
        "preferred_carriers": [],
    },
    "SIRI": {
        "preferred_lanes": ["EL PASO"],
        "commodity": "Office Nails",
        "priority": "cheapest",
        "behavior": "Price sensitive — check nhiều lần trước khi chốt",
        "preferred_carriers": [],
    },
    "PANDA": {
        "preferred_lanes": ["LAX", "LONG BEACH"],
        "commodity": "Mixed (General)",
        "priority": "direct",
        "behavior": "Ưu tiên Maersk & Direct. Hay thua CMA — cân nhắc hạ markup",
        "preferred_carriers": ["MSK", "MAERSK"],
    },
}


def get_profile(customer_name: str) -> dict | None:
    """
    Return combined profile for a customer.
    Static profile merged with DB dynamic rules.
    """
    key = customer_name.strip().upper()
    profile = STATIC_PROFILES.get(key)
    if profile:
        return {"customer": key, **profile, "source": "static+db"}
    return None


def enrich_query(parsed: dict, customer_name: str) -> dict:
    """
    Given a parsed query dict (from query_parser.parse_rate_query),
    auto-fill missing fields based on customer profile.

    Rules:
    1. If place_terms is empty → inject preferred_lanes (first one)
    2. If carrier is None and priority='carrier:XXX' → inject carrier
    3. Always set parsed['customer'] = customer_name
    """
    profile = get_profile(customer_name)
    if not profile:
        return parsed

    enriched = parsed.copy()
    enriched['customer'] = customer_name.upper()

    # Inject place if user didn't specify any
    if not enriched.get('place_terms') and profile.get('preferred_lanes'):
        lanes = profile['preferred_lanes']
        # Use first preferred lane as default
        enriched['place_terms'] = [lanes[0]]
        logger.info(f"[Profile] {customer_name}: injected place '{lanes[0]}' from profile")

    # Inject carrier preference if priority is carrier-specific
    priority = profile.get('priority', '')
    if not enriched.get('carrier') and priority.startswith('carrier:'):
        carrier = priority.split(':', 1)[1].strip().upper()
        enriched['carrier'] = carrier
        logger.info(f"[Profile] {customer_name}: injected carrier '{carrier}' from priority")

    return enriched


def format_profile_header(customer_name: str) -> str:
    """
    Return a one-line profile badge to prepend to quote results.
    Example: '🏢 HML | Stone/Slabs | Tuyến: Denver, El Paso, Kansas'
    """
    profile = get_profile(customer_name)
    if not profile:
        return ""

    lanes = ", ".join(profile.get('preferred_lanes', []))
    commodity = profile.get('commodity', '')
    priority = profile.get('priority', '')
    behavior = profile.get('behavior', '')

    priority_tag = ""
    if priority == 'direct':
        priority_tag = "⚡ Direct"
    elif priority == 'cheapest':
        priority_tag = "💲 Cheapest"
    elif priority.startswith('carrier:'):
        priority_tag = f"🚢 {priority.split(':',1)[1]}"

    parts = [f"🏢 **{customer_name.upper()}**"]
    if commodity:
        parts.append(f"📦 {commodity}")
    if lanes:
        parts.append(f"🗺️ {lanes}")
    if priority_tag:
        parts.append(priority_tag)
    if behavior:
        parts.append(f"💡 {behavior}")

    return " | ".join(parts)


def list_profile_customers() -> list[str]:
    """Return list of all statically profiled customers."""
    return list(STATIC_PROFILES.keys())


def get_all_lanes(customer_name: str) -> list[str]:
    """Return all preferred lanes for a customer (for multi-lane quote)."""
    profile = get_profile(customer_name)
    if not profile:
        return []
    return profile.get('preferred_lanes', [])
