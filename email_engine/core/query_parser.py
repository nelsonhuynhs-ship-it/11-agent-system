# -*- coding: utf-8 -*-
"""
query_parser.py — Extract shipment_ref + customer hint from natural-language query.

Patterns handled:
  "Lô ACB2604 của PANDA đến đâu rồi?"   → {ref: "ACB2604", customer: "PANDA"}
  "Status shipment EBKG260401"            → {ref: "EBKG260401", customer: None}
  "SIRI có vướng gì không?"               → {ref: None, customer: "SIRI"}
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

# ── Shipment ref regex  (2-6 uppercase letters + 4-10 digits) ─────────────────
# Note: spec says 6-10 digits but real queries use shorter refs like ACB2604 (4 digits).
# Using 4+ to capture both short codes (YYMM format) and long BL numbers.
SHIPMENT_REF_RE = re.compile(r"\b([A-Z]{2,6}\d{4,10})\b", re.IGNORECASE)

# ── Customer-rules location (same path used by email_engine pipeline) ─────────
_CUSTOMER_RULES_PATHS = [
    Path("D:/OneDrive/NelsonData/email/customer_rules.json"),
    Path(__file__).parent.parent / "data" / "customer_rules.json",
]


@lru_cache(maxsize=1)
def _load_customer_keys() -> list[str]:
    """Return sorted list of customer IDs from customer_rules.json.

    Falls back to [] if file not found — parser will still work for ref-only queries.
    """
    for p in _CUSTOMER_RULES_PATHS:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                # Support both {"customers": {...}} and flat {"ID": {...}} schemas
                if "customers" in data:
                    keys = list(data["customers"].keys())
                else:
                    keys = [k for k in data.keys() if not k.startswith("_")]
                # Longest first — so "PANDA EXPRESS" matches before "PANDA"
                return sorted(keys, key=len, reverse=True)
            except Exception:
                return []
    return []


def _find_customer(text: str) -> Optional[str]:
    """Return first matching customer key found in text (case-insensitive)."""
    text_upper = text.upper()
    for cid in _load_customer_keys():
        if cid.upper() in text_upper:
            return cid
    return None


def parse_query(text: str) -> dict:
    """Parse free-text query into structured {ref, customer} dict.

    Args:
        text: Natural-language query string (≤500 chars).

    Returns:
        {"ref": str | None, "customer": str | None}

    Both values can be None if the query is too vague.
    """
    text = (text or "").strip()[:500]

    # Extract shipment ref candidates
    refs = SHIPMENT_REF_RE.findall(text.upper())
    ref = refs[0] if refs else None

    # Extract customer hint
    customer = _find_customer(text)

    return {"ref": ref, "customer": customer}


# ── Standalone test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    samples = [
        "Lô ACB2604 của PANDA đến đâu rồi?",
        "Status shipment EBKG260401",
        "SIRI có vướng gì không?",
        "hbkg260412 update?",
        "tình trạng lô hàng ACB123456 CHERRY BLOSSOM?",
    ]
    for s in samples:
        print(f"  Q: {s!r}")
        print(f"  → {parse_query(s)}")
        print()
