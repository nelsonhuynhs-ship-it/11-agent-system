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

# State → row background color + badge + icon
_STATE_COLOR = {
    "URGENT":      {"bg": "#fef2f2", "badge": "#b91c1c", "icon": "🚨",
                    "bar": "#dc2626", "text": "#991b1b"},
    "COMPETITIVE": {"bg": "#ecfdf5", "badge": "#047857", "icon": "💰",
                    "bar": "#10b981", "text": "#064e3b"},
    "STABLE":      {"bg": "#f0fdf4", "badge": "#15803d", "icon": "✓",
                    "bar": "#22c55e", "text": "#14532d"},
    "DECLINING":   {"bg": "#eff6ff", "badge": "#1d4ed8", "icon": "🔽",
                    "bar": "#3b82f6", "text": "#1e3a8a"},
}

# Port code → human-readable name (for Pudong Prime style rate table)
_POL_NAMES = {
    "HPH": "Hai Phong",
    "HCM": "Ho Chi Minh",
    "DAD": "Da Nang",
    "SGN": "Ho Chi Minh",
    "HAN": "Hanoi",
    "MYPKG": "Port Klang",
    "SIN": "Singapore",
}

_POD_NAMES = {
    "USLAX": "Los Angeles, CA",
    "USLGB": "Long Beach, CA",
    "USOAK": "Oakland, CA",
    "USSEA": "Seattle, WA",
    "USTIW": "Tacoma, WA",
    "USNYC": "New York, NY",
    "USHOU": "Houston, TX",
    "USSAV": "Savannah, GA",
    "USCHS": "Charleston, SC",
    "USMIA": "Miami, FL",
    "USMEM": "Memphis, TN",
    "USORF": "Norfolk, VA",
    "USBAL": "Baltimore, MD",
    "USILG": "Wilmington, DE",
    "USPDX": "Portland, OR",
    "USJAX": "Jacksonville, FL",
    "USMSY": "New Orleans, LA",
    "USBOS": "Boston, MA",
    "USPHL": "Philadelphia, PA",
    "CAVAN": "Vancouver, BC",
    "CAMTR": "Montreal, QC",
    "CAPRR": "Prince Rupert, BC",
    "CATOR": "Toronto, ON",
    "MXZLO": "Manzanillo",
    "MXVER": "Veracruz",
}


def _load_rate_table_tpl() -> str:
    """Load the rate_table.html partial (returns '' if missing)."""
    try:
        if _RATE_TABLE_PATH.exists():
            return _RATE_TABLE_PATH.read_text(encoding="utf-8")
    except Exception as e:
        log.warning("[builder] could not load rate_table.html: %s", e)
    return ""


def _pol_name(code: str) -> str:
    """POL full name for display. Falls back to code if unknown."""
    return _POL_NAMES.get((code or "").upper(), code.upper() if code else "")


def _pod_name(code: str) -> str:
    """POD full name for display."""
    return _POD_NAMES.get((code or "").upper(), code.upper() if code else "")


def _fmt_rate(v) -> str:
    """Format USD rate as bold number (no prefix — column header says USD)."""
    if v is None or v == "" or v == 0:
        return "—"
    try:
        return f"{int(float(v)):,}"
    except Exception:
        return "—"


def _pick_best_lane(lane_intels: list[dict]) -> dict | None:
    """Return the lane that should get the BEST badge (lowest 40HQ rate wins).
    Falls back to first lane if rates missing.
    """
    if not lane_intels:
        return None
    rated = [ln for ln in lane_intels if ln.get("current_rate_40hq")]
    if not rated:
        return lane_intels[0]
    return min(rated, key=lambda ln: float(ln.get("current_rate_40hq") or 1e9))


def _render_rate_table(lane_intels: list[dict]) -> str:
    """
    Render per-lane rate table — Pudong Prime branded quote style.

    Layout:
      [Column header row: CARRIER | 20GP | 40HQ | VALID | SVC | MARKET]
      [POL band — full-width blue bar with port name]
      [POD chevron row: › LOS ANGELES, CA  via ...]
      [Rate row — green highlight for BEST, state-colored for others]
      ... repeat per POD ...
    """
    if not lane_intels:
        return (
            "<p style='color:#94a3b8;font-style:italic;padding:12px 16px;"
            "border:1px dashed #e2e8f0;border-radius:6px;margin:8px 0;'>"
            "No rate data available for these lanes.</p>"
        )

    pol_code = (lane_intels[0].get("pol") or "HPH").upper()
    pol_full = _pol_name(pol_code)
    best_lane = _pick_best_lane(lane_intels)
    best_id = id(best_lane) if best_lane else None

    # Validity window: this week Mon → next week Fri (common quote pattern)
    from datetime import date, timedelta
    today = date.today()
    valid_start = today - timedelta(days=today.weekday())  # this Monday
    valid_end = valid_start + timedelta(days=11)  # next Friday
    valid_str = f"{valid_start.strftime('%d %b')} – {valid_end.strftime('%d %b')}"

    rows = []

    # ─── Column header row ────────────────────────────────────────
    rows.append(
        "<tr style='background:#f8fafc;border-bottom:1px solid #e2e8f0;'>"
        "<td style='padding:10px 16px;color:#64748b;font-size:10px;"
        "letter-spacing:1.5px;font-weight:700;text-transform:uppercase;'>CARRIER</td>"
        "<td style='padding:10px 12px;color:#64748b;font-size:10px;"
        "letter-spacing:1.5px;font-weight:700;text-align:right;'>20GP</td>"
        "<td style='padding:10px 12px;color:#64748b;font-size:10px;"
        "letter-spacing:1.5px;font-weight:700;text-align:right;'>40HQ</td>"
        "<td style='padding:10px 12px;color:#64748b;font-size:10px;"
        "letter-spacing:1.5px;font-weight:700;'>VALID</td>"
        "<td style='padding:10px 12px;color:#64748b;font-size:10px;"
        "letter-spacing:1.5px;font-weight:700;'>MARKET</td>"
        "<td style='padding:10px 12px;color:#64748b;font-size:10px;"
        "letter-spacing:1.5px;font-weight:700;'>FORECAST</td>"
        "</tr>"
    )

    # ─── POL band (blue full-width) ──────────────────────────────
    rows.append(
        "<tr><td colspan='6' style='padding:0;'>"
        "<div style='background:#2553e2;color:#ffffff;padding:12px 16px;"
        "margin:4px 0 0;'>"
        f"<span style='font-size:15px;font-weight:800;letter-spacing:0.5px;'>{pol_code}</span>"
        f"<span style='color:#c7d2fe;margin-left:12px;font-size:13px;'>{pol_full}</span>"
        "</div></td></tr>"
    )

    # ─── Per-POD rows ────────────────────────────────────────────
    for lane in lane_intels:
        state = str(lane.get("state", "STABLE")).upper()
        colors = _STATE_COLOR.get(state, _STATE_COLOR["STABLE"])
        dest_code = str(lane.get("destination", "")).upper()
        dest_full = _pod_name(dest_code)
        is_best = (id(lane) == best_id)

        r20 = _fmt_rate(lane.get("current_rate_20gp"))
        r40 = _fmt_rate(lane.get("current_rate_40hq"))
        fcst = _fmt_rate(lane.get("forecast_next_week"))
        delta = lane.get("delta_pct", 0.0) or 0
        delta_sign = "+" if delta > 0 else ""

        # POD chevron row
        routing_hint = lane.get("routing") or "direct service"
        rows.append(
            "<tr><td colspan='6' style='padding:12px 16px 4px;'>"
            "<span style='color:#334155;font-size:14px;font-weight:700;'>"
            f"› {dest_code}"
            f"<span style='color:#64748b;font-weight:400;margin-left:8px;'>"
            f"{dest_full}</span></span>"
            "</td></tr>"
        )

        # Rate row — BEST uses green accent; others use state color
        if is_best:
            row_bg = "#ecfdf5"
            accent = "#10b981"
            rate_color = "#064e3b"
            carrier_label = "NELSON"
            best_pill = (
                "<span style='background:#10b981;color:#ffffff;padding:2px 8px;"
                "border-radius:10px;font-size:9px;font-weight:800;margin-left:8px;"
                "letter-spacing:0.5px;vertical-align:middle;'>BEST</span>"
            )
        else:
            row_bg = colors["bg"]
            accent = colors["bar"]
            rate_color = colors["text"]
            carrier_label = "NELSON"
            best_pill = ""

        rows.append(
            f"<tr style='background:{row_bg};border-left:3px solid {accent};'>"
            f"<td style='padding:12px 16px;'>"
            f"<strong style='color:{rate_color};font-size:13px;'>{carrier_label}</strong>"
            f"{best_pill}"
            f"<div style='font-size:11px;color:#94a3b8;margin-top:2px;'>{routing_hint}</div>"
            f"</td>"
            f"<td style='padding:12px 12px;text-align:right;font-weight:700;"
            f"color:{rate_color};font-size:14px;'>{r20}</td>"
            f"<td style='padding:12px 12px;text-align:right;font-weight:700;"
            f"color:{rate_color};font-size:14px;'>{r40}</td>"
            f"<td style='padding:12px 12px;color:#475569;font-size:11px;'>{valid_str}</td>"
            f"<td style='padding:12px 12px;color:{colors['badge']};"
            f"font-size:11px;font-weight:700;white-space:nowrap;'>"
            f"{colors['icon']} {state}"
            f"{(' ' + delta_sign + str(round(delta,1)) + '%') if delta else ''}"
            f"</td>"
            f"<td style='padding:12px 12px;text-align:right;color:#64748b;"
            f"font-size:11px;'>{fcst}</td>"
            f"</tr>"
        )

    # ─── Footer info strip ───────────────────────────────────────
    rows.append(
        "<tr><td colspan='6' style='padding:14px 16px;background:#eff6ff;"
        "border-top:1px solid #dbeafe;'>"
        "<span style='color:#1e3a8a;font-size:12px;'>"
        "› <strong>Local Charge &amp; Handling Fee:</strong> "
        "<span style='color:#2553e2;font-weight:700;'>$45</span> / shipment (US) · "
        "<span style='color:#ea580c;'>Canada: $85 / shipment</span>"
        "</span></td></tr>"
    )

    return (
        "<table cellpadding='0' cellspacing='0' width='100%' "
        "style='border-collapse:collapse;margin:16px 0;width:100%;"
        "font-family:Segoe UI,Arial,sans-serif;border:1px solid #e2e8f0;"
        "border-radius:8px;overflow:hidden;'>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _wrap_branded_shell(
    intro_html: str,
    rate_table_html: str,
    cta_html: str,
    signature_html: str,
    recipient_label: str,
    week: int,
) -> str:
    """
    Wrap email body in Pudong Prime branded shell:
      [Header: logo + title + recipient + date]
      [Intro]
      [Rate table]
      [CTA text]
      [Footer CTA band with button]
      [Signature]
      [Domain bottom]
    """
    from datetime import date
    today = date.today()
    date_str = today.strftime("%d %b %Y")

    return f"""
<div style="margin:0;padding:0;background:#f1f5f9;font-family:Segoe UI,Arial,sans-serif;">
<table cellpadding="0" cellspacing="0" width="100%"
       style="background:#f1f5f9;padding:24px 0;">
  <tr><td align="center">
    <table cellpadding="0" cellspacing="0" width="680"
           style="max-width:680px;background:#ffffff;border-radius:12px;
                  overflow:hidden;box-shadow:0 1px 3px rgba(15,23,42,.06),
                  0 4px 16px rgba(15,23,42,.04);">

      <!-- ══ HEADER ══ -->
      <tr><td style="padding:28px 36px 20px;border-bottom:1px solid #f1f5f9;">
        <table width="100%"><tr>
          <td valign="top">
            <div style="font-size:19px;font-weight:800;color:#0f172a;
                        letter-spacing:-0.3px;line-height:1.2;">
              Pudong Prime Group
            </div>
            <div style="font-size:10px;color:#64748b;letter-spacing:2.5px;
                        margin-top:6px;font-weight:600;">
              OCEAN FREIGHT UPDATE
            </div>
            <div style="font-size:10px;color:#94a3b8;margin-top:8px;">
              A member of VLA · JCTrans · NVOCC
            </div>
          </td>
          <td valign="top" align="right">
            <div style="color:#2553e2;font-weight:700;font-size:15px;">
              {recipient_label}
            </div>
            <div style="color:#64748b;font-size:11px;margin-top:6px;">
              {date_str} · USD · WEEK {week}
            </div>
          </td>
        </tr></table>
      </td></tr>

      <!-- ══ INTRO ══ -->
      <tr><td style="padding:24px 36px 8px;color:#334155;font-size:14px;
                     line-height:1.7;">
        {intro_html}
      </td></tr>

      <!-- ══ RATE TABLE ══ -->
      <tr><td style="padding:0 20px;">
        {rate_table_html}
      </td></tr>

      <!-- ══ CTA TEXT ══ -->
      <tr><td style="padding:8px 36px 20px;color:#334155;font-size:14px;
                     line-height:1.7;">
        {cta_html}
      </td></tr>

      <!-- ══ FOOTER CTA BAND ══ -->
      <tr><td style="padding:22px 36px;background:#2553e2;">
        <table width="100%"><tr>
          <td style="color:#c7d2fe;font-size:14px;vertical-align:middle;">
            Ready to book?
          </td>
          <td align="right">
            <a href="mailto:nelson@pudongprime.vn?subject=Re: Ocean Freight Quote"
               style="background:#ffffff;color:#2553e2;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:700;
                      font-size:13px;display:inline-block;
                      letter-spacing:0.3px;">
              Confirm Booking →
            </a>
          </td>
        </tr></table>
      </td></tr>

      <!-- ══ SIGNATURE ══ -->
      <tr><td style="padding:24px 36px;color:#475569;font-size:12px;
                     line-height:1.6;border-top:1px solid #f1f5f9;
                     white-space:pre-line;">
        {signature_html or ""}
      </td></tr>

      <!-- ══ DOMAIN FOOTER ══ -->
      <tr><td style="padding:14px 36px;background:#f8fafc;
                     text-align:right;font-size:11px;color:#94a3b8;
                     letter-spacing:0.5px;">
        pudongprime.com
      </td></tr>

    </table>
  </td></tr>
</table>
</div>
""".strip()


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
    # market_engine returns 40HQ only; we estimate 20GP using industry
    # rule-of-thumb: 20GP ≈ 40HQ × 0.78 (Asia-US container pricing ratio).
    lane_intels = []
    for dest in destinations:
        intel = analyze_lane(pol, dest)
        intel["pol"] = pol  # annotate for renderer convenience
        # Derive 20GP + apply markup
        r40 = intel.get("current_rate_40hq")
        if r40:
            intel["current_rate_40hq"] = float(r40) + float(markup or 0)
            intel["current_rate_20gp"] = round(float(r40) * 0.78 + float(markup or 0))
        fcst = intel.get("forecast_next_week")
        if fcst:
            intel["forecast_next_week"] = float(fcst) + float(markup or 0)
        lane_intels.append(intel)

    # 2. Dominant state across all lanes
    dom = dominant_state(lane_intels)

    # 3. Match template
    tmpl = tmpl_match(destinations, [dom])

    # 4. Build tokens
    tokens = _build_tokens(profile, lane_intels, pol, destinations)

    # 5. Render intro/cta/signature as HTML chunks (existing renderer)
    rendered = render_email(tmpl, tokens)

    # 6. Wrap in Pudong Prime branded shell
    profile = profile or {}
    recipient_label = (
        profile.get("first_name")
        or profile.get("name")
        or profile.get("company")
        or "Valued Client"
    )
    if profile.get("first_name") and profile.get("company"):
        recipient_label = f"{profile['first_name']} @ {profile['company']}"

    # Pull signature HTML from rendered (already escaped) or build from tokens
    signature_html = ""
    sig = tokens.get("signature", "")
    if sig:
        import html as _html_mod
        escaped = _html_mod.escape(str(sig), quote=True)
        signature_html = escaped.replace("\n", "<br>")

    branded_html = _wrap_branded_shell(
        intro_html=rendered.get("intro_html", ""),
        rate_table_html=tokens.get("rate_table_html", ""),
        cta_html=rendered.get("cta_html", ""),
        signature_html=signature_html,
        recipient_label=recipient_label,
        week=tokens.get("week", date.today().isocalendar()[1]),
    )

    return {
        "to": cnee_email,
        "subject": rendered["subject"],
        "html_body": branded_html,
        "meta": {
            "template_id": tmpl.get("id", "unknown"),
            "dominant_state": dom,
            "lanes_analyzed": len(lane_intels),
            "match_reason": tmpl.get("match_reason", ""),
            "markup": markup,
            "pol": pol,
            "destinations": destinations,
            "lane_states": [ln.get("state") for ln in lane_intels],
            "shell": "pudong_prime_v1",
        },
    }
