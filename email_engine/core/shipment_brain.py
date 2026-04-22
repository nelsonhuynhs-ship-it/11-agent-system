# -*- coding: utf-8 -*-
from __future__ import annotations
"""
shipment_brain.py — Shipment Intelligence Layer  v1.0
=======================================================
Reads incoming Outlook emails (already routed by main.py),
extracts shipment identifiers (HBL/BKG/Container), maps them to
lifecycle stages, updates shipment_state.json, and fires Telegram
alerts for risks (DELAY, CHANGE_VESSEL) and completed payments.

Architecture
------------
  Input  : Outlook Inbox (live + TEAM SUNNY subfolders)
  Config : shipment_patterns.yaml, customer_rules.json
  State  : shipment_state.json  (persistent, append-only updates)
  Output : Telegram alerts + log

Run via Windows Task Scheduler every 30 minutes, same window as main.py.

Usage:
    python shipment_brain.py
"""

import json, re, os, sys, logging, logging.handlers
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ─── Phase 2: Booking Pool imports (soft — scanner must not crash if absent) ──
try:
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent.parent / "Pricing_Engine"))
    from booking_parser import parse_booking_subject, parse_booking_body, detect_booking_mail
    from booking_pool_writer import append_booking_event
    _BOOKING_PARSER_OK = True
except Exception as _booking_import_err:
    _BOOKING_PARSER_OK = False
    logging.getLogger(__name__).warning(
        "booking_parser unavailable: %s", _booking_import_err
    )

import win32com.client
import yaml
import httpx           # For Telegram API

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent

# Config files live on OneDrive (master data). Resolve via shared.paths.
# Fallback to local if shared.paths unavailable (keeps module importable in tests).
try:
    import sys as _sys
    _sys.path.insert(0, str(PROJECT_ROOT.parent))
    from shared.paths import SHIPMENT_PATTERNS as _SP, CUSTOMER_RULES as _CR
    PATTERNS_FILE = _SP
    CUSTOMER_FILE = _CR
except Exception:
    PATTERNS_FILE = PROJECT_ROOT / "data" / "shipment_patterns.yaml"
    CUSTOMER_FILE = PROJECT_ROOT / "data" / "customer_rules.json"

# State file stays local (runtime, not synced cross-machine).
STATE_FILE      = PROJECT_ROOT / "data" / "shipment_state.json"
ORG_RULES_FILE  = BASE_DIR / "org_rules.json"
LOG_FILE        = BASE_DIR / "shipment_brain.log"

# ─── Telegram (reuse env vars or config) ──────────────────────────────────────
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ─── Outlook COM ──────────────────────────────────────────────────────────────
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
INBOX_SCAN_LIMIT = 150   # emails to scan per run from Inbox
PROCESSED_FLAG   = "BRAIN_PROCESSED"  # UserProperty name to mark done emails

# Ownership Detection
LEADERSHIP_EMAILS = {"nelson@pudongprime.vn", "sunny@pudongprime.vn", "jessie@pudongprime.vn"}
MENTEE_EMAILS = {"otis@pudongprime.vn", "jun@pudongprime.vn", "lina@pudongprime.vn", "jennie@pudongprime.vn", "johnny@pudongprime.vn", "blue@pudongprime.vn"}

# ─── Logging ──────────────────────────────────────────────────────────────────
_fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")
_fh  = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=500_000, backupCount=3, encoding="utf-8")
_fh.setFormatter(_fmt)
_sh  = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_fh, _sh])
log = logging.getLogger(__name__)

# ─── Time Guard ───────────────────────────────────────────────────────────────
from datetime import time as dtime
START_H, END_H = dtime(7, 30), dtime(18, 0)


# ==============================================================================
# 1. CONFIG LOADERS
# ==============================================================================

def load_patterns() -> dict:
    """Load shipment_patterns.yaml — identifier regex + lifecycle stages."""
    if not PATTERNS_FILE.exists():
        log.error("shipment_patterns.yaml not found at %s", PATTERNS_FILE)
        return {}
    with PATTERNS_FILE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_customers() -> dict:
    """Load customer_rules.json — customer groups, SLA, known identifiers."""
    if not CUSTOMER_FILE.exists():
        log.error("customer_rules.json not found at %s", CUSTOMER_FILE)
        return {}
    with CUSTOMER_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_org_rules() -> dict:
    """Load org_rules.json — department emails for mentee PIC detection."""
    if not ORG_RULES_FILE.exists():
        log.warning("org_rules.json not found — mentee assignment disabled")
        return {}
    with ORG_RULES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def detect_mentee_pic(email_participants: list[str], org_rules: dict) -> str:
    """Detect which Sales mentee is the PIC for this shipment.

    Logic: find the first participant that matches a mentee email in org_rules.
    Mentees are checked first (most specific), then mid_level.
    """
    if not org_rules:
        return ""
    lookup = org_rules.get("email_lookup", {})
    mentee_emails = set(lookup.get("mentee_emails", []))

    for email in email_participants:
        email_lo = email.lower().strip()
        if email_lo in mentee_emails:
            return email_lo
    return ""


def load_state() -> dict:
    """Load shipment_state.json — persistent lifecycle state per shipment."""
    if not STATE_FILE.exists():
        return {"shipments": {}, "last_updated": ""}
    with STATE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    """Write state back to shipment_state.json atomically."""
    state["last_updated"] = datetime.now().isoformat()
    tmp = STATE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    tmp.replace(STATE_FILE)


# ==============================================================================
# 2. IDENTIFIER EXTRACTION
# ==============================================================================

# Pre-compiled identifier regex patterns (from real email analysis)
_IDENTIFIER_PATTERNS = [
    # HBL — ONE/Hapag/CMA format: P + 3-letter port code + 7-12 digits
    ("HBL", re.compile(r'\b(P(?:NYC|SAV|HOU|DEN|CHS|SEA|OMA|YTO|ELP|MAN|LAX|OAK|BAL|SAV|SEA|ORD|ATL)\d{7,12})\b', re.I)),
    # HBL — Hapag MAPI
    ("HBL", re.compile(r'\b(HLCU[A-Z]{3}\d{9,})\b', re.I)),
    # HBL — ZIM
    ("HBL", re.compile(r'\b(ZIMU(?:HCM|HAI|SGN|HPH)\d{8,})\b', re.I)),
    # HBL — Yang Ming / Evergreen numeric
    ("HBL", re.compile(r'\b(HANG\d{8,12})\b', re.I)),
    # HBL — Evergreen ESLV
    ("HBL", re.compile(r'\b(ESLV[A-Z0-9]{5,15})\b', re.I)),
    # HBL — CMA/MSC Pelican-type
    ("HBL", re.compile(r'\b(PELP\d{7,12})\b', re.I)),
    # HBL — MSC
    ("HBL", re.compile(r'\b(MSC[A-Z]{2,6}\d{6,10})\b', re.I)),
    # BKG — "BKG 14380157" or "BKG SGNNNNNN"
    ("BKG", re.compile(r'\bBKG[\s#]*([A-Z0-9]{5,12})\b', re.I)),
    # BKG — EBKG prefix (Nafood style)
    ("BKG", re.compile(r'\bEBKG(\d{8,12})\b', re.I)),
    # BKG — SGN prefix
    ("BKG", re.compile(r'\b(SGN\d{7,10})\b', re.I)),
    # BKG — HANFG prefix
    ("BKG", re.compile(r'\b(HANFG\d{7,10})\b', re.I)),
    # Container — ISO standard CCCCNNNNNNN
    ("CTN", re.compile(r'\b([A-Z]{4}\d{7})\b', re.I)),
]

# Lifecycle stage keyword mappings (from trained dataset)
_STAGE_PATTERNS: list[tuple[str, list[str]]] = [
    ("BOOKING_CONFIRMED",  ["booking confirmation", "bkg confirmed", "confirmed //", "keep booking"]),
    ("SI_SUBMITTED",       ["si bkg", " si //", "shipping instruction"]),
    ("DRAFT_BL_ISSUED",    ["draft b/l", "draft bl", "draft b_l", "bill nháp"]),
    ("DRAFT_BL_CONFIRMED", ["confirm draft", "draft ok", "xác nhận draft"]),
    ("LOADED",             ["loaded on board", "đã lên tàu", "cargo loaded"]),
    ("ATD",                ["update atd", "atd__", "atd//", "vessel departed"]),
    ("DN_SENT",            ["dn __", " dn //", "debit //", "debit note", "giấy báo tiền"]),
    ("INVOICE_ISSUED",     ["invoice", "e-invoice", "xuất hóa đơn"]),
    ("PAYMENT_CONFIRMED",  ["payment received", "paid", "đã thanh toán", "xác nhận thanh toán", "đã nhận"]),
    ("ETA_UPDATE",         ["update eta", "eta update", "arrival notice"]),
    ("DELAY_NOTICE",       ["delay notice", "delay", "rollover", "postpone"]),
    ("CHANGE_VESSEL",      ["change vessel", "vessel change", "changed mother vessel", "rebooking"]),
]

# Risk levels
_RISK_MAP = {
    "CRITICAL": ["change vessel", "changed mother vessel", "urgent", "top priority", "poa"],
    "HIGH":     ["delay notice", "delay", "rollover", "amendment"],
    "MEDIUM":   ["postpone", "omit", "customs hold"],
}

# Lifecycle precedence (higher number = more advanced stage)
_STAGE_PRECEDENCE = {
    "BOOKING_CONFIRMED":   10,
    "SI_SUBMITTED":        20,
    "DRAFT_BL_ISSUED":     30,
    "DRAFT_BL_CONFIRMED":  35,
    "LOADED":              50,
    "ATD":                 60,
    "ETA_UPDATE":          65,
    "DN_SENT":             70,
    "INVOICE_ISSUED":      80,
    "PAYMENT_CONFIRMED":   100,
    # Risk stages (don't affect lifecycle order)
    "DELAY_NOTICE":        -1,
    "CHANGE_VESSEL":       -2,
}


# ─── Phase 2: Keep Space subject detector ─────────────────────────────────────
_KEEP_SPACE_SUBJ_RE = re.compile(r'^\s*\[KEEP\s+SPACE', re.I)


def _is_keep_space_subject(subj: str) -> bool:
    """Return True if subject starts with '[KEEP SPACE' marker."""
    return bool(_KEEP_SPACE_SUBJ_RE.match(subj or ""))


def extract_identifiers(text: str) -> dict[str, list[str]]:
    """Extract all shipment identifiers from a text string."""
    result: dict[str, list[str]] = {"HBL": [], "BKG": [], "CTN": []}
    text_u = text.upper()
    for id_type, pattern in _IDENTIFIER_PATTERNS:
        for m in pattern.finditer(text_u):
            val = m.group(1).strip()
            if len(val) >= 5 and val not in result[id_type]:
                result[id_type].append(val)
    return result


def detect_stages(text: str) -> list[str]:
    text_lo = text.lower()
    return [stage for stage, kws in _STAGE_PATTERNS if any(kw in text_lo for kw in kws)]


def detect_risk(text: str) -> Optional[str]:
    text_lo = text.lower()
    for level, kws in _RISK_MAP.items():
        if any(kw in text_lo for kw in kws):
            return level
    return None


def primary_id(ids: dict) -> str:
    """Return the primary identifier string for a shipment."""
    return (ids["HBL"] + ids["BKG"] + ids["CTN"] or ["UNKNOWN"])[0]


# ==============================================================================
# 3. CUSTOMER DETECTION
# ==============================================================================

def detect_customer(text: str, customers: dict) -> tuple[str, str, str]:
    """Match email text to a known customer. Returns (name, type, owner)."""
    text_lo = text.lower()
    for name, data in customers.get("customers", {}).items():
        # Match by keyword
        if name.lower() in text_lo:
            return name, data.get("type", "UNKNOWN")
        # Match by known sender domain
        for domain in data.get("email_domains", []):
            if domain.lower() in text_lo:
                return name, data.get("type", "UNKNOWN")
    return "UNKNOWN", "UNKNOWN"


# ?? Ownership helpers ??

def get_all_participants(mail_item) -> list[str]:
    participants = []
    sender = get_sender_smtp(mail_item)
    if sender:
        participants.append(sender)
    try:
        for i in range(1, mail_item.Recipients.Count + 1):
            recip = mail_item.Recipients.Item(i)
            try:
                addr = recip.PropertyAccessor.GetProperty(PR_SMTP_ADDRESS)
                if addr: participants.append(addr.strip().lower())
            except:
                addr = recip.Address or ""
                if "@" in addr: participants.append(addr.strip().lower())
    except:
        pass
    return participants


def determine_owner(customer, owner_from_rules, participants):
    if customer != "UNKNOWN" and owner_from_rules:
        return owner_from_rules
    for email in participants:
        if email.lower().strip() in MENTEE_EMAILS:
            return "mentee:" + email.split("@")[0]
    return "nelson"


# ==============================================================================
# 4. STATE MANAGEMENT
# ==============================================================================

def update_shipment_state(state: dict, shipment_id: str, stage: str,
                          customer: str, ctype: str, owner: str,
                          subject: str, sender: str, risk: Optional[str]) -> dict:
    """
    Update shipment lifecycle in state store.
    Only advances stage — never goes backward (uses precedence).
    Returns dict of changes made.
    """
    shipments = state.setdefault("shipments", {})
    now_str   = datetime.now().isoformat()
    changes   = {}

    if shipment_id not in shipments:
        shipments[shipment_id] = {
            "id":           shipment_id,
            "customer":     customer,
            "type":         ctype,
            "owner":        owner,
            "stage":        stage,
            "stage_history": [],
            "risks":        [],
            "created_at":   now_str,
            "updated_at":   now_str,
            "last_subject": subject[:80],
            "last_sender":  sender,
        }
        changes["new_shipment"] = True
        changes["stage"]        = stage
        log.info("NEW shipment: %s | %s [%s] | %s | %s", shipment_id, customer, owner, stage, subject[:50])
    else:
        rec = shipments[shipment_id]
        old_prec = _STAGE_PRECEDENCE.get(rec.get("stage", ""), 0)
        new_prec = _STAGE_PRECEDENCE.get(stage, 0)

        if new_prec > 0 and new_prec > old_prec:
            changes["stage_advanced"] = True
            changes["from_stage"]     = rec["stage"]
            changes["to_stage"]       = stage
            rec["stage"]              = stage
            rec["updated_at"]         = now_str
            rec["last_subject"]        = subject[:80]
            rec["last_sender"]         = sender
            log.info("ADVANCE: %s | %s → %s | %s",
                     shipment_id, changes["from_stage"], stage, subject[:50])

    # Append stage to history — with DEDUP guard
    rec = shipments[shipment_id]
    history = rec.setdefault("stage_history", [])
    
    # Only add if this exact (stage + sender + subject) combo doesn't already exist
    entry_key = (stage, sender.lower(), subject[:60].lower())
    existing_keys = set(
        (h.get("stage", ""), h.get("sender", "").lower(), h.get("subject", "").lower())
        for h in history
    )
    if entry_key not in existing_keys:
        history.append({
            "stage":   stage,
            "at":      now_str,
            "subject": subject[:60],
            "sender":  sender,
        })
    else:
        # Already recorded — skip duplicate
        pass

    # Track risks
    if risk:
        risk_entry = {"level": risk, "stage": stage, "at": now_str, "subject": subject[:60]}
        rec.setdefault("risks", []).append(risk_entry)
        changes["risk"] = risk
        log.warning("RISK [%s]: %s | %s | %s", risk, shipment_id, customer, subject[:50])

    return changes


# ==============================================================================
# 5. TELEGRAM NOTIFICATIONS
# ==============================================================================

def send_telegram(message: str) -> bool:
    """Send a Telegram message. Returns True on success."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        log.debug("Telegram not configured — skipping alert.")
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception as e:
        log.warning("Telegram send failed: %s", e)
        return False


def alert_risk(shipment_id: str, customer: str, ctype: str,
               risk_level: str, subject: str, sender: str) -> None:
    icons = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "🟡"}
    icon  = icons.get(risk_level, "⚠️")
    msg   = (
        f"{icon} <b>[{risk_level}] RISK DETECTED</b>\n"
        f"📦 <b>Shipment</b>: {shipment_id}\n"
        f"👤 <b>Customer</b>: {customer} ({ctype})\n"
        f"📧 <b>Subject</b>: {subject[:70]}\n"
        f"👤 <b>From</b>: {sender}\n"
        f"🕒 {datetime.now().strftime('%H:%M  %d/%m/%Y')}"
    )
    send_telegram(msg)


def alert_payment(shipment_id: str, customer: str, ctype: str,
                  subject: str, sender: str) -> None:
    msg = (
        f"✅ <b>PAYMENT CONFIRMED</b>\n"
        f"📦 <b>Shipment</b>: {shipment_id}\n"
        f"👤 <b>Customer</b>: {customer} ({ctype})\n"
        f"📧 <b>Subject</b>: {subject[:70]}\n"
        f"👤 <b>From</b>: {sender}\n"
        f"🕒 {datetime.now().strftime('%H:%M  %d/%m/%Y')}"
    )
    send_telegram(msg)


def alert_new_shipment(shipment_id: str, customer: str, ctype: str,
                       stage: str, subject: str) -> None:
    icon = "🆕"
    msg  = (
        f"{icon} <b>NEW SHIPMENT DETECTED</b>\n"
        f"📦 <b>ID</b>: {shipment_id}\n"
        f"👤 <b>Customer</b>: {customer} ({ctype})\n"
        f"📊 <b>Stage</b>: {stage}\n"
        f"📧 <b>Subject</b>: {subject[:70]}\n"
        f"🕒 {datetime.now().strftime('%H:%M  %d/%m/%Y')}"
    )
    send_telegram(msg)


# ==============================================================================
# 6. OUTLOOK HELPERS
# ==============================================================================

def connect_outlook():
    try:
        app = win32com.client.Dispatch("Outlook.Application")
        return app.GetNamespace("MAPI")
    except Exception as e:
        log.error("Outlook connection failed: %s", e)
        sys.exit(1)


def get_sender_smtp(mail_item) -> str:
    try:
        addr = mail_item.SenderEmailAddress
        if addr and "@" in addr and not addr.startswith("/O="):
            return addr.strip().lower()
    except: pass
    try:
        pa   = mail_item.Sender.PropertyAccessor
        smtp = pa.GetProperty(PR_SMTP_ADDRESS)
        if smtp: return smtp.strip().lower()
    except: pass
    return ""


def is_processed(mail_item) -> bool:
    """Check if this email was already processed by shipment_brain."""
    try:
        props = mail_item.UserProperties
        prop  = props.Find(PROCESSED_FLAG)
        return prop is not None and bool(prop.Value)
    except:
        return False


def mark_processed(mail_item) -> None:
    """Tag email with UserProperty so it won't be reprocessed."""
    try:
        prop = mail_item.UserProperties.Add(PROCESSED_FLAG, 6)  # 6 = olYesNo
        prop.Value = True
        mail_item.Save()
    except:
        pass  # Not critical if tagging fails


# ==============================================================================
# 7. MAIN SCAN ENGINE
# ==============================================================================

def scan_and_update(ns, state: dict, customers: dict) -> dict:
    """
    Scan Inbox + TEAM SUNNY subfolders for new emails,
    extract shipment data, update state, fire alerts.

    Returns dict with run statistics.
    """
    inbox  = ns.GetDefaultFolder(6)   # olFolderInbox
    items  = inbox.Items
    items.Sort("[ReceivedTime]", True)  # newest first

    total     = items.Count
    limit     = min(total, INBOX_SCAN_LIMIT)
    stats     = {"scanned": 0, "processed": 0, "new": 0, "advanced": 0,
                 "risks": 0, "payments": 0, "skipped": 0}

    log.info("=" * 60)
    log.info("Shipment Brain scan | Inbox: %d items | checking: %d", total, limit)
    log.info("=" * 60)

    index     = 1
    processed = 0

    while processed < limit:
        try:
            item = items[index]
        except:
            break

        if item.Class != 43:  # skip non-mail
            index += 1
            processed += 1
            continue

        # Skip already processed
        if is_processed(item):
            index += 1
            processed += 1
            stats["skipped"] += 1
            continue

        try:
            subject   = item.Subject     or ""
            sender    = get_sender_smtp(item)
            body_prev = (item.Body or "")[:400]
            full_text = f"{subject} {body_prev}"

            # ── Phase 2: Booking Pool detection ───────────────────────────
            # Runs BEFORE stage detection so booking events are always captured
            # even for mails that carry no standard lifecycle keywords.
            if _BOOKING_PARSER_OK:
                try:
                    _bk_subj = subject

                    # (A) Direct booking: subject has BKG number + route
                    if detect_booking_mail(_bk_subj):
                        _parsed = parse_booking_subject(_bk_subj)
                        # Pull SI/CY from full body for richer record
                        _body_full = getattr(item, "Body", "") or ""
                        _body_parsed = parse_booking_body(_body_full)
                        _parsed.update(_body_parsed)

                        _bk_sender = ""
                        try:
                            _bk_sender = item.SenderEmailAddress or ""
                        except Exception:
                            pass

                        append_booking_event(
                            event_type="booking_received",
                            booking_data=_parsed,
                            mail_id=getattr(item, "EntryID", ""),
                            sender=_bk_sender,
                            received=getattr(item, "ReceivedTime", None),
                        )

                    # (B) Keep Space request: "[KEEP SPACE ...]" subject, no BKG yet
                    elif _is_keep_space_subject(_bk_subj):
                        _parsed = parse_booking_subject(_bk_subj)
                        _parsed["bkg_no"] = ""  # no BKG assigned yet

                        _bk_sender = ""
                        try:
                            _bk_sender = item.SenderEmailAddress or ""
                        except Exception:
                            pass

                        append_booking_event(
                            event_type="keep_space_request",
                            booking_data=_parsed,
                            mail_id=getattr(item, "EntryID", ""),
                            sender=_bk_sender,
                            received=getattr(item, "ReceivedTime", None),
                        )

                    # (C) SI request template — "Pls kindly send your SI and VGM"
                    _body_lo = (getattr(item, "Body", "") or "").lower()
                    if "kindly send your si" in _body_lo:
                        _parsed_si = parse_booking_subject(_bk_subj)
                        if _parsed_si.get("bkg_no"):
                            _body_full_si = getattr(item, "Body", "") or ""
                            _body_parsed_si = parse_booking_body(_body_full_si)
                            append_booking_event(
                                event_type="si_request_48h",
                                booking_data={**_parsed_si, **_body_parsed_si},
                                mail_id=getattr(item, "EntryID", ""),
                                sender=getattr(item, "SenderEmailAddress", ""),
                                received=getattr(item, "ReceivedTime", None),
                            )

                except Exception as _bk_err:
                    log.debug("Booking Pool hook error (non-fatal): %s", _bk_err)
            # ── End Booking Pool detection ─────────────────────────────────

            # Extract identifiers
            ids   = extract_identifiers(full_text)
            pid   = primary_id(ids)
            if pid == "UNKNOWN":
                mark_processed(item)
                index += 1
                processed += 1
                stats["skipped"] += 1
                continue

            # Detect stages and risk
            stages    = detect_stages(full_text)
            risk      = detect_risk(full_text)
            customer, ctype, owner_from_rules = detect_customer(full_text, customers)

            if not stages and not risk:
                mark_processed(item)
                index += 1
                processed += 1
                stats["skipped"] += 1
                continue

            stats["processed"] += 1

            # Determine owner
            participants = get_all_participants(item)
            owner = determine_owner(customer, owner_from_rules, participants)

            # Update state for each detected stage
            for stage in stages:
                changes = update_shipment_state(
                    state, pid, stage, customer, ctype, owner, subject, sender, risk
                )

                if changes.get("new_shipment") and stage not in ("DELAY_NOTICE", "CHANGE_VESSEL"):
                    stats["new"] += 1
                    if ctype == "DIRECT":  # Alert for DIRECT customers only
                        alert_new_shipment(pid, customer, ctype, stage, subject)

                if changes.get("stage_advanced"):
                    stats["advanced"] += 1

                # PAYMENT alert → always notify
                if stage == "PAYMENT_CONFIRMED":
                    stats["payments"] += 1
                    alert_payment(pid, customer, ctype, subject, sender)

                # RISK alert
                if risk:
                    stats["risks"] += 1
                    alert_risk(pid, customer, ctype, risk, subject, sender)
                    risk = None  # Alert once per email

            # ── CNEE Milestone hook ────────────────────────────────────────
            # Fires after all stages are detected for this email.
            # ATD/LOADED detected → attempt to compose Outlook Draft for CNEE.
            if any(s in {"ATD", "LOADED"} for s in stages):
                try:
                    from email_engine.core.cnee_milestone import on_atd_detected
                    on_atd_detected(item, stages, ids, sender)
                except Exception as _milestone_err:
                    log.error("cnee_milestone hook failed: %s", _milestone_err)
            # ── End CNEE Milestone hook ────────────────────────────────────

            mark_processed(item)

        except Exception as e:
            log.debug("Error processing item %d: %s", index, e)

        index     += 1
        processed += 1
        stats["scanned"] += 1

    # ── Flush CNEE Milestone Telegram summary ──────────────────────────────
    # Sends one consolidated message at end of scan (not per-email spam).
    try:
        from email_engine.core.cnee_milestone import flush_telegram_summary
        flush_telegram_summary()
    except Exception:
        pass
    # ── End flush ──────────────────────────────────────────────────────────

    return stats


# ==============================================================================
# 8. ENTRY POINT
# ==============================================================================

def main() -> None:
    # Time guard — only run within working hours
    now = datetime.now().time()
    if not (START_H <= now <= END_H):
        log.info("Outside window (%s–%s). Time: %s. Exiting.",
                 START_H.strftime("%H:%M"), END_H.strftime("%H:%M"),
                 now.strftime("%H:%M"))
        return

    log.info("Shipment Brain starting @ %s", datetime.now().strftime("%Y-%m-%d %H:%M"))

    # Load configs
    patterns  = load_patterns()
    customers = load_customers()
    state     = load_state()

    if not customers:
        log.error("No customer rules loaded. Check customer_rules.json.")
        return

    log.info("Loaded %d customers | %d known shipments in state",
             len(customers.get("customers", {})),
             len(state.get("shipments", {})))

    # Connect Outlook
    ns = connect_outlook()

    # Run scan
    stats = scan_and_update(ns, state, customers)

    # Persist state
    save_state(state)

    # ── Phase 5-merged: time-based SI 48h alert ─────────────────────────────
    # Same shipment-monitoring domain, just different data source (xlsm).
    # Merged 2026-04-22 per Nelson architecture review: 1 sub-job for the
    # entire shipment lifecycle (event-driven + time-driven).
    si_stats = {"alerts_sent": 0, "rows_checked": 0}
    try:
        import importlib.util
        _si_script = PROJECT_ROOT.parent / "scripts" / "si-48h-alert.py"
        if _si_script.exists():
            _spec = importlib.util.spec_from_file_location("si_48h_alert_module", _si_script)
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            si_result = _mod.run_alert(dry_run=False)
            if si_result.get("status") == "ok":
                si_stats["alerts_sent"] = si_result.get("alerts_sent", 0)
                si_stats["rows_checked"] = si_result.get("rows_checked", 0)
            elif si_result.get("status") == "error":
                log.warning("SI 48h alert error: %s", si_result.get("error"))
    except Exception as _si_err:
        log.warning("SI 48h alert skipped: %s", _si_err)

    # Summary
    log.info("=" * 60)
    log.info("DONE | Scanned: %d | New: %d | Advanced: %d | "
             "Risks: %d | Payments: %d | Skipped: %d | SI-alerts: %d/%d",
             stats["scanned"], stats["new"], stats["advanced"],
             stats["risks"], stats["payments"], stats["skipped"],
             si_stats["alerts_sent"], si_stats["rows_checked"])
    log.info("State: %d shipments tracked | %s",
             len(state.get("shipments", {})), STATE_FILE)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
