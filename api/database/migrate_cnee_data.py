# -*- coding: utf-8 -*-
"""
migrate-cnee-data.py — CNEE + Email Log → PostgreSQL Migration
===============================================================
Migrates email campaign data from flat files into the email platform tables.

Sources:
  - cnee_master.xlsx   → cnee_master table
  - email_log.csv      → email_log table
  - customer_rules.json → customer_rules table

Usage:
    set DATABASE_URL=postgresql://user:pass@host:5432/nelson_freight
    python -m database.migrate-cnee-data
    python -m database.migrate-cnee-data --dry-run
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("migrate-cnee")

from shared import paths as sp
from database.connection import execute_sync, run_migrations, is_postgres_configured

# ── Constants ─────────────────────────────────────────────────────────────────
CNEE_XLSX = sp.CNEE_MASTER
EMAIL_LOG_CSV = sp.EMAIL_LOG
CUSTOMER_RULES_JSON = sp.CUSTOMER_RULES


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_prereqs():
    """Validate files and DB connection exist before starting."""
    if not is_postgres_configured():
        log.error("DATABASE_URL not set. Example:")
        log.error("  $env:DATABASE_URL = 'postgresql://user:pass@host:5432/nelson_freight'")
        sys.exit(1)

    missing = []
    for label, path in [
        ("cnee_master.xlsx", CNEE_XLSX),
        ("email_log.csv", EMAIL_LOG_CSV),
        ("customer_rules.json", CUSTOMER_RULES_JSON),
    ]:
        if not path.exists():
            missing.append(f"  {label}: {path}")

    if missing:
        log.warning("Some source files not found (will skip):\n%s", "\n".join(missing))


def _parse_timestamp(val) -> str | None:
    """Parse various timestamp formats to ISO string."""
    if not val or str(val).strip() in ("", "nan", "NaT", "None"):
        return None
    try:
        if hasattr(val, "isoformat"):
            return val.isoformat()
        return str(val)[:19]  # trim microseconds
    except Exception:
        return None


# ── Migration Functions ───────────────────────────────────────────────────────

def migrate_cnee_master(dry_run: bool = False) -> int:
    """Migrate cnee_master.xlsx → cnee_master table."""
    if not CNEE_XLSX.exists():
        log.warning("cnee_master.xlsx not found at %s — skipping", CNEE_XLSX)
        return 0

    try:
        import pandas as pd
    except ImportError:
        log.error("pandas not installed: pip install pandas openpyxl")
        return 0

    df = pd.read_excel(CNEE_XLSX, engine="openpyxl")
    log.info("cnee_master.xlsx: %d rows, columns: %s", len(df), list(df.columns))

    # Normalize column names to lowercase
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Column mapping (xlsx → table)
    col_map = {
        "company": "company_name",
        "company_name": "company_name",
        "contact": "contact_name",
        "contact_name": "contact_name",
        "email": "email",
        "campaign": "campaign",
        "country": "country",
        "port": "port",
        "status": "status",
        "lead_score": "lead_score",
        "last_contacted": "last_contacted",
    }

    migrated = 0
    for i, row in df.iterrows():
        def get(col_names):
            for c in col_names if isinstance(col_names, list) else [col_names]:
                if c in df.columns and str(row.get(c, "")).strip() not in ("", "nan"):
                    return str(row[c]).strip()
            return None

        company = get(["company_name", "company", "name"])
        email = get(["email"])
        campaign = get(["campaign"])

        if not email and not company:
            continue  # skip empty rows

        status_raw = get(["status"]) or "active"
        status = status_raw if status_raw in ("active", "unsubscribed", "bounced", "invalid") else "active"

        try:
            lead_score = float(row.get("lead_score", 0) or 0)
        except (ValueError, TypeError):
            lead_score = 0.0

        if dry_run:
            migrated += 1
            continue

        execute_sync("""
            INSERT INTO cnee_master
                (company_name, contact_name, email, campaign, country, port,
                 status, lead_score, last_contacted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            company,
            get(["contact_name", "contact"]),
            email,
            campaign,
            get(["country"]),
            get(["port", "pod"]),
            status,
            lead_score,
            _parse_timestamp(row.get("last_contacted")),
        ), fetch=False)
        migrated += 1

        if migrated % 500 == 0:
            log.info("  Migrated %d/%d CNEE rows...", migrated, len(df))

    log.info("cnee_master: %s %d/%d rows", "[DRY RUN]" if dry_run else "migrated", migrated, len(df))
    return migrated


def migrate_email_log(dry_run: bool = False) -> int:
    """Migrate email_log.csv → email_log table."""
    if not EMAIL_LOG_CSV.exists():
        log.warning("email_log.csv not found at %s — skipping", EMAIL_LOG_CSV)
        return 0

    try:
        import pandas as pd
    except ImportError:
        log.error("pandas not installed")
        return 0

    df = pd.read_csv(EMAIL_LOG_CSV)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    log.info("email_log.csv: %d rows", len(df))

    migrated = 0
    for _, row in df.iterrows():
        email = str(row.get("email", "")).strip()
        if not email or email == "nan":
            continue

        status_raw = str(row.get("status", "sent")).strip()
        status = status_raw if status_raw in ("sent", "failed", "bounced", "opened", "clicked") else "sent"

        if dry_run:
            migrated += 1
            continue

        execute_sync("""
            INSERT INTO email_log (email, subject, template_used, status, sent_at, sent_by, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            email,
            str(row.get("subject", "")).strip() or None,
            str(row.get("template", row.get("template_used", ""))).strip() or None,
            status,
            _parse_timestamp(row.get("sent_at", row.get("timestamp"))),
            str(row.get("sent_by", row.get("sender", ""))).strip() or None,
            str(row.get("error", row.get("error_message", ""))).strip() or None,
        ), fetch=False)
        migrated += 1

    log.info("email_log: %s %d/%d rows", "[DRY RUN]" if dry_run else "migrated", migrated, len(df))
    return migrated


def migrate_customer_rules(dry_run: bool = False) -> int:
    """Migrate customer_rules.json → customer_rules table."""
    if not CUSTOMER_RULES_JSON.exists():
        log.warning("customer_rules.json not found at %s — skipping", CUSTOMER_RULES_JSON)
        return 0

    with CUSTOMER_RULES_JSON.open(encoding="utf-8") as f:
        data = json.load(f)

    entries = data if isinstance(data, list) else list(data.values())
    log.info("customer_rules.json: %d entries", len(entries))

    migrated = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        rule_name = str(entry.get("name", entry.get("code", f"rule_{migrated+1}"))).strip()
        rule_type = str(entry.get("type", entry.get("rule_type", "general"))).strip()

        if dry_run:
            migrated += 1
            continue

        execute_sync("""
            INSERT INTO customer_rules (rule_name, rule_type, rule_data, active)
            VALUES (%s, %s, %s, %s)
        """, (
            rule_name,
            rule_type,
            json.dumps(entry),
            True,
        ), fetch=False)
        migrated += 1

    log.info("customer_rules: %s %d/%d entries", "[DRY RUN]" if dry_run else "migrated", migrated, len(entries))
    return migrated


def verify_counts():
    """Print row counts for the 3 migrated tables."""
    for table in ("cnee_master", "email_log", "customer_rules"):
        rows = execute_sync(f"SELECT COUNT(*) AS c FROM {table}")
        count = rows[0]["c"] if rows else 0
        log.info("  %-25s %d rows", table, count)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Migrate CNEE + email data to PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Count rows only, do not insert")
    args = parser.parse_args()

    dry = args.dry_run
    log.info("=" * 60)
    log.info("  CNEE Data Migration%s", " [DRY RUN]" if dry else "")
    log.info("=" * 60)

    _check_prereqs()

    if not dry:
        log.info("\n[0] Running SQL migrations (003_email_platform.sql)...")
        run_migrations()

    log.info("\n[1] cnee_master.xlsx → cnee_master")
    n1 = migrate_cnee_master(dry_run=dry)

    log.info("\n[2] email_log.csv → email_log")
    n2 = migrate_email_log(dry_run=dry)

    log.info("\n[3] customer_rules.json → customer_rules")
    n3 = migrate_customer_rules(dry_run=dry)

    log.info("\n%s", "=" * 60)
    if not dry:
        log.info("Verifying counts...")
        verify_counts()

    log.info("Total migrated: cnee=%d, email_log=%d, rules=%d", n1, n2, n3)
    log.info("=" * 60)
    log.info("Done ✓")


if __name__ == "__main__":
    main()
