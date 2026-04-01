# -*- coding: utf-8 -*-
"""
email_scanner.py — Outlook Email Scanner for Webapp
=====================================================
Scans Outlook folders (TEAM SUNNY / customer subfolders), extracts
shipment identifiers + lifecycle stages, and produces outlook_dataset.json.

This is the webapp-local copy of the scanner, adapted from email_engine.
Can run standalone or via Task Scheduler.

Usage:
    python email_scanner.py              # Full scan
    python email_scanner.py --quick      # Quick scan (last 20 per folder)

Output:
    ../email_data/outlook_dataset.json   (webapp-local copy)
    Also updates original at D:/NELSON/email_engine/outlook_dataset.json
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent                    # api/
WEBAPP_DIR = BASE_DIR.parent                        # webapp/ (Engine_test)
EMAIL_DATA_DIR = BASE_DIR / "email_data"
EMAIL_DATA_DIR.mkdir(exist_ok=True)

OUTPUT_JSON = EMAIL_DATA_DIR / "outlook_dataset.json"
LOG_FILE = EMAIL_DATA_DIR / "email_scanner.log"

# Original email_engine path (also write there for backward compat)
ORIGINAL_EMAIL_ENGINE = Path(r"D:\NELSON\email_engine")
ORIGINAL_DATASET = ORIGINAL_EMAIL_ENGINE / "outlook_dataset.json"

# ─── Logging ──────────────────────────────────────────────────────────────────
_fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s",
                         datefmt="%Y-%m-%d %H:%M:%S")
_fh = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=500_000, backupCount=3, encoding="utf-8")
_fh.setFormatter(_fmt)
_sh = logging.StreamHandler(sys.stdout)
_sh.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_fh, _sh])
log = logging.getLogger(__name__)

# ─── Target Folders ───────────────────────────────────────────────────────────
# customer_name → (group_type, [outlook_folder_names])
TARGET_FOLDERS = {
    # FWD / Coload
    "SIRI":          ("FWD",    ["SIRI LOG"]),
    "HML":           ("FWD",    ["HML"]),
    "PANDA":         ("FWD",    ["PANDA GROUP", "PANDA HN", "PANDA BN"]),
    # Direct customers
    "NAFOOD":        ("DIRECT", ["NAFOOD"]),
    "PT FOOD":       ("DIRECT", ["PT FOOD"]),
    "VINARES":       ("DIRECT", ["VINARES", "Vinares"]),
    "HER HUI WOOD":  ("DIRECT", ["HER HUI WOOD"]),
    "CREATIVE LIGHT":("DIRECT", ["CREATIVE LIGHT"]),
}

MAX_EMAILS_PER_FOLDER = 50
MAX_EMAILS_QUICK = 20
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"

# ─── Identifier Patterns ─────────────────────────────────────────────────────
ID_PATTERNS = [
    ("HBL", r'\b(P(?:NYC|SAV|HOU|DEN|CHS|SEA|OMA|YTO|ELP|MAN|LAX|OAK|BAL)\d{7,12})\b'),
    ("HBL", r'\b(HLCU[A-Z]{3}\d{9,})\b'),
    ("HBL", r'\b(ZIMU(?:HCM|HAI|SGN)\d{8,})\b'),
    ("HBL", r'\b(HANG\d{8,12})\b'),
    ("HBL", r'\b(ESLV[A-Z0-9]{5,15})\b'),
    ("HBL", r'\b(PELP\d{7,12})\b'),
    ("HBL", r'\b(MSC[A-Z]{2,6}\d{6,10})\b'),
    ("BKG", r'\bBKG[\s#]*([A-Z0-9]{6,12})\b'),
    ("BKG", r'\bEBKG(\d{8,12})\b'),
    ("BKG", r'\b(SGN\d{7,10})\b'),
    ("BKG", r'\b(HANFG\d{7,10})\b'),
    ("BKG", r'\b(HANFA\d{7,10})\b'),
    ("BKG", r'\b(HANFF\d{7,10})\b'),
    ("CONTAINER", r'\b([A-Z]{4}\d{7})\b'),
]

# ─── Lifecycle Stage Keywords ─────────────────────────────────────────────────
LIFECYCLE_STAGES = {
    "BOOKING_CONFIRMED": ["booking confirmation", "bkg confirmed", "confirmed //", "keep booking"],
    "SI_SUBMITTED":      ["si bkg", " si //", "shipping instruction", "si hang"],
    "DRAFT_BL_ISSUED":   ["draft b/l", "draft bl", "draft b_l", "bill nháp"],
    "DRAFT_BL_CONFIRMED":["confirm draft", "draft ok", "xác nhận draft"],
    "LOADED":            ["loaded on board", "đã lên tàu", "cargo loaded"],
    "ATD":               ["update atd", "atd__", " atd//", "vessel departed", "cfm atd"],
    "DN_SENT":           ["dn __", " dn //", "debit //", "debit note", "giấy báo tiền"],
    "INVOICE_ISSUED":    ["invoice", "e-invoice", "xuất hóa đơn"],
    "PAYMENT_CONFIRMED": ["payment received", "paid", "đã thanh toán", "xác nhận thanh toán", "đã nhận"],
    "ETA_UPDATE":        ["update eta", "eta update", "arrival notice"],
    "DELAY_NOTICE":      ["delay notice", "delay", "rollover", "postpone"],
    "CHANGE_VESSEL":     ["change vessel", "vessel change", "changed mother vessel", "rebooking"],
    "GATE_IN_CONFIRMED": ["container gated in", "cy gate in", "gate in"],
    "HBL_ISSUED":        ["hbl attached", "hbl issue", "hbl draft confirmed"],
    "SI_RECEIVED":       ["si confirmed", "si received"],
}

# ─── Risk Keywords ────────────────────────────────────────────────────────────
RISK_KEYWORDS = {
    "CRITICAL": ["urgent", "gấp", "asap", "top priority", "poa", "change vessel"],
    "HIGH":     ["delay", "rollover", "amendment", "si change", "delay notice"],
    "MEDIUM":   ["update atd", "vessel change", "omit", "customs hold"],
}

# ─── Trouble Keywords (for alert detection) ───────────────────────────────────
TROUBLE_KEYWORDS = [
    "delay", "roll", "custom hold", "document missing",
    "customs hold", "amendment", "rollover", "postpone",
    "short ship", "cargo damage", "container damage",
    "overweight", "seal broken",
]


# ==============================================================================
# OUTLOOK HELPERS
# ==============================================================================

def connect_outlook():
    """Connect to Outlook via COM automation."""
    try:
        import win32com.client
        app = win32com.client.Dispatch("Outlook.Application")
        ns = app.GetNamespace("MAPI")
        log.info("Connected to Outlook ✓")
        return ns
    except ImportError:
        log.error("win32com not available — install pywin32")
        return None
    except Exception as e:
        log.error("Cannot connect to Outlook: %s", e)
        return None


def get_sender_email(mail_item) -> str:
    """Extract SMTP email from mail item."""
    try:
        addr = mail_item.SenderEmailAddress
        if addr and "@" in addr and not addr.startswith("/O="):
            return addr.strip().lower()
    except:
        pass
    try:
        import win32com.client
        pa = mail_item.Sender.PropertyAccessor
        smtp = pa.GetProperty(PR_SMTP_ADDRESS)
        if smtp:
            return smtp.strip().lower()
    except:
        pass
    return ""


def find_folder_recursive(parent, target_name: str, depth=0):
    """Search for folder by name (case-insensitive) up to depth 6."""
    if depth > 6:
        return None
    try:
        for folder in parent.Folders:
            if folder.Name.strip().lower() == target_name.strip().lower():
                return folder
            found = find_folder_recursive(folder, target_name, depth + 1)
            if found:
                return found
    except:
        pass
    return None


def find_customer_folder(ns, folder_name: str):
    """Search for folder across all Outlook stores."""
    for store in ns.Stores:
        try:
            root = store.GetRootFolder()
            folder = find_folder_recursive(root, folder_name)
            if folder:
                log.info("  Found '%s' in store: %s", folder_name, store.DisplayName)
                return folder
        except:
            continue
    return None


# ==============================================================================
# EXTRACTION HELPERS
# ==============================================================================

def extract_identifiers(text: str) -> dict:
    """Extract HBL, BKG, CONTAINER from text."""
    result = {"HBL": [], "BKG": [], "CONTAINER": []}
    text_u = text.upper()
    for id_type, pat in ID_PATTERNS:
        for m in re.finditer(pat, text_u, re.IGNORECASE):
            val = m.group(1).strip()
            if len(val) >= 5 and val not in result[id_type]:
                result[id_type].append(val)
    return result


def detect_stages(subject: str, body: str) -> list[str]:
    """Detect lifecycle stages from email content."""
    combined = (subject + " " + body).lower()
    return [stage for stage, kws in LIFECYCLE_STAGES.items()
            if any(kw in combined for kw in kws)]


def detect_risks(subject: str, body: str) -> list[str]:
    """Detect risk keywords from email content."""
    combined = (subject + " " + body).lower()
    found = []
    for level, kws in RISK_KEYWORDS.items():
        for kw in kws:
            if kw in combined:
                found.append(f"{level}:{kw}")
    return found


def detect_trouble(subject: str, body: str) -> list[str]:
    """Detect trouble keywords for alert generation."""
    combined = (subject + " " + body).lower()
    return [kw for kw in TROUBLE_KEYWORDS if kw in combined]


def extract_route(text: str) -> str:
    """Extract route like HPH-KANSAS CITY from email subject."""
    m = re.search(
        r'\b(HPH|HCM|DAD|SGN)\s*[-–]\s*([A-Z][A-Z\s,]+?)(?:\s*(?:via|VIA)\s*[A-Z\s]+)?\s*(?://|__|$)',
        text, re.IGNORECASE)
    return f"{m.group(1).upper()}-{m.group(2).strip().upper()}" if m else ""


def extract_container_type(text: str) -> str:
    """Extract container type like 20DC, 40HQ from text."""
    m = re.search(r'\d+\s*[Xx]?\s*(20DC|20GP|40HC|40HQ|20RF|40RF|40GP)', text, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def extract_carrier(text: str) -> str:
    """Extract carrier name from text."""
    text_u = text.upper()
    for carrier in ["ONE SOC", "ONE", "ZIM", "CMA CGM", "CMA", "MSC", "HPL",
                     "HAPAG", "EMC", "YML", "KMTC", "MSK", "EVERGREEN", "WHL"]:
        if carrier in text_u:
            return carrier
    return ""


def extract_etd(text: str) -> str:
    """Extract ETD date from text."""
    m = re.search(
        r'ETD[\s_:]*([\d]{1,2}\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(?:\s*\d{2,4})?)',
        text, re.IGNORECASE)
    return m.group(1).upper().strip() if m else ""


# ==============================================================================
# SCAN ENGINE
# ==============================================================================

def scan_customer_folder(ns, customer_name: str, folder_name: str,
                         group_type: str, max_emails: int) -> list[dict]:
    """Scan one Outlook folder and return extracted email metadata."""
    folder = find_customer_folder(ns, folder_name)
    if folder is None:
        log.warning("  Folder '%s' not found in any Outlook store.", folder_name)
        return []

    try:
        items = folder.Items
        items.Sort("[ReceivedTime]", True)
        total = items.Count
        limit = min(total, max_emails)
        log.info("  [%s] %s — %d emails (scanning %d)", group_type, folder_name, total, limit)
    except Exception as e:
        log.error("  Cannot read folder items: %s", e)
        return []

    exported = []
    index = 1
    processed = 0

    while processed < limit:
        try:
            item = items[index]
        except:
            break

        if item.Class != 43:  # olMail = 43
            index += 1
            processed += 1
            continue

        try:
            subj = item.Subject or ""
            sender = get_sender_email(item)
            ts = str(item.ReceivedTime) if item.ReceivedTime else ""
            body_prev = (item.Body or "")[:600]
            full_text = f"{subj} {body_prev}"

            ids = extract_identifiers(full_text)
            stages = detect_stages(subj, body_prev)
            risks = detect_risks(subj, body_prev)
            troubles = detect_trouble(subj, body_prev)

            exported.append({
                "customer":       customer_name,
                "group":          group_type,
                "subject":        subj,
                "sender":         sender,
                "timestamp":      ts,
                "body_preview":   body_prev[:200],
                "hbl":            ids["HBL"],
                "bkg":            ids["BKG"],
                "container":      ids["CONTAINER"],
                "stages":         stages,
                "risks":          risks,
                "troubles":       troubles,
                "route":          extract_route(subj),
                "container_type": extract_container_type(subj),
                "carrier":        extract_carrier(subj + body_prev),
                "etd":            extract_etd(subj),
            })

        except Exception as e:
            log.debug("  Error on item %d: %s", index, e)

        index += 1
        processed += 1

    return exported


# ==============================================================================
# DATASET BUILDER
# ==============================================================================

def build_dataset(all_emails: list[dict]) -> dict:
    """Build structured JSON dataset from raw email list."""
    customers_map = {}
    shipments = []

    for e in all_emails:
        cname = e["customer"]
        ctype = e["group"]

        # Build customer profile
        if cname not in customers_map:
            customers_map[cname] = {
                "customer_name": cname, "type": ctype,
                "shipment_count": 0, "sla_hours": 2 if ctype == "DIRECT" else 4,
                "stages_seen": set(), "carriers": set(), "routes": set(),
                "hbl_prefixes": set(), "senders": set(),
            }
        c = customers_map[cname]
        c["shipment_count"] += 1
        c["stages_seen"].update(e["stages"])
        if e["carrier"]:
            c["carriers"].add(e["carrier"])
        if e["route"]:
            c["routes"].add(e["route"])
        if e["sender"]:
            c["senders"].add(e["sender"])
        for h in e["hbl"]:
            prefix = re.match(r'([A-Z]{4})', h)
            if prefix:
                c["hbl_prefixes"].add(prefix.group(1))

        # Build shipment entries
        primary_id = (e["hbl"] + e["bkg"])
        if primary_id:
            shipments.append({
                "shipment_id":    primary_id[0],
                "hbl":            e["hbl"],
                "bkg":            e["bkg"],
                "container_type": e["container_type"],
                "route":          e["route"],
                "etd":            e["etd"],
                "customer":       cname,
                "customer_type":  ctype,
                "carrier":        e["carrier"],
                "stages":         e["stages"],
                "risks":          e["risks"],
                "troubles":       e.get("troubles", []),
                "email_subject":  e["subject"][:80],
                "sender":         e["sender"],
                "timestamp":      e["timestamp"],
            })

    # Serialize sets
    customers_out = []
    for name, c in customers_map.items():
        customers_out.append({
            "customer_name": name, "type": c["type"],
            "shipment_count": c["shipment_count"], "sla_hours": c["sla_hours"],
            "stages_seen": sorted(c["stages_seen"]),
            "carriers": sorted(c["carriers"]),
            "routes": sorted(c["routes"]),
            "hbl_prefixes": sorted(c["hbl_prefixes"]),
            "senders": sorted(c["senders"]),
        })

    return {
        "generated_at": datetime.now().isoformat(),
        "total_emails": len(all_emails),
        "customers": customers_out,
        "shipments": shipments,
    }


# ==============================================================================
# MAIN
# ==============================================================================

def run_scan(quick: bool = False) -> dict:
    """
    Main entry point. Scans Outlook, builds dataset, writes JSON.
    Returns stats dict.
    """
    log.info("=" * 60)
    log.info("  EMAIL SCANNER v2.0 — %s mode", "QUICK" if quick else "FULL")
    log.info("  %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("=" * 60)

    ns = connect_outlook()
    if ns is None:
        return {"error": "Cannot connect to Outlook", "ok": False}

    max_per = MAX_EMAILS_QUICK if quick else MAX_EMAILS_PER_FOLDER
    all_emails = []
    stats = {}

    for customer_name, (group_type, folder_names) in TARGET_FOLDERS.items():
        combined = []
        for folder_name in folder_names:
            emails = scan_customer_folder(ns, customer_name, folder_name, group_type, max_per)
            combined.extend(emails)
        all_emails.extend(combined)
        stats[customer_name] = len(combined)

    if not all_emails:
        log.warning("No emails found. Check Outlook folder names.")
        return {"ok": False, "error": "No emails found", "stats": stats}

    # Build dataset
    dataset = build_dataset(all_emails)

    # Write to webapp-local path
    log.info("Writing dataset to %s", OUTPUT_JSON)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    # Also write to original email_engine path
    if ORIGINAL_EMAIL_ENGINE.exists():
        log.info("Also writing to %s", ORIGINAL_DATASET)
        with open(ORIGINAL_DATASET, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)

    result = {
        "ok": True,
        "total_emails": dataset["total_emails"],
        "customers": len(dataset["customers"]),
        "shipments": len(dataset["shipments"]),
        "output": str(OUTPUT_JSON),
        "scanned_at": datetime.now().isoformat(),
        "stats": stats,
    }

    log.info("DONE | %d emails | %d customers | %d shipment entries",
             result["total_emails"], result["customers"], result["shipments"])
    return result


def main():
    quick = "--quick" in sys.argv
    result = run_scan(quick=quick)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
