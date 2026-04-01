# -*- coding: utf-8 -*-
from __future__ import annotations
import sys, io, os

# Set UTF-8 for Windows console (must be before docstring/other imports)
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
os.environ['PYTHONIOENCODING'] = 'utf-8'

"""
scan_outlook_folders.py
========================
Automatically scans Outlook folders (FWD/DIRECT), exports .msg files,
analyzes lifecycle patterns, and generates structured JSON datasets.

Usage:
    python scan_outlook_folders.py
"""

import json, re, time, logging, traceback
from datetime import datetime
from pathlib import Path

import win32com.client

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(__file__).parent / "scan_folders.log", encoding="utf-8"),
    ]
)
log = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
OUTLOOK_DIR = BASE_DIR / "outlook"
OUTPUT_JSON = PROJECT_ROOT / "assets" / "outlook_dataset.json"

# Target folder structure to scan
# key = customer_name, value = (group_type, [list_of_outlook_folder_names])
# Supports multiple Outlook subfolders per customer (e.g. PANDA has 3 offices)
TARGET_FOLDERS = {
    # FWD / Coload — actual Outlook folder names
    "SIRI":         ("FWD",    ["SIRI LOG"]),
    "HML":          ("FWD",    ["HML"]),
    "PANDA":        ("FWD",    ["PANDA GROUP", "PANDA HN", "PANDA BN"]),
    # Direct customers
    "NAFOOD":       ("DIRECT", ["NAFOOD"]),
    "PT FOOD":      ("DIRECT", ["PT FOOD"]),
    "VINARES":      ("DIRECT", ["VINARES", "Vinares"]),
    "HER HUI WOOD": ("DIRECT", ["HER HUI WOOD"]),
    "CREATIVE LIGHT":("DIRECT", ["CREATIVE LIGHT"]),
}

MAX_EMAILS_PER_FOLDER = 50    # 50 emails per folder — enough to build pipeline patterns
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"

# ─── Identifier & Lifecycle Patterns ─────────────────────────────────────────
ID_PATTERNS = [
    ("HBL", r'\b(P(?:NYC|SAV|HOU|DEN|CHS|SEA|OMA|YTO|ELP|MAN|LAX|OAK|BAL|SAV)\d{7,12})\b'),
    ("HBL", r'\b(HLCU[A-Z]{3}\d{9,})\b'),
    ("HBL", r'\b(ZIMU(?:HCM|HAI|SGN)\d{8,})\b'),
    ("HBL", r'\b(HANG\d{8,12})\b'),
    ("HBL", r'\b(ESLV[A-Z0-9]{5,15})\b'),
    ("BKG", r'\bBKG[\s#]*([A-Z0-9]{6,12})\b'),
    ("BKG", r'\bEBKG(\d{8,12})\b'),
    ("BKG", r'\b(SGN\d{7,10})\b'),
    ("BKG", r'\b(HANFG\d{7,10})\b'),
    ("BKG", r'\b(ZIMUHCM\d{6,})\b'),
    ("CONTAINER", r'\b([A-Z]{4}\d{7})\b'),
]

LIFECYCLE_STAGES = {
    "BOOKING_CONFIRMED": ["booking confirmation", "bkg confirmed", "confirmed //", "keep booking"],
    "SI_SUBMITTED":      ["si bkg", " si //", "shipping instruction", "si hang"],
    "DRAFT_BL_ISSUED":   ["draft b/l", "draft bl", "draft b_l", "bill nháp"],
    "DRAFT_BL_CONFIRMED":["confirm draft", "draft ok", "xác nhận draft"],
    "LOADED":            ["loaded on board", "đã lên tàu"],
    "ATD":               ["update atd", "atd__", " atd//", "vessel departed"],
    "DN_SENT":           ["dn __", " dn //", "debit //", "debit note", "giấy báo tiền"],
    "INVOICE_ISSUED":    ["invoice", "e-invoice"],
    "PAYMENT_CONFIRMED": ["payment received", "paid", "đã thanh toán", "xác nhận thanh toán", "đã nhận"],
    "ETA_UPDATE":        ["update eta", "eta update", "arrival notice"],
    "DELAY_NOTICE":      ["delay notice", "delay", "rollover", "postpone"],
    "CHANGE_VESSEL":     ["change vessel", "vessel change", "changed mother vessel", "rebooking"],
}

RISK_KEYWORDS = {
    "CRITICAL": ["urgent", "gấp", "asap", "top priority", "poa", "change vessel"],
    "HIGH":     ["delay", "rollover", "amendment", "si change", "delay notice"],
    "MEDIUM":   ["update atd", "vessel change", "omit", "customs hold"],
}


# ─── Outlook Helpers ──────────────────────────────────────────────────────────
def connect_outlook():
    try:
        app = win32com.client.Dispatch("Outlook.Application")
        ns  = app.GetNamespace("MAPI")
        log.info("Connected to Outlook ✓")
        return ns
    except Exception as e:
        log.error("Cannot connect to Outlook: %s", e)
        sys.exit(1)


def get_sender_email(mail_item) -> str:
    try:
        addr = mail_item.SenderEmailAddress
        if addr and "@" in addr and not addr.startswith("/O="):
            return addr.strip().lower()
    except: pass
    try:
        pa = mail_item.Sender.PropertyAccessor
        smtp = pa.GetProperty(PR_SMTP_ADDRESS)
        if smtp: return smtp.strip().lower()
    except: pass
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


def find_customer_folder(ns, customer_name: str):
    """
    Search for customer folder across all Outlook stores.
    Strategy: look for exact name match anywhere in the folder tree.
    """
    for store in ns.Stores:
        try:
            root   = store.GetRootFolder()
            folder = find_folder_recursive(root, customer_name)
            if folder:
                log.info("  Found '%s' in store: %s", customer_name, store.DisplayName)
                return folder
        except:
            continue
    return None


def load_pst_if_needed(ns, pst_path: Path):
    """Mount PST file into Outlook if not already mounted."""
    pst_str = str(pst_path)
    try:
        for store in ns.Stores:
            try:
                if pst_path.stem.lower() in store.DisplayName.lower():
                    log.info("PST already mounted: %s", store.DisplayName)
                    return True
            except: pass
        log.info("Mounting PST: %s", pst_str)
        ns.AddStore(pst_str)
        time.sleep(3)  # Give Outlook time to index
        log.info("PST mounted ✓")
        return True
    except Exception as e:
        log.warning("Could not mount PST (%s) — will scan live mailbox only", e)
        return False


def export_email_as_msg(mail_item, dest_dir: Path, index: int) -> Path | None:
    """Save a MailItem as .msg file. Returns path or None on failure."""
    try:
        subject = (mail_item.Subject or "no_subject")
        # Sanitize filename
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', subject)[:80]
        filename  = f"{index:04d}_{safe_name}.msg"
        dest      = dest_dir / filename
        if dest.exists():
            return dest   # Already exported
        mail_item.SaveAs(str(dest), 3)  # 3 = olMSG
        return dest
    except Exception as e:
        log.debug("SaveAs failed: %s", e)
        return None


# ─── Scan Engine ──────────────────────────────────────────────────────────────
def scan_customer_folder(ns, customer_name: str, group_type: str) -> list[dict]:
    """
    Find the customer's Outlook folder, export all emails as .msg,
    and return list of extracted metadata dicts.
    """
    dest_dir = OUTLOOK_DIR / group_type / customer_name
    dest_dir.mkdir(parents=True, exist_ok=True)

    log.info("")
    log.info("─" * 60)
    log.info("Scanning: [%s] %s", group_type, customer_name)
    log.info("─" * 60)

    # Find folder in Outlook
    folder = find_customer_folder(ns, customer_name)
    if folder is None:
        log.warning("  Folder '%s' not found in any Outlook store.", customer_name)
        return []

    # Scan messages
    try:
        items = folder.Items
        items.Sort("[ReceivedTime]", True)   # newest first
        total   = items.Count
        limit   = min(total, MAX_EMAILS_PER_FOLDER)
        log.info("  Total emails: %d | Exporting: %d", total, limit)
    except Exception as e:
        log.error("  Cannot read folder items: %s", e)
        return []

    exported  = []
    skipped   = 0
    index     = 1
    processed = 0

    while processed < limit:
        try:
            item = items[index]
        except:
            break

        if item.Class != 43:   # olMail = 43
            index += 1
            processed += 1
            continue

        try:
            subj      = item.Subject     or ""
            sender    = get_sender_email(item)
            ts        = str(item.ReceivedTime) if item.ReceivedTime else ""
            body_prev = (item.Body or "")[:600]

            # Export as .msg
            msg_path = export_email_as_msg(item, dest_dir, processed + 1)

            # Extract identifiers & stages
            full_text = f"{subj} {body_prev}"
            ids    = extract_identifiers(full_text)
            stages = detect_stages(subj, body_prev)
            risks  = detect_risks(subj, body_prev)

            exported.append({
                "customer":      customer_name,
                "group":         group_type,
                "subject":       subj,
                "sender":        sender,
                "timestamp":     ts,
                "body_preview":  body_prev[:200],
                "hbl":           ids["HBL"],
                "bkg":           ids["BKG"],
                "container":     ids["CONTAINER"],
                "stages":        stages,
                "risks":         risks,
                "route":         extract_route(subj),
                "container_type": extract_container_type(subj),
                "carrier":       extract_carrier(subj + body_prev),
                "etd":           extract_etd(subj),
                "msg_file":      str(msg_path) if msg_path else "",
            })

            if processed % 20 == 0 and processed > 0:
                log.info("  ... processed %d/%d", processed, limit)

        except Exception as e:
            log.debug("  Error on item %d: %s", index, e)
            skipped += 1

        index     += 1
        processed += 1

    # Count unique stages found
    all_stages = set(s for e in exported for s in e["stages"])
    log.info("  Done: %d emails exported | Stages: %s",
             len(exported), ", ".join(sorted(all_stages)) or "none")
    return exported


# ─── Extraction Helpers ───────────────────────────────────────────────────────
def extract_identifiers(text: str) -> dict:
    result = {"HBL": [], "BKG": [], "CONTAINER": []}
    text_u = text.upper()
    for id_type, pat in ID_PATTERNS:
        for m in re.finditer(pat, text_u, re.IGNORECASE):
            val = m.group(1).strip()
            if len(val) >= 5 and val not in result[id_type]:
                result[id_type].append(val)
    return result


def detect_stages(subject: str, body: str) -> list[str]:
    combined = (subject + " " + body).lower()
    return [stage for stage, kws in LIFECYCLE_STAGES.items()
            if any(kw in combined for kw in kws)]


def detect_risks(subject: str, body: str) -> list[str]:
    combined = (subject + " " + body).lower()
    found = []
    for level, kws in RISK_KEYWORDS.items():
        for kw in kws:
            if kw in combined:
                found.append(f"{level}:{kw}")
    return found


def extract_route(text: str) -> str:
    m = re.search(
        r'\b(HPH|HCM|DAD|SGN)\s*[-–]\s*([A-Z][A-Z\s,]+?)(?:\s*(?:via|VIA)\s*[A-Z\s]+)?\s*(?://|__|$)',
        text, re.IGNORECASE)
    return f"{m.group(1).upper()}-{m.group(2).strip().upper()}" if m else ""


def extract_container_type(text: str) -> str:
    m = re.search(r'\d+\s*[Xx]?\s*(20DC|40HC|20RF|40RF|40GP|20GP)', text, re.IGNORECASE)
    return m.group(1).upper() if m else ""


def extract_carrier(text: str) -> str:
    text_u = text.upper()
    for carrier in ["ONE SOC","ONE","ZIM","CMA CGM","CMA","MSC","HPL","HAPAG",
                     "EMC","YML","KMTC","MSK","EVERGREEN","WHL"]:
        if carrier in text_u:
            return carrier
    return ""


def extract_etd(text: str) -> str:
    m = re.search(
        r'ETD[\s_:]*(\d{1,2}\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(?:\s*\d{2,4})?)',
        text, re.IGNORECASE)
    return m.group(1).upper().strip() if m else ""


# ─── Dataset Builder ──────────────────────────────────────────────────────────
def build_datasets(all_emails: list[dict]) -> dict:
    customers_map  = {}
    shipments      = []
    lifecycle_evts = []
    payment_pats   = []
    stage_map      = {}

    for e in all_emails:
        cname = e["customer"]
        ctype = e["group"]

        # Customers
        if cname not in customers_map:
            customers_map[cname] = {
                "customer_name":  cname,
                "type":           ctype,
                "shipment_count": 0,
                "stages_seen":    set(),
                "carriers":       set(),
                "routes":         set(),
                "sla_hours":      2 if ctype == "DIRECT" else 4,
                "hbl_prefixes":   set(),
                "senders":        set(),
            }
        c = customers_map[cname]
        c["shipment_count"] += 1
        c["stages_seen"].update(e["stages"])
        if e["carrier"]:  c["carriers"].add(e["carrier"])
        if e["route"]:    c["routes"].add(e["route"])
        if e["sender"]:   c["senders"].add(e["sender"])
        for h in e["hbl"]:
            prefix = re.match(r'([A-Z]{4})', h)
            if prefix: c["hbl_prefixes"].add(prefix.group(1))

        # Shipments
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
                "email_subject":  e["subject"][:80],
                "sender":         e["sender"],
                "timestamp":      e["timestamp"],
            })

        # Lifecycle events
        for stage in e["stages"]:
            lifecycle_evts.append({
                "stage":            stage,
                "shipment_id":      primary_id[0] if primary_id else "",
                "customer":         cname,
                "customer_type":    ctype,
                "email_subject":    e["subject"][:80],
                "sender":           e["sender"],
                "timestamp":        e["timestamp"],
                "identifier_type":  "HBL" if e["hbl"] else ("BKG" if e["bkg"] else "NONE"),
                "keywords_found":   [kw for kw in LIFECYCLE_STAGES.get(stage, [])
                                     if kw.lower() in (e["subject"] + e["body_preview"]).lower()],
            })

            # Aggregate stage patterns
            if stage not in stage_map:
                stage_map[stage] = {
                    "stage_name":       stage,
                    "keywords":         list(LIFECYCLE_STAGES.get(stage, [])),
                    "sample_subjects":  [],
                    "sender_roles":     set(),
                    "customers_seen":   set(),
                    "identifier_types": set(),
                    "count":            0,
                    "automation_action": _stage_action(stage),
                }
            sm = stage_map[stage]
            sm["count"] += 1
            sm["customers_seen"].add(cname)
            sm["identifier_types"].add("HBL" if e["hbl"] else "BKG")
            if e["subject"][:80] not in sm["sample_subjects"][:10]:
                sm["sample_subjects"].append(e["subject"][:80])

        # Payment patterns
        if any(s in e["stages"] for s in ["DN_SENT", "INVOICE_ISSUED", "PAYMENT_CONFIRMED"]):
            payment_pats.append({
                "sender":        e["sender"],
                "subject":       e["subject"][:80],
                "hbl":           e["hbl"],
                "bkg":           e["bkg"],
                "customer":      cname,
                "stage":         [s for s in e["stages"]
                                  if s in {"DN_SENT","INVOICE_ISSUED","PAYMENT_CONFIRMED"}],
                "timestamp":     e["timestamp"],
            })

    # Serialize sets
    customers_out = []
    for name, c in customers_map.items():
        customers_out.append({
            "customer_name":  name,
            "type":           c["type"],
            "shipment_count": c["shipment_count"],
            "sla_hours":      c["sla_hours"],
            "stages_seen":    sorted(c["stages_seen"]),
            "carriers":       sorted(c["carriers"]),
            "routes":         sorted(c["routes"]),
            "hbl_prefixes":   sorted(c["hbl_prefixes"]),
            "senders":        sorted(c["senders"]),
        })

    lifecycle_patterns = []
    for stage, sm in stage_map.items():
        sm["sender_roles"]     = ["ops_team", "accounting", "carrier"]
        sm["customers_seen"]   = sorted(sm["customers_seen"])
        sm["identifier_types"] = sorted(sm["identifier_types"])
        lifecycle_patterns.append(sm)

    return {
        "generated_at":      datetime.now().isoformat(),
        "total_emails":      len(all_emails),
        "customers":         customers_out,
        "shipments":         shipments,
        "lifecycle_events":  lifecycle_evts,
        "lifecycle_patterns": lifecycle_patterns,
        "payment_patterns":  payment_pats,
    }


def _stage_action(stage: str) -> str:
    return {
        "BOOKING_CONFIRMED":  "create_job_record + update_status",
        "SI_SUBMITTED":       "update_status:SI_SUBMITTED + log_si",
        "DRAFT_BL_ISSUED":    "update_status + alert_team_member",
        "DRAFT_BL_CONFIRMED": "update_status:DRAFT_BL_CONFIRMED",
        "LOADED":             "update_status + start_eta_countdown",
        "ATD":                "update_status + trigger_eta_alerts",
        "DN_SENT":            "update_payment:PENDING + alert_nelson",
        "INVOICE_ISSUED":     "update_payment:INVOICE_SENT",
        "PAYMENT_CONFIRMED":  "update_payment:PAID + telegram_notify_nelson",
        "ETA_UPDATE":         "update_eta + notify_customer",
        "DELAY_NOTICE":       "alert_nelson:URGENT + notify_customer",
        "CHANGE_VESSEL":      "alert_nelson:CRITICAL + update_vessel",
    }.get(stage, "log_event")


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("  OUTLOOK FOLDER SCANNER  v1.0")
    log.info("  %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    log.info("=" * 60)

    # Connect Outlook
    ns = connect_outlook()

    # Mount PST if it exists
    pst_path = OUTLOOK_DIR / "backup.pst"
    if pst_path.exists():
        log.info("PST file found (%d MB) — mounting...",
                 pst_path.stat().st_size // 1024 // 1024)
        load_pst_if_needed(ns, pst_path)
    else:
        log.info("No PST found — scanning live Outlook mailbox only")

    # Scan each customer folder (supports multiple Outlook folders per customer)
    all_emails = []
    stats = {}

    for customer_name, (group_type, folder_names) in TARGET_FOLDERS.items():
        combined = []
        for folder_name in folder_names:
            emails = scan_customer_folder(ns, folder_name, group_type)
            # Tag with canonical customer name
            for e in emails:
                e["customer"] = customer_name
            combined.extend(emails)
        all_emails.extend(combined)
        stats[customer_name] = len(combined)

    # Summary per customer
    log.info("")
    log.info("=" * 60)
    log.info("  EXPORT SUMMARY")
    log.info("=" * 60)
    for customer, count in stats.items():
        group = TARGET_FOLDERS[customer][0]
        status = "✓" if count > 0 else "✗ (folder not found)"
        log.info("  [%-6s] %-16s : %3d emails  %s", group, customer, count, status)
    log.info("  TOTAL: %d emails across %d customers", len(all_emails), len(stats))

    if not all_emails:
        log.warning("No emails exported — check folder names match Outlook.")
        return

    # Build datasets
    log.info("")
    log.info("Building structured datasets...")
    datasets = build_datasets(all_emails)

    # Write JSON
    log.info("Writing %s...", OUTPUT_JSON)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(datasets, f, ensure_ascii=False, indent=2)

    # Print summary
    log.info("")
    log.info("=" * 60)
    log.info("  DATASET SUMMARY")
    log.info("=" * 60)
    log.info("  Total emails       : %d", datasets["total_emails"])
    log.info("  Customers          : %d", len(datasets["customers"]))
    log.info("  Shipments detected : %d", len(datasets["shipments"]))
    log.info("  Lifecycle events   : %d", len(datasets["lifecycle_events"]))
    log.info("  Lifecycle patterns : %d", len(datasets["lifecycle_patterns"]))
    log.info("  Payment patterns   : %d", len(datasets["payment_patterns"]))
    log.info("")
    log.info("  Stages detected:")
    stage_counts = {}
    for ev in datasets["lifecycle_events"]:
        stage_counts[ev["stage"]] = stage_counts.get(ev["stage"], 0) + 1
    for stage, cnt in sorted(stage_counts.items(), key=lambda x: -x[1]):
        log.info("    %-25s : %d", stage, cnt)
    log.info("")
    log.info("  Output: %s", OUTPUT_JSON)
    log.info("=" * 60)


if __name__ == "__main__":
    main()
