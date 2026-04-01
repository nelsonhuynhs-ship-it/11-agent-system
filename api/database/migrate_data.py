# -*- coding: utf-8 -*-
"""
migrate_data.py — JSON → PostgreSQL Data Migration
=====================================================
One-time migration tool to move data from JSON files to PostgreSQL.

Usage:
    set DATABASE_URL=postgresql://user:pass@host:5432/nelson_freight
    python -m database.migrate_data

Steps:
    1. Run SQL migrations (create tables)
    2. Import quotes.json → quotes + quote_carriers
    3. Import shipment_state.json → shipments + events
    4. Import outlook_dataset.json → email_matches
    5. Import customer_rules.json → customers
    6. Verify counts
"""
import hashlib
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("migration")

from database.connection import (
    execute_sync, run_migrations, is_postgres_configured,
    DEFAULT_TENANT_ID,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE = Path(os.environ.get("NELSON_BASE_DIR",
            r"D:\NELSON\2. Areas\PricingSystem\Engine_test"))
API_DATA = BASE / "api" / "data"
EMAIL_ENGINE = Path(os.environ.get("EMAIL_ENGINE_DIR",
                    r"D:\NELSON\email_engine"))


def _load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if not path.exists():
        log.warning("File not found: %s", path)
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ── Migration Functions ──────────────────────────────────────────────────────

def migrate_quotes():
    """Import quotes.json → quotes + quote_carriers tables."""
    data = _load_json(API_DATA / "quotes.json")
    quotes = data.get("quotes", {})
    log.info("Migrating %d quotes...", len(quotes))

    for qid, q in quotes.items():
        # Insert quote
        execute_sync("""
            INSERT INTO quotes (id, tenant_id, customer, service_type, pol, pod, place,
                routing, status, markup_mode, global_markup, win_probability,
                parent_quote_id, version, converted_shipment_id,
                optional_charges, charges_total, transit, freetime, validity,
                price_alerts, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            qid, DEFAULT_TENANT_ID,
            q.get("customer", ""), q.get("service_type", "CY-CY"),
            q.get("pol", ""), q.get("pod", ""), q.get("place", ""),
            q.get("routing", ""), q.get("status", "DRAFT"),
            q.get("markup_mode", "global"), q.get("global_markup", 0),
            q.get("win_probability"), q.get("parent_quote_id"),
            q.get("version", 1), q.get("converted_shipment_id"),
            json.dumps(q.get("optional_charges", [])),
            q.get("charges_total", 0),
            q.get("transit", ""), q.get("freetime", ""),
            q.get("validity", ""),
            json.dumps(q.get("price_alerts", [])),
            q.get("created_at", datetime.now().isoformat()),
            q.get("updated_at", datetime.now().isoformat()),
        ), fetch=False)

        # Insert carriers
        for carrier in q.get("carriers", []):
            execute_sync("""
                INSERT INTO quote_carriers (quote_id, carrier, badge, transit,
                    freetime, container_rates, carrier_markup, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                qid, carrier.get("carrier", ""),
                carrier.get("badge", ""), carrier.get("transit", ""),
                carrier.get("freetime", ""),
                json.dumps(carrier.get("containers", {})),
                json.dumps(carrier.get("carrier_markup", {})),
                carrier.get("note", ""),
            ), fetch=False)

    log.info("✓ Quotes migration complete: %d quotes", len(quotes))


def migrate_shipments():
    """Import shipment_state.json → shipments + events tables."""
    data = _load_json(EMAIL_ENGINE / "shipment_state.json")
    shipments = data.get("shipments", {})
    log.info("Migrating %d shipments...", len(shipments))

    for sid, s in shipments.items():
        # Insert shipment
        execute_sync("""
            INSERT INTO shipments (id, tenant_id, source_quote_id, customer, carrier,
                routing, container_type, quantity, stage, service_type,
                selling_rate, buying_rate, profit, profit_margin,
                delay_count, source, risks, all_containers,
                optional_charges, last_subject, last_sender, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            sid, DEFAULT_TENANT_ID,
            s.get("quote_id"), s.get("customer", ""),
            s.get("carrier", ""), s.get("routing", ""),
            s.get("container", ""), s.get("quantity", 1),
            s.get("stage", "BOOKING_PENDING"),
            s.get("type", "CY-CY"),
            s.get("selling_rate", 0), s.get("buying_rate", 0),
            s.get("profit", 0), s.get("profit_margin", "0%"),
            s.get("delay_count", 0), s.get("source", "email"),
            json.dumps(s.get("risks", [])),
            json.dumps(s.get("all_containers", {})),
            json.dumps(s.get("optional_charges", [])),
            s.get("last_subject", ""), s.get("last_sender", ""),
            s.get("created_at", datetime.now().isoformat()),
            s.get("updated_at", datetime.now().isoformat()),
        ), fetch=False)

        # Insert stage_history as events
        for stage in s.get("stage_history", []):
            execute_sync("""
                INSERT INTO events (tenant_id, entity_type, entity_id,
                    event_type, payload, source, actor)
                VALUES (%s, 'shipment', %s, 'stage_changed', %s, %s, 'migration')
            """, (
                DEFAULT_TENANT_ID, sid,
                json.dumps({
                    "to_stage": stage.get("stage", ""),
                    "subject": stage.get("subject", ""),
                }),
                stage.get("source", "email"),
            ), fetch=False)

    log.info("✓ Shipments migration complete: %d shipments", len(shipments))


def migrate_emails():
    """Import outlook_dataset.json → email_matches table."""
    data = _load_json(EMAIL_ENGINE / "outlook_dataset.json")
    entries = data if isinstance(data, list) else data.get("entries", [])
    log.info("Migrating %d email entries...", len(entries))

    migrated = 0
    for entry in entries:
        subject = entry.get("subject", "")
        sender = entry.get("sender", "")
        email_hash = hashlib.sha256(f"{subject}|{sender}".encode()).hexdigest()[:16]

        try:
            execute_sync("""
                INSERT INTO email_matches (tenant_id, shipment_id, email_hash,
                    subject, sender, matched_by, extracted_ids,
                    detected_stages, detected_risks, email_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email_hash) DO NOTHING
            """, (
                DEFAULT_TENANT_ID,
                entry.get("shipment_id"),
                email_hash,
                subject, sender,
                entry.get("matched_by", ""),
                json.dumps(entry.get("extracted_ids", {})),
                json.dumps(entry.get("detected_stages", [])),
                json.dumps(entry.get("detected_risks", [])),
                entry.get("email_date"),
            ), fetch=False)
            migrated += 1
        except Exception as e:
            log.warning("Skip email entry: %s", e)

    log.info("✓ Email migration complete: %d/%d entries", migrated, len(entries))


def migrate_customers():
    """Import customer_rules.json → customers table."""
    data = _load_json(API_DATA / "customer_rules.json")
    customers = data if isinstance(data, list) else list(data.values())
    log.info("Migrating %d customers...", len(customers))

    for c in customers:
        code = c.get("code", c.get("name", "unknown"))
        execute_sync("""
            INSERT INTO customers (tenant_id, code, name, ports, cargo_type, notes, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, code) DO NOTHING
        """, (
            DEFAULT_TENANT_ID,
            code, c.get("name", code),
            json.dumps(c.get("ports", c.get("preferred_ports", []))),
            c.get("cargo_type", ""),
            c.get("notes", ""),
            json.dumps(c.get("tags", [])),
        ), fetch=False)

    log.info("✓ Customers migration complete: %d", len(customers))


def verify_migration():
    """Verify data counts after migration."""
    log.info("Verifying migration...")
    tables = ["tenants", "users", "quotes", "quote_carriers",
              "shipments", "events", "email_matches", "customers"]
    for table in tables:
        rows = execute_sync(f"SELECT COUNT(*) as c FROM {table}")
        count = rows[0]["c"] if rows else 0
        log.info("  %-20s %d rows", table, count)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_full_migration():
    """Run the complete migration pipeline."""
    log.info("=" * 60)
    log.info("  NELSON FREIGHT — JSON → PostgreSQL Migration")
    log.info("=" * 60)

    if not is_postgres_configured():
        log.error("DATABASE_URL not set! Set it first:")
        log.error("  $env:DATABASE_URL = 'postgresql://user:pass@host:5432/nelson_freight'")
        return False

    # Step 1: Create tables
    log.info("\n[1/5] Running SQL migrations...")
    run_migrations()

    # Step 2: Quotes
    log.info("\n[2/5] Migrating quotes...")
    migrate_quotes()

    # Step 3: Shipments
    log.info("\n[3/5] Migrating shipments...")
    migrate_shipments()

    # Step 4: Emails
    log.info("\n[4/5] Migrating emails...")
    migrate_emails()

    # Step 5: Customers
    log.info("\n[5/5] Migrating customers...")
    migrate_customers()

    # Verify
    log.info("\n" + "=" * 60)
    verify_migration()
    log.info("=" * 60)
    log.info("Migration complete! ✓")
    return True


if __name__ == "__main__":
    run_full_migration()
