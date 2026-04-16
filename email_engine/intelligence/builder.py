# -*- coding: utf-8 -*-
"""
builder.py — Orchestrator for smart emails.

Combines:
    profile (optional, caller-supplied — usually from intel/memory Phase 02)
    + market_engine.analyze_lane() per destination
    + template_selector.match() by dominant state
    + template_renderer.render_email()
    + rate_table HTML (color-coded by state — Jinja-lite partial)

Public API
----------
build_email(cnee_email, pol, destinations, markup=20.0, profile=None) -> dict
    Returns {to, subject, html_body, meta}.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from .market_engine import analyze_lane
from .template_selector import match as tmpl_match, dominant_state, load_rules
from .template_renderer import render_email, render_text

log = logging.getLogger("intelligence_builder")

# Rate-table partial (simple Jinja-lite template)
_RATE_TABLE_PATH = (
    Path(__file__).resolve().parent.parent / "templates" / "rate_table.html"
)

# State → row background color
_STATE_COLOR = {
    "URGENT":      {"bg": "#fee2e2", "badge": "#b91c1c", "icon": "🚨"},
    "COMPETITIVE": {"bg": "#fef9c3", "badge": "#a16207", "icon": "💰"},
    "STABLE":      {"bg": "#dcfce7", "badge": "#15803d", "icon": "✓"},
    "DECLINING":   {"bg": "#dbeafe", "badge": "#1d4ed8", "icon": "🔽"},
}


def _load_rate_table_tpl() -> str:
    """Load the rate_table.html partial (returns '' if missing)."""
    try:
        if _RATE_TABLE_PATH.exists():
            return _RATE_TABLE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        log.warning("[builder] could not load rate_table.html: %s", e)
    return ""


def _render_rate_table(lane_intels: list[dict]) -> str:
    """
    Render the per-lane rate table as HTML, color-coded by state.

    Each lane dict: {destination, state, current_rate_40hq, prev_rate_40hq,
                     delta_pct, mean_90d, forecast_next_week, confidence}
    """
    if not lane_intels:
        return "<p style='color:#6b7280;font-style:italic;'>No rate data available.</p>"

    rows_html = []
    for lane in lane_intels:
        state = str(lane.get("state", "STABLE")).upper()
        colors = _STATE_COLOR.get(state, _STATE_COLOR["STABLE"])
        dest = str(lane.get("destination", ""))
        r20 = lane.get("current_rate_20gp")  # may be None
        r40 = lane.get("current_rate_40hq")
        delta = lane.get("delta_pct", 0.0)
        delta_sign = "+" if (delta or 0) > 0 else ""
        fcst = lane.get("forecast_next_week")

        r20_s = f"USD {int(r20):,}" if r20 else "—"
        r40_s = f"USD {int(r40):,}" if r40 else "—"
        fcst_s = f"USD {int(fcst):,}" if fcst else "—"

        rows_html.append(
            f"<tr style='background:{colors['bg']};'>"
            f"<td style='padding:8px 12px;border:1px solid #e5e7eb;'><strong>{lane.get('pol','HPH')}→{dest}</strong></td>"
            f"<td style='padding:8px 12px;border:1px solid #e5e7eb;text-align:right;'>{r20_s}</td>"
            f"<td style='padding:8px 12px;border:1px solid #e5e7eb;text-align:right;'>{r40_s}</td>"
            f"<td style='padding:8px 12px;border:1px solid #e5e7eb;text-align:center;color:{colors['badge']};font-weight:bold;'>"
            f"{colors['icon']} {state} {delta_sign}{delta}%"
            f"</td>"
            f"<td style='padding:8px 12px;border:1px solid #e5e7eb;text-align:right;color:#6b7280;font-size:12px;'>{fcst_s}</td>"
            f"</tr>"
        )

    return (
        "<table style='border-collapse:collapse;margin:12px 0;width:100%;font-family:Segoe UI,Arial,sans-serif;font-size:13px;'>"
        "<thead><tr style='background:#1f2937;color:#fff;'>"
        "<th style='padding:8px 12px;border:1px solid #374151;text-align:left;'>Route</th>"
        "<th style='padding:8px 12px;border:1px solid #374151;'>20GP</th>"
        "<th style='padding:8px 12px;border:1px solid #374151;'>40HQ</th>"
        "<th style='padding:8px 12px;border:1px solid #374151;'>Market</th>"
        "<th style='padding:8px 12px;border:1px solid #374151;'>Next Wk Forecast</th>"
        "</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody></table>"
    )


def _build_tokens(
    profile: dict | None,
    lane_intels: list[dict],
    pol: str,
    destinations: list[str],
) -> dict:
    """Assemble the tokens dict for the template renderer."""
    profile = profile or {}
    today = date.today()
    iso_week = today.isocalendar()[1]

    # Pick lane with highest-priority state for headline tokens
    from .template_selector import _STATE_PRIORITY
    headline = None
    best_sc = -1
    for ln in lane_intels:
        sc = _STATE_PRIORITY.get(str(ln.get("state", "STABLE")).upper(), 0)
        if sc > best_sc:
            headline = ln
            best_sc = sc

    headline = headline or {}
    mean_90d = headline.get("mean_90d")
    current = headline.get("current_rate_40hq")
    gap_to_mean = None
    if mean_90d and current:
        gap_to_mean = round(float(mean_90d) - float(current), 2)

    tokens = {
        # profile tokens
        "first_name": profile.get("first_name") or profile.get("name") or "",
        "company": profile.get("company") or profile.get("cnee_name") or "",
        "last_rate_quoted": profile.get("last_rate_quoted", ""),
        "days_since_last": profile.get("days_since_last", ""),
        "profile": profile,

        # lane tokens
        "delta": headline.get("delta_pct", 0),
        "current_rate_40hq": current or "",
        "prev_rate_40hq": headline.get("prev_rate_40hq", ""),
        "mean_90d": mean_90d or "",
        "forecast_next_week": headline.get("forecast_next_week", ""),
        "gap_to_mean": gap_to_mean if gap_to_mean is not None else "",
        "sample_size": headline.get("sample_size", 0),
        "confidence": headline.get("confidence", 0),
        "typical_pol": pol.upper(),
        "typical_dest": destinations[0].upper() if destinations else "",

        # meta
        "week": iso_week,
        "year": today.year,
        "date": today.isoformat(),
        "suffix": "NELSON",

        # fallback intro (used by default template)
        "default_intro": f"Dear {profile.get('first_name', 'Team')},\n"
                        f"Weekly Asia-US ocean freight update for {profile.get('company', 'your team')}.",

        # HTML chunks
        "rate_table_html": _render_rate_table(lane_intels),
    }

    # Signature from YAML defaults
    rules = load_rules()
    defaults_cfg = rules.get("defaults") or {}
    sig = defaults_cfg.get("signature")
    if sig:
        tokens["signature"] = sig
    sfx = defaults_cfg.get("subject_suffix")
    if sfx:
        tokens["suffix"] = sfx

    return tokens


def build_email(
    cnee_email: str,
    pol: str,
    destinations: list[str],
    markup: float = 20.0,
    profile: dict | None = None,
) -> dict:
    """
    Build a complete smart email for one CNEE.

    Args:
        cnee_email:  recipient email (required)
        pol:         port of loading (HPH / HCM)
        destinations: list of POD port codes (e.g. ['USLAX','USLGB'])
        markup:      USD markup per container (default 20)
        profile:     optional CNEE profile dict (from Phase 02 intel/memory).
                     Keys: first_name, company, last_rate_quoted, days_since_last, ...

    Returns:
        {
            to: str,
            subject: str,
            html_body: str,
            meta: {
                template_id, dominant_state, lanes_analyzed,
                match_reason, markup, pol, destinations
            }
        }
    """
    pol = (pol or "HPH").strip().upper()
    destinations = [d.strip().upper() for d in (destinations or []) if d and d.strip()]

    # 1. Per-lane market analysis
    lane_intels = []
    for dest in destinations:
        intel = analyze_lane(pol, dest)
        intel["pol"] = pol  # annotate for renderer convenience
        lane_intels.append(intel)

    # 2. Dominant state across all lanes
    dom = dominant_state(lane_intels)

    # 3. Match template
    tmpl = tmpl_match(destinations, [dom])

    # 4. Build tokens
    tokens = _build_tokens(profile, lane_intels, pol, destinations)

    # 5. Render
    rendered = render_email(tmpl, tokens)

    return {
        "to": cnee_email,
        "subject": rendered["subject"],
        "html_body": rendered["html_body"],
        "meta": {
            "template_id": tmpl.get("id", "unknown"),
            "dominant_state": dom,
            "lanes_analyzed": len(lane_intels),
            "match_reason": tmpl.get("match_reason", ""),
            "markup": markup,
            "pol": pol,
            "destinations": destinations,
            "lane_states": [ln.get("state") for ln in lane_intels],
        },
    }
