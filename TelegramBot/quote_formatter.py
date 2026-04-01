# -*- coding: utf-8 -*-
"""
quote_formatter.py — Sprint Reorg Phase 2
Formats Parquet query results into professional Quotation text.
Reads carrier advisory notes from carrier_tips.json (no hardcoding).

Exports:
  format_quotation(results_df, container, parsed, freetime_fn) -> str
"""
import json
import os
from datetime import date

import pandas as pd

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_TIPS_FILE = os.path.join(_THIS_DIR, "carrier_tips.json")

# ── Carrier tips cache ────────────────────────────────────────────────────────
_carrier_tips: dict = {}


def _load_carrier_tips() -> dict:
    """Load carrier advisory notes from carrier_tips.json (cached)."""
    global _carrier_tips
    if _carrier_tips:
        return _carrier_tips
    try:
        with open(_TIPS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        _carrier_tips = {k.upper(): v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        _carrier_tips = {}
    return _carrier_tips


# ── Advisory note per row ─────────────────────────────────────────────────────

def _smart_note(row: pd.Series, rank: int) -> str:
    """Generate smart advisory note per result row."""
    carrier = str(row.get("Carrier", "")).upper()
    note    = str(row.get("Note", "")).upper()

    try:
        exp = pd.to_datetime(row.get("Exp"), errors="coerce")
        days_left = (exp - pd.Timestamp(date.today())).days
    except Exception:
        days_left = 99

    advice = []

    # SOC / COC type hint
    if "SOC" in note:
        advice.append("SOC — phu hop hang co thung rieng")
    elif "COC" in note:
        advice.append("COC — thung hang tau, thu tuc don gian")

    # Carrier-specific tip from JSON
    if not advice:
        tips = _load_carrier_tips()
        for key, tip in tips.items():
            if key in carrier:
                advice.append(tip)
                break

    # Rank fallback
    if not advice:
        fallback = {1: "Gia tot nhat hien tai", 2: "Lua chon on dinh", 3: "Phu hop giu gia dai han"}
        advice.append(fallback.get(rank, ""))

    # Validity urgency
    if days_left <= 5:
        advice.append(f"[!] Con {days_left} ngay hieu luc — can chot gap")
    elif days_left <= 14:
        advice.append(f"Con {days_left} ngay hieu luc — nen chot som")

    return advice[0] if advice else ""


# ── Main formatter ────────────────────────────────────────────────────────────

def format_quotation(
    results_df: pd.DataFrame,
    container: str,
    parsed: dict,
    freetime_fn=None,        # callable(carrier, container, pol) -> str | None
) -> str:
    """
    Format Parquet rate results as professional Quotation text.
    Clean text — ready to copy and send to customers. Max 3 options.

    Args:
        results_df  : DataFrame from query_parquet()
        container   : e.g. '40HQ'
        parsed      : dict from parse_rate_query()
        freetime_fn : optional callable to get freetime summary per carrier
    """
    if results_df is None or results_df.empty:
        terms = " ".join(parsed.get("place_terms") or [])
        svc   = f" [{parsed.get('service')}]" if parsed.get("service") else ""
        return f"Khong tim thay gia {container}{svc} cho: {terms}"

    pol        = (parsed.get("pol") or "HPH").upper()
    place_info = " ".join(parsed.get("place_terms") or []).upper() or "ALL"
    pod_info   = f" | VIA {parsed['pod'].upper()}" if parsed.get("pod") else ""
    svc_label  = f" | {parsed['service']}"          if parsed.get("service") else ""
    comm_label = f" | {parsed['commodity'].upper()}" if parsed.get("commodity") else ""
    label_map  = {1: "Best Price", 2: "Stability", 3: "Long Validity"}

    lines = [
        f"QUOTATION  {pol} - {place_info}{pod_info} | {container}{svc_label}{comm_label}",
        "\u2500" * 42,
    ]

    rows  = results_df.reset_index(drop=True)
    shown = min(len(rows), 3)

    for rank in range(1, shown + 1):
        row     = rows.iloc[rank - 1]
        carrier = str(row.get("Carrier", ""))
        amount  = row.get("Amount", 0)
        note    = str(row.get("Note", ""))

        try:
            exp_str = pd.to_datetime(row.get("Exp"), errors="coerce").strftime("%d-%b-%Y")
        except Exception:
            exp_str = "N/A"

        try:
            price_fmt = f"USD {int(float(amount)):,}"
        except Exception:
            price_fmt = str(amount)

        label        = label_map.get(rank, "Alternative")
        note_display = f" ({note})" if note and note.upper() not in ("NAN", "", "NONE") else ""
        smart        = _smart_note(row, rank)

        lines.append("")
        lines.append(f"Option {rank}: {carrier}{note_display}  [{label}]")
        lines.append(f"  Rate     : *{price_fmt}*")
        lines.append(f"  Validity : {exp_str}")
        if smart:
            lines.append(f"  Note     : {smart}")

    lines.append("")
    lines.append("\u2500" * 42)

    # Freetime — via injected function (from freetime_formatter or carrier_rules.json)
    pol_for_ft     = parsed.get("pol") or "HPH"
    carriers_shown = [str(rows.iloc[i].get("Carrier", "")) for i in range(shown)]
    seen: set      = set()
    ft_lines       = []

    if freetime_fn:
        for c in carriers_shown:
            ck = c.upper()
            if ck in seen:
                continue
            seen.add(ck)
            ft = freetime_fn(c, container, pol_for_ft)
            if ft:
                ft_lines.append(f"  {c}: {ft}")

    if ft_lines:
        lines.append("Freetime at POL:")
        lines.extend(ft_lines)
    else:
        lines.append("Freetime at POL: confirm with carrier")

    lines.append("")
    lines.append(f"/savequote CUSTOMER {' '.join(str(i) for i in range(1, shown + 1))}")
    lines.append(f"/win QUOTE-ID [qty]")

    return "\n".join(lines)
