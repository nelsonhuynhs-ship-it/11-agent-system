# -*- coding: utf-8 -*-
"""
rate_table_renderer.py - Rate Table v2 HTML Renderer (Outlook-safe inline)
===========================================================================
Side-by-side HPH/HCM layout with inland POD styling.
All critical styles are INLINED on each element because Outlook Desktop
(Word rendering engine) strips or ignores most <style> rules.

Public API
----------
render_dual_rate_table(hph_rates, hcm_rates, pod_list, week, exp_label) -> str
    Returns a self-contained HTML fragment (inline-styled table).
    No dependencies outside stdlib. Safe to embed inside email body.

Input shape per rate dict (from auto_rate_builder.build_rate_table_for_customer):
    pod_code, carrier, rate_20, rate_40, eff, exp, rate_type,
    routing_label, rate_type_routing  (inland only)
"""
from __future__ import annotations

import html as _html

# ── POD metadata lookup ───────────────────────────────────────────────────────
_POD_CITY: dict[str, str] = {
    "USATL": "Atlanta",
    "USCHI": "Chicago",
    "USDAL": "Dallas",
    "USDEN": "Denver",
    "USTIW": "Tacoma",
}

_INLAND_PODS = {"USATL", "USCHI", "USDAL", "USDEN"}
_RIPI_PODS = {"USATL"}

# ── Inline style snippets (Outlook-safe) ─────────────────────────────────────
# Keep them as constants so rows stay concise.
_S_TD_BASE = (
    "padding:4px 6px;border:1px solid #dce5e0;vertical-align:top;"
    "font-size:11.5px;font-family:Segoe UI,Arial,sans-serif;"
    "word-wrap:break-word;overflow:hidden;"
)
_S_TD_EVEN = _S_TD_BASE + "background:#fafcfb;"
_S_TH_HPH = (
    "padding:6px;text-align:left;font-weight:700;border:1px solid #8bc9a3;"
    "background:#c8e8d4;color:#0a4d3c;font-size:11px;"
    "font-family:Segoe UI,Arial,sans-serif;"
)
_S_TH_HCM = (
    "padding:6px;text-align:left;font-weight:700;border:1px solid #7fb3dd;"
    "background:#c6dfef;color:#0a3d5c;font-size:11px;"
    "font-family:Segoe UI,Arial,sans-serif;"
)
_S_TITLE_HPH = (
    "font-size:13px;font-weight:700;padding:10px 12px;"
    "border:1px solid #8bc9a3;border-bottom:none;"
    "background:#d4f0dd;color:#0a4d3c;"
    "text-transform:uppercase;letter-spacing:0.5px;"
    "font-family:Segoe UI,Arial,sans-serif;"
)
_S_TITLE_HCM = (
    "font-size:13px;font-weight:700;padding:10px 12px;"
    "border:1px solid #7fb3dd;border-bottom:none;"
    "background:#d9ebf8;color:#0a3d5c;"
    "text-transform:uppercase;letter-spacing:0.5px;"
    "font-family:Segoe UI,Arial,sans-serif;"
)
_S_POD_CELL = "font-weight:700;color:#0a4d3c;"
_S_POD_INLAND = (
    "padding:4px 6px;border:1px solid #dce5e0;border-left:3px solid #0366d6;"
    "vertical-align:top;background:#eef5ff;"
    "font-size:11.5px;font-family:Segoe UI,Arial,sans-serif;"
    "word-wrap:break-word;overflow:hidden;"
)
_S_POD_CODE_INLAND = "color:#0366d6;font-weight:700;font-size:12px;"
_S_POD_SUB = (
    "font-size:9px;color:#4a6b8a;font-weight:500;display:block;"
    "margin-top:2px;letter-spacing:0.2px;"
)
_S_CARRIER_NAME = "font-weight:700;font-size:12px;"
_S_RATE_PRICE = (
    "font-weight:600;color:#0a4d3c;white-space:nowrap;"
    "font-size:11.5px;line-height:1.3;"
)
_S_RATE_META = "color:#666;font-size:9.5px;line-height:1.25;"

# Badges (inline-block + solid bg colors render fine in Outlook)
_S_BADGE_BASE = (
    "display:inline-block;color:#fff;font-size:8px;padding:1px 4px;"
    "border-radius:2px;margin-left:3px;vertical-align:middle;"
    "letter-spacing:0.3px;font-family:Segoe UI,Arial,sans-serif;"
)
_S_BADGE_BEST = _S_BADGE_BASE + "background:#0a4d3c;"
_S_BADGE_SCFI = _S_BADGE_BASE + "background:#e8a617;"
_S_BADGE_RIPI = _S_BADGE_BASE + "background:#0366d6;font-weight:700;"
_S_BADGE_IPI = _S_BADGE_BASE + "background:#6b46c1;font-weight:700;"

_S_FOOTER = (
    "background:#f7f7f7;padding:10px 12px;margin-top:8px;"
    "font-size:11px;color:#555;border:1px solid #e0e0e0;"
    "font-family:Segoe UI,Arial,sans-serif;"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_exp(exp) -> str:
    """Return 'D Mon' e.g. '3 May'. Returns '' if invalid."""
    if exp is None:
        return ""
    try:
        import pandas as pd
        if pd.isnull(exp):
            return ""
        ts = pd.to_datetime(exp)
        return f"{ts.day} {ts.strftime('%b')}"
    except Exception:
        return ""


# ── Core render functions ─────────────────────────────────────────────────────

def render_carrier_cell(rate: dict, is_best: bool, row_even: bool) -> str:
    """Render one <td> for one carrier (rate cell) with inline styles."""
    carrier = _html.escape(str(rate.get("carrier") or ""))
    rate_type = str(rate.get("rate_type") or "").upper().strip()
    amount_40 = rate.get("rate_40") or 0
    amount_20 = rate.get("rate_20") or 0
    exp = rate.get("exp")
    routing_label = str(rate.get("routing_label") or "").strip()

    badges = []
    if is_best:
        badges.append(f'<span style="{_S_BADGE_BEST}">BEST</span>')
    if rate_type == "SCFI":
        badges.append(f'<span style="{_S_BADGE_SCFI}">SCFI 7d</span>')
    badge_str = "".join(badges)

    price_parts = []
    if amount_40:
        price_parts.append(f"${int(amount_40):,}")
    if amount_20:
        price_parts.append(f"20GP ${int(amount_20):,}")
    price_str = " / ".join(price_parts) if price_parts else "—"

    meta_parts = []
    if rate_type:
        meta_parts.append(_html.escape(rate_type))
    if routing_label:
        meta_parts.append(_html.escape(routing_label))
    elif exp:
        exp_str = _fmt_exp(exp)
        if exp_str:
            meta_parts.append(f"to {exp_str}")
    meta = " · ".join(meta_parts)

    td_style = _S_TD_EVEN if row_even else _S_TD_BASE
    return (
        f'<td style="{td_style}">'
        f'<span style="{_S_CARRIER_NAME}">{carrier}</span>{badge_str}'
        f'<div style="{_S_RATE_PRICE}">{price_str}</div>'
        f'<div style="{_S_RATE_META}">{meta}</div>'
        f'</td>'
    )


def render_pod_row(pod_info: dict, rates: list[dict], row_even: bool) -> str:
    """Render one <tr> for one POD with up to 3 carrier cells, inline styles."""
    code = str(pod_info.get("code") or "").upper()
    city = str(pod_info.get("city") or "")
    pod_type = str(pod_info.get("type") or "main")
    is_inland = pod_type == "inland" or code in _INLAND_PODS

    if is_inland:
        pod_td_style = _S_POD_INLAND if not row_even else (
            _S_POD_INLAND.replace("background:#eef5ff", "background:#e6f1fd")
        )
        is_ripi = code in _RIPI_PODS or str(pod_info.get("gateway") or "").upper() == "RIPI"
        # WHY: inline-block badge with margin-left glues to POD code in narrow POD cell.
        # Override to block-level inside POD column so each element wraps to its own line.
        _badge_block = (
            "display:inline-block;color:#fff;font-size:8px;padding:1px 5px;"
            "border-radius:2px;margin:3px 0 0 0;letter-spacing:0.3px;"
            "font-family:Segoe UI,Arial,sans-serif;font-weight:700;"
        )
        _badge_bg = "background:#0366d6;" if is_ripi else "background:#6b46c1;"
        _badge_label = "RIPI" if is_ripi else "IPI"
        badge_html = (
            f'<div style="line-height:1;margin-top:3px;">'
            f'<span style="{_badge_block}{_badge_bg}">{_badge_label}</span>'
            f'</div>'
        )
        city_html = f'<span style="{_S_POD_SUB}">{_html.escape(city)}</span>' if city else ""
        code_html = f'<div style="{_S_POD_CODE_INLAND}line-height:1.2;">{code}</div>'
    else:
        pod_td_style = (_S_TD_EVEN if row_even else _S_TD_BASE) + _S_POD_CELL
        badge_html = ""
        city_html = (
            f'<span style="{_S_POD_SUB}">{_html.escape(city)}</span>'
            if code == "USTIW" and city else ""
        )
        code_html = code

    pod_td = f'<td style="{pod_td_style}">{code_html}{badge_html}{city_html}</td>'

    carrier_cells = "".join(
        render_carrier_cell(r, is_best=(i == 0), row_even=row_even)
        for i, r in enumerate(rates[:3])
    )
    empty_count = 3 - min(len(rates), 3)
    empty_td_style = (_S_TD_EVEN if row_even else _S_TD_BASE) + "color:#aaa;font-size:11px;"
    carrier_cells += f'<td style="{empty_td_style}">—</td>' * empty_count

    return f'<tr>{pod_td}{carrier_cells}</tr>'


def _render_pol_table(pol_code: str, rates_by_pod: dict[str, list[dict]],
                      pod_list: list[dict], week: int, exp_label: str) -> str:
    """Render one complete rate table for one POL with inline styles."""
    pol_upper = pol_code.upper()
    if pol_upper == "HPH":
        title_style = _S_TITLE_HPH
        th_style = _S_TH_HPH
        flag_name = "HAIPHONG (HPH)"
        flag_bg = "#0a4d3c"
    else:
        title_style = _S_TITLE_HCM
        th_style = _S_TH_HCM
        flag_name = "HO CHI MINH (HCM)"
        flag_bg = "#0a6cb0"

    flag_html = (
        f'<span style="display:inline-block;width:10px;height:10px;'
        f'border-radius:50%;margin-right:6px;vertical-align:middle;'
        f'background:{flag_bg};">&nbsp;</span>'
    )
    # WHY: per-cell "to {date}" already shows validity on each rate row;
    # duplicating at POL title level adds noise.
    header = (
        f'<div style="{title_style}">'
        f'{flag_html}FROM {_html.escape(flag_name)} · Week {week}'
        f'</div>'
    )

    rows_html = []
    for i, pod_info in enumerate(pod_list):
        code = str(pod_info.get("code") or "").upper()
        rates = rates_by_pod.get(code, [])
        rows_html.append(render_pod_row(pod_info, rates, row_even=(i % 2 == 1)))

    table_style = (
        "width:100%;border-collapse:collapse;background:#fff;"
        "table-layout:fixed;"
        "font-size:12px;font-family:Segoe UI,Arial,sans-serif;"
    )
    th_pod = th_style + "width:18%;"
    th_best = th_style + "width:28%;"
    th_2nd = th_style + "width:27%;"
    th_3rd = th_style + "width:27%;"
    table = (
        f'<table cellpadding="0" cellspacing="0" border="0" style="{table_style}">'
        f'<thead><tr>'
        f'<th style="{th_pod}">POD</th>'
        f'<th style="{th_best}">Best Rate</th>'
        f'<th style="{th_2nd}">2nd Option</th>'
        f'<th style="{th_3rd}">3rd Option</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table>'
    )

    return header + table


def _earliest_exp_label(rates: list[dict]) -> str:
    """Find the earliest expiry date across all rates for the header."""
    try:
        import pandas as pd
        dates = []
        for r in rates:
            exp = r.get("exp")
            if exp:
                try:
                    ts = pd.to_datetime(exp)
                    if not pd.isnull(ts):
                        dates.append(ts)
                except Exception:
                    pass
        if not dates:
            return ""
        earliest = min(dates)
        return f"{earliest.day} {earliest.strftime('%b')}"
    except Exception:
        return ""


def _rates_to_pod_map(rates: list[dict]) -> dict[str, list[dict]]:
    """Group rate dicts by pod_code, each group sorted cheapest-first."""
    result: dict[str, list[dict]] = {}
    for r in rates:
        pod = str(r.get("pod_code") or "").upper()
        if pod:
            result.setdefault(pod, []).append(r)
    for pod in result:
        result[pod].sort(key=lambda x: x.get("rate_40") or 9_999_999)
    return result


def _footer_html() -> str:
    # WHY: Outlook strips inline-block spacing between legend items, gluing
    # "BEST top pick per PODSCFI 7d HPL index...". Render as 2x2 grid table with
    # each badge in its own cell + explicit gap for guaranteed alignment.
    item = "padding:3px 14px 3px 0;font-size:11px;color:#333;white-space:nowrap;"
    return (
        f'<div style="{_S_FOOTER}">'
        f'<div style="font-weight:700;margin-bottom:4px;">Badge key:</div>'
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">'
        f'<tr>'
        f'<td style="{item}"><span style="{_S_BADGE_BEST}">BEST</span>&nbsp; top pick per POD</td>'
        f'<td style="{item}"><span style="{_S_BADGE_SCFI}">SCFI 7d</span>&nbsp; HPL index, re-confirm weekly</td>'
        f'</tr>'
        f'<tr>'
        f'<td style="{item}"><span style="{_S_BADGE_RIPI}">RIPI</span>&nbsp; Rail via East Coast</td>'
        f'<td style="{item}"><span style="{_S_BADGE_IPI}">IPI</span>&nbsp; Rail via West Coast</td>'
        f'</tr>'
        f'</table>'
        f'<div style="margin-top:6px;border-top:1px solid #e0e0e0;padding-top:6px;">'
        f'Handling fee: <strong>$65</strong>/shipment US · Canada <strong>$85</strong>/shipment'
        f'</div>'
        f'</div>'
    )


# ── Main public function ──────────────────────────────────────────────────────

def render_dual_rate_table(
    hph_rates: list[dict],
    hcm_rates: list[dict],
    pod_list: list[dict],
    week: int | None = None,
    exp_label: str = "",
) -> str:
    """Render side-by-side HPH/HCM rate table as HTML fragment (Outlook-safe).

    Single POL → full-width table.
    Both POLs → 50/50 split using Outlook-compatible <table> wrapper with inline styles.
    """
    if week is None:
        from datetime import date
        week = date.today().isocalendar()[1]

    if not exp_label:
        all_rates = list(hph_rates) + list(hcm_rates)
        exp_label = _earliest_exp_label(all_rates)

    has_hph = bool(hph_rates)
    has_hcm = bool(hcm_rates)

    if not has_hph and not has_hcm:
        return (
            "<p style='color:#94a3b8;font-style:italic;padding:12px;'>"
            "No rate data available.</p>"
        )

    parts: list[str] = []

    if has_hph and has_hcm:
        hph_map = _rates_to_pod_map(hph_rates)
        hcm_map = _rates_to_pod_map(hcm_rates)
        hph_block = _render_pol_table("HPH", hph_map, pod_list, week, exp_label)
        hcm_block = _render_pol_table("HCM", hcm_map, pod_list, week, exp_label)

        wrap_style = "width:100%;border-collapse:collapse;"
        left_style = "vertical-align:top;padding-right:8px;width:50%;"
        right_style = "vertical-align:top;padding-left:8px;width:50%;"
        parts.append(
            f'<table cellpadding="0" cellspacing="0" border="0" style="{wrap_style}">'
            '<tbody><tr>'
            f'<td style="{left_style}">{hph_block}</td>'
            f'<td style="{right_style}">{hcm_block}</td>'
            '</tr></tbody></table>'
        )
    else:
        pol_code = "HPH" if has_hph else "HCM"
        rate_list = hph_rates if has_hph else hcm_rates
        pol_map = _rates_to_pod_map(rate_list)
        pol_block = _render_pol_table(pol_code, pol_map, pod_list, week, exp_label)
        parts.append(pol_block)

    parts.append(_footer_html())
    return "\n".join(parts)
