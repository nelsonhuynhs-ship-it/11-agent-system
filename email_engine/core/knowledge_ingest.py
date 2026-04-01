# -*- coding: utf-8 -*-
"""
knowledge_ingest.py — Auto-ingest email knowledge into Parquet
================================================================
Scans outlook/ routed folders and knowledge/ JSON files,
extracts structured data (customer, mentee, HBL, BKG, stage),
and saves per-customer knowledge Parquet files.

Called by outlook_scanner.py as part of the unified 30-min scan cycle.

Output structure:
    Pricing_Engine/data/knowledge_db/
    ├── _all_emails.parquet          ← Master (all emails)
    ├── customer_SIRI.parquet        ← Per-customer
    ├── customer_PANDA.parquet
    ├── customer_HML.parquet
    ├── customer_NAFOOD.parquet
    └── ...

Usage:
    from knowledge_ingest import run_knowledge_ingest
    result = run_knowledge_ingest()
"""
import json
import logging
import re
import sys
import io
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

# Fix encoding for Windows console
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

log = logging.getLogger("nelson.knowledge_ingest")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).parent                          # email_engine/core
EMAIL_ENGINE    = BASE_DIR.parent                                # email_engine/
ENGINE_TEST     = EMAIL_ENGINE.parent                            # Engine_test/
OUTLOOK_DIR     = EMAIL_ENGINE / "outlook"                       # Routed .msg files
KNOWLEDGE_DIR   = ENGINE_TEST / "Pricing_Engine" / "data" / "knowledge"  # Raw JSON
OUTPUT_DIR      = ENGINE_TEST / "Pricing_Engine" / "data" / "knowledge_db"
ORG_RULES_FILE  = BASE_DIR / "org_rules.json"
MASTER_PARQUET  = OUTPUT_DIR / "_all_emails.parquet"

# Ensure output dir
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Org Rules Loader ──────────────────────────────────────────────────────────
_org_rules_cache = None

def _load_org_rules() -> dict:
    global _org_rules_cache
    if _org_rules_cache is not None:
        return _org_rules_cache
    if not ORG_RULES_FILE.exists():
        log.warning("org_rules.json not found")
        return {}
    with ORG_RULES_FILE.open(encoding="utf-8") as f:
        _org_rules_cache = json.load(f)
    return _org_rules_cache


def _get_department(email: str, org: dict) -> str:
    e = email.lower().strip()
    lookup = org.get("email_lookup", {})
    if e in set(lookup.get("sale_emails", [])):     return "sale"
    if e in set(lookup.get("doc_emails", [])):      return "doc"
    if e in set(lookup.get("cs_emails", [])):       return "cs"
    if e in set(lookup.get("pricing_emails", [])):  return "pricing"
    if e in set(lookup.get("accounting_emails", [])): return "accounting"
    return "external"


def _get_mentee(email: str, org: dict) -> str:
    e = email.lower().strip()
    lookup = org.get("email_lookup", {})
    return e if e in set(lookup.get("mentee_emails", [])) else ""


# ── Customer Detection (3-layer) ─────────────────────────────────────────────
_hbl_customer_map: dict[str, str] = {}  # Auto-learn cache: HBL → customer

def _detect_customer_3layer(text: str, org: dict) -> str:
    """3-layer customer detection: keyword → HBL lookup → domain."""
    customers = org.get("customer_identification", {}).get("known_customers", {})
    text_lo = text.lower()

    # Layer 1: Keyword match
    for name, data in customers.items():
        for kw in data.get("keywords", []):
            if kw.lower() in text_lo:
                return name

    # Layer 2: HBL auto-learn lookup
    hbls = _HBL_RE.findall(text.upper())
    for hbl in hbls:
        if hbl in _hbl_customer_map:
            return _hbl_customer_map[hbl]

    # Layer 3: Domain match
    for name, data in customers.items():
        for domain in data.get("domains", []):
            if domain.lower() in text_lo:
                return name

    return ""


def _learn_hbl_customer(text: str, customer: str):
    """If customer is known, learn HBL→customer mapping."""
    if not customer:
        return
    hbls = _HBL_RE.findall(text.upper())
    for hbl in hbls:
        if hbl not in _hbl_customer_map:
            _hbl_customer_map[hbl] = customer
            log.debug("  Learned: %s → %s", hbl, customer)


# ── Identifier Extraction ────────────────────────────────────────────────────
_HBL_RE = re.compile(
    r'\b(P(?:NYC|SAV|HOU|DEN|CHS|SEA|OMA|YTO|ELP|MAN|LAX|OAK|BAL|ORD|ATL|MSP|CHI|TOR)\d{7,12})\b', re.I)
_BKG_RE = re.compile(r'\bBKG[\s#]*([A-Z0-9]{5,12})\b', re.I)
_SGN_RE = re.compile(r'\b(SGN\d{7,10})\b', re.I)

def _extract_ids(text: str) -> tuple[str, str]:
    text_u = text.upper()
    hbls = set(_HBL_RE.findall(text_u)) | set(_SGN_RE.findall(text_u))
    bkgs = set(_BKG_RE.findall(text_u))
    return "|".join(hbls) if hbls else "", "|".join(bkgs) if bkgs else ""


# ── Folder→Customer Mapping ──────────────────────────────────────────────────
_FOLDER_CUSTOMER_MAP = {
    # FWD
    "HML": "HML",
    "PANDA BN": "PANDA",
    "PANDA HN": "PANDA",
    "PANDA GROUP": "PANDA",
    "SIRI LOG": "SIRI",
    # DIRECT
    "CREATIVE LIGHT": "CREATIVE LIGHT",
    "HER HUI WOOD": "HER HUI WOOD",
    "NAFOOD": "Nafood",
    "PT FOOD": "PT FOOD",
    "VINARES": "VINARES",
    # TEAM SUNNY mentees — customer detected from content
    "BLUE": "",
    "JENNIE": "",
    "JOHNNY": "",
    "JUN": "",
    "LINA": "",
    "OTIS": "",
}


# ==============================================================================
# CORE: Process Knowledge JSONs
# ==============================================================================

def _process_knowledge_jsons(org: dict) -> list[dict]:
    """Process all JSON files in knowledge/ folder."""
    records = []
    if not KNOWLEDGE_DIR.exists():
        return records

    for f in KNOWLEDGE_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            subject = data.get("subject", "")
            sender = data.get("sender", "")
            date_str = data.get("date", "")
            body = data.get("body_preview", "")
            full_text = subject + " " + body

            hbl, bkg = _extract_ids(subject)
            customer = _detect_customer_3layer(full_text, org)
            _learn_hbl_customer(full_text, customer)

            records.append({
                "date": date_str,
                "subject": subject[:120],
                "sender": sender,
                "department": _get_department(sender, org),
                "mentee_pic": _get_mentee(sender, org),
                "customer": customer,
                "hbl": hbl,
                "bkg": bkg,
                "type": data.get("type", ""),
                "body_preview": body[:200] if body else "",
                "source": "knowledge_json",
                "source_file": f.name,
            })
        except Exception as e:
            log.debug("  Skip %s: %s", f.name, e)

    return records


# ==============================================================================
# CORE: Process Outlook .msg files (from routed folders)
# ==============================================================================

def _process_outlook_msgs(org: dict) -> list[dict]:
    """Process .msg files from outlook/ subfolders (per-customer routing)."""
    records = []
    if not OUTLOOK_DIR.exists():
        return records

    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
    except ImportError:
        log.warning("win32com not available — skipping .msg processing")
        return records

    # Walk all subfolders: DIRECT/*, FWD/*, TEAM_SUNNY/*, NELSON/
    for category_dir in OUTLOOK_DIR.iterdir():
        if not category_dir.is_dir() or category_dir.name.startswith("_"):
            continue

        category = category_dir.name  # DIRECT, FWD, TEAM_SUNNY, NELSON

        for sub_dir in category_dir.iterdir():
            if sub_dir.is_dir():
                # Sub-folder = customer or mentee name
                folder_name = sub_dir.name
                folder_customer = _FOLDER_CUSTOMER_MAP.get(folder_name, "")

                for msg_file in sub_dir.glob("*.msg"):
                    rec = _parse_msg_file(msg_file, org, folder_customer, category, folder_name)
                    if rec:
                        records.append(rec)
            elif category_dir.name == "NELSON" and sub_dir.suffix.lower() == ".msg":
                # NELSON/ direct .msg files
                rec = _parse_msg_file(sub_dir, org, "", "NELSON", "NELSON")
                if rec:
                    records.append(rec)

    return records


def _parse_msg_file(msg_path: Path, org: dict, folder_customer: str,
                    category: str, folder_name: str) -> Optional[dict]:
    """Parse a single .msg file into a knowledge record."""
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        msg = outlook.CreateItemFromTemplate(str(msg_path))

        subject = msg.Subject or ""
        sender = ""
        try:
            sender = msg.SenderEmailAddress or ""
            if "@" not in sender:
                sender = msg.Sender.GetExchangeUser().PrimarySmtpAddress
        except Exception:
            pass

        body = (msg.Body or "")[:300]
        date_str = ""
        try:
            date_str = msg.SentOn.strftime("%Y-%m-%d") if msg.SentOn else ""
        except Exception:
            pass

        full_text = subject + " " + body
        hbl, bkg = _extract_ids(subject)

        # Customer: folder mapping first, then 3-layer detection
        customer = folder_customer or _detect_customer_3layer(full_text, org)
        _learn_hbl_customer(full_text, customer)

        return {
            "date": date_str,
            "subject": subject[:120],
            "sender": sender.lower(),
            "department": _get_department(sender, org),
            "mentee_pic": _get_mentee(sender, org),
            "customer": customer,
            "hbl": hbl,
            "bkg": bkg,
            "type": category,
            "body_preview": body[:200],
            "source": "outlook_msg",
            "source_file": msg_path.name,
        }
    except Exception as e:
        log.debug("  Skip MSG %s: %s", msg_path.name, e)
        return None


# ==============================================================================
# MAIN: Run Knowledge Ingest
# ==============================================================================

def run_knowledge_ingest() -> dict:
    """
    Main entry point — collects from knowledge/ JSONs + outlook/ .msg files,
    merges with existing master, deduplicates, saves master + per-customer parquets.
    """
    result = {
        "new_emails": 0,
        "total_emails": 0,
        "customers_updated": [],
        "master_parquet": str(MASTER_PARQUET),
    }

    org = _load_org_rules()

    # ── Collect new records ────────────────────
    log.info("[Knowledge] Scanning knowledge/ JSONs...")
    json_records = _process_knowledge_jsons(org)
    log.info("[Knowledge]   JSONs: %d records", len(json_records))

    log.info("[Knowledge] Scanning outlook/ .msg files...")
    msg_records = _process_outlook_msgs(org)
    log.info("[Knowledge]   MSGs: %d records", len(msg_records))

    all_new = json_records + msg_records
    if not all_new:
        log.info("[Knowledge] No new records found")
        return result

    df_new = pd.DataFrame(all_new)

    # ── Merge with existing master ────────────
    if MASTER_PARQUET.exists():
        df_existing = pd.read_parquet(MASTER_PARQUET)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_combined = df_new

    # ── Dedup ────────────────────────────────
    before = len(df_combined)
    df_combined = df_combined.drop_duplicates(
        subset=["date", "subject", "sender"], keep="last"
    )
    after = len(df_combined)
    dupes = before - after

    log.info("[Knowledge] Master: %d records (removed %d dupes)", after, dupes)

    # ── Save master ───────────────────────────
    df_combined.to_parquet(MASTER_PARQUET, index=False)
    result["total_emails"] = after
    result["new_emails"] = len(all_new) - dupes

    # ── Save per-customer parquets ────────────
    customers_done = []
    for customer_name, group in df_combined.groupby("customer"):
        if not customer_name:
            continue
        safe_name = re.sub(r'[^\w]', '_', customer_name).strip('_')
        out_path = OUTPUT_DIR / f"customer_{safe_name}.parquet"
        group.to_parquet(out_path, index=False)
        customers_done.append(f"{customer_name}({len(group)})")
        log.info("[Knowledge]   Saved: customer_%s.parquet (%d rows)", safe_name, len(group))

    # Also save unidentified
    unid = df_combined[df_combined["customer"] == ""]
    if len(unid) > 0:
        unid.to_parquet(OUTPUT_DIR / "customer_UNIDENTIFIED.parquet", index=False)
        customers_done.append(f"UNIDENTIFIED({len(unid)})")

    result["customers_updated"] = customers_done
    log.info("[Knowledge] Done: %d customers updated", len(customers_done))

    # ── Auto-cleanup: delete source files after successful ingest ──
    cleanup_count = 0

    # Clean .msg files from outlook/ (keep folder structure)
    if OUTLOOK_DIR.exists():
        for msg_file in OUTLOOK_DIR.rglob("*.msg"):
            try:
                msg_file.unlink()
                cleanup_count += 1
            except Exception as e:
                log.debug("  Could not delete %s: %s", msg_file.name, e)

    # Clean knowledge/ JSON files (already in Parquet)
    if KNOWLEDGE_DIR.exists():
        for json_file in KNOWLEDGE_DIR.glob("*.json"):
            try:
                json_file.unlink()
                cleanup_count += 1
            except Exception as e:
                log.debug("  Could not delete %s: %s", json_file.name, e)

    # Clean processed rate files from Harry (already imported into Parquet)
    processed_rates_dir = ENGINE_TEST / "Pricing_Engine" / "data" / "processed"
    if processed_rates_dir.exists():
        for rate_file in processed_rates_dir.glob("*.xlsx"):
            try:
                rate_file.unlink()
                cleanup_count += 1
            except Exception as e:
                log.debug("  Could not delete %s: %s", rate_file.name, e)

    if cleanup_count > 0:
        log.info("[Knowledge] Auto-cleanup: %d source files deleted", cleanup_count)
    result["files_cleaned"] = cleanup_count

    return result


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-5s | %(message)s",
                        datefmt="%H:%M:%S")

    result = run_knowledge_ingest()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
