"""
combine_all.py -- Master Data Layer Builder
=============================================
Reads ALL panjiva_raw_*.xlsx from data_panjiva/ and existing data.xlsx,
then produces three master files:

  cnee_master.xlsx     -- All consignee contacts (from shipment data)
  contact_master.xlsx  -- All named contacts (from Contact Info sheets)
  shipper_master.xlsx  -- All shipper contacts (from shipment data)

Each master file is enriched with:
  - Email quality scoring
  - KB status from email_knowledge.csv
  - Send history from email_log.csv
  - Sequence tracking columns

Usage:
    python combine_all.py
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# =========================================================
# CONFIG (paths via shared.paths — OneDrive data, local runtime)
# =========================================================
_repo_root = str(Path(__file__).parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from shared import paths as sp

PANJIVA_DIR    = sp.PANJIVA_DIR
LOG_DIR        = sp.EMAIL_LOG_DIR
KNOWLEDGE_FILE = sp.EMAIL_LOG_DIR / "email_knowledge.csv"
EMAIL_LOG_FILE = sp.EMAIL_LOG
DATA_FILE      = sp.EMAIL_CODE / "data.xlsx"

OUT_CNEE       = sp.CNEE_MASTER
OUT_CONTACT    = sp.CONTACT_MASTER
OUT_SHIPPER    = sp.SHIPPER_MASTER

# Shipment sheet name variants (try in order)
SHIPMENT_SHEETS = ["US Imports Shipments", "US Imports Consignee Shipments"]

# =========================================================
# LOGGING
# =========================================================
logging.basicConfig(
    level   = logging.INFO,
    format  = "[%(asctime)s] %(levelname)-8s %(message)s",
    datefmt = "%H:%M:%S",
    handlers= [logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# =========================================================
# EMAIL CLEANING
# =========================================================
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

BAD_PATTERNS = {
    "noreply", "no-reply", "mailer-daemon", "postmaster",
    "bounce", "donotreply", "do-not-reply",
}

FREE_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "icloud.com", "aol.com", "live.com", "msn.com",
}

stats = {
    "emails_cleaned": 0,
    "emails_bad_format": 0,
    "kb_blocked": 0,
}


def clean_email(raw) -> str:
    """Clean and validate a single email string. Returns '' if invalid."""
    if not isinstance(raw, str) or not raw.strip():
        return ""
    raw = raw.strip().lower()

    # Strip bad prefixes (em, me, te followed by punctuation)
    m = EMAIL_RE.search(raw)
    if not m:
        stats["emails_bad_format"] += 1
        return ""

    email = m.group(0)
    local, domain = email.split("@", 1)

    # Strip leading punctuation from local part
    local = local.lstrip(".,-")

    # Remove em/me/te prefix artifacts
    for p in ("em", "me", "te"):
        if local.startswith(p) and len(local) > 4:
            cleaned = local[len(p):].lstrip(".,-")
            if cleaned:
                local = cleaned
                stats["emails_cleaned"] += 1

    # Check for bad patterns
    if any(bp in local for bp in BAD_PATTERNS):
        return ""

    return f"{local}@{domain}"


def extract_emails(*cells) -> list[str]:
    """Extract all valid emails from multiple cell values."""
    result = []
    for c in cells:
        if isinstance(c, str):
            for m in EMAIL_RE.finditer(c):
                e = clean_email(m.group(0))
                if e:
                    result.append(e)
    return list(set(result))


def email_quality_score(email: str) -> int:
    """Score email quality: 100 = corporate, 50 = free provider, 0 = invalid."""
    if not email or "@" not in email:
        return 0
    _, domain = email.split("@", 1)
    if domain in FREE_DOMAINS:
        return 50
    return 100


# =========================================================
# PORT / DESTINATION MAPPING (reuse from normalize.py)
# =========================================================
PORT_MAP_FILE = PROJECT_ROOT / "data" / "Port_Code_Mapping_Final.xlsx"

POL_RULES = {
    "HOCHIMINH": "HCM", "HO CHI MINH": "HCM", "VUNG TAU": "HCM",
    "CAI MEP": "HCM", "HAI PHONG": "HPH",
}


def load_destination_map() -> list[tuple[str, str]]:
    if not PORT_MAP_FILE.exists():
        return []
    df = pd.read_excel(PORT_MAP_FILE, sheet_name="Port_Code_Mapping_Final")
    df.columns = df.columns.astype(str).str.strip().str.lower()
    dm = (
        df[["portname", "portcode"]]
        .dropna()
        .assign(
            portname=lambda d: d["portname"].astype(str).str.upper().str.strip(),
            portcode=lambda d: d["portcode"].astype(str).str.upper().str.strip(),
            length=lambda d: d["portname"].str.len(),
        )
        .sort_values("length", ascending=False)
    )
    return list(zip(dm["portname"], dm["portcode"]))


DEST_MAP = load_destination_map()


def map_destination(text) -> str:
    if not isinstance(text, str) or not text.strip():
        return ""
    t = text.upper()
    for name, code in DEST_MAP:
        if name in t:
            return code
    return ""


def map_pol(text) -> str:
    if not isinstance(text, str):
        return ""
    t = text.upper()
    for k, v in POL_RULES.items():
        if k in t:
            return v
    return ""


# =========================================================
# PRIORITY SCORING (for contact_master)
# =========================================================
PRIORITY_KEYWORDS: list[tuple[int, list[str]]] = [
    (10, ["logistics manager", "import coordinator",
          "director of supply chain", "import export specialist",
          "shipping manager", "logistics lead",
          "transportation manager", "freight manager",
          "import specialist", "export specialist"]),
    (8,  ["purchasing", "procurement", "supply chain manager",
          "import manager", "logistics coordinator",
          "supply chain analyst", "sourcing manager"]),
    (6,  ["vice president", "director", "general manager",
          "operations manager", "vp of", "coo"]),
    (4,  ["president", "owner", "manager", "branch manager",
          "ceo", "founder"]),
    (2,  ["sales manager", "customer service", "operations",
          "account manager", "business development"]),
]


def compute_priority_score(position: str) -> int:
    if not isinstance(position, str) or not position.strip():
        return 1
    pos_lower = position.lower().strip()
    for score, keywords in PRIORITY_KEYWORDS:
        for kw in keywords:
            if kw in pos_lower:
                return score
    return 1


# =========================================================
# LOAD KB + LOG
# =========================================================
def load_kb() -> dict[str, str]:
    """Returns dict: email -> status (lowercase)."""
    if not KNOWLEDGE_FILE.exists():
        return {}
    df = pd.read_csv(KNOWLEDGE_FILE, encoding="utf-8-sig")
    df.columns = df.columns.str.upper().str.strip()
    result = {}
    for _, row in df.iterrows():
        email = str(row.get("EMAIL", "")).lower().strip()
        status = str(row.get("STATUS", "")).lower().strip()
        if email and "@" in email and status and status != "nan":
            result[email] = status
    return result


def load_sent_log() -> dict[str, str]:
    """Returns dict: email -> last_sent_date (string)."""
    if not EMAIL_LOG_FILE.exists():
        return {}
    df = pd.read_csv(EMAIL_LOG_FILE)
    df.columns = df.columns.str.lower().str.strip()
    df["email"] = df["email"].astype(str).str.lower().str.strip()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    result = {}
    for _, row in df.iterrows():
        e = row["email"]
        t = row["timestamp"]
        if pd.notna(t) and e and "@" in e:
            ts = t.strftime("%Y-%m-%d")
            if e not in result or ts > result[e]:
                result[e] = ts
    return result


# =========================================================
# CAMPAIGN NAME FROM FILE
# =========================================================
def extract_campaign(file_path: Path) -> str:
    name = file_path.stem.lower()
    if "panjiva_raw_" in name:
        return name.split("panjiva_raw_", 1)[1].upper()
    return name.upper()


# =========================================================
# FIND COLUMN (fuzzy)
# =========================================================
def find_col(cols, *keys) -> str | None:
    """Find first column that contains all keys (case-insensitive)."""
    for c in cols:
        cl = c.lower()
        if all(k in cl for k in keys):
            return c
    return None


# =========================================================
# MAIN INGEST
# =========================================================
def main():
    log.info("=" * 60)
    log.info("  COMBINE ALL -- Master Data Layer Builder")
    log.info("=" * 60)

    # Load reference data
    kb_dict = load_kb()
    sent_dict = load_sent_log()
    log.info("KB entries: %d | Sent log entries: %d", len(kb_dict), len(sent_dict))

    cnee_rows    = []
    contact_rows = []
    shipper_rows = []

    panjiva_files = sorted(PANJIVA_DIR.glob("panjiva_raw_*.xlsx"))
    if not panjiva_files:
        log.error("No panjiva_raw_*.xlsx files found in %s", PANJIVA_DIR)
        return

    log.info("Found %d Panjiva files", len(panjiva_files))

    for fpath in panjiva_files:
        campaign = extract_campaign(fpath)
        log.info("")
        log.info("--- %s (campaign: %s) ---", fpath.name, campaign)

        xls = pd.ExcelFile(fpath)

        # =============================================
        # SHIPMENT SHEET -> CNEE + SHIPPER rows
        # =============================================
        ship_sheet = None
        for sname in SHIPMENT_SHEETS:
            if sname in xls.sheet_names:
                ship_sheet = sname
                break

        if ship_sheet:
            df = pd.read_excel(fpath, sheet_name=ship_sheet)
            df.columns = df.columns.astype(str).str.strip()
            cols = list(df.columns)

            # Find relevant columns (handle both naming conventions)
            col_cnee = find_col(cols, "consignee") or find_col(cols, "consignee name")
            col_shipper = find_col(cols, "shipper")
            col_carrier = find_col(cols, "carrier")
            col_dest = find_col(cols, "destination")
            col_pol = (find_col(cols, "place", "receipt")
                       or find_col(cols, "port", "lading"))

            # Collect all consignee email columns
            cnee_email_cols = [c for c in cols
                               if "consignee" in c.lower() and "email" in c.lower()]
            shipper_email_cols = [c for c in cols
                                  if "shipper" in c.lower() and "email" in c.lower()]

            cnee_count = 0
            shipper_count = 0

            for _, row in df.iterrows():
                cnee_name = str(row.get(col_cnee, "")).strip().upper() if col_cnee else ""
                carrier = str(row.get(col_carrier, "")).strip().upper() if col_carrier else ""
                dest = map_destination(str(row.get(col_dest, ""))) if col_dest else ""
                pol = map_pol(str(row.get(col_pol, ""))) if col_pol else ""

                # CNEE emails
                cnee_emails = extract_emails(
                    *(str(row.get(c, "")) for c in cnee_email_cols)
                )
                for e in cnee_emails:
                    pic = _derive_pic(e)
                    cnee_rows.append({
                        "EMAIL": e,
                        "COMPANY": cnee_name,
                        "CNEE_PIC": pic,
                        "POL": pol,
                        "DESTINATION": dest,
                        "CARRIER": carrier,
                        "TOTAL_SHIPMENT": 1,
                        "CAMPAIGN_ID": campaign,
                    })
                    cnee_count += 1

                # SHIPPER emails
                shipper_name = ""
                if col_shipper:
                    shipper_name = str(row.get(col_shipper, "")).strip().upper()

                shipper_emails = extract_emails(
                    *(str(row.get(c, "")) for c in shipper_email_cols)
                )
                for e in shipper_emails:
                    pic = _derive_pic(e)
                    shipper_rows.append({
                        "EMAIL": e,
                        "COMPANY": shipper_name,
                        "SHIPPER_PIC": pic,
                        "POL": pol,
                        "DESTINATION": dest,
                        "CARRIER": carrier,
                        "TOTAL_SHIPMENT": 1,
                        "CAMPAIGN_ID": campaign,
                    })
                    shipper_count += 1

            log.info("  Shipments: %d cnee emails, %d shipper emails",
                     cnee_count, shipper_count)
        else:
            log.warning("  No shipment sheet found in %s", fpath.name)

        # =============================================
        # CONTACT INFO SHEET -> CONTACT rows
        # =============================================
        if "Contact Info" in xls.sheet_names:
            df_ci = pd.read_excel(fpath, sheet_name="Contact Info")
            df_ci.columns = df_ci.columns.astype(str).str.strip()
            ci_cols = list(df_ci.columns)

            # Handle the "ail" typo column name (found in candle file)
            col_email = find_col(ci_cols, "email") or find_col(ci_cols, "ail")
            col_company = find_col(ci_cols, "company")
            col_name = find_col(ci_cols, "contact name") or find_col(ci_cols, "name")
            col_position = find_col(ci_cols, "position")
            col_phone = find_col(ci_cols, "phone")
            col_profile = find_col(ci_cols, "profile")

            ci_count = 0
            for _, row in df_ci.iterrows():
                raw_email = str(row.get(col_email, "")) if col_email else ""
                email = clean_email(raw_email)
                if not email:
                    continue

                company = str(row.get(col_company, "")).strip() if col_company else ""
                name = str(row.get(col_name, "")).strip() if col_name else ""
                position = str(row.get(col_position, "")).strip() if col_position else ""
                phone = str(row.get(col_phone, "")).strip() if col_phone else ""
                profile = str(row.get(col_profile, "")).strip() if col_profile else ""

                # Clean nan strings
                for val_name in ["company", "name", "position", "phone", "profile"]:
                    if locals()[val_name].lower() in ("nan", "none", ""):
                        exec(f"{val_name} = ''")

                contact_rows.append({
                    "EMAIL": email,
                    "COMPANY": company,
                    "CONTACT_NAME": name if name.lower() not in ("nan", "none") else "",
                    "POSITION": position if position.lower() not in ("nan", "none") else "",
                    "PHONE": phone if phone.lower() not in ("nan", "none") else "",
                    "CAMPAIGN_ID": campaign,
                    "PROFILE_URL": profile if profile.lower() not in ("nan", "none") else "",
                })
                ci_count += 1

            log.info("  Contacts: %d valid emails", ci_count)
        else:
            log.warning("  No Contact Info sheet in %s", fpath.name)

    # =============================================
    # STEP 5: MIGRATE existing data.xlsx
    # =============================================
    log.info("")
    log.info("--- Migrating existing data.xlsx ---")
    if DATA_FILE.exists():
        df_data = pd.read_excel(DATA_FILE)
        df_data.columns = df_data.columns.str.strip().str.upper().str.replace(" ", "_")

        existing_cnee_emails = {r["EMAIL"] for r in cnee_rows}
        existing_shipper_emails = {r["EMAIL"] for r in shipper_rows}

        migrated_cnee = 0
        migrated_shipper = 0

        for _, row in df_data.iterrows():
            status = str(row.get("STATUS", "")).strip().upper()

            # Map STATUS -> SEQ_STATUS
            if status in ("BOUNCED", "BLOCKED"):
                seq_status = "BOUNCED"
            else:
                seq_status = "ACTIVE"

            # CNEE
            cnee_email = str(row.get("CNEE_EMAIL", "")).strip().lower()
            if "@" in cnee_email and cnee_email not in existing_cnee_emails:
                cnee_rows.append({
                    "EMAIL": cnee_email,
                    "COMPANY": str(row.get("CNEE_NAME", "")).strip(),
                    "CNEE_PIC": str(row.get("CNEE_PIC", "")).strip(),
                    "POL": str(row.get("POL", "")).strip(),
                    "DESTINATION": str(row.get("DESTINATION", "")).strip(),
                    "CARRIER": str(row.get("CARRIER", "")).strip(),
                    "TOTAL_SHIPMENT": int(row.get("TOTAL_SHIPMENT", 1))
                        if pd.notna(row.get("TOTAL_SHIPMENT")) else 1,
                    "CAMPAIGN_ID": str(row.get("CMD_NAME", "")).strip(),
                    "_SEQ_STATUS_OVERRIDE": seq_status,
                })
                existing_cnee_emails.add(cnee_email)
                migrated_cnee += 1

            # SHIPPER
            shipper_email = str(row.get("SHIPPER_EMAIL", "")).strip().lower()
            if "@" in shipper_email and shipper_email not in existing_shipper_emails:
                shipper_rows.append({
                    "EMAIL": shipper_email,
                    "COMPANY": str(row.get("SHIPPER_NAME", "")).strip(),
                    "SHIPPER_PIC": str(row.get("SHIPPER_PIC", "")).strip(),
                    "POL": str(row.get("POL", "")).strip(),
                    "DESTINATION": str(row.get("DESTINATION", "")).strip(),
                    "CARRIER": str(row.get("CARRIER", "")).strip(),
                    "TOTAL_SHIPMENT": int(row.get("TOTAL_SHIPMENT", 1))
                        if pd.notna(row.get("TOTAL_SHIPMENT")) else 1,
                    "CAMPAIGN_ID": str(row.get("CMD_NAME", "")).strip(),
                    "_SEQ_STATUS_OVERRIDE": seq_status,
                })
                existing_shipper_emails.add(shipper_email)
                migrated_shipper += 1

        log.info("  Migrated from data.xlsx: %d cnee, %d shipper", migrated_cnee, migrated_shipper)
    else:
        log.warning("data.xlsx not found -- skipping migration")

    # =============================================
    # BUILD MASTER DataFrames + DEDUP + ENRICH
    # =============================================
    log.info("")
    log.info("--- Building master files ---")

    # --- CNEE MASTER ---
    df_cnee = _build_cnee_master(cnee_rows, kb_dict, sent_dict)
    df_cnee.to_excel(OUT_CNEE, index=False)
    log.info("cnee_master.xlsx: %d rows", len(df_cnee))

    # --- CONTACT MASTER ---
    df_contact = _build_contact_master(contact_rows, kb_dict, sent_dict)
    df_contact.to_excel(OUT_CONTACT, index=False)
    log.info("contact_master.xlsx: %d rows", len(df_contact))

    # --- SHIPPER MASTER ---
    df_shipper = _build_shipper_master(shipper_rows, kb_dict, sent_dict)
    df_shipper.to_excel(OUT_SHIPPER, index=False)
    log.info("shipper_master.xlsx: %d rows", len(df_shipper))

    # =============================================
    # SUMMARY REPORT
    # =============================================
    _print_summary(df_cnee, df_contact, df_shipper)


# =========================================================
# DERIVE PIC FROM EMAIL
# =========================================================
def _derive_pic(email: str) -> str:
    if not isinstance(email, str) or "@" not in email:
        return ""
    local = email.split("@")[0]
    tokens = re.split(r"[._\-]", local)
    tokens = [t for t in tokens if t.isalpha()]
    if not tokens:
        return ""
    if len(tokens) == 1:
        return tokens[0].capitalize()
    return f"{tokens[0].capitalize()} {tokens[-1].capitalize()}"


# =========================================================
# BUILD CNEE MASTER
# =========================================================
def _build_cnee_master(rows: list[dict], kb: dict, sent: dict) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Clean nan strings
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].replace({"nan": "", "None": "", "NAN": ""})

    # DEDUP: keep row with highest TOTAL_SHIPMENT per EMAIL
    df["TOTAL_SHIPMENT"] = pd.to_numeric(df["TOTAL_SHIPMENT"], errors="coerce").fillna(1).astype(int)
    df = df.sort_values("TOTAL_SHIPMENT", ascending=False).drop_duplicates("EMAIL", keep="first")

    # Aggregate destinations/carriers/pols per email before dedup lost them
    # (Already deduped, so just use what we have)

    # Extract seq_status override if present
    seq_override = df.pop("_SEQ_STATUS_OVERRIDE") if "_SEQ_STATUS_OVERRIDE" in df.columns else None

    # Enrich
    df["EMAIL_QUALITY_SCORE"] = df["EMAIL"].apply(email_quality_score)
    df["KB_STATUS"] = df["EMAIL"].apply(lambda e: kb.get(e, ""))
    df["ALREADY_SENT"] = df["EMAIL"].apply(lambda e: "Y" if e in sent else "N")
    df["LAST_SENT_DATE"] = df["EMAIL"].apply(lambda e: sent.get(e, ""))
    df["SEQ_STEP"] = 0
    df["SEQ_LAST_SENT"] = ""

    # SEQ_STATUS: default ACTIVE, but if KB says dead -> BOUNCED
    dead_statuses = {"hard_bounce", "policy_reject", "spam_block", "invalid"}
    df["SEQ_STATUS"] = df["KB_STATUS"].apply(
        lambda s: "BOUNCED" if s in dead_statuses else "ACTIVE"
    )

    # Apply override from data.xlsx migration
    if seq_override is not None:
        mask = seq_override.notna() & (seq_override != "")
        df.loc[mask, "SEQ_STATUS"] = seq_override[mask]

    df["SOURCE"] = "shipment"

    # Block count
    stats["kb_blocked"] += (df["SEQ_STATUS"] == "BOUNCED").sum()

    final_cols = [
        "EMAIL", "COMPANY", "CNEE_PIC", "POL", "DESTINATION", "CARRIER",
        "TOTAL_SHIPMENT", "CAMPAIGN_ID",
        "EMAIL_QUALITY_SCORE", "KB_STATUS", "ALREADY_SENT",
        "LAST_SENT_DATE", "SEQ_STEP", "SEQ_LAST_SENT", "SEQ_STATUS", "SOURCE",
    ]
    return df[[c for c in final_cols if c in df.columns]].reset_index(drop=True)


# =========================================================
# BUILD CONTACT MASTER
# =========================================================
def _build_contact_master(rows: list[dict], kb: dict, sent: dict) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Clean nan strings
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].replace({"nan": "", "None": "", "NAN": ""})

    # Compute priority score
    df["PRIORITY_SCORE"] = df["POSITION"].apply(compute_priority_score)

    # DEDUP: keep row with highest PRIORITY_SCORE per EMAIL
    df = df.sort_values("PRIORITY_SCORE", ascending=False).drop_duplicates("EMAIL", keep="first")

    # Enrich
    df["EMAIL_QUALITY_SCORE"] = df["EMAIL"].apply(email_quality_score)
    df["KB_STATUS"] = df["EMAIL"].apply(lambda e: kb.get(e, ""))
    df["ALREADY_SENT"] = df["EMAIL"].apply(lambda e: "Y" if e in sent else "N")
    df["LAST_SENT_DATE"] = df["EMAIL"].apply(lambda e: sent.get(e, ""))
    df["SEQ_STEP"] = 0
    df["SEQ_LAST_SENT"] = ""

    dead_statuses = {"hard_bounce", "policy_reject", "spam_block", "invalid"}
    df["SEQ_STATUS"] = df["KB_STATUS"].apply(
        lambda s: "BOUNCED" if s in dead_statuses else "ACTIVE"
    )
    df["SOURCE"] = "contact_info"

    stats["kb_blocked"] += (df["SEQ_STATUS"] == "BOUNCED").sum()

    final_cols = [
        "EMAIL", "COMPANY", "CONTACT_NAME", "POSITION", "PHONE",
        "CAMPAIGN_ID", "PROFILE_URL", "PRIORITY_SCORE",
        "EMAIL_QUALITY_SCORE", "KB_STATUS", "ALREADY_SENT",
        "LAST_SENT_DATE", "SEQ_STEP", "SEQ_LAST_SENT", "SEQ_STATUS", "SOURCE",
    ]
    return df[[c for c in final_cols if c in df.columns]].reset_index(drop=True)


# =========================================================
# BUILD SHIPPER MASTER
# =========================================================
def _build_shipper_master(rows: list[dict], kb: dict, sent: dict) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Clean nan strings
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].replace({"nan": "", "None": "", "NAN": ""})

    df["TOTAL_SHIPMENT"] = pd.to_numeric(df["TOTAL_SHIPMENT"], errors="coerce").fillna(1).astype(int)
    df = df.sort_values("TOTAL_SHIPMENT", ascending=False).drop_duplicates("EMAIL", keep="first")

    seq_override = df.pop("_SEQ_STATUS_OVERRIDE") if "_SEQ_STATUS_OVERRIDE" in df.columns else None

    df["EMAIL_QUALITY_SCORE"] = df["EMAIL"].apply(email_quality_score)
    df["KB_STATUS"] = df["EMAIL"].apply(lambda e: kb.get(e, ""))
    df["ALREADY_SENT"] = df["EMAIL"].apply(lambda e: "Y" if e in sent else "N")
    df["LAST_SENT_DATE"] = df["EMAIL"].apply(lambda e: sent.get(e, ""))
    df["SEQ_STEP"] = 0
    df["SEQ_LAST_SENT"] = ""

    dead_statuses = {"hard_bounce", "policy_reject", "spam_block", "invalid"}
    df["SEQ_STATUS"] = df["KB_STATUS"].apply(
        lambda s: "BOUNCED" if s in dead_statuses else "ACTIVE"
    )

    if seq_override is not None:
        mask = seq_override.notna() & (seq_override != "")
        df.loc[mask, "SEQ_STATUS"] = seq_override[mask]

    df["SOURCE"] = "shipper"

    stats["kb_blocked"] += (df["SEQ_STATUS"] == "BOUNCED").sum()

    final_cols = [
        "EMAIL", "COMPANY", "SHIPPER_PIC", "POL", "DESTINATION", "CARRIER",
        "TOTAL_SHIPMENT", "CAMPAIGN_ID",
        "EMAIL_QUALITY_SCORE", "KB_STATUS", "ALREADY_SENT",
        "LAST_SENT_DATE", "SEQ_STEP", "SEQ_LAST_SENT", "SEQ_STATUS", "SOURCE",
    ]
    return df[[c for c in final_cols if c in df.columns]].reset_index(drop=True)


# =========================================================
# SUMMARY
# =========================================================
def _print_summary(df_cnee, df_contact, df_shipper):
    log.info("")
    log.info("=" * 60)
    log.info("  COMBINE ALL -- SUMMARY REPORT")
    log.info("=" * 60)

    log.info("")
    log.info("  CNEE MASTER:    %d total rows", len(df_cnee))
    if not df_cnee.empty:
        new_cnee = (df_cnee["ALREADY_SENT"] == "N").sum()
        log.info("    New (never sent): %d", new_cnee)
        log.info("    Already sent:     %d", (df_cnee["ALREADY_SENT"] == "Y").sum())
        log.info("    KB blocked:       %d", (df_cnee["SEQ_STATUS"] == "BOUNCED").sum())

    log.info("")
    log.info("  CONTACT MASTER: %d total rows", len(df_contact))
    if not df_contact.empty:
        new_cont = (df_contact["ALREADY_SENT"] == "N").sum()
        high_pri = (df_contact["PRIORITY_SCORE"] >= 8).sum()
        log.info("    New (never sent):     %d", new_cont)
        log.info("    Already sent:         %d", (df_contact["ALREADY_SENT"] == "Y").sum())
        log.info("    High priority (>=8):  %d  <-- DECISION MAKERS", high_pri)
        log.info("    KB blocked:           %d", (df_contact["SEQ_STATUS"] == "BOUNCED").sum())

        log.info("")
        log.info("  Top 5 positions by count:")
        if "POSITION" in df_contact.columns:
            pos = df_contact[df_contact["POSITION"] != ""]["POSITION"]
            for p, c in pos.value_counts().head(5).items():
                log.info("    %-40s : %d", p, c)

    log.info("")
    log.info("  SHIPPER MASTER: %d total rows", len(df_shipper))
    if not df_shipper.empty:
        new_ship = (df_shipper["ALREADY_SENT"] == "N").sum()
        log.info("    New (never sent): %d", new_ship)
        log.info("    Already sent:     %d", (df_shipper["ALREADY_SENT"] == "Y").sum())
        log.info("    KB blocked:       %d", (df_shipper["SEQ_STATUS"] == "BOUNCED").sum())

    log.info("")
    log.info("  CLEANING STATS:")
    log.info("    Emails cleaned (prefix stripped): %d", stats["emails_cleaned"])
    log.info("    Emails rejected (bad format):     %d", stats["emails_bad_format"])
    log.info("    Total blocked by KB:              %d", stats["kb_blocked"])
    log.info("=" * 60)


if __name__ == "__main__":
    main()
