"""
one_group_resolver.py — ONE carrier group code resolver.

Maps (contract_type, commodity, note, pod) → (group_code, group_label)
using 12 priority rules from carrier_rules/ONE.json one_group_codes section.

Public API:
    resolve_one_group_code(contract_type, commodity, note, pod) -> tuple[str, str]

CLI:
    python one_group_resolver.py --self-test   # runs all 17 built-in tests, exits 0/1

Nelson defaults (locked):
  - REEFER ambiguous (no FROZEN/CHILLED/FRESH keyword) → default to code "1" (FROZEN)
    because Nelson mainly handles frozen cargo.
  - Canada ambiguous (consol vs single) → default to "990131" (SINGLE).
  - Alias map: SEAFOOD, FROZEN FISH, FISH → treated as FROZEN → code "1".
"""
from __future__ import annotations

import logging
import sys
from typing import NamedTuple

log = logging.getLogger("one_group_resolver")

# ---------------------------------------------------------------------------
# Region detection
# ---------------------------------------------------------------------------

def _pod_region(pod: str) -> str:
    """Return 'CANADA' or 'USA' based on POD prefix.

    CANADA: pod starts with 'CA' but NOT 'CAI' (Cai Mep is Vietnam, not Canada).
    """
    p = pod.upper().strip()
    if p.startswith("CA") and not p.startswith("CAI"):
        return "CANADA"
    return "USA"


# ---------------------------------------------------------------------------
# Keyword helpers
# ---------------------------------------------------------------------------

# Frozen-alias keywords: these commodities are treated as FROZEN even without
# the word FROZEN/REEFER, per Nelson's operational reality.
_FROZEN_ALIASES = {"SEAFOOD", "FROZEN FISH", "FISH", "FROZEN"}


def _contains_any(text: str, keywords: list[str]) -> bool:
    """Return True if `text` contains any of the keywords (case-insensitive, whole substring)."""
    t = text.upper()
    return any(kw.upper() in t for kw in keywords)


def _is_frozen_commodity(commodity_upper: str) -> bool:
    """Return True if commodity indicates frozen cargo.

    Covers:
      - Direct keywords: FROZEN, REEFER FROZEN
      - Aliases: SEAFOOD, FROZEN FISH, FISH
    """
    # Alias exact match first (e.g. bare "FISH" should match, not partial)
    for alias in _FROZEN_ALIASES:
        if alias in commodity_upper:
            return True
    return False


def _is_chilled_commodity(commodity_upper: str) -> bool:
    """Return True only if commodity explicitly mentions CHILLED or FRESH."""
    return "CHILLED" in commodity_upper or "FRESH" in commodity_upper


# ---------------------------------------------------------------------------
# Core resolver
# ---------------------------------------------------------------------------

_UNKNOWN = ("UNKNOWN", "NO_RULE_MATCH")


def resolve_one_group_code(
    contract_type: str,
    commodity: str,
    note: str,
    pod: str,
) -> tuple[str, str]:
    """Resolve ONE carrier group code from booking parameters.

    Args:
        contract_type: "FAK" or "FIX" (case-insensitive)
        commodity:     Raw commodity string, e.g. "GARMENT", "REEFER FROZEN"
        note:          Note/routing field, e.g. "SOC DIRECT", ""
        pod:           Port of discharge code, e.g. "USLAX", "CATOR", "CAI MEP"

    Returns:
        (group_code, group_label) tuple.
        Falls back to ("UNKNOWN", "NO_RULE_MATCH") if no rule matches (should
        never happen in practice given priority-12 catch-all).

    Priority rules (first match wins):
        P1  FIX + GARMENT           → 990117
        P2  FIX + any               → 990104
        P3  FAK + REEFER/FROZEN     → 1       (frozen reefer)
        P4  FAK + CHILLED/FRESH     → 2       (chilled reefer)
        P5  FAK + TANK/HAZ/CHEMICAL → 990302
        P6  FAK + GDSM SOC + SOC note → 990104
        P7  FAK + SHORT TERM GDSM   → 990154
        P8  FAK + GARMENT + SOC note → 990117 (TPE10)
        P9  FAK + SOC/S1/TPE9 + SOC note → 990132
        P10 FAK + CANADA + GARMENT  → 990117
        P11 FAK + CANADA + any      → 990131  (default single; log warning)
        P12 FAK + USA + any         → 990146  (catch-all)
    """
    ct = contract_type.upper().strip()
    com = commodity.upper().strip()
    nt = note.upper().strip()
    region = _pod_region(pod)

    # ── Priority 1: FIX + GARMENT ─────────────────────────────────────────
    if ct == "FIX" and "GARMENT" in com:
        return ("990117", "GARMENT, NOS")

    # ── Priority 2: FIX + any ─────────────────────────────────────────────
    if ct == "FIX":
        return ("990104", "GDSGM")

    # FAK-only rules below ─────────────────────────────────────────────────
    if ct != "FAK":
        log.warning("resolve_one_group_code: unknown contract_type=%r, treating as FAK", contract_type)

    # ── Priority 3/4: FAK + REEFER / FROZEN / CHILLED / FRESH ───────────────
    # Must evaluate P3/P4 BEFORE P5-P12 because reefer cargo has special codes.
    # P3 vs P4 decision: CHILLED/FRESH keyword -> P4; else default FROZEN -> P3.
    # is_reefer_context covers: REEFER, frozen aliases, and explicit CHILLED/FRESH
    # (e.g. "FRESH PRODUCE" has no REEFER word but is definitely P4 reefer cargo).
    is_reefer_context = "REEFER" in com or _is_frozen_commodity(com) or _is_chilled_commodity(com)
    if is_reefer_context:
        if _is_chilled_commodity(com):
            # Priority 4: explicit CHILLED or FRESH
            return ("2", "Group REF FAK - Chilled or Fresh")
        else:
            # Priority 3: FROZEN (default for ambiguous reefer per Nelson rule)
            if "FROZEN" not in com and "CHILLED" not in com and "FRESH" not in com:
                log.warning(
                    "resolve_one_group_code: ambiguous reefer commodity=%r — "
                    "defaulting to FROZEN (code 1) per Nelson rule", commodity
                )
            return ("1", "Group REF FAK - Frozen")

    # ── Priority 5: FAK + TANK/HAZARD/CHEMICAL/HAZ ────────────────────────
    if _contains_any(com, ["TANK", "HAZARD", "CHEMICAL", "HAZ"]):
        return ("990302", "GROUP SOC TANK - Chemical HAZ")

    # ── Priority 6: FAK + GDSM SOC/NAC GROUP + SOC note ──────────────────
    has_soc_note = _contains_any(nt, ["SOC", "SOC DIRECT", "SOC TRANSIT"])
    gdsm_soc_keywords = ["GDSM SOC", "NAC GROUP", "GDSM SOC(NAC)"]
    if _contains_any(com, gdsm_soc_keywords) and has_soc_note:
        return ("990104", "GDSM SOC (NAC GROUP)")

    # ── Priority 7: FAK + SHORT TERM GDSM / GDSM STRAIGHT ────────────────
    if _contains_any(com, ["SHORT TERM GDSM", "GDSM STRAIGHT"]):
        return ("990154", "GDSM STRAIGHT (SHORT TERM)")

    # ── Priority 8: FAK + GARMENT + SOC note ──────────────────────────────
    if "GARMENT" in com and has_soc_note:
        return ("990117", "TPE10 - Group SOC Big 4: Garments")

    # ── Priority 9: FAK + SOC/S1/TPE9 + SOC note ─────────────────────────
    soc_group_keywords = ["SOC", "S1", "TPE9"]
    if _contains_any(com, soc_group_keywords) and has_soc_note:
        return ("990132", "S1-TPE9 - Group SOC Big 4")

    # ── Priority 10: FAK + CANADA + GARMENT ───────────────────────────────
    if region == "CANADA" and "GARMENT" in com:
        return ("990117", "TPE3 - Canada - GARMENT")

    # ── Priority 11: FAK + CANADA + any ──────────────────────────────────
    if region == "CANADA":
        log.warning(
            "resolve_one_group_code: Canada commodity=%r — defaulting to SINGLE "
            "990131 (CONSOL=990132 if needed), per Nelson rule", commodity
        )
        return ("990131", "TPE3 Canada SINGLE")

    # ── Priority 12: FAK + USA + any (catch-all) ──────────────────────────
    if region == "USA":
        return ("990146", "TPE1 - FAK & GARMENT")

    # Should never reach here
    log.warning(
        "resolve_one_group_code: no rule matched "
        "contract_type=%r commodity=%r note=%r pod=%r",
        contract_type, commodity, note, pod,
    )
    return _UNKNOWN


# ---------------------------------------------------------------------------
# CLI self-test
# ---------------------------------------------------------------------------

class _TestCase(NamedTuple):
    name: str
    args: tuple
    expected_code: str
    note: str = ""


_SELF_TEST_CASES: list[_TestCase] = [
    # P1 — FIX + GARMENT
    _TestCase("P1 FIX GARMENT USA",
              ("FIX", "GARMENT", "", "USLAX"), "990117"),
    # P2 — FIX + any
    _TestCase("P2 FIX GENERAL CARGO",
              ("FIX", "GENERAL CARGO", "", "USLAX"), "990104"),
    # P3 — FAK REEFER FROZEN explicit
    _TestCase("P3 FAK REEFER FROZEN explicit",
              ("FAK", "REEFER FROZEN", "", "USLAX"), "1"),
    # P3 alias — SEAFOOD
    _TestCase("P3 alias SEAFOOD",
              ("FAK", "SEAFOOD", "", "USLAX"), "1"),
    # P3 alias — FROZEN FISH
    _TestCase("P3 alias FROZEN FISH",
              ("FAK", "FROZEN FISH", "", "USLAX"), "1"),
    # P3 ambiguous REEFER (no FROZEN/CHILLED) → Nelson default FROZEN
    _TestCase("P3 ambiguous REEFER default frozen",
              ("FAK", "REEFER", "", "USLAX"), "1"),
    # P4 — FAK REEFER CHILLED explicit
    _TestCase("P4 FAK REEFER CHILLED",
              ("FAK", "REEFER CHILLED", "", "USLAX"), "2"),
    # P4 — FRESH keyword
    _TestCase("P4 FAK FRESH PRODUCE",
              ("FAK", "FRESH PRODUCE", "", "USLAX"), "2"),
    # P5 — TANK HAZARD
    _TestCase("P5 FAK TANK CHEMICAL HAZ",
              ("FAK", "TANK CHEMICAL HAZ", "", "USLAX"), "990302"),
    # P6 — GDSM SOC + SOC note
    _TestCase("P6 FAK GDSM SOC NAC SOC DIRECT",
              ("FAK", "GDSM SOC (NAC)", "SOC DIRECT", "USLAX"), "990104"),
    # P7 — SHORT TERM GDSM
    _TestCase("P7 FAK SHORT TERM GDSM",
              ("FAK", "SHORT TERM GDSM", "", "USLAX"), "990154"),
    # P8 — GARMENT + SOC note (TPE10)
    _TestCase("P8 FAK GARMENT SOC DIRECT",
              ("FAK", "GARMENT", "SOC DIRECT", "USLAX"), "990117"),
    # P9 — S1-TPE9 + SOC note
    _TestCase("P9 FAK S1-TPE9 SOC TRANSIT",
              ("FAK", "S1-TPE9", "SOC TRANSIT", "USLAX"), "990132"),
    # P10 — Canada + GARMENT
    _TestCase("P10 FAK GARMENT CANADA CATOR",
              ("FAK", "GARMENT", "", "CATOR"), "990117"),
    # P11 — Canada + any (default single)
    _TestCase("P11 FAK GENERAL CARGO CANADA",
              ("FAK", "GENERAL CARGO", "", "CATOR"), "990131"),
    # P12 — USA catchall
    _TestCase("P12 FAK GENERAL CARGO USA",
              ("FAK", "GENERAL CARGO", "", "USLAX"), "990146"),
    # Edge: CAI MEP (Vietnam, NOT Canada) — should route by keyword rules, then P12 catchall
    _TestCase("Edge CAI MEP treated as Vietnam (not Canada)",
              ("FAK", "GARMENT", "", "CAI MEP"), "990146",
              note="CAI MEP starts with CA but has CAI prefix => USA region => P12 catchall for GARMENT no-SOC"),
]


def _run_self_test() -> int:
    """Run all test cases. Returns 0 on all-pass, 1 on any failure."""
    # Silence WARNING logs during self-test to keep output clean
    logging.basicConfig(level=logging.ERROR)

    passed = 0
    failed = 0
    for tc in _SELF_TEST_CASES:
        code, label = resolve_one_group_code(*tc.args)
        ok = code == tc.expected_code
        status = "PASS" if ok else "FAIL"
        marker = "" if ok else f"  → got {code!r}, expected {tc.expected_code!r}"
        print(f"  [{status}] {tc.name}{marker}")
        if tc.note and not ok:
            print(f"         note: {tc.note}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{passed}/{passed + failed} tests passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_run_self_test())
    else:
        print("Usage: python one_group_resolver.py --self-test")
        sys.exit(1)
