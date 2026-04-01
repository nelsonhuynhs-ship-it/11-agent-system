"""
replacement_outreach.py -- OOO Replacement Contact Lead Generator
=================================================================
Reads email_knowledge.csv, filters auto_reply entries with a
REPLACEMENT_EMAIL, cross-references data.xlsx for company info,
and produces replacement_leads.xlsx with actionable outreach records.

Usage:
    python replacement_outreach.py
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

# =========================================================
# CONFIG
# =========================================================
BASE_DIR       = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent
LOG_DIR        = PROJECT_ROOT / "logs"
KNOWLEDGE_FILE = PROJECT_ROOT / "logs" / "email_knowledge.csv"
EMAIL_LOG_FILE = PROJECT_ROOT / "logs" / "email_log.csv"
DATA_FILE      = PROJECT_ROOT / "data.xlsx"
OUTPUT_FILE    = PROJECT_ROOT / "data" / "replacement_leads.xlsx"

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


def main() -> None:
    log.info("=" * 60)
    log.info("  REPLACEMENT CONTACT LEAD GENERATOR")
    log.info("=" * 60)

    # ---- 1. Load knowledge base ----
    if not KNOWLEDGE_FILE.exists():
        log.error("email_knowledge.csv not found.")
        return

    df_kb = pd.read_csv(KNOWLEDGE_FILE, encoding="utf-8-sig")
    df_kb.columns = df_kb.columns.str.upper().str.strip()
    df_kb["EMAIL"] = df_kb["EMAIL"].astype(str).str.lower().str.strip()
    df_kb["REPLACEMENT_EMAIL"] = df_kb["REPLACEMENT_EMAIL"].astype(str).str.lower().str.strip()

    # ---- 2. Filter: auto_reply with replacement email ----
    auto = df_kb[df_kb["STATUS"].str.lower() == "auto_reply"].copy()
    has_repl = auto[
        (auto["REPLACEMENT_EMAIL"].notna()) &
        (auto["REPLACEMENT_EMAIL"] != "") &
        (auto["REPLACEMENT_EMAIL"] != "nan")
    ].copy()

    log.info("Auto-reply entries: %d", len(auto))
    log.info("With replacement email: %d", len(has_repl))

    if has_repl.empty:
        log.info("No replacement contacts found. Nothing to do.")
        return

    # ---- 3. Cross-reference data.xlsx for company/campaign info ----
    company_map: dict[str, dict] = {}
    campaign_map: dict[str, str] = {}

    if DATA_FILE.exists():
        df_data = pd.read_excel(DATA_FILE)
        df_data.columns = df_data.columns.str.upper().str.replace(" ", "_")
        for _, row in df_data.iterrows():
            for e_col, n_col, cmd_col in [
                ("CNEE_EMAIL", "CNEE_NAME", "CMD_NAME"),
                ("SHIPPER_EMAIL", "SHIPPER_NAME", "CMD_NAME"),
            ]:
                email = str(row.get(e_col, "")).lower().strip()
                if "@" in email:
                    company_map[email] = {
                        "COMPANY": str(row.get(n_col, "")),
                        "CMD_NAME": str(row.get(cmd_col, "")),
                    }

    # Campaign from email_log
    if EMAIL_LOG_FILE.exists():
        df_log = pd.read_csv(EMAIL_LOG_FILE)
        df_log.columns = df_log.columns.str.lower().str.strip()
        df_log["email"] = df_log["email"].astype(str).str.lower().str.strip()
        df_log["campaign_id"] = df_log["campaign_id"].astype(str).str.upper()
        for _, row in df_log.iterrows():
            e = row["email"]
            if e not in campaign_map and row["campaign_id"] != "NAN":
                campaign_map[e] = row["campaign_id"]

    # ---- 4. Check which replacements were already contacted ----
    sent_emails: set[str] = set()
    if EMAIL_LOG_FILE.exists():
        sent_emails = set(df_log["email"].unique())

    # ---- 5. Parse name/title from REMARK ----
    import re

    def parse_name(remark: str) -> str:
        m = re.search(r"alt contact:\s*([^|]+)", str(remark), re.I)
        return m.group(1).strip() if m else ""

    def parse_title(remark: str) -> str:
        m = re.search(r"title:\s*([^|]+)", str(remark), re.I)
        return m.group(1).strip() if m else ""

    # ---- 6. Build output records ----
    records = []
    for _, row in has_repl.iterrows():
        original = row["EMAIL"]
        replacement = row["REPLACEMENT_EMAIL"]

        # Company info from data.xlsx
        info = company_map.get(original, {})
        company = info.get("COMPANY", row.get("COMPANY", ""))

        # Campaign
        campaign = campaign_map.get(original, info.get("CMD_NAME", ""))

        # Name / title
        remark = str(row.get("REMARK", ""))
        name = parse_name(remark)
        title = str(row.get("ROLE_HINT", "")) or parse_title(remark)

        # Already contacted?
        already_sent = "YES" if replacement in sent_emails else "NO"

        outreach_status = "ALREADY_SENT" if already_sent == "YES" else "PENDING"

        records.append({
            "COMPANY":              company,
            "ORIGINAL_EMAIL":       original,
            "REPLACEMENT_EMAIL":    replacement,
            "REPLACEMENT_NAME":     name,
            "REPLACEMENT_TITLE":    title,
            "CAMPAIGN_ID":          campaign,
            "OUTREACH_STATUS":      outreach_status,
            "ALREADY_CONTACTED":    already_sent,
            "REMARK":               remark,
        })

    df_out = pd.DataFrame(records)

    # Sort: PENDING first, then by company
    df_out = df_out.sort_values(
        ["OUTREACH_STATUS", "COMPANY"],
        ascending=[False, True],
    )

    df_out.to_excel(OUTPUT_FILE, index=False)

    # ---- 7. Summary ----
    pending = len(df_out[df_out["OUTREACH_STATUS"] == "PENDING"])
    sent    = len(df_out[df_out["OUTREACH_STATUS"] == "ALREADY_SENT"])

    log.info("")
    log.info("=" * 60)
    log.info("  OUTPUT: %s", OUTPUT_FILE.name)
    log.info("=" * 60)
    log.info("  Total replacement leads  : %d", len(df_out))
    log.info("  PENDING (never contacted): %d  <-- ACTION NEEDED", pending)
    log.info("  ALREADY_SENT             : %d", sent)
    log.info("")
    if pending > 0:
        log.info("  Top PENDING leads:")
        for _, r in df_out[df_out["OUTREACH_STATUS"] == "PENDING"].head(5).iterrows():
            log.info("    %-35s -> %s", r["ORIGINAL_EMAIL"], r["REPLACEMENT_EMAIL"])
    log.info("=" * 60)


if __name__ == "__main__":
    main()
