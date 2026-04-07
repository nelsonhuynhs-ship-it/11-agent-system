# -*- coding: utf-8 -*-
"""
local_email_builder.py — Build full email HTML locally from Parquet (no VPS)
=============================================================================
Wraps auto_rate_builder.build_rate_table_for_customer() into a complete v2
email HTML.  Interface matches VPS API response so auto-campaign.py needs
minimal changes.

Usage:
    from local_email_builder import build_email_for_lead
    result = build_email_for_lead(lead_dict, markup=20)
    # result: {subject, html, row_count, is_blocked, days_used, warn_msg}
"""
import os
import re
import sys
import time
import random
import logging
from datetime import date
from pathlib import Path

# ── sys.path: ensure Engine_test root is importable ──────────────────────────
_THIS_DIR   = Path(__file__).parent                          # tools/goclaw/
_REPO_ROOT  = _THIS_DIR.parent.parent                        # Engine_test/
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

log = logging.getLogger("local_email_builder")

# ── Default destination port codes (fallback when lead has no valid port codes) ─
# Covers major US gateways: West Coast, East Coast, Gulf, Midwest, Inland hubs
_DEFAULT_DESTINATIONS = "USLAX,USLGB,USNYC,USEWR,USSAV,USCHI,USDAL,USDEN"
_PORT_CODE_RE = re.compile(r"^[A-Z]{2,5}$")  # valid code: 2-5 uppercase letters


def _normalize_destinations(dest_str: str) -> str:
    """
    Return comma-separated port codes for the rate query.

    Rules:
    - If dest_str is empty/NaN → return default list
    - If all comma-parts look like port codes (2-5 uppercase letters) → use them
    - Otherwise (full text like "Port of Oakland, California") → return default list
    """
    if not dest_str or dest_str.lower() in ("nan", "none", ""):
        return _DEFAULT_DESTINATIONS
    parts = [p.strip().upper() for p in dest_str.split(",") if p.strip()]
    if parts and all(_PORT_CODE_RE.match(p) for p in parts):
        return ",".join(parts)
    log.debug("[LocalBuilder] DESTINATION '%s' is not port codes → using default", dest_str[:60])
    return _DEFAULT_DESTINATIONS


# ── Surcharge page URL (host the HTML file somewhere accessible to customers) ─
SURCHARGE_URL = os.environ.get(
    "SURCHARGE_URL",
    "http://14.225.207.145:8100/static/bunker-surcharge.html",
)

# ── Subject templates ─────────────────────────────────────────────────────────
_SUBJECT_TEMPLATES = [
    "Vietnam Freight Rates // NELSON WEEK {week}",
    "Ocean Freight Update — WEEK {week} // Nelson Freight NVOCC",
    "What Importers Need to Know // NELSON WEEK {week}",
    "Current Rates Vietnam→USA | WEEK {week}",
    "HPH/HCM → USA Rates This Week // NELSON W{week}",
]

# ── Disclaimer text (above signature) ────────────────────────────────────────
_DISCLAIMER_HTML = """<div style="margin:20px 0 0;padding:10px 14px;background:#f0f7ff;border-left:3px solid #2563EB;border-radius:3px;font-size:11px;color:#555;line-height:1.6;">
  <strong style="color:#1a3a5c;">Note:</strong>
  This email is sent by Nelson Huynh (Ch&#237;nh) from Pudong Prime Vietnam — a logistics company
  specialized in handling export shipments from Vietnam to USA &amp; Canada. Through market research,
  we identified that your company may have import business from Asia to the US market.
  If this information is not relevant to your business, we sincerely apologize for the interruption.
  Please reply to this email and we will remove you from our mailing list immediately.
</div>"""


def _gen_subject(company: str) -> str:
    iso_week = date.today().isocalendar()[1]
    tmpl = random.choice(_SUBJECT_TEMPLATES)
    return tmpl.format(week=iso_week)


def _get_days_used() -> int:
    """Return age in days of the local Parquet file."""
    try:
        from shared.paths import PARQUET_FILE
        if PARQUET_FILE.exists():
            return int((time.time() - PARQUET_FILE.stat().st_mtime) / 86400)
    except Exception:
        pass
    return 0


def _get_signature() -> str:
    return """<table cellpadding="0" cellspacing="0" style="font-family:Calibri,Arial,sans-serif;font-size:12px;color:#333;line-height:1.4;">
<tr><td colspan="2" style="padding-bottom:8px;">
  <span style="color:#c0392b;font-size:11px;font-weight:600;">Remark: *For any important message, please copy to my superior, Mrs Jessie (Sale Manageress), at <a href="mailto:jessie@pudongprime.vn" style="color:#c0392b;">jessie@pudongprime.vn</a></span>
</td></tr>
<tr>
  <td style="padding-right:14px;vertical-align:top;width:120px;border-right:2px solid #f0a500;">
    <p style="margin:0 0 4px;font-size:11px;font-weight:700;color:#1a3a5c;">PUDONG PRIME GROUP</p>
    <p style="margin:0;font-size:10px;color:#666;">A member of<br><strong>JC TRANS</strong></p>
  </td>
  <td style="padding-left:14px;vertical-align:top;">
    <p style="margin:0;"><strong style="font-size:13px;color:#1a3a5c;">Nelson Huynh (Chinh)</strong></p>
    <p style="margin:0;color:#555;">Sales Team Leader</p>
    <p style="margin:6px 0 0;"><strong>Pudong Prime International Co Ltd</strong></p>
    <p style="margin:0;color:#555;">(Ho Chi Minh Branch)</p>
    <p style="margin:4px 0 0;font-size:11px;color:#555;">L'MAK The Signature, 147 &#8211; 147BIS Hai Ba Trung, Phuong Xuan Hoa, TP Ho Chi Minh</p>
    <p style="margin:2px 0;font-size:11px;">Phone: +84 28 36362111 ext. 239 | Cell: +84 931.301.014</p>
    <p style="margin:2px 0;font-size:11px;">E-mail: <a href="mailto:nelson@pudongprime.vn" style="color:#2563EB;">nelson@pudongprime.vn</a></p>
    <p style="margin:2px 0;font-size:11px;">Web-site: <a href="https://www.pudongprime.vn/vi" style="color:#2563EB;">https://www.pudongprime.vn/vi</a></p>
    <p style="margin:2px 0;font-size:11px;">Office: Vietnam | China | USA</p>
    <p style="margin:6px 0 0;font-weight:700;">JC TRANS ID: 155843</p>
    <p style="margin:0;font-weight:700;">FMC OTI License: 024060</p>
  </td>
</tr>
<tr><td colspan="2" style="padding-top:8px;border-top:1px solid #ddd;font-size:10px;color:#999;font-style:italic;">
  All transactions are subject to the Company's Standard Trading Conditions (a copy is available upon request),
  which in certain circumstances limits or excepts the Company's liability.
</td></tr>
</table>"""


def _build_full_html(
    rate_table_html: str,
    company: str,
    pic: str,
    iso_week: int,
    days_used: int,
) -> str:
    greeting = f"Dear {pic}," if pic and pic not in ("Sir/Madam", "") else "Dear Sir/Madam,"
    surcharge_link = (
        f'<a href="{SURCHARGE_URL}" '
        f'style="color:#2563EB;font-weight:600;text-decoration:none;" '
        f'target="_blank">&#x1F4CA; View Bunker &amp; Fuel Surcharge Schedule</a>'
    )
    signature = _get_signature()

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ margin:0; padding:0; font-family:Calibri,Arial,sans-serif; background:#f0f4f8; color:#333; font-size:13px; }}
  .wrapper {{ max-width:800px; margin:0 auto; background:#ffffff; }}
  .topbar {{ background:#1a3a5c; padding:6px 20px; text-align:right; }}
  .topbar span {{ color:#f0a500; font-size:11px; font-weight:700; letter-spacing:0.5px; }}
  .body {{ padding:22px 28px; line-height:1.65; }}
  .body p {{ margin:6px 0; }}
  .validity-bar {{
    background:#f8f9fa; border:1px solid #e2e8f0; border-radius:4px;
    padding:8px 14px; margin:14px 0; font-size:11px; color:#555;
  }}
  .validity-bar strong {{ color:#1a3a5c; }}
  .surcharge-bar {{
    background:#fffbeb; border:1px solid #fde68a; border-radius:4px;
    padding:8px 14px; margin:10px 0 14px; font-size:11px; color:#92400e;
  }}
  .cta {{ display:inline-block; background:#1a3a5c; color:#fff!important; padding:10px 24px;
          text-decoration:none; border-radius:4px; font-size:12px; font-weight:700; margin-top:16px; }}
  .pdf-note {{ font-size:11px; color:#666; margin-top:10px; padding:8px 12px;
               background:#fefce8; border-left:3px solid #f0a500; border-radius:3px; }}
  .sig-wrap {{ padding:18px 28px; border-top:3px solid #f0a500; background:#fafbfc; }}
</style>
</head>
<body>
<div class="wrapper">

  <!-- Minimal top bar with WEEK badge -->
  <div class="topbar">
    <span>NELSON WEEK {iso_week}</span>
  </div>

  <!-- Body -->
  <div class="body">
    <p>{greeting}</p>
    <p>We are pleased to offer our latest ocean freight rates from Vietnam to USA &amp; Canada for your reference.</p>

    <!-- Rate table -->
    {rate_table_html}

    <!-- Surcharge reference -->
    <div class="surcharge-bar">
      &#9888; Rates above include Bunker &amp; Fuel surcharges &mdash;
      {surcharge_link} to view the breakdown per carrier
    </div>

    <p style="margin-top:14px;">We look forward to the opportunity of serving your shipping needs.
    Please feel free to contact us for booking or any inquiries.</p>

    <!-- CTA -->
    <p style="text-align:center;margin-top:20px;">
      <a href="mailto:nelson@pudongprime.vn?subject=RE: Booking Inquiry WEEK {iso_week}" class="cta">Reply for Booking</a>
    </p>

    <!-- Company profile note -->
    <div class="pdf-note">
      Please find attached our <strong>Company Profile</strong> for your reference.
    </div>
  </div>

  <!-- Disclaimer (above signature) -->
  <div style="padding:0 28px;">
    {_DISCLAIMER_HTML}
  </div>

  <!-- Signature -->
  <div class="sig-wrap">
    {signature}
  </div>

</div>
</body>
</html>"""


def build_email_for_lead(lead: dict, markup: float = 20.0) -> dict:
    """
    Build full email HTML for a single lead, reading rates from local Parquet.

    Args:
        lead:   dict with keys: EMAIL, COMPANY, POL, DESTINATION, TIER, PIC (optional)
        markup: markup per container in USD (default 20)

    Returns:
        {
            "subject":    str,
            "html":       str,
            "row_count":  int,
            "is_blocked": bool,
            "days_used":  int,
            "warn_msg":   str,
        }
    """
    from email_engine.core.auto_rate_builder import build_rate_table_for_customer

    _pol_raw = str(lead.get("POL", "") or "").strip().upper()
    pol      = _pol_raw if _pol_raw and _pol_raw not in ("NAN", "NONE", "N/A") else "HPH"
    dest    = _normalize_destinations(str(lead.get("DESTINATION", "") or ""))
    company = str(lead.get("COMPANY", "") or "").strip()
    pic     = str(lead.get("PIC", "") or "").strip()

    result = build_rate_table_for_customer(pol=pol, destinations=dest, markup=markup)

    row_count   = result.get("total_rates", 0)
    is_blocked  = (row_count == 0)
    days_used   = _get_days_used()
    warn_msg    = ""

    if is_blocked:
        warn_msg = f"No rates found for {pol} → {dest}"
        html = f"<p>No current rates available for {pol} → {dest}.</p>"
    else:
        iso_week = date.today().isocalendar()[1]
        html = _build_full_html(
            rate_table_html=result["html"],
            company=company,
            pic=pic,
            iso_week=iso_week,
            days_used=days_used,
        )

    if days_used > 3:
        warn_msg = f"Parquet {days_used}d old — sync OneDrive"

    subject = _gen_subject(company)

    return {
        "subject":    subject,
        "html":       html,
        "row_count":  row_count,
        "is_blocked": is_blocked,
        "days_used":  days_used,
        "warn_msg":   warn_msg,
    }


# ── Quick smoke test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    lead = {
        "EMAIL":       "test@example.com",
        "COMPANY":     "Test Importer Co",
        "POL":         "HPH",
        "DESTINATION": "USLAX,USLGB,USNYC",
        "TIER":        "HOT",
        "PIC":         "",
    }
    r = build_email_for_lead(lead, markup=20)
    print(f"subject   : {r['subject']}")
    print(f"row_count : {r['row_count']}")
    print(f"is_blocked: {r['is_blocked']}")
    print(f"days_used : {r['days_used']}")
    print(f"warn_msg  : {r['warn_msg']}")
    print(f"HTML len  : {len(r['html'])}")
    # Write preview
    out = Path(__file__).parent / "_preview_email.html"
    out.write_text(r["html"], encoding="utf-8")
    print(f"Preview   : {out}")
