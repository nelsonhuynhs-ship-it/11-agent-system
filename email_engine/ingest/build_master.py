# -*- coding: utf-8 -*-
"""
build_master.py — Phase 3: Split, Cross-ref, Tier Assignment
=============================================================
Takes raw collected records from collect_all_sources + email_cleaner,
then produces final master files:

  cnee_master_v2.xlsx   — CNEE contacts (importers US/CA/intl)
  shipper_master.xlsx   — Shipper contacts (VN/TH/MY exporters)

Tier system (6 levels):
  VIP       — PROTENTIAL (replied + engaging in conversation)
  HOT       — Confirmed human reply (excludes auto-replies)
  WARM_A    — DATA USA verified emails (paid verification)
  WARM_B    — Panjiva cleaned valid emails
  COOL      — Valid email, low info
  PARK      — Generic/invalid/bounced, skip sending

Usage:
    python -m email_engine.ingest.build_master
"""

from __future__ import annotations

import logging
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

_repo = str(Path(__file__).parent.parent.parent)
if _repo not in sys.path:
    sys.path.insert(0, _repo)

from shared import paths as sp
from email_engine.ingest.email_cleaner import clean_panjiva_email, validate_email
from email_engine.ingest.collect_all_sources import collect_all

log = logging.getLogger(__name__)

# ── Auto-reply detection ─────────────────────────────────────────────────────

# Emails that look like department/system mailboxes (likely auto-responders)
_AUTO_EMAIL_PATTERNS = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "postmaster", "mailer-daemon", "bounce",
    "accountspayable", "accounts-payable",
]

_DEPT_EMAIL_PREFIXES = [
    "info@", "contact@", "queries@", "sales@", "connect@",
    "documents@", "customs@", "transport@", "shipping@",
    "logistics@", "freight@", "import@", "export@",
    "operations@", "support@", "tech.support@",
    "plastics@", "op1@", "op2@", "op3@",
]

# Subject keywords that indicate out-of-office / auto-reply
_AUTO_SUBJECT_KW = [
    "out of office", "automatic reply", "auto-reply", "autoreply",
    "away from", "on vacation", "no longer with", "has left",
    "undeliverable", "delivery status", "unsubscribe",
    "automatique", "absence du bureau",  # French auto-reply (Canada)
]


def is_auto_reply(email: str, subject: str = "") -> bool:
    """Detect if a reply is likely automation, not human."""
    el = email.lower().strip()
    sl = subject.lower() if subject else ""

    # Check subject for auto-reply keywords
    for kw in _AUTO_SUBJECT_KW:
        if kw in sl:
            return True

    # Check email prefix patterns
    for p in _AUTO_EMAIL_PATTERNS:
        if p in el:
            return True

    for p in _DEPT_EMAIL_PREFIXES:
        if el.startswith(p):
            return True

    return False


# ── VN domain detection (for Shipper split) ──────────────────────────────────

_VN_TLDS = {".vn", ".com.vn", ".net.vn", ".org.vn", ".edu.vn", ".gov.vn"}
_VN_COUNTRY_KEYWORDS = {"vietnam", "viet nam", "vn", "hcm", "hanoi", "hai phong"}


def is_shipper_email(email: str, source_record: dict) -> bool:
    """Determine if a record belongs to Shipper (VN exporter) vs CNEE."""
    el = email.lower()
    domain = el.split("@")[-1] if "@" in el else ""

    # Rule 1: .vn domain = Shipper
    for tld in _VN_TLDS:
        if domain.endswith(tld):
            return True

    # Rule 2: Source record explicitly tagged as shipper
    rtype = str(source_record.get("_record_type", "")).lower()
    if rtype == "shipper":
        return True

    # Rule 3: Source file is a shipper-specific file
    src = str(source_record.get("SOURCE_FILE", "")).lower()
    if "shipper" in src:
        return True

    # Rule 4: Country field indicates VN
    country = str(source_record.get("COUNTRY", "")).lower()
    if country and any(kw in country for kw in _VN_COUNTRY_KEYWORDS):
        return True

    return False


# ── PIC derivation from email ─────────────────────────────────────────────────

_GENERIC_PREFIXES = {
    "info", "contact", "sales", "support", "admin", "office",
    "hello", "team", "service", "help", "enquiry", "inquiry",
    "billing", "accounts", "hr", "general", "mail", "webmaster",
    "noreply", "no-reply", "operations", "ops", "customs",
    "import", "export", "logistics", "shipping", "freight",
    "documents", "doc", "reception", "marketing", "purchasing",
    "procurement", "accounting", "finance", "order", "orders",
    "dispatch", "warehouse", "delivery", "compliance",
}


def derive_pic_from_email(email: str) -> str:
    """Derive PIC name from email prefix. Returns '' if not derivable."""
    if not email or "@" not in email:
        return ""
    prefix = email.split("@")[0].lower().strip()

    # Skip generic/department prefixes
    if prefix in _GENERIC_PREFIXES:
        return ""

    # Skip if starts with numbers or is too short
    if prefix[0].isdigit() or len(prefix) < 3:
        return ""

    # Pattern: firstname.lastname or firstname_lastname or firstname-lastname
    for sep in (".", "_", "-"):
        if sep in prefix:
            parts = [p for p in prefix.split(sep) if p.isalpha() and len(p) > 1]
            if len(parts) >= 2:
                return " ".join(p.capitalize() for p in parts[:2])
            elif len(parts) == 1:
                return parts[0].capitalize()

    # Single word prefix (e.g. "gagan@arhea.com" → "Gagan")
    if prefix.isalpha() and len(prefix) >= 3:
        return prefix.capitalize()

    # Mixed alphanumeric (e.g. "ken_maxswholesale" already handled above)
    # Try to extract alpha-only part
    alpha = re.sub(r"[^a-z]", "", prefix)
    if alpha and len(alpha) >= 3 and alpha not in _GENERIC_PREFIXES:
        return alpha.capitalize()

    return ""


def build_greeting(pic: str, company: str) -> str:
    """Build email greeting: 'Hi {PIC}' or 'Dear {Company} Team'."""
    if pic and pic.lower() not in ("nan", "none", ""):
        # Use first name only
        first = pic.split()[0] if pic.strip() else ""
        if first and len(first) >= 2:
            return f"Hi {first}"
    if company and company.lower() not in ("nan", "none", ""):
        # Shorten company name for greeting
        short = company.split(",")[0].split("(")[0].strip()
        if len(short) > 30:
            return "Dear Import Team"
        return f"Dear {short} Team"
    return "Dear Import Team"


# ── Scoring ──────────────────────────────────────────────────────────────────

def compute_priority_score(rec: dict) -> int:
    """Score 0-100 based on data richness and value signals."""
    score = 0

    # Email quality (0-30)
    eq = rec.get("EMAIL_QUALITY_SCORE", 0)
    if eq >= 100:
        score += 30
    elif eq >= 80:
        score += 25
    elif eq >= 50:
        score += 15

    # Has PIC name (0-15)
    pic = str(rec.get("PIC", "")).strip()
    if pic and pic.lower() not in ("nan", "none", ""):
        score += 15

    # Has phone (0-10)
    phone = str(rec.get("PHONE", "")).strip()
    if phone and phone.lower() not in ("nan", "none", ""):
        score += 10

    # Has shipment count (0-15)
    ship = rec.get("TOTAL_SHIPMENT", 0)
    if isinstance(ship, (int, float)) and ship > 0:
        if ship >= 50:
            score += 15
        elif ship >= 20:
            score += 12
        elif ship >= 5:
            score += 8
        else:
            score += 4

    # Has carrier info (0-10)
    carrier = str(rec.get("CARRIER", "")).strip()
    if carrier and carrier.lower() not in ("nan", "none", ""):
        score += 10

    # Has destination (0-10)
    dest = str(rec.get("DESTINATION", "")).strip()
    if dest and dest.lower() not in ("nan", "none", ""):
        score += 10

    # Has commodity (0-10)
    cmd = str(rec.get("CAMPAIGN_ID", "")).strip()
    if cmd and cmd.lower() not in ("nan", "none", ""):
        score += 10

    return min(score, 100)


# ── Tier assignment ──────────────────────────────────────────────────────────

def assign_tier(
    email: str,
    priority_score: int,
    protential_set: set,
    human_replied_set: set,
    auto_replied_set: set,
    verified_set: set,
    bounced_set: set,
) -> str:
    """Assign tier based on signals. Order matters."""
    el = email.lower().strip()

    # Tier 0: Bounced = PARK (always, regardless of other signals)
    if el in bounced_set:
        return "PARK"

    # Tier 1: VIP — PROTENTIAL (confirmed engaging prospects)
    if el in protential_set:
        return "VIP"

    # Tier 2: HOT — Confirmed human reply (NOT auto-reply)
    if el in human_replied_set:
        return "HOT"

    # Auto-replied contacts get WARM_A at best, not HOT
    # (they replied but it was automated, not a real conversation)

    # Tier 3: WARM_A — Verified emails (DATA USA paid verify) or auto-replied
    if el in verified_set or el in auto_replied_set:
        return "WARM_A"

    # Tier 4: WARM_B — Good score from Panjiva data
    if priority_score >= 50:
        return "WARM_B"

    # Tier 5: COOL — Valid but low data richness
    if priority_score >= 20:
        return "COOL"

    # Tier 6: PARK — Everything else
    return "PARK"


# ── Build logic ──────────────────────────────────────────────────────────────

def _load_send_history() -> tuple[dict, set, set, set]:
    """Load email_log → per-email stats, replied sets, bounced set."""
    send_stats: dict[str, dict] = {}
    human_replied: set[str] = set()
    auto_replied: set[str] = set()
    bounced: set[str] = set()

    log_file = sp.EMAIL_LOG
    if not log_file.exists():
        log.warning("email_log not found at %s", log_file)
        return send_stats, human_replied, auto_replied, bounced

    df = pd.read_csv(log_file)
    for _, row in df.iterrows():
        email = str(row.get("email", "")).lower().strip()
        if not email or "@" not in email:
            continue

        status = str(row.get("status", "")).upper()
        subject = str(row.get("subject", ""))

        # Aggregate send stats
        if email not in send_stats:
            send_stats[email] = {
                "send_count": 0,
                "last_sent": "",
                "last_campaign": "",
            }
        if "SENT" in status or "REPLIED" in status:
            send_stats[email]["send_count"] += 1
            ts = str(row.get("timestamp", ""))
            if ts > send_stats[email]["last_sent"]:
                send_stats[email]["last_sent"] = ts
                send_stats[email]["last_campaign"] = str(
                    row.get("campaign_id", "")
                )

        # Classify replies
        if "REPLIED" in status:
            if is_auto_reply(email, subject):
                auto_replied.add(email)
            else:
                human_replied.add(email)

    # Load bounced from cnee_master SEQ_STATUS
    if sp.CNEE_MASTER.exists():
        cm = pd.read_excel(sp.CNEE_MASTER)
        for _, row in cm.iterrows():
            seq = str(row.get("SEQ_STATUS", "")).upper()
            if seq == "BOUNCED":
                em = str(row.get("EMAIL", "")).lower().strip()
                if em:
                    bounced.add(em)

    return send_stats, human_replied, auto_replied, bounced


def _load_verified_set() -> set[str]:
    """Load emails from DATA USA report (paid-verified)."""
    verified: set[str] = set()
    usa_file = sp.DATA_LOC_DIR / "DATA USA report.xlsx"
    if not usa_file.exists():
        return verified
    try:
        df = pd.read_excel(usa_file, sheet_name="DATA CNEE US")
        for e in df["EMAIL"].dropna():
            v = str(e).strip().lower()
            if "@" in v:
                verified.add(v)
    except Exception as exc:
        log.warning("Failed to load DATA USA verified: %s", exc)
    return verified


def _load_protential_set() -> set[str]:
    """Load PROTENTIAL VIP contacts."""
    vip: set[str] = set()
    usa_file = sp.DATA_LOC_DIR / "DATA USA report.xlsx"
    if not usa_file.exists():
        return vip
    try:
        df = pd.read_excel(usa_file, sheet_name="PROTENTIAL")
        col = "EMAIL" if "EMAIL" in df.columns else None
        if col:
            for e in df[col].dropna():
                v = str(e).strip().lower()
                if "@" in v:
                    vip.add(v)
    except Exception as exc:
        log.warning("Failed to load PROTENTIAL: %s", exc)
    return vip


def build_masters() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Main pipeline: collect → clean → dedup → split → tier → output."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # ── Step 1: Collect all raw records ──
    log.info("Step 1: Collecting from all sources...")
    raw_records = collect_all()
    log.info("  Collected %d raw records", len(raw_records))

    # ── Step 2: Clean emails + explode multi-email fields ──
    log.info("Step 2: Cleaning emails (8-pattern algorithm)...")
    cleaned: list[dict] = []
    stats = {"total": 0, "cleaned": 0, "invalid": 0, "multi_split": 0}

    for rec in raw_records:
        raw_email = str(rec.get("EMAIL", ""))
        if not raw_email or "@" not in raw_email:
            stats["invalid"] += 1
            continue

        emails_out = clean_panjiva_email(raw_email)
        if len(emails_out) > 1:
            stats["multi_split"] += len(emails_out) - 1

        for em in emails_out:
            valid_email, quality = validate_email(em)
            if not valid_email:
                stats["invalid"] += 1
                continue

            new_rec = dict(rec)
            new_rec["EMAIL"] = valid_email
            new_rec["EMAIL_QUALITY_SCORE"] = quality
            cleaned.append(new_rec)
            stats["cleaned"] += 1

    stats["total"] = len(raw_records)
    log.info(
        "  Cleaned: %d valid, %d invalid, %d multi-split",
        stats["cleaned"], stats["invalid"], stats["multi_split"],
    )

    # ── Step 3: Dedup by email (keep richest record) ──
    log.info("Step 3: Deduplicating by email...")
    email_best: dict[str, dict] = {}
    for rec in cleaned:
        em = rec["EMAIL"]
        if em not in email_best:
            email_best[em] = rec
        else:
            # Keep record with more fields filled
            old = email_best[em]
            old_filled = sum(
                1 for v in old.values()
                if str(v).strip() not in ("", "nan", "None")
            )
            new_filled = sum(
                1 for v in rec.values()
                if str(v).strip() not in ("", "nan", "None")
            )
            if new_filled > old_filled:
                email_best[em] = rec

    deduped = list(email_best.values())
    log.info("  Deduped: %d unique emails", len(deduped))

    # ── Step 4: Split CNEE vs Shipper ──
    log.info("Step 4: Splitting CNEE vs Shipper...")
    cnee_recs: list[dict] = []
    shipper_recs: list[dict] = []

    for rec in deduped:
        if is_shipper_email(rec["EMAIL"], rec):
            shipper_recs.append(rec)
        else:
            cnee_recs.append(rec)

    log.info("  CNEE: %d | Shipper: %d", len(cnee_recs), len(shipper_recs))

    # ── Step 5: Load cross-reference data ──
    log.info("Step 5: Loading cross-reference data...")
    send_stats, human_replied, auto_replied, bounced = _load_send_history()
    verified = _load_verified_set()
    protential = _load_protential_set()

    log.info(
        "  Replied: %d human, %d auto | Bounced: %d | Verified: %d | VIP: %d",
        len(human_replied), len(auto_replied),
        len(bounced), len(verified), len(protential),
    )

    # ── Step 6: Score + Tier CNEE ──
    log.info("Step 6: Scoring + Tiering CNEE contacts...")
    cnee_output: list[dict] = []
    tier_counts: dict[str, int] = defaultdict(int)

    for rec in cnee_recs:
        em = rec["EMAIL"]
        score = compute_priority_score(rec)
        tier = assign_tier(
            em, score, protential,
            human_replied, auto_replied,
            verified, bounced,
        )
        tier_counts[tier] += 1

        # Get send history
        sh = send_stats.get(em, {})

        # Determine action
        if tier == "PARK":
            action = "SKIP"
        elif tier == "VIP":
            action = "PERSONALIZED"
        elif tier == "HOT":
            action = "FOLLOW_UP"
        elif em in send_stats and sh.get("send_count", 0) >= 5:
            action = "COOLDOWN"
        elif em in send_stats:
            action = "SEQUENCE_NEXT"
        else:
            action = "SEND_NOW"

        # Determine reply status
        if em in human_replied:
            reply_status = "HUMAN_REPLY"
        elif em in auto_replied:
            reply_status = "AUTO_REPLY"
        else:
            reply_status = "NO_REPLY"

        # Derive PIC from email if missing
        raw_pic = rec.get("CONTACT_NAME", "") or rec.get("PIC", "")
        pic = str(raw_pic).strip() if str(raw_pic).strip().lower() not in ("nan", "none", "") else ""
        if not pic:
            pic = derive_pic_from_email(em)
        company = str(rec.get("COMPANY", "")).strip()
        greeting = build_greeting(pic, company)

        cnee_output.append({
            "EMAIL": em,
            "COMPANY": company,
            "PIC": pic,
            "GREETING": greeting,
            "PHONE": rec.get("PHONE", ""),
            "POSITION": rec.get("POSITION", ""),
            "POL": rec.get("POL", ""),
            "DESTINATION": rec.get("DESTINATION", ""),
            "CARRIER": rec.get("CARRIER", ""),
            "TOTAL_SHIPMENT": rec.get("TOTAL_SHIPMENT", ""),
            "CAMPAIGN_ID": rec.get("CAMPAIGN_ID", ""),
            "EMAIL_QUALITY_SCORE": rec.get("EMAIL_QUALITY_SCORE", 0),
            "PRIORITY_SCORE": score,
            "TIER": tier,
            "ACTION": action,
            "REPLY_STATUS": reply_status,
            "SEND_COUNT": sh.get("send_count", 0),
            "LAST_SENT_DATE": sh.get("last_sent", ""),
            "SEQ_STEP": 0,
            "SEQ_STATUS": "BOUNCED" if em in bounced else "ACTIVE",
            "SOURCE_FILE": rec.get("SOURCE_FILE", ""),
        })

    # Sort: VIP first, then HOT, WARM_A, WARM_B, COOL, PARK
    tier_order = {"VIP": 0, "HOT": 1, "WARM_A": 2, "WARM_B": 3, "COOL": 4, "PARK": 5}
    cnee_output.sort(key=lambda r: (tier_order.get(r["TIER"], 9), -r["PRIORITY_SCORE"]))

    df_cnee = pd.DataFrame(cnee_output)
    log.info("  CNEE tiers: %s", dict(tier_counts))

    # ── Step 7: Build Shipper output ──
    log.info("Step 7: Building Shipper master...")
    shipper_output: list[dict] = []
    for rec in shipper_recs:
        shipper_output.append({
            "EMAIL": rec["EMAIL"],
            "COMPANY": rec.get("COMPANY", ""),
            "PIC": rec.get("CONTACT_NAME", "") or rec.get("PIC", ""),
            "PHONE": rec.get("PHONE", ""),
            "ADDRESS": rec.get("ADDRESS", ""),
            "MST": "",  # To be enriched via Chrome skill later
            "COUNTRY": rec.get("COUNTRY", ""),
            "PRODUCTS": rec.get("CAMPAIGN_ID", ""),
            "TOTAL_SHIPMENT": rec.get("TOTAL_SHIPMENT", ""),
            "CRM_STATUS": "NEW",
            "HANDLED_BY": "",
            "SOURCE_FILE": rec.get("SOURCE_FILE", ""),
        })

    df_shipper = pd.DataFrame(shipper_output) if shipper_output else pd.DataFrame()
    log.info("  Shipper: %d contacts", len(shipper_output))

    return df_cnee, df_shipper


def save_masters(df_cnee: pd.DataFrame, df_shipper: pd.DataFrame) -> None:
    """Save to OneDrive output paths."""
    out_cnee = sp.EMAIL_DATA / "cnee_master_v2.xlsx"
    out_shipper = sp.SHIPPER_MASTER

    df_cnee.to_excel(out_cnee, index=False, engine="openpyxl")
    log.info("Saved CNEE master: %s (%d rows)", out_cnee, len(df_cnee))

    if not df_shipper.empty:
        df_shipper.to_excel(out_shipper, index=False, engine="openpyxl")
        log.info("Saved Shipper master: %s (%d rows)", out_shipper, len(df_shipper))


def print_report(df_cnee: pd.DataFrame, df_shipper: pd.DataFrame) -> None:
    """Print summary report to console."""
    print("\n" + "=" * 60)
    print("  PHASE 3 REPORT — Build Master")
    print("=" * 60)

    print(f"\n  CNEE Master: {len(df_cnee)} contacts")
    if not df_cnee.empty:
        tc = df_cnee["TIER"].value_counts()
        for tier in ["VIP", "HOT", "WARM_A", "WARM_B", "COOL", "PARK"]:
            count = tc.get(tier, 0)
            pct = count / len(df_cnee) * 100
            bar = "█" * int(pct / 2)
            print(f"    {tier:8} : {count:>5}  ({pct:5.1f}%) {bar}")

        ac = df_cnee["ACTION"].value_counts()
        print(f"\n  Actions:")
        for action, count in ac.items():
            print(f"    {action:16} : {count:>5}")

        rc = df_cnee["REPLY_STATUS"].value_counts()
        print(f"\n  Reply Classification:")
        for rs, count in rc.items():
            print(f"    {rs:16} : {count:>5}")

        send_now = len(df_cnee[df_cnee["ACTION"] == "SEND_NOW"])
        print(f"\n  ★ Ready to SEND_NOW: {send_now}")

    print(f"\n  Shipper Master: {len(df_shipper)} contacts")
    print("=" * 60)


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df_c, df_s = build_masters()
    print_report(df_c, df_s)
    save_masters(df_c, df_s)
    print("\nDone. Files saved to OneDrive.")
