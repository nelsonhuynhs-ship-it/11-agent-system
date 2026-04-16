"""
process_reply.py — Customer Reply Tier Classifier  v3.0
=========================================================
UPGRADE v3.0:
  - Quote-Only Filter: only analyse emails from quote campaigns
    (CAMPAIGN_ID in email_log.csv) AND prospect customers
    (TOTAL_SHIPMENT = 0 / NaN in data.xlsx).
    Active customers (TOTAL_SHIPMENT > 0) are SKIPPED entirely.
  - Intent Classifier: reads subject + body of each reply to
    categorise as booking_intent / price_inquiry / negotiating /
    gratitude / objection / general.
  - Auto Tier Promotion: intent overrides raw count-based tier.
  - Tier History: appends a row to logs/tier_history.csv every run.
  - Output: customer_final.xlsx now includes INTENT column + new
    FOLLOW_UP sheet (handoff to follow_up_engine.py).

Sheets produced:
  NO_REPLY     - sent but no response (prospect only)
  REPLY_1      - replied exactly 1 time
  REPLY_2      - replied 2 times OR price_inquiry intent
  REPLY_3      - replied 3+ times OR negotiating/booking intent (HOT)
  BOUNCED      - hard_bounce / policy_reject / spam_block
  AUTO_REPLY   - out-of-office detected
  FOLLOW_UP    - combined alert view for follow_up_engine
"""

from __future__ import annotations

import csv
import logging
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import win32com.client

# =========================================================
# CONFIG
# =========================================================
SCAN_DAYS         = 60     # scan last N days of email (replaces fixed item limit)
PR_SMTP_ADDRESS   = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
BODY_SCAN_CHARS   = 800   # only read first N chars of body for speed
TEAM_FOLDER_NAME  = "TEAM SUNNY"  # sub-folder where main.py routes emails

BASE_DIR       = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
LOG_DIR        = PROJECT_ROOT / "logs"
BACKUP_DIR     = PROJECT_ROOT / "backup"
DATA_FILE      = PROJECT_ROOT / "data.xlsx"
EMAIL_LOG_FILE = PROJECT_ROOT / "logs"  / "email_log.csv"
KNOWLEDGE_FILE = PROJECT_ROOT / "logs"  / "email_knowledge.csv"
FINAL_FILE     = PROJECT_ROOT / "data" / "customer_final.xlsx"
TIER_HISTORY_FILE = LOG_DIR / "tier_history.csv"

LOG_DIR.mkdir(exist_ok=True)
BACKUP_DIR.mkdir(exist_ok=True)

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
# KNOWLEDGE STATUS GROUPS
# =========================================================
DEAD_STATUSES     = {"hard_bounce", "policy_reject", "spam_block", "invalid"}
AUTO_OOO_STATUSES = {"auto_reply"}

# =========================================================
# INTENT KEYWORD MAP
# Higher-ranked intents override lower-ranked ones.
# Rank: booking_intent (5) > negotiating (4) > price_inquiry (3)
#       > gratitude (2) > objection (1) > general (0)
# =========================================================
INTENT_RULES: list[tuple[str, int, list[str]]] = [
    ("booking_intent", 5, [
        "please book", "please proceed", "go ahead", "confirm booking",
        "let's proceed", "proceed to book", "place the booking",
        "we would like to book", "book this shipment", "confirmed",
    ]),
    ("negotiating", 4, [
        "better rate", "can you do better", "competitor offer",
        "beat the price", "match the rate", "lower the rate",
        "reduce the price", "can you offer", "best rate", "what is your best",
    ]),
    ("price_inquiry", 3, [
        "your rate", "freight rate", "quote", "how much", "what is the price",
        "provide rate", "rate request", "pricing", "cost for",
        "shipping cost", "sea freight", "ocean freight", "fcl rate", "lcl rate",
        "transit time", "etd", "eta", "free time", "demurrage",
        "chào giá", "báo giá", "giá cước",
    ]),
    ("gratitude", 2, [
        "thank you", "thanks", "thank u", "appreciate", "cảm ơn",
        "noted with thanks", "noted", "well received", "received",
        "đã nhận", "đã xem",
    ]),
    ("objection", 1, [
        "too high", "not competitive", "no need", "not interested",
        "already have", "pass on this", "decline", "not suitable",
        "don't need", "không cần", "thôi", "không phù hợp",
    ]),
]


def classify_intent(subject: str, body: str) -> str:
    """
    Analyse subject + truncated body and return the highest-ranked intent.

    Returns one of:
        booking_intent | negotiating | price_inquiry |
        gratitude | objection | general
    """
    text = f"{subject} {body[:BODY_SCAN_CHARS]}".lower()
    best_rank   = -1
    best_intent = "general"

    for intent_name, rank, keywords in INTENT_RULES:
        for kw in keywords:
            if kw in text:
                if rank > best_rank:
                    best_rank   = rank
                    best_intent = intent_name
                break  # one keyword match per intent is enough

    return best_intent


def intent_to_min_tier(intent: str) -> Optional[str]:
    """
    Return the minimum tier this intent forces, or None (use count-based).

    booking_intent → REPLY_3 (hot lead)
    negotiating    → REPLY_3
    price_inquiry  → REPLY_2 (at least)
    gratitude      → REPLY_1 (at least)
    objection      → stays at count-based (may stay NO_REPLY if not replied)
    general        → stays at count-based
    """
    return {
        "booking_intent": "REPLY_3",
        "negotiating":    "REPLY_3",
        "price_inquiry":  "REPLY_2",
        "gratitude":      "REPLY_1",
    }.get(intent, None)


# =========================================================
# HELPERS
# =========================================================
def get_sender_smtp(msg) -> str:
    """Resolve true SMTP address bypassing Exchange X500."""
    try:
        smtp = msg.Sender.PropertyAccessor.GetProperty(PR_SMTP_ADDRESS)
        if smtp and "@" in smtp:
            return smtp.strip().lower()
    except Exception:
        pass
    try:
        addr = msg.SenderEmailAddress
        if addr and "@" in addr and not addr.startswith("/O="):
            return addr.strip().lower()
    except Exception:
        pass
    try:
        if msg.SenderEmailType == "EX":
            return msg.Sender.GetExchangeUser().PrimarySmtpAddress.lower()
    except Exception:
        pass
    return ""


# =========================================================
# LOAD EMAIL LOG  →  quote campaign addresses only
# =========================================================
def load_email_log() -> pd.DataFrame:
    """
    Load email_log.csv and return only rows that belong to a valid
    quote campaign (CAMPAIGN_ID is a non-empty string, not NaN/None).
    """
    if not EMAIL_LOG_FILE.exists():
        log.warning("email_log.csv not found.")
        return pd.DataFrame(columns=["email", "campaign_id", "status"])

    df = pd.read_csv(EMAIL_LOG_FILE)
    df.columns = df.columns.str.lower()
    df["email"]       = df["email"].astype(str).str.lower().str.strip()
    df["campaign_id"] = df["campaign_id"].astype(str).str.upper().str.strip()
    df["status"]      = df["status"].astype(str).str.upper().str.strip()

    # Keep only valid campaign rows (exclude NaN / empty campaign IDs)
    valid_mask = df["campaign_id"].notna() & (df["campaign_id"] != "NAN") & (df["campaign_id"] != "")
    df_quote = df[valid_mask].copy()

    log.info("Email log: %d total rows -> %d quote-campaign rows",
             len(df), len(df_quote))
    return df_quote


# =========================================================
# LOAD DATA  →  derive prospect email set (TOTAL_SHIPMENT = 0/NaN)
# =========================================================
def load_prospect_emails(df_log: pd.DataFrame) -> set[str]:
    """
    Return the set of emails that are PROSPECTS (not active customers).

    Rule: an email is an active customer if it appears in data.xlsx
    with TOTAL_SHIPMENT > 0. All other emails in the quote log are
    treated as prospects and included in analysis.
    """
    if not DATA_FILE.exists():
        log.warning("data.xlsx not found — treating all log emails as prospects.")
        return set(df_log["email"].unique())

    df_data = pd.read_excel(DATA_FILE)
    df_data.columns = df_data.columns.str.strip().str.upper().str.replace(" ", "_")

    # Build active customer email set (TOTAL_SHIPMENT > 0)
    active_emails: set[str] = set()
    shipment_col = "TOTAL_SHIPMENT" if "TOTAL_SHIPMENT" in df_data.columns else None

    if shipment_col:
        df_data[shipment_col] = pd.to_numeric(df_data[shipment_col], errors="coerce").fillna(0)
        for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]:
            if col not in df_data.columns:
                continue
            active_rows = df_data[df_data[shipment_col] > 0]
            emails = active_rows[col].dropna().astype(str).str.lower().str.strip()
            active_emails.update(e for e in emails if "@" in e)

    all_quote_emails = set(df_log["email"].unique())
    prospect_emails  = all_quote_emails - active_emails

    log.info("Quote emails: %d | Active customer (excluded): %d | Prospects (analysed): %d",
             len(all_quote_emails), len(active_emails), len(prospect_emails))
    return prospect_emails


# =========================================================
# LOAD KNOWLEDGE
# =========================================================
def load_knowledge() -> dict[str, dict]:
    if not KNOWLEDGE_FILE.exists():
        return {}
    df = pd.read_csv(KNOWLEDGE_FILE, encoding="utf-8-sig")
    df.columns = df.columns.str.upper()
    df["EMAIL"] = df["EMAIL"].astype(str).str.lower().str.strip()
    result = {}
    for _, row in df.iterrows():
        email = row["EMAIL"]
        if email and "@" in email:
            result[email] = {
                "status":      str(row.get("STATUS", "")).lower().strip(),
                "replacement": str(row.get("REPLACEMENT_EMAIL", "")).lower().strip(),
                "role_hint":   str(row.get("ROLE_HINT", "")).strip(),
                "remark":      str(row.get("REMARK", "")).strip(),
                "count":       int(row.get("COUNT", 1)),
            }
    return result


# =========================================================
# SCAN OUTLOOK FOR HUMAN REPLIES  (with intent analysis)
# v3.1: Scans Inbox + TEAM SUNNY sub-folders, date-range based
# =========================================================
def _find_team_folder(namespace):
    """Find the TEAM SUNNY folder (searches root, inbox children, and recursively)."""
    for store in namespace.Stores:
        try:
            root = store.GetRootFolder()
        except Exception:
            continue
        # Direct child of root
        try:
            return root.Folders[TEAM_FOLDER_NAME]
        except Exception:
            pass
        # Inside Inbox
        try:
            inbox = namespace.GetDefaultFolder(6)
            return inbox.Folders[TEAM_FOLDER_NAME]
        except Exception:
            pass
    return None


def _collect_all_subfolders(folder) -> list:
    """Recursively collect all sub-folders under a given folder."""
    result = [folder]
    try:
        for sub in folder.Folders:
            result.extend(_collect_all_subfolders(sub))
    except Exception:
        pass
    return result


def _scan_folder_for_replies(
    folder,
    prospect_emails: set[str],
    reply_count: dict[str, int],
    reply_intent: dict[str, str],
    cutoff_date,
    intent_rank: dict,
) -> int:
    """Scan a single folder for prospect replies. Returns items scanned."""
    AUTO_MARKERS   = ["automatic reply", "out of office", "auto reply", "auto-reply"]
    BOUNCE_MARKERS = ["undeliverable", "delivery status notification",
                      "mail delivery failed", "returned mail"]
    scanned = 0
    try:
        messages = folder.Items
        messages.Sort("[ReceivedTime]", True)
    except Exception:
        return 0

    for msg in messages:
        try:
            received = msg.ReceivedTime
            if received < cutoff_date:
                break  # sorted newest-first, so we can stop
        except Exception:
            continue

        scanned += 1
        try:
            if msg.Class != 43:  # olMail = 43
                continue
            subject = (msg.Subject or "").lower()
            sender  = get_sender_smtp(msg)
        except Exception:
            continue

        if any(k in subject for k in AUTO_MARKERS + BOUNCE_MARKERS):
            continue

        if sender and sender in prospect_emails:
            reply_count[sender] = reply_count.get(sender, 0) + 1
            try:
                body = msg.Body or ""
            except Exception:
                body = ""
            intent = classify_intent(msg.Subject or "", body)
            existing_rank = intent_rank.get(reply_intent.get(sender, "general"), 0)
            if intent_rank.get(intent, 0) > existing_rank:
                reply_intent[sender] = intent

    return scanned


def scan_for_replies(
    prospect_emails: set[str],
) -> tuple[dict[str, int], dict[str, str]]:
    """
    Scan Inbox + TEAM SUNNY sub-folders for human replies.
    Uses date-range (last SCAN_DAYS days) instead of fixed item limit.

    Returns
    -------
    reply_count  : dict email -> int
    reply_intent : dict email -> highest intent string
    """
    try:
        outlook   = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        inbox     = namespace.GetDefaultFolder(6)
    except Exception as exc:
        log.error("Cannot connect to Outlook: %s", exc)
        return {}, {}

    reply_count:  dict[str, int] = {}
    reply_intent: dict[str, str] = {}
    total_scanned = 0

    INTENT_RANK = {
        "booking_intent": 5, "negotiating": 4, "price_inquiry": 3,
        "gratitude": 2, "objection": 1, "general": 0,
    }

    # Date cutoff (COM-compatible datetime)
    import pywintypes
    cutoff = datetime.now() - __import__('datetime').timedelta(days=SCAN_DAYS)
    cutoff_com = pywintypes.Time(cutoff)

    # --- 1. Scan Inbox ---
    n = _scan_folder_for_replies(
        inbox, prospect_emails, reply_count, reply_intent, cutoff_com, INTENT_RANK
    )
    total_scanned += n
    log.info("Scanned Inbox: %d items (last %d days)", n, SCAN_DAYS)

    # --- 2. Scan TEAM SUNNY sub-folders ---
    team_folder = _find_team_folder(namespace)
    if team_folder:
        subfolders = _collect_all_subfolders(team_folder)
        for sf in subfolders:
            try:
                sf_name = sf.Name
            except Exception:
                sf_name = "(unknown)"
            n = _scan_folder_for_replies(
                sf, prospect_emails, reply_count, reply_intent, cutoff_com, INTENT_RANK
            )
            if n > 0:
                log.info("Scanned '%s': %d items", sf_name, n)
            total_scanned += n
    else:
        log.warning("TEAM SUNNY folder not found -- only Inbox was scanned.")

    log.info("Total scanned %d items | Replies from %d prospects | %d with intent signals",
             total_scanned, len(reply_count),
             sum(1 for i in reply_intent.values() if i != "general"))
    return reply_count, reply_intent


# =========================================================
# FALLBACK: Cross-reference email_log.csv REPLIED entries
# =========================================================
def supplement_from_log(
    prospect_emails: set[str],
    reply_count: dict[str, int],
    reply_intent: dict[str, str],
) -> None:
    """
    For any email with status=REPLIED in email_log.csv that is a prospect
    but NOT already in reply_count, add it as a REPLY_1 with 'general' intent.
    This catches replies that Outlook scan may have missed (e.g. old emails
    that fell outside the scan window or were in archived folders).
    """
    if not EMAIL_LOG_FILE.exists():
        return

    df = pd.read_csv(EMAIL_LOG_FILE)
    df.columns = df.columns.str.lower().str.strip()
    df["email"]  = df["email"].astype(str).str.lower().str.strip()
    df["status"] = df["status"].astype(str).str.upper().str.strip()

    replied_mask = df["status"].isin(["REPLIED", "REPLIED_1", "REPLIED_2", "REPLIED_3"])
    replied_emails = set(df[replied_mask]["email"].unique())

    # Only add prospects not already found by Outlook scan
    new_replies = (replied_emails & prospect_emails) - set(reply_count.keys())

    for email in new_replies:
        reply_count[email] = max(reply_count.get(email, 0), 1)
        if email not in reply_intent:
            reply_intent[email] = "general"

    if new_replies:
        log.info("Fallback: added %d REPLIED emails from email_log.csv", len(new_replies))


# =========================================================
# ASSIGN TIER  (intent-aware)
# =========================================================
def assign_tier(
    email: str,
    reply_count: dict,
    reply_intent: dict,
    knowledge: dict,
) -> str:
    email  = email.lower().strip()
    kb     = knowledge.get(email, {})
    status = kb.get("status", "")

    if status in DEAD_STATUSES:
        return "BOUNCED"
    if status in AUTO_OOO_STATUSES:
        return "AUTO_REPLY"

    count  = reply_count.get(email, 0)
    intent = reply_intent.get(email, "general")

    # Count-based baseline
    if count == 0:
        base = "NO_REPLY"
    elif count == 1:
        base = "REPLY_1"
    elif count == 2:
        base = "REPLY_2"
    else:
        base = "REPLY_3"

    # Intent override (can only promote, never demote)
    tier_rank = {"NO_REPLY": 0, "REPLY_1": 1, "REPLY_2": 2, "REPLY_3": 3}
    min_tier  = intent_to_min_tier(intent)
    if min_tier and tier_rank.get(min_tier, 0) > tier_rank.get(base, 0):
        return min_tier

    return base


# =========================================================
# WRITE TIER HISTORY
# =========================================================
def append_tier_history(
    email: str,
    tier: str,
    intent: str,
    campaign_id: str,
    days_since_contact: int,
) -> None:
    """Append one row to logs/tier_history.csv (creates file + header if needed)."""
    file_exists = TIER_HISTORY_FILE.exists()
    with open(TIER_HISTORY_FILE, "a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if not file_exists:
            writer.writerow([
                "scan_date", "email", "campaign_id",
                "tier", "intent", "days_since_last_contact",
            ])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            email,
            campaign_id,
            tier,
            intent,
            days_since_contact,
        ])


# =========================================================
# MAIN
# =========================================================
def main() -> None:
    log.info("=" * 60)
    log.info("  CUSTOMER REPLY TIER CLASSIFIER  v3.0")
    log.info("  Quote-Only | Intent-Aware | Tier History")
    log.info("=" * 60)

    # 1. Load quote campaign email log
    df_log = load_email_log()
    if df_log.empty:
        log.error("No quote campaign emails in email_log.csv. Run send_email.py first.")
        return

    # 2. Filter to prospect emails only (exclude active customers)
    prospect_emails = load_prospect_emails(df_log)
    if not prospect_emails:
        log.warning("No prospect emails found after active-customer filter.")
        return

    # 3. Build campaign lookup: email → campaign_id (most recent)
    email_campaign: dict[str, str] = {}
    if "timestamp" in df_log.columns:
        df_sorted = df_log.sort_values("timestamp", ascending=False)
    else:
        df_sorted = df_log
    for _, row in df_sorted.iterrows():
        e = row["email"]
        if e not in email_campaign:
            email_campaign[e] = row["campaign_id"]

    # 4. Load knowledge
    knowledge = load_knowledge()
    log.info("Knowledge entries: %d", len(knowledge))

    # 5. Scan Outlook for human replies (prospect-only)
    reply_count, reply_intent = scan_for_replies(prospect_emails)

    # 5b. Fallback: supplement with email_log.csv REPLIED entries
    supplement_from_log(prospect_emails, reply_count, reply_intent)

    # 6. Load data.xlsx (for full row context)
    if not DATA_FILE.exists():
        log.error("data.xlsx not found.")
        return

    df_data = pd.read_excel(DATA_FILE)
    df_data.columns = df_data.columns.str.strip().str.upper().str.replace(" ", "_")

    # Normalise email columns
    for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]:
        if col in df_data.columns:
            df_data[col] = df_data[col].astype(str).str.lower().str.strip()

    # Numeric total_shipment for filtering
    if "TOTAL_SHIPMENT" in df_data.columns:
        df_data["TOTAL_SHIPMENT"] = pd.to_numeric(
            df_data["TOTAL_SHIPMENT"], errors="coerce"
        ).fillna(0)

    # ─── Keep ONLY prospect rows ──────────────────────────────────────────
    def row_has_prospect_email(row) -> bool:
        for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]:
            e = str(row.get(col, ""))
            if "@" in e and e in prospect_emails:
                return True
        return False

    df_prospects = df_data[df_data.apply(row_has_prospect_email, axis=1)].copy()
    active_count = len(df_data) - len(df_prospects)
    log.info("Rows kept (prospect): %d | Rows excluded (active customer): %d",
             len(df_prospects), active_count)
    # ─────────────────────────────────────────────────────────────────────

    # 7. Assign tier + intent to each row
    tier_priority = {
        "BOUNCED": 6, "AUTO_REPLY": 5, "REPLY_3": 4,
        "REPLY_2": 3, "REPLY_1": 2, "NO_REPLY": 1,
    }

    def get_row_tier(row) -> str:
        emails = [
            str(row.get(col, "")).lower().strip()
            for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]
            if "@" in str(row.get(col, ""))
        ]
        best = "NO_REPLY"
        for e in emails:
            if e not in prospect_emails:
                continue
            t = assign_tier(e, reply_count, reply_intent, knowledge)
            if tier_priority.get(t, 0) > tier_priority.get(best, 0):
                best = t
        return best

    def get_row_intent(row) -> str:
        emails = [
            str(row.get(col, "")).lower().strip()
            for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]
            if "@" in str(row.get(col, ""))
        ]
        best_rank   = -1
        best_intent = "general"
        intent_rank = {
            "booking_intent": 5, "negotiating": 4, "price_inquiry": 3,
            "gratitude": 2, "objection": 1, "general": 0,
        }
        for e in emails:
            i = reply_intent.get(e, "general")
            if intent_rank.get(i, 0) > best_rank:
                best_rank   = intent_rank[i]
                best_intent = i
        return best_intent

    def get_row_reply_count(row) -> int:
        return max(
            reply_count.get(str(row.get("CNEE_EMAIL", "")).lower(), 0),
            reply_count.get(str(row.get("SHIPPER_EMAIL", "")).lower(), 0),
        )

    df_prospects["REPLY_TIER"]  = df_prospects.apply(get_row_tier, axis=1)
    df_prospects["INTENT"]      = df_prospects.apply(get_row_intent, axis=1)
    df_prospects["REPLY_COUNT"] = df_prospects.apply(get_row_reply_count, axis=1)
    df_prospects["CAMPAIGN_ID"] = df_prospects.apply(
        lambda row: email_campaign.get(
            str(row.get("CNEE_EMAIL", "")).lower(), ""
        ) or email_campaign.get(
            str(row.get("SHIPPER_EMAIL", "")).lower(), ""
        ), axis=1
    )

    # 8. Knowledge supplement columns
    def _get_kb(row) -> dict:
        for col in ["CNEE_EMAIL", "SHIPPER_EMAIL"]:
            e = str(row.get(col, "")).lower().strip()
            if e in knowledge:
                return knowledge[e]
        return {}

    def _parse_name_from_remark(remark: str) -> str:
        m = re.search(r"alt contact:\s*([^|\n]+)", remark, re.I)
        return m.group(1).strip() if m else ""

    df_prospects["KB_REMARK"]         = df_prospects.apply(lambda r: _get_kb(r).get("remark", ""), axis=1)
    df_prospects["REPLACEMENT_EMAIL"] = df_prospects.apply(
        lambda r: _get_kb(r).get("replacement", ""), axis=1
    )
    df_prospects["REPLACEMENT_NAME"]  = df_prospects.apply(
        lambda r: _parse_name_from_remark(_get_kb(r).get("remark", "")), axis=1
    )
    df_prospects["REPLACEMENT_TITLE"] = df_prospects.apply(
        lambda r: _get_kb(r).get("role_hint", ""), axis=1
    )

    # 9. Write tier_history.csv
    now_str = datetime.now().strftime("%Y-%m-%d")
    for _, row in df_prospects.iterrows():
        primary_email = (
            str(row.get("CNEE_EMAIL", "")).lower()
            if "@" in str(row.get("CNEE_EMAIL", ""))
            else str(row.get("SHIPPER_EMAIL", "")).lower()
        )
        if "@" not in primary_email:
            continue
        append_tier_history(
            email            = primary_email,
            tier             = row["REPLY_TIER"],
            intent           = row["INTENT"],
            campaign_id      = row.get("CAMPAIGN_ID", ""),
            days_since_contact = 0,  # follow_up_engine.py will compute this properly
        )

    log.info("Tier history updated: %s", TIER_HISTORY_FILE)

    # 10. Build output sheets
    TIER_ORDER = ["NO_REPLY", "REPLY_1", "REPLY_2", "REPLY_3", "BOUNCED", "AUTO_REPLY"]

    # Priority columns for intent-heavy sheets
    INTENT_FRONT_COLS = ["CNEE_NAME", "CNEE_EMAIL", "CAMPAIGN_ID",
                         "REPLY_TIER", "INTENT", "REPLY_COUNT"]

    if FINAL_FILE.exists():
        shutil.copy(FINAL_FILE,
                    BACKUP_DIR / f"customer_final_{datetime.now():%Y%m%d_%H%M%S}.xlsx")

    tier_counts: dict[str, int] = {}

    with pd.ExcelWriter(FINAL_FILE, engine="openpyxl") as writer:
        for tier in TIER_ORDER:
            sheet_df = df_prospects[df_prospects["REPLY_TIER"] == tier].copy()
            sheet_df = sheet_df.sort_values(
                ["INTENT", "REPLY_COUNT"],
                ascending=[True, False],
                key=lambda col: col.map(
                    {"booking_intent": 0, "negotiating": 1,
                     "price_inquiry": 2, "gratitude": 3,
                     "objection": 4, "general": 5}
                ) if col.name == "INTENT" else col,
            )

            # Bring useful columns to the front for REPLY tiers
            if tier.startswith("REPLY") or tier == "NO_REPLY":
                front = [c for c in INTENT_FRONT_COLS if c in sheet_df.columns]
                other = [c for c in sheet_df.columns if c not in front]
                sheet_df = sheet_df[front + other]

            # AUTO_REPLY: put replacement cols first
            if tier == "AUTO_REPLY":
                priority = ["CNEE_NAME", "CNEE_EMAIL",
                            "REPLACEMENT_EMAIL", "REPLACEMENT_NAME",
                            "REPLACEMENT_TITLE", "KB_REMARK"]
                front = [c for c in priority if c in sheet_df.columns]
                other = [c for c in sheet_df.columns if c not in front]
                sheet_df = sheet_df[front + other]

            sheet_df.to_excel(writer, sheet_name=tier, index=False)
            tier_counts[tier] = len(sheet_df)

        # FOLLOW_UP sheet — hot prospects for follow_up_engine.py
        hot = df_prospects[
            df_prospects["REPLY_TIER"].isin(["REPLY_3", "REPLY_2"])
        ].copy()
        hot = hot.sort_values(
            ["REPLY_TIER", "REPLY_COUNT"], ascending=[True, False]
        )
        follow_up_cols = ["CNEE_NAME", "CNEE_EMAIL", "CAMPAIGN_ID",
                          "REPLY_TIER", "INTENT", "REPLY_COUNT",
                          "KB_REMARK", "REPLACEMENT_EMAIL"]
        fu_front = [c for c in follow_up_cols if c in hot.columns]
        fu_other = [c for c in hot.columns if c not in fu_front]
        hot[fu_front + fu_other].to_excel(writer, sheet_name="FOLLOW_UP", index=False)
        tier_counts["FOLLOW_UP"] = len(hot)

    # 11. Summary
    log.info("")
    log.info("=" * 60)
    log.info("  OUTPUT: customer_final.xlsx")
    log.info("  Active customers EXCLUDED: %d rows", active_count)
    log.info("=" * 60)
    for tier in TIER_ORDER + ["FOLLOW_UP"]:
        count = tier_counts.get(tier, 0)
        bar   = "#" * min(count // 5, 30)
        log.info("  %-12s : %4d rows  %s", tier, count, bar)
    log.info("=" * 60)


# =========================================================
# PHASE-04 UPGRADE: export REPLY events to intel.db
# ---------------------------------------------------------
# Re-use the existing Outlook scan + classify_intent machinery and
# write one REPLY event per prospect reply into email_engine.intel.memory.
# The xlsx output pipeline above is kept for backward compat.
# =========================================================
def export_events_to_intel() -> dict:
    """
    Scan Outlook Inbox + TEAM SUNNY for the last SCAN_DAYS (60d) and emit a
    REPLY event per prospect reply into intel.db.

    Returns
    -------
    dict — counts {scanned, events_logged, skipped}
    """
    stats = {"scanned": 0, "events_logged": 0, "skipped": 0}

    # 1. Load prospect universe (reuse existing helpers)
    df_log = load_email_log()
    if df_log.empty:
        log.warning("export_events_to_intel: email_log.csv empty — no prospects")
        return stats
    prospect_emails = load_prospect_emails(df_log)
    if not prospect_emails:
        log.warning("export_events_to_intel: no prospects after active-customer filter")
        return stats

    # 2. Intel hook (stub if module not yet present)
    try:
        from email_engine.intel.memory import log_event as _log_event  # type: ignore
    except Exception:
        def _log_event(event_type: str, **fields) -> None:  # type: ignore
            log.debug("[STUB log_event] %s %s", event_type, fields)

    # 3. Outlook iteration (reuses _find_team_folder + _collect_all_subfolders)
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        namespace = outlook.GetNamespace("MAPI")
        inbox = namespace.GetDefaultFolder(6)
    except Exception as exc:
        log.error("export_events_to_intel: cannot connect to Outlook: %s", exc)
        return stats

    import pywintypes  # noqa: WPS433 (delayed import ok for COM)
    from datetime import timedelta as _timedelta
    cutoff = datetime.now() - _timedelta(days=SCAN_DAYS)
    cutoff_com = pywintypes.Time(cutoff)

    folders = [inbox]
    team_folder = _find_team_folder(namespace)
    if team_folder:
        folders.extend(_collect_all_subfolders(team_folder))

    AUTO_MARKERS = ["automatic reply", "out of office", "auto reply", "auto-reply"]
    BOUNCE_MARKERS = ["undeliverable", "delivery status notification",
                      "mail delivery failed", "returned mail"]

    for folder in folders:
        try:
            messages = folder.Items
            messages.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        for msg in messages:
            try:
                if msg.ReceivedTime < cutoff_com:
                    break
            except Exception:
                continue
            stats["scanned"] += 1
            try:
                if msg.Class != 43:  # olMail
                    stats["skipped"] += 1
                    continue
                subject = (msg.Subject or "")
                if any(k in subject.lower() for k in AUTO_MARKERS + BOUNCE_MARKERS):
                    stats["skipped"] += 1
                    continue
                sender = get_sender_smtp(msg)
                if not sender or sender not in prospect_emails:
                    stats["skipped"] += 1
                    continue
                body = msg.Body or ""
                intent = classify_intent(subject, body)
                _log_event(
                    "REPLY",
                    email=sender,
                    subject=subject,
                    body_preview=body[:800],
                    intent=intent,
                    timestamp=datetime.now().isoformat(),
                    source="process_reply.export_events_to_intel",
                )
                stats["events_logged"] += 1
            except Exception:
                stats["skipped"] += 1

    log.info("export_events_to_intel: %s", stats)
    return stats


if __name__ == "__main__":
    main()
