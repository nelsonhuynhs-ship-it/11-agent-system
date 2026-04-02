# -*- coding: utf-8 -*-
"""
email_rate_router.py — Rate & Send Email Endpoints
====================================================
Replaces desktop GUI (CustomTkinter) with WebApp-accessible API.

Uses DuckDB engine (28x faster than Pandas) — no blocking, RAM-efficient.
Sends via Office 365 SMTP — no Outlook COM required.

Endpoints:
  GET  /api/email-rate/customers          — Customer list for autocomplete
  POST /api/email-rate/preview            — Build HTML rate table preview
  POST /api/email-rate/send               — Send rate email via SMTP
  GET  /api/email-rate/config             — Default config (ports, pols, etc.)
  ── Campaign (Sprint 14) ──
  GET  /api/email-rate/campaign/prospects  — CNEE list with filters
  GET  /api/email-rate/campaign/stats      — Campaign statistics
  POST /api/email-rate/campaign/preview    — Campaign email preview with rates
  POST /api/email-rate/campaign/send       — Send campaign email + log
"""
from __future__ import annotations

import logging
import json
import csv
import smtplib
import ssl
import os
import uuid
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

log = logging.getLogger("nelson.email_rate")

# ── Paths ──────────────────────────────────────────────────────────────────────
_ENGINE_TEST    = Path(__file__).parent.parent.parent
_PARQUET_FILE   = _ENGINE_TEST / "Pricing_Engine" / "data" / "Cleaned_Master_History.parquet"
_CUSTOMER_RULES = _ENGINE_TEST / "email_engine" / "data" / "customer_rules.json"
_PORT_MAP_FILE  = _ENGINE_TEST / "email_engine" / "data" / "Port_Code_Mapping_Final.xlsx"
_CONFIG_XLSX    = _ENGINE_TEST / "email_engine" / "data" / "config.xlsx"
_CNEE_MASTER    = _ENGINE_TEST / "email_engine" / "data" / "cnee_master.xlsx"
_EMAIL_LOG      = _ENGINE_TEST / "email_engine" / "logs" / "email_log.csv"
_COMPANY_PDF    = _ENGINE_TEST / "email_engine" / "assets" / "PUDONG PRIME PROFILE.pdf"

router = APIRouter(prefix="/api/email-rate", tags=["Email Rate"])

# ── DuckDB singleton ───────────────────────────────────────────────────────────
_freight_db = None

def _get_db():
    global _freight_db
    if _freight_db is None:
        sys_path = str(_ENGINE_TEST)
        import sys
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        from db.duckdb_engine import FreightDB
        _freight_db = FreightDB(_PARQUET_FILE)
    return _freight_db

# ── Caches ─────────────────────────────────────────────────────────────────────
_customer_cache: dict | None = None
_port_map_cache: dict | None = None
_config_cache:   dict | None = None

def _load_customers() -> dict:
    global _customer_cache
    if _customer_cache is not None:
        return _customer_cache
    if not _CUSTOMER_RULES.exists():
        return {}
    with open(_CUSTOMER_RULES, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    _customer_cache = data.get("customers", data) if "customers" in data else data
    return _customer_cache

def _load_port_map() -> dict:
    global _port_map_cache
    if _port_map_cache is not None:
        return _port_map_cache
    if not _PORT_MAP_FILE.exists():
        _port_map_cache = {}
        return {}
    df = pd.read_excel(_PORT_MAP_FILE)
    df.columns = df.columns.str.strip()
    _port_map_cache = {}
    for _, row in df.iterrows():
        code = str(row.get("PortCode", "")).strip().upper()
        name = str(row.get("PortName", "")).strip()
        if code and name:
            _port_map_cache[code] = name.split(",")[0].strip()
    return _port_map_cache

def _load_config() -> dict:
    """Load email template config from config.xlsx (openpyxl — preserves HTML in cells)."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    defaults = {
        "from_name": "Nelson Freight",
        "from_email": os.getenv("SMTP_USER", ""),
        "SUBJECTTEMPLATES": "Plan Ahead | Asia–US Ocean Freight This Week | What Importers Need to Know | Asia to US/CA Freight Outlook | This Week | Rates & Space Visibility | Your Weekly Asia–US Freight Brief | Current Ocean Freight Levels | Asia Export to USA | Weekly Planning View",
        "SUBJECTSUFFIX": "NELSON",
        "PREHEADER": "A concise view of current rates, capacity, and near-term planning conditions | Key insights to support your Asia–US freight decisions this week",
        "SIGNATURE": "",
        "INTROTEXT": "Pls find the best rate update below:",
        "CLOSINGTEXT": "Please do not hesitate to contact us for further clarification.",
        "intro_default": "Dear {pic},\n\nPlease find below our latest ocean freight rates for your reference.",
        "closing_default": "Please do not hesitate to contact us.\n\nBest regards,\nNelson",
    }
    if not _CONFIG_XLSX.exists():
        _config_cache = defaults
        return _config_cache
    try:
        import openpyxl as _opxl
        wb = _opxl.load_workbook(str(_CONFIG_XLSX), data_only=True)
        ws = wb.active
        config = defaults.copy()
        for row in ws.iter_rows(max_col=2, values_only=True):
            key = str(row[0] or "").strip().upper()
            val = row[1]
            if key and key != "KEY" and val is not None:
                config[key] = str(val).strip()
        wb.close()
        _config_cache = config
    except Exception as e:
        log.warning("Could not load config.xlsx: %s", e)
        _config_cache = defaults
    return _config_cache

import random as _random

def _gen_subject(cfg: dict, company: str = "") -> str:
    """
    Random subject từ SUBJECTTEMPLATES + suffix NELSON WEEK {ISO}.
    Format: '{template} // NELSON WEEK 14'
    """
    templates_raw = cfg.get("SUBJECTTEMPLATES", "")
    templates = [t.strip() for t in templates_raw.split("|") if t.strip()]
    base = _random.choice(templates) if templates else "Ocean Freight Rates Update"
    suffix = cfg.get("SUBJECTSUFFIX", "NELSON").strip()
    iso_week = date.today().isocalendar()[1]
    return f"{base} // {suffix} WEEK {iso_week}"

def _build_preheader_html(cfg: dict) -> str:
    """Hidden preheader text for email clients (inbox preview line)."""
    preheaders_raw = cfg.get("PREHEADER", "")
    preheaders = [p.strip() for p in preheaders_raw.split("|") if p.strip()]
    text = _random.choice(preheaders) if preheaders else ""
    if not text:
        return ""
    return (
        f'<span style="display:none!important;visibility:hidden;opacity:0;'
        f'color:transparent;height:0;width:0;overflow:hidden;mso-hide:all;">'
        f'{text}</span>'
    )

def _get_signature(cfg: dict) -> str:
    """Full HTML signature — from config or Nelson's real signature."""
    sig = cfg.get("SIGNATURE", "")
    if sig and sig.strip():
        return sig
    # Fallback: Nelson's real signature (matches his Outlook signature)
    return """
<table cellpadding="0" cellspacing="0" style="font-family:Calibri,Arial,sans-serif;font-size:12px;color:#333;line-height:1.4;">
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
    <p style="margin:4px 0 0;font-size:11px;color:#555;">L'MAK The Signature, 147 – 147BIS Hai Ba Trung, Phuong Xuan Hoa, TP Ho Chi Minh</p>
    <p style="margin:2px 0;font-size:11px;">Phone: +84 28 36362111 ext. 239 | Cell: +84 931.301.014</p>
    <p style="margin:2px 0;font-size:11px;">E-mail: <a href="mailto:nelson@pudongprime.vn" style="color:#2563EB;">nelson@pudongprime.vn</a></p>
    <p style="margin:2px 0;font-size:11px;">Web-site: <a href="https://www.pudongprime.vn/vi" style="color:#2563EB;">https://www.pudongprime.vn/vi</a></p>
    <p style="margin:2px 0;font-size:11px;">Office: Vietnam | China | USA</p>
    <p style="margin:6px 0 0;font-weight:700;">JC TRANS ID: 155843</p>
    <p style="margin:0;font-weight:700;">FMC OTI License: 024060</p>
  </td>
</tr>
<tr><td colspan="2" style="padding-top:8px;border-top:1px solid #ddd;font-size:10px;color:#999;font-style:italic;">
  All transactions are subject to the Company's Standard Trading Conditions (a copy is available upon request), which in certain circumstances limits or excepts the Company's liability.
</td></tr>
</table>"""


# ── VIA Region Mapping ────────────────────────────────────────────────────────
_VIA_REGION = {
    # US West Coast
    "USLAX": "WC", "USLGB": "WC", "USOAK": "WC", "USSEA": "WC", "USTIW": "WC",
    "USPDX": "WC", "USSFO": "WC",
    # US East Coast
    "USNYC": "EC", "USEWR": "EC", "USSAV": "EC", "USBAL": "EC", "USBOS": "EC",
    "USPHL": "EC", "USCHS": "EC", "USNOR": "EC", "USWIL": "EC",
    # US Gulf
    "USHOU": "GULF", "USMIA": "GULF", "USJAX": "GULF", "USMOB": "GULF",
    "USMSY": "GULF", "USTPA": "GULF",
    # Canada West Coast
    "CAVAN": "CAWC", "CAVCT": "CAWC",
    # Canada East Coast
    "CAHAL": "CAEC", "CATOR": "CAEC", "CAMON": "CAEC", "CAYUL": "CAEC",
}

_VIA_REGION_LABEL = {
    "WC": "US WEST COAST", "EC": "US EAST COAST", "GULF": "US GULF",
    "IPI/WC": "US INLAND (VIA WEST COAST)", "IPI/EC": "US INLAND (VIA EAST COAST)",
    "IPI/GULF": "US INLAND (VIA GULF)",
    "CAWC": "CANADA WEST COAST", "CAEC": "CANADA EAST COAST",
}

def _get_via_region(pod: str, place: str = "") -> str:
    """Determine VIA region from POD code or place name."""
    pod_up = pod.strip().upper()
    # Direct POD match
    if pod_up in _VIA_REGION:
        return _VIA_REGION[pod_up]
    # If has place (inland), determine IPI region from the port it transits through
    if place and place.strip():
        # If POD is a port, it's the transit port for IPI
        if pod_up in _VIA_REGION:
            base = _VIA_REGION[pod_up]
            return f"IPI/{base}"
        # Default IPI logic by known inland cities
        place_up = place.strip().upper()
        wc_cities = {"DENVER", "SALT LAKE", "PHOENIX", "LAS VEGAS", "RENO", "BOISE", "PORTLAND"}
        ec_cities = {"CHICAGO", "DETROIT", "COLUMBUS", "PITTSBURGH", "CLEVELAND", "MINNEAPOLIS", "INDIANAPOLIS"}
        gulf_cities = {"DALLAS", "HOUSTON", "AUSTIN", "SAN ANTONIO", "MEMPHIS", "NASHVILLE", "ATLANTA", "KANSAS"}
        for city in wc_cities:
            if city in place_up:
                return "IPI/WC"
        for city in ec_cities:
            if city in place_up:
                return "IPI/EC"
        for city in gulf_cities:
            if city in place_up:
                return "IPI/GULF"
    return "OTHER"

# ── HTML table CSS ─────────────────────────────────────────────────────────────
_TABLE_CSS = """
<style>
  .tg { border-collapse: collapse; width: 100%; font-family: Calibri, Arial, sans-serif; font-size: 13px; }
  .tg th { background: #1a3a5c; color: #fff; padding: 7px 10px; text-align: center; border: 1px solid #ccc; }
  .tg td { padding: 6px 10px; border: 1px solid #ddd; text-align: center; }
  .tg tr:nth-child(even) td { background: #f5f8fc; }
  .amt  { font-weight: 700; color: #1a3a5c; }
  .val  { font-size: 11px; color: #666; }
  .exp-warn { color: #c0392b; font-weight: 600; }
  .exp-ok   { color: #27ae60; }
  .fresh-ok   { display:inline-block; font-size:10px; color:#27ae60; background:#eafaf1; border-radius:3px; padding:1px 5px; margin-left:4px; }
  .fresh-warn { display:inline-block; font-size:10px; color:#e67e22; background:#fef9e7; border-radius:3px; padding:1px 5px; margin-left:4px; }
  .fresh-old  { display:inline-block; font-size:10px; color:#c0392b; background:#fdedec; border-radius:3px; padding:1px 5px; margin-left:4px; }
  .fallback-note { font-size:11px; color:#888; font-style:italic; margin-bottom:6px; }
</style>
"""

# ── Helpers ────────────────────────────────────────────────────────────────────
DEFAULT_POLS  = ["HPH", "HCM"]
DEFAULT_DESTS = "USLAX,USLGB,USTIW,CAVAN,USNYC,USEWR,USSAV,USCHS,CAHAL,USDAL,USDEN,USSEA,USCHI"

def _resolve_pol(raw: str) -> list[str]:
    cleaned = raw.strip().upper()
    if not cleaned or cleaned in ("NAN", "NONE", "", "N/A"):
        return list(DEFAULT_POLS)
    return [cleaned]

def _query_rates_with_fallback(db, pol: str, search_term: str, dest: str) -> tuple[pd.DataFrame, int]:
    """
    Query rates với fallback: 7d → 30d → 60d → 90d.
    Returns (dataframe, days_used).
    Ưu tiên data mới nhất (7d) trước, chỉ mở rộng nếu empty.
    """
    for days in [7, 30, 60, 90]:
        try:
            df = db.query_rates(pol=pol, pod=search_term, days=days)
            if df.empty and search_term != dest:
                df = db.query_rates(pol=pol, pod=dest, days=days)
            if not df.empty:
                return df, days
        except Exception as e:
            log.warning("DuckDB query error POL=%s dest=%s days=%d: %s", pol, dest, days, e)
    return pd.DataFrame(), 30

def _fmt_validity(eff_val, exp_val) -> tuple[str, str]:
    """Return (display_text, css_class) for validity cell."""
    today = date.today()

    def _parse(v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            return pd.to_datetime(v, errors="coerce")
        except Exception:
            return None

    eff = _parse(eff_val)
    exp = _parse(exp_val)

    eff_ok = eff is not None and not pd.isnull(eff)
    exp_ok = exp is not None and not pd.isnull(exp)

    css = "val"
    if exp_ok:
        css = "val exp-warn" if exp.date() <= today else "val exp-ok"

    def _fmt(ts):
        return f"{ts.day}{ts.strftime('%b')}"

    if eff_ok and exp_ok:
        if eff.month == exp.month and eff.year == exp.year:
            text = f"{eff.day}-{_fmt(exp)}"
        else:
            text = f"{_fmt(eff)}-{_fmt(exp)}"
    elif exp_ok:
        text = f"-{_fmt(exp)}"
    elif eff_ok:
        text = f"{_fmt(eff)}-"
    else:
        text = "—"

    return text, css

def _freshness_badge(eff_val) -> str:
    """Return HTML badge cho freshness: xanh ≤7d, cam 8–30d, đỏ >30d."""
    if eff_val is None:
        return ""
    try:
        eff = pd.to_datetime(eff_val, errors="coerce")
        if pd.isnull(eff):
            return ""
        days_ago = (date.today() - eff.date()).days
        if days_ago <= 7:
            return f'<span class="fresh-ok">{days_ago}d ago</span>'
        elif days_ago <= 30:
            return f'<span class="fresh-warn">{days_ago}d ago ⚠</span>'
        else:
            return f'<span class="fresh-old">{days_ago}d ago !</span>'
    except Exception:
        return ""

def _build_html_table(rows: list[dict], days_used: int = 30) -> tuple[str, bool, str]:
    """
    Build HTML rate table grouped by VIA region, min 3 carriers per POD, best price highlighted.
    Returns (html, is_blocked, warning_message).
    """
    if not rows:
        return "<p><em>No rates found for this route.</em></p>", False, ""

    expired_carriers = []
    warn_carriers    = []
    today            = date.today()

    # ── Assign VIA region to each row ──
    for r in rows:
        r["via_region"] = _get_via_region(r.get("pod", ""), r.get("place", ""))

    # ── Find best (cheapest) 40HC price per POD for highlighting ──
    pod_best_40 = {}
    for r in rows:
        pod_key = r.get("pod", "") + "|" + r.get("place", "")
        price = r.get("rate_40") or 999999
        if pod_key not in pod_best_40 or price < pod_best_40[pod_key]:
            pod_best_40[pod_key] = price

    # ── Track expiry (None/NaT exp = assumed valid, NOT expired) ──
    for r in rows:
        exp_raw = r.get("exp")
        carrier = r.get("carrier", "")
        if exp_raw is None:
            continue  # No expiry date = valid
        try:
            exp_ts = pd.to_datetime(exp_raw, errors="coerce")
            if pd.isnull(exp_ts):
                continue  # Unparseable = treat as valid
            if exp_ts.date() < today:
                expired_carriers.append(carrier)
            elif exp_ts.date() == today:
                warn_carriers.append(carrier)
        except Exception:
            pass

    # ── Group rows by VIA region ──
    region_order = ["WC", "EC", "GULF", "IPI/WC", "IPI/EC", "IPI/GULF", "CAWC", "CAEC", "OTHER"]
    from collections import defaultdict
    by_region = defaultdict(list)
    for r in rows:
        by_region[r["via_region"]].append(r)

    # ── Build HTML ──
    lines = [_TABLE_CSS]

    if days_used > 30:
        lines.append(
            f'<p class="fallback-note">⚠ Best available rates from last {days_used} days '
            f'(no data within 30 days — please update Parquet)</p>'
        )

    for region in region_order:
        region_rows = by_region.get(region, [])
        if not region_rows:
            continue

        region_label = _VIA_REGION_LABEL.get(region, region)
        lines.append(
            f'<div style="margin:14px 0 6px;padding:6px 10px;background:#1a3a5c;color:#fff;'
            f'font-size:12px;font-weight:700;letter-spacing:0.5px;border-radius:3px;">'
            f'{region_label}</div>'
        )

        lines.append('<table class="tg"><thead><tr>')
        for col in ["POL", "POD", "VIA", "Carrier", "20GP (USD)", "40HC (USD)", "Valid"]:
            lines.append(f'<th>{col}</th>')
        lines.append('</tr></thead><tbody>')

        # Sort by POD then price ascending
        region_rows.sort(key=lambda x: (x.get("pod", ""), x.get("rate_40") or 999999))

        for r in region_rows:
            val_text, val_css = _fmt_validity(r.get("eff"), r.get("exp"))
            carrier = r.get("carrier", "")

            r20 = f"${r.get('rate_20', 0):,.0f}" if r.get('rate_20') else "—"
            r40 = f"${r.get('rate_40', 0):,.0f}" if r.get('rate_40') else "—"

            # Best price highlighting
            pod_key = r.get("pod", "") + "|" + r.get("place", "")
            is_best = (r.get("rate_40") or 999999) == pod_best_40.get(pod_key, -1)
            best_style = ' style="background:#e8f5e9;font-weight:700;"' if is_best else ''

            lines.append(f"""<tr{best_style}>
  <td>{r.get('pol','')}</td>
  <td>{r.get('pod','')}</td>
  <td style="font-size:11px;color:#666;">{region}</td>
  <td><strong>{carrier}</strong></td>
  <td class="amt">{r20}</td>
  <td class="amt">{r40}</td>
  <td class="{val_css}">{val_text}</td>
</tr>""")

        lines.append('</tbody></table>')

    # Legend
    lines.append(
        '<p style="font-size:10px;color:#888;margin-top:8px;">'
        '<span style="display:inline-block;width:12px;height:12px;background:#e8f5e9;'
        'border:1px solid #c8e6c9;border-radius:2px;vertical-align:middle;margin-right:4px;"></span>'
        ' Best price per route | Rates subject to GRI/PSS/Local Charges | Valid at time of quotation</p>'
    )

    # Never block — let Nelson preview and decide. Show warning only.
    is_blocked = False
    warn_msg   = ""
    if expired_carriers:
        warn_msg = f"⚠️ Some rates may be outdated ({', '.join(set(expired_carriers))}) — review before sending"
    elif warn_carriers:
        warn_msg = f"⚠️ Rates expiring today — {', '.join(set(warn_carriers))}"

    return "\n".join(lines), is_blocked, warn_msg

def _plain_to_html(text: str) -> str:
    """
    Convert plain text to HTML preserving:
    - Line breaks (\\n → <br>)
    - Bullets (• or - at start)
    - **bold** markers → <strong>
    - ALL CAPS words kept as-is (natural rendering)
    - Blank lines → paragraph breaks
    """
    import re
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Convert **bold** markers to <strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    lines = text.split("\n")
    html_parts = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        is_bullet = stripped.startswith("•") or stripped.startswith("- ") or stripped.startswith("* ")

        if is_bullet:
            if not in_list:
                html_parts.append("<ul style='margin:4px 0; padding-left:18px;'>")
                in_list = True
            item = stripped.lstrip("•").lstrip("-").lstrip("*").strip()
            html_parts.append(f"<li style='margin:2px 0;'>{item}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if not stripped:
                html_parts.append("<br>")
            else:
                html_parts.append(f"<p style='margin:4px 0;'>{stripped}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)

# ══════════════════════════════════════════════════════════════════════════════
# Request / Response Models
# ══════════════════════════════════════════════════════════════════════════════

class PreviewRequest(BaseModel):
    customer:     str
    pic:          str
    pol:          str = ""
    destinations: str = DEFAULT_DESTS
    markup:       float = 20.0
    intro:        str = ""
    closing:      str = ""
    subject:      str = ""

class SendRequest(PreviewRequest):
    to_email:  str
    cc_emails: List[str] = []

# ══════════════════════════════════════════════════════════════════════════════
# 1. GET /api/email-rate/customers
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/customers")
def get_customers():
    """Return customer list for autocomplete dropdown."""
    customers = _load_customers()
    if isinstance(customers, dict):
        result = [
            {
                "name": k,
                "pol": v.get("pol", "HPH") if isinstance(v, dict) else "HPH",
                "destinations": v.get("destinations", DEFAULT_DESTS) if isinstance(v, dict) else DEFAULT_DESTS,
                "pic": v.get("pic", "") if isinstance(v, dict) else "",
                "email": v.get("email", "") if isinstance(v, dict) else "",
            }
            for k, v in customers.items()
        ]
    elif isinstance(customers, list):
        result = [
            {
                "name": c.get("name", ""),
                "pol": c.get("pol", "HPH"),
                "destinations": c.get("destinations", DEFAULT_DESTS),
                "pic": c.get("pic", ""),
                "email": c.get("email", ""),
            }
            for c in customers
        ]
    else:
        result = []

    return {"customers": result, "total": len(result)}

# ══════════════════════════════════════════════════════════════════════════════
# 2. GET /api/email-rate/config
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/config")
def get_email_config():
    """Return default config for the Rate & Send form."""
    cfg = _load_config()
    return {
        "default_pols": DEFAULT_POLS,
        "default_destinations": DEFAULT_DESTS,
        "subject_templates": cfg.get("subject_templates", []),
        "intro_default": cfg.get("intro_default", ""),
        "closing_default": cfg.get("closing_default", ""),
        "from_name": cfg.get("from_name", "Nelson Freight"),
        "from_email": cfg.get("from_email", os.getenv("SMTP_USER", "")),
    }

# ══════════════════════════════════════════════════════════════════════════════
# 3. POST /api/email-rate/preview
# ══════════════════════════════════════════════════════════════════════════════

def _extract_rates_from_df(df: pd.DataFrame, pol: str, dest: str, markup: float, all_rows: list, days_used: int):
    """
    Extract best rates per carrier per container type từ DataFrame,
    merge vào all_rows. Dùng chung cho preview và campaign/preview.
    """
    for ct, ct_key in [("40HQ", "rate_40"), ("20GP", "rate_20")]:
        # S14A: Mở rộng type_variants để bắt mọi variant thực tế trong Parquet
        # 40HQ variants: "40HQ", "40HC", "40HG", "40' HC", "HC40", "40H"
        # 20GP variants: "20GP", "20DC", "20", "20'", "20' GP", "GP20"
        if ct == "40HQ":
            type_variants = ["40HQ", "40HC", "40HG", "40H", "HC40", "40' HC", "40'HC"]
        else:
            type_variants = ["20GP", "20DC", "20", "20'", "20' GP", "GP20", "20'GP"]

        if "Container_Type" not in df.columns:
            sub = pd.DataFrame()
        else:
            ct_upper = df["Container_Type"].str.strip().str.upper()
            # Match exact OR contains (để bắt "40' HIGH CUBE", "20 GP" etc.)
            exact_mask   = ct_upper.isin(type_variants)
            contain_mask = ct_upper.str.contains(
                r"^40.*(H[CQG]|HIGH)" if ct == "40HQ" else r"^20.*(GP|DC|GEN)",
                na=False, regex=True
            )
            sub = df[exact_mask | contain_mask].copy()

        if sub.empty:
            continue

        # Strongly prefer non-expired rates
        today_ts = pd.Timestamp(date.today())
        if "Exp" in sub.columns:
            exp_parsed = pd.to_datetime(sub["Exp"], errors="coerce")
            is_expired = exp_parsed < today_ts
            # Add sort key: expired=1, valid/no-exp=0
            sub = sub.copy()
            sub["_expired"] = is_expired.fillna(False).astype(int)
        else:
            sub = sub.copy()
            sub["_expired"] = 0

        # Sort: non-expired first, then by price ascending
        sub = sub.sort_values(["_expired", "Amount"])
        best_per_carrier = sub.drop_duplicates(subset=["Carrier"], keep="first")
        # Remove any fully-expired carriers if we have valid alternatives
        valid_carriers = best_per_carrier[best_per_carrier["_expired"] == 0]
        if not valid_carriers.empty:
            best_per_carrier = valid_carriers

        for _, row in best_per_carrier.head(3).iterrows():
            carrier = str(row.get("Carrier", ""))
            existing = next(
                (r for r in all_rows if r["carrier"] == carrier and r["place"] == dest),
                None
            )
            amount = float(row.get("Amount", 0)) + markup

            if existing:
                existing[ct_key] = amount
                if ct_key == "rate_40":
                    existing["eff"]       = row.get("Eff")
                    existing["exp"]       = row.get("Exp")
                    existing["days_used"] = days_used
            else:
                all_rows.append({
                    "pol":       pol,
                    "pod":       str(row.get("POD", dest)),
                    "place":     dest,
                    "carrier":   carrier,
                    "rate_20":   amount if ct == "20GP" else None,
                    "rate_40":   amount if ct == "40HQ" else None,
                    "eff":       row.get("Eff"),
                    "exp":       row.get("Exp"),
                    "days_used": days_used,
                })

@router.post("/preview")
def preview_rate_email(req: PreviewRequest):
    """
    Query DuckDB for rates and build HTML email preview.
    Returns full HTML + expiry status without sending.
    Auto-fallback: 30d → 60d → 90d nếu không có data.
    """
    db       = _get_db()
    port_map = _load_port_map()
    pol_list = _resolve_pol(req.pol)
    dests    = [d.strip() for d in req.destinations.split(",") if d.strip()]

    all_rows: list    = []
    max_days_used     = 0   # S14A fix: init=0 để detect "không có data gì cả" vs "30d ok"
    route_debug: dict = {}  # {dest: "mapped → search_term (Xd)"} — debug POD mapping

    for dest in dests:
        search_term = port_map.get(dest.upper(), dest)
        mapped      = search_term != dest.upper()

        found_any = False
        for pol in pol_list:
            df, days_used = _query_rates_with_fallback(db, pol, search_term, dest)
            if df.empty and search_term != dest:
                df, days_used = _query_rates_with_fallback(db, pol, dest, dest)

            if not df.empty:
                found_any = True
                max_days_used = max(max_days_used, days_used)
                mapping_note  = f"→ '{search_term}' (mapped)" if mapped else "(direct match)"
                route_debug[dest] = f"✅ {dest} {mapping_note}: {len(df)} rows, best in {days_used}d"
                _extract_rates_from_df(df, pol, dest, req.markup, all_rows, days_used)

        # Inland/unknown dest: auto-expand to major ports so customer gets rates
        if not found_any:
            fallback_ports = ["USLAX", "USLGB", "USNYC", "USSAV"]
            expanded_rows_before = len(all_rows)
            for fb_port in fallback_ports:
                fb_search = port_map.get(fb_port, fb_port)
                for pol in pol_list:
                    df, days_used = _query_rates_with_fallback(db, pol, fb_search, fb_port)
                    if not df.empty:
                        max_days_used = max(max_days_used, days_used)
                        _extract_rates_from_df(df, pol, fb_port, req.markup, all_rows, days_used)
            if len(all_rows) > expanded_rows_before:
                route_debug[dest] = f"⚡ {dest} (inland/unknown) → expanded to major ports: LAX,LGB,NYC,SAV"
            else:
                route_debug[dest] = f"❌ {dest} → no data (tried direct + major ports, 90d)"

    # S14A fix: nếu không có data nào cả, set days về 90 để hiện warning đúng
    if max_days_used == 0:
        max_days_used = 90

    # Dùng max days_used cho fallback note trong table
    html_table, is_blocked, warn_msg = _build_html_table(all_rows, max_days_used)

    # Build full email HTML with professional template v2
    intro_html   = _plain_to_html(req.intro) if req.intro else \
                   f"<p>Dear {req.pic},</p><p>Please find our latest ocean freight rates below.</p>"
    closing_html = _plain_to_html(req.closing) if req.closing else \
                   "<p>Best regards,<br>Nelson</p>"

    _cfg_sub = _load_config()
    subject = req.subject or _gen_subject(_cfg_sub, req.customer)

    email_html = _build_professional_html(all_rows, intro_html, closing_html, "professional", max_days_used)

    return {
        "subject":     subject,
        "html":        email_html,
        "row_count":   len(all_rows),
        "is_blocked":  is_blocked,
        "warn_msg":    warn_msg,
        "pol_queried": pol_list,
        "dests_found": len(set(r["place"] for r in all_rows)),
        "days_used":   max_days_used,
        "route_debug": route_debug,
    }

# ══════════════════════════════════════════════════════════════════════════════
# 4. POST /api/email-rate/send
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/send")
def send_rate_email(req: SendRequest):
    """
    Build rate email and send via Office 365 SMTP.
    Blocked if any rate is expired (same as GUI).
    """
    # Build preview first
    preview = preview_rate_email(req)

    if preview["is_blocked"]:
        raise HTTPException(
            status_code=400,
            detail=f"Send blocked: {preview['warn_msg']}. Update rates before sending."
        )

    if not req.to_email:
        raise HTTPException(status_code=400, detail="to_email is required")

    # ── Queue for Outlook COM (no SMTP needed) ──
    queue = _load_queue()
    item = {
        "id": str(uuid.uuid4())[:8],
        "to": req.to_email,
        "cc": req.cc_emails,
        "subject": preview["subject"],
        "html_body": preview["html"],
        "company": "",
        "campaign_id": "",
        "attach_pdf": True,
        "status": "pending",
        "queued_at": datetime.now().isoformat(),
        "sent_at": None,
    }
    queue.append(item)
    _save_queue(queue)
    log.info("Email queued for %s | subject: %s | id: %s", req.to_email, preview["subject"], item["id"])

    return {
        "status":     "queued",
        "queue_id":   item["id"],
        "to":         req.to_email,
        "cc":         req.cc_emails,
        "subject":    preview["subject"],
        "rows_sent":  preview["row_count"],
        "timestamp":  datetime.now().isoformat(),
        "message":    "Email queued — Outlook agent will send shortly",
    }


# ══════════════════════════════════════════════════════════════════════════════
# ── CAMPAIGN ENDPOINTS (Sprint 14) ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

_cnee_cache: pd.DataFrame | None = None
_sent_emails_cache: set | None = None   # emails sent via webapp (from email_log.csv)

def _load_sent_emails() -> set:
    """
    Load set of emails that have been sent via webapp (from email_log.csv).
    This is the SOURCE OF TRUTH for sent status — overrides cnee_master.xlsx ALREADY_SENT.
    Cache is intentionally NOT applied here so stats always reflect latest sends.
    """
    if not _EMAIL_LOG.exists():
        return set()
    try:
        df = pd.read_csv(_EMAIL_LOG)
        if "email" in df.columns and "status" in df.columns:
            sent = df[df["status"] == "sent"]["email"].str.strip().str.lower()
            return set(sent.tolist())
        return set()
    except Exception as e:
        log.warning("Could not load email_log.csv: %s", e)
        return set()


def _load_cnee() -> pd.DataFrame:
    """Load CNEE master database (cached)."""
    global _cnee_cache
    if _cnee_cache is not None:
        return _cnee_cache
    if not _CNEE_MASTER.exists():
        log.warning("cnee_master.xlsx not found at %s", _CNEE_MASTER)
        return pd.DataFrame()
    df = pd.read_excel(_CNEE_MASTER)
    df.columns = df.columns.str.strip()
    # Normalize
    for col in ["EMAIL", "COMPANY", "CNEE_PIC", "POL", "DESTINATION", "CAMPAIGN_ID", "ALREADY_SENT"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
    _cnee_cache = df
    return _cnee_cache


def _merge_sent_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge email_log.csv sent status into CNEE dataframe.
    email_log.csv WINS over cnee_master.xlsx ALREADY_SENT.
    """
    sent_emails = _load_sent_emails()
    if not sent_emails:
        return df
    df = df.copy()
    mask = df["EMAIL"].str.lower().isin(sent_emails)
    df.loc[mask, "ALREADY_SENT"] = "Y"
    # Also store the last sent date from log if available
    if _EMAIL_LOG.exists():
        try:
            log_df = pd.read_csv(_EMAIL_LOG)
            if "email" in log_df.columns and "timestamp" in log_df.columns:
                last_sent = (
                    log_df[log_df["status"] == "sent"]
                    .sort_values("timestamp")
                    .drop_duplicates("email", keep="last")
                    .set_index("email")["timestamp"]
                )
                for email_addr, ts in last_sent.items():
                    idx = df["EMAIL"].str.lower() == email_addr.lower()
                    df.loc[idx, "LAST_SENT_DATE"] = ts[:10] if len(str(ts)) >= 10 else ts
        except Exception:
            pass
    return df


def _build_professional_html(rows: list[dict], intro_html: str, closing_html: str,
                              template: str = "professional", days_used: int = 30) -> str:
    """Build full email HTML with professional template v2 + real Nelson signature + PDF attachment note."""
    cfg = _load_config()
    table_html, _, _ = _build_html_table(rows, days_used)
    preheader = _build_preheader_html(cfg)
    signature = _get_signature(cfg)
    reply_email = os.getenv("SMTP_USER", "nelson@pudongprime.vn")
    iso_week = date.today().isocalendar()[1]
    validity_date = date.today().strftime("%d %b %Y")

    if template == "plain":
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Calibri,Arial,sans-serif; font-size:13px; color:#222; max-width:900px; margin:0 auto; padding:16px;">
{preheader}
{intro_html}
<br>
{table_html}
<br>
{closing_html}
<br>
<hr style="border:none;border-top:1px solid #ddd;margin:16px 0;">
{signature}
</body></html>"""

    # ── Professional Template v2 — Region-grouped, Nelson branding ──
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin:0; padding:0; font-family:Calibri,Arial,sans-serif; background:#f0f4f8; color:#333; }}
  .wrapper {{ max-width:800px; margin:0 auto; background:#ffffff; }}
  .header {{ background:#1a3a5c; padding:18px 28px; }}
  .header-inner {{ display:flex; justify-content:space-between; align-items:center; }}
  .header h1 {{ color:#fff; margin:0; font-size:17px; font-weight:700; letter-spacing:0.3px; }}
  .header-sub {{ color:#a8c8e8; margin:3px 0 0; font-size:10.5px; }}
  .header-week {{ color:#f0a500; font-size:12px; font-weight:700; }}
  .body {{ padding:20px 28px; font-size:13px; line-height:1.6; }}
  .body p {{ margin:6px 0; }}
  .rate-section {{ margin:16px 0; }}
  .validity-bar {{ background:#f8f9fa; border:1px solid #e2e8f0; border-radius:4px; padding:8px 14px; margin-bottom:14px; font-size:11px; color:#555; }}
  .validity-bar strong {{ color:#1a3a5c; }}
  .cta {{ display:inline-block; background:#1a3a5c; color:#fff!important; padding:10px 24px; text-decoration:none; border-radius:4px; font-size:12px; font-weight:700; margin-top:16px; }}
  .cta:hover {{ background:#2c5f8a; }}
  .pdf-note {{ font-size:11px; color:#666; margin-top:10px; padding:8px 12px; background:#fefce8; border-left:3px solid #f0a500; border-radius:3px; }}
  .sig-wrap {{ padding:18px 28px; border-top:3px solid #f0a500; background:#fafbfc; }}
</style>
</head>
<body>
<div class="wrapper">
  <!-- Header -->
  <div class="header">
    <table width="100%" cellpadding="0" cellspacing="0"><tr>
      <td>
        <h1 style="color:#fff;margin:0;font-size:17px;font-weight:700;">Nelson Freight — NVOCC</h1>
        <p style="color:#a8c8e8;margin:3px 0 0;font-size:10.5px;">Vietnam &rarr; USA &amp; Canada | FMC OTI License: 024060</p>
      </td>
      <td style="text-align:right;">
        <span style="color:#f0a500;font-size:12px;font-weight:700;">WEEK {iso_week}</span>
      </td>
    </tr></table>
  </div>

  {preheader}

  <!-- Body -->
  <div class="body">
    {intro_html}

    <!-- Validity bar -->
    <div class="validity-bar">
      <strong>Rate validity:</strong> As of {validity_date} — Subject to GRI/PSS/Local Charges &amp; space availability
    </div>

    <!-- Rate Tables (grouped by region) -->
    <div class="rate-section">
      {table_html}
    </div>

    {closing_html}

    <!-- CTA -->
    <p style="text-align:center;margin-top:20px;">
      <a href="mailto:{reply_email}?subject=RE: Booking Inquiry" class="cta">Reply for Booking</a>
    </p>

    <!-- PDF attachment note -->
    <div class="pdf-note">
      Please find attached our <strong>Company Profile</strong> for your reference.
    </div>
  </div>

  <!-- Signature -->
  <div class="sig-wrap">
    {signature}
  </div>
</div>
</body></html>"""


def _log_campaign_send(email: str, company: str, campaign: str, subject: str, status: str, rows: int):
    """Append send log to email_log.csv."""
    try:
        file_exists = _EMAIL_LOG.exists()
        _EMAIL_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(_EMAIL_LOG, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "email", "company", "campaign_id", "subject", "status", "rows_sent"])
            writer.writerow([
                datetime.now().isoformat(),
                email, company, campaign, subject, status, rows
            ])
    except Exception as e:
        log.warning("Failed to log campaign send: %s", e)


# ── Campaign Models ───────────────────────────────────────────────────────────

class CampaignPreviewRequest(BaseModel):
    email:        str
    company:      str
    pic:          str = ""
    pol:          str = ""
    destinations: str = DEFAULT_DESTS
    markup:       float = 20.0
    intro:        str = ""
    closing:      str = ""
    subject:      str = ""
    template:     str = "professional"   # "professional" | "plain"

class CampaignSendRequest(CampaignPreviewRequest):
    campaign_id:  str = ""
    cc_emails:    List[str] = []

class CampaignBulkSendRequest(BaseModel):
    emails:       List[str]          # emails to send to (from cnee_master)
    markup:       float = 20.0
    template:     str = "professional"
    campaign_id:  str = ""
    cc_emails:    List[str] = []
    subject:      str = ""           # blank = auto NELSON WEEK format per email


# ══════════════════════════════════════════════════════════════════════════════
# 5. GET /api/email-rate/campaign/prospects
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/campaign/prospects")
def get_campaign_prospects(
    campaign: str = Query("", description="Filter by campaign ID"),
    search: str = Query("", description="Search company or email"),
    sent_status: str = Query("all", description="all | sent | not_sent"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
):
    """Return CNEE prospects with filtering and pagination."""
    df = _load_cnee()
    if df.empty:
        return {"prospects": [], "total": 0, "campaigns": [], "page": 1, "page_size": page_size}

    # Merge actual sent status from email_log.csv (source of truth)
    df = _merge_sent_status(df)

    # Available campaigns
    campaigns = sorted(df["CAMPAIGN_ID"].unique().tolist()) if "CAMPAIGN_ID" in df.columns else []

    # Filter by campaign
    if campaign:
        df = df[df["CAMPAIGN_ID"].str.upper() == campaign.upper()]

    # Filter by sent status
    if sent_status == "sent":
        df = df[df["ALREADY_SENT"].str.upper() == "Y"]
    elif sent_status == "not_sent":
        df = df[df["ALREADY_SENT"].str.upper() != "Y"]

    # Search
    if search:
        s = search.lower()
        mask = df["COMPANY"].str.lower().str.contains(s, na=False) | \
               df["EMAIL"].str.lower().str.contains(s, na=False)
        df = df[mask]

    total = len(df)

    # Paginate
    start = (page - 1) * page_size
    page_df = df.iloc[start:start + page_size]

    prospects = []
    for _, row in page_df.iterrows():
        prospects.append({
            "email":        str(row.get("EMAIL", "")),
            "company":      str(row.get("COMPANY", "")),
            "pic":          str(row.get("CNEE_PIC", "")),
            "pol":          str(row.get("POL", "HPH")),
            "destination":  str(row.get("DESTINATION", "")),
            "carrier":      str(row.get("CARRIER", "")),
            "total_shipment": int(row.get("TOTAL_SHIPMENT", 0)) if pd.notna(row.get("TOTAL_SHIPMENT")) else 0,
            "campaign_id":  str(row.get("CAMPAIGN_ID", "")),
            "already_sent": str(row.get("ALREADY_SENT", "N")),
            "last_sent":    str(row.get("LAST_SENT_DATE", "")),
            "email_quality": int(row.get("EMAIL_QUALITY_SCORE", 0)) if pd.notna(row.get("EMAIL_QUALITY_SCORE")) else 0,
        })

    return {
        "prospects": prospects,
        "total": total,
        "campaigns": campaigns,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. GET /api/email-rate/campaign/stats
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/campaign/stats")
def get_campaign_stats():
    """Campaign overview statistics — sent count from email_log.csv (source of truth)."""
    df = _load_cnee()
    if df.empty:
        return {"total": 0, "sent": 0, "not_sent": 0, "campaigns": {}}

    # Always merge live sent status
    df = _merge_sent_status(df)

    total = len(df)
    sent = len(df[df["ALREADY_SENT"].str.upper() == "Y"]) if "ALREADY_SENT" in df.columns else 0
    not_sent = total - sent

    # Per campaign stats
    campaign_stats = {}
    if "CAMPAIGN_ID" in df.columns:
        for cid, grp in df.groupby("CAMPAIGN_ID"):
            c_sent = len(grp[grp["ALREADY_SENT"].str.upper() == "Y"]) if "ALREADY_SENT" in grp.columns else 0
            campaign_stats[str(cid)] = {
                "total": len(grp),
                "sent": c_sent,
                "not_sent": len(grp) - c_sent,
            }

    return {
        "total": total,
        "sent": sent,
        "not_sent": not_sent,
        "campaigns": campaign_stats,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. POST /api/email-rate/campaign/preview
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/campaign/preview")
def campaign_preview(req: CampaignPreviewRequest):
    """
    Build campaign email preview with rate table for a CNEE prospect.
    Auto-fallback: 30d → 60d → 90d nếu không có data.
    """
    db       = _get_db()
    port_map = _load_port_map()
    pol_list = _resolve_pol(req.pol)

    # Resolve destinations — use prospect's destinations or default main ports
    raw_dests = req.destinations.strip() if req.destinations.strip() else DEFAULT_DESTS
    dests = [d.strip() for d in raw_dests.split(",") if d.strip()]

    all_rows: list    = []
    max_days_used     = 0   # S14A fix: init=0 để detect "no data at all"
    route_debug: dict = {}

    for dest in dests:
        search_term = port_map.get(dest.upper(), dest)
        mapped      = search_term != dest.upper()

        found_any = False
        for pol in pol_list:
            df, days_used = _query_rates_with_fallback(db, pol, search_term, dest)
            if df.empty and search_term != dest:
                df, days_used = _query_rates_with_fallback(db, pol, dest, dest)

            if not df.empty:
                found_any = True
                max_days_used = max(max_days_used, days_used)
                mapping_note  = f"→ '{search_term}' (mapped)" if mapped else "(direct match)"
                route_debug[dest] = f"✅ {dest} {mapping_note}: {len(df)} rows, best in {days_used}d"
                _extract_rates_from_df(df, pol, dest, req.markup, all_rows, days_used)

        # Inland/unknown dest: auto-expand to major ports
        if not found_any:
            fallback_ports = ["USLAX", "USLGB", "USNYC", "USSAV"]
            expanded_before = len(all_rows)
            for fb_port in fallback_ports:
                fb_search = port_map.get(fb_port, fb_port)
                for pol in pol_list:
                    df, days_used = _query_rates_with_fallback(db, pol, fb_search, fb_port)
                    if not df.empty:
                        max_days_used = max(max_days_used, days_used)
                        _extract_rates_from_df(df, pol, fb_port, req.markup, all_rows, days_used)
            if len(all_rows) > expanded_before:
                route_debug[dest] = f"⚡ {dest} (inland/unknown) → expanded to major ports: LAX,LGB,NYC,SAV"
            else:
                route_debug[dest] = f"❌ {dest} → no data (tried direct + major ports, 90d)"

    # S14A fix: nếu không có data nào, set 90d để hiện đúng warning
    if max_days_used == 0:
        max_days_used = 90

    _, is_blocked, warn_msg = _build_html_table(all_rows, max_days_used)

    # Build intro / closing
    pic_name = req.pic if req.pic else "Sir/Madam"
    intro_html = _plain_to_html(req.intro) if req.intro else \
        f"<p>Dear {pic_name},</p><p>We are pleased to offer our latest ocean freight rates from Vietnam to USA &amp; Canada for your reference.</p>"
    closing_html = _plain_to_html(req.closing) if req.closing else \
        "<p>We look forward to the opportunity of serving your shipping needs. Please feel free to contact us for booking or any inquiries.</p>"

    # Build full email
    email_html = _build_professional_html(all_rows, intro_html, closing_html, req.template, max_days_used)

    # Auto-generate subject
    _cfg_sub = _load_config()
    subject = req.subject or _gen_subject(_cfg_sub, req.company)

    return {
        "subject":     subject,
        "html":        email_html,
        "row_count":   len(all_rows),
        "is_blocked":  is_blocked,
        "warn_msg":    warn_msg,
        "pol_queried": pol_list,
        "dests_found": len(set(r["place"] for r in all_rows)),
        "template":    req.template,
        "days_used":   max_days_used,
        "route_debug": route_debug,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 8. POST /api/email-rate/campaign/send
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/campaign/send")
def campaign_send(req: CampaignSendRequest):
    """Send campaign email to a CNEE prospect and log the send."""
    preview = campaign_preview(req)

    if preview["is_blocked"]:
        raise HTTPException(
            status_code=400,
            detail=f"Send blocked: {preview['warn_msg']}. Update rates before sending."
        )

    if not req.email:
        raise HTTPException(status_code=400, detail="email is required")

    # ── Queue for Outlook COM (no SMTP needed) ──
    queue = _load_queue()
    item = {
        "id": str(uuid.uuid4())[:8],
        "to": req.email,
        "cc": req.cc_emails,
        "subject": preview["subject"],
        "html_body": preview["html"],
        "company": req.company,
        "campaign_id": req.campaign_id,
        "attach_pdf": True,
        "status": "pending",
        "queued_at": datetime.now().isoformat(),
        "sent_at": None,
    }
    queue.append(item)
    _save_queue(queue)
    log.info("Campaign email queued for %s (%s) | id: %s", req.email, req.company, item["id"])

    return {
        "status":      "queued",
        "queue_id":    item["id"],
        "to":          req.email,
        "company":     req.company,
        "cc":          req.cc_emails,
        "subject":     preview["subject"],
        "rows_sent":   preview["row_count"],
        "campaign_id": req.campaign_id,
        "template":    req.template,
        "timestamp":   datetime.now().isoformat(),
        "message":     "Email queued — Outlook agent will send shortly",
    }


# ══════════════════════════════════════════════════════════════════════════════
# 9. POST /api/email-rate/campaign/bulk-send
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/campaign/bulk-send")
def campaign_bulk_send(req: CampaignBulkSendRequest):
    """
    Bulk send campaign emails to multiple CNEE prospects at once.
    Looks up each email in cnee_master.xlsx to get company/pic/pol/destination.
    Returns per-email results including any failures.
    """
    if not req.emails:
        raise HTTPException(status_code=400, detail="emails list is empty")

    smtp_host = os.getenv("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        raise HTTPException(status_code=500, detail="SMTP not configured. Set SMTP_USER and SMTP_PASS in .env")

    # Load CNEE data
    df = _load_cnee()
    df = _merge_sent_status(df)

    email_lower_map = {e.lower().strip(): e for e in req.emails}
    targets = df[df["EMAIL"].str.lower().isin(email_lower_map.keys())]

    if targets.empty:
        raise HTTPException(status_code=404, detail="No prospects found for the given emails")

    cfg       = _load_config()
    from_name = cfg.get("from_name", "Nelson Freight")
    sent_ok   = []
    errors    = []

    try:
        ctx = ssl.create_default_context()
        smtp_conn = smtplib.SMTP(smtp_host, smtp_port)
        smtp_conn.ehlo()
        smtp_conn.starttls(context=ctx)
        smtp_conn.login(smtp_user, smtp_pass)
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=401, detail="SMTP authentication failed. Check SMTP_USER/SMTP_PASS.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMTP connect failed: {e}")

    try:
        for _, prospect in targets.iterrows():
            email_addr  = str(prospect.get("EMAIL", "")).strip()
            company     = str(prospect.get("COMPANY", ""))
            pic         = str(prospect.get("CNEE_PIC", ""))
            pol         = str(prospect.get("POL", "HPH"))
            destination = str(prospect.get("DESTINATION", ""))
            campaign_id = str(prospect.get("CAMPAIGN_ID", req.campaign_id))

            try:
                prev_req = CampaignPreviewRequest(
                    email=email_addr,
                    company=company,
                    pic=pic,
                    pol=pol,
                    destinations=destination or DEFAULT_DESTS,
                    markup=req.markup,
                    intro="",
                    closing="",
                    subject=req.subject,
                    template=req.template,
                )
                preview = campaign_preview(prev_req)

                if preview["is_blocked"]:
                    errors.append({"email": email_addr, "company": company, "error": f"Blocked: {preview['warn_msg']}"})
                    continue

                msg = MIMEMultipart("mixed")
                msg["Subject"] = preview["subject"]
                msg["From"]    = f"{from_name} <{smtp_user}>"
                msg["To"]      = email_addr
                if req.cc_emails:
                    msg["Cc"] = ", ".join(req.cc_emails)
                msg.attach(MIMEText(preview["html"], "html", "utf-8"))

                # Attach company profile PDF
                if _COMPANY_PDF.exists():
                    try:
                        with open(_COMPANY_PDF, "rb") as pdf_file:
                            pdf_part = MIMEBase("application", "pdf")
                            pdf_part.set_payload(pdf_file.read())
                            encoders.encode_base64(pdf_part)
                            pdf_part.add_header("Content-Disposition", 'attachment; filename="Pudong Prime - Company Profile.pdf"')
                            msg.attach(pdf_part)
                    except Exception:
                        pass

                all_recip = [email_addr] + req.cc_emails
                smtp_conn.sendmail(smtp_user, all_recip, msg.as_string())

                _log_campaign_send(email_addr, company, campaign_id, preview["subject"], "sent", preview["row_count"])
                sent_ok.append({"email": email_addr, "company": company, "subject": preview["subject"], "status": "sent"})
                log.info("Bulk send OK: %s (%s)", email_addr, company)

            except Exception as e:
                log.warning("Bulk send error for %s: %s", email_addr, e)
                errors.append({"email": email_addr, "company": company, "error": str(e)})
    finally:
        try:
            smtp_conn.quit()
        except Exception:
            pass

    return {
        "sent":      len(sent_ok),
        "failed":    len(errors),
        "results":   sent_ok,
        "errors":    errors,
        "timestamp": datetime.now().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# ── EMAIL QUEUE — Outlook COM Integration ─────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
# WebApp queues emails here → Local agent polls → Sends via Outlook COM
# No SMTP Auth needed. No IT Admin approval needed.

_QUEUE_FILE = _ENGINE_TEST / "email_engine" / "data" / "email_queue.json"

def _load_queue() -> list:
    if not _QUEUE_FILE.exists():
        return []
    try:
        with open(_QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_queue(queue: list):
    _QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


class QueueEmailRequest(BaseModel):
    to_email: str
    cc_emails: List[str] = []
    subject: str
    html_body: str
    company: str = ""
    campaign_id: str = ""
    attach_pdf: bool = True


@router.post("/queue/add")
def queue_add_email(req: QueueEmailRequest):
    """Add email to queue — local Outlook agent will pick it up and send."""
    queue = _load_queue()
    item = {
        "id": str(uuid.uuid4())[:8],
        "to": req.to_email,
        "cc": req.cc_emails,
        "subject": req.subject,
        "html_body": req.html_body,
        "company": req.company,
        "campaign_id": req.campaign_id,
        "attach_pdf": req.attach_pdf,
        "status": "pending",
        "queued_at": datetime.now().isoformat(),
        "sent_at": None,
    }
    queue.append(item)
    _save_queue(queue)
    return {"status": "queued", "id": item["id"], "position": len([q for q in queue if q["status"] == "pending"])}


@router.get("/queue/pending")
def queue_get_pending():
    """Get all pending emails — called by local Outlook agent."""
    queue = _load_queue()
    pending = [q for q in queue if q["status"] == "pending"]
    return {"count": len(pending), "emails": pending}


@router.post("/queue/mark-sent/{email_id}")
def queue_mark_sent(email_id: str):
    """Mark email as sent — called by local agent after Outlook send."""
    queue = _load_queue()
    for item in queue:
        if item["id"] == email_id:
            item["status"] = "sent"
            item["sent_at"] = datetime.now().isoformat()
            _save_queue(queue)
            # Also log to email_log.csv
            _log_campaign_send(
                item["to"], item.get("company", ""), item.get("campaign_id", ""),
                item["subject"], "sent", 0
            )
            return {"status": "ok", "id": email_id}
    raise HTTPException(status_code=404, detail=f"Email {email_id} not found in queue")


@router.post("/queue/mark-failed/{email_id}")
def queue_mark_failed(email_id: str, error: str = "unknown"):
    """Mark email as failed — called by local agent on error."""
    queue = _load_queue()
    for item in queue:
        if item["id"] == email_id:
            item["status"] = "failed"
            item["error"] = error
            item["sent_at"] = datetime.now().isoformat()
            _save_queue(queue)
            return {"status": "ok", "id": email_id}
    raise HTTPException(status_code=404, detail=f"Email {email_id} not found in queue")


@router.get("/queue/history")
def queue_history(limit: int = 50):
    """Get recent email queue history (all statuses)."""
    queue = _load_queue()
    # Most recent first
    queue.sort(key=lambda x: x.get("queued_at", ""), reverse=True)
    return {"total": len(queue), "emails": queue[:limit]}
