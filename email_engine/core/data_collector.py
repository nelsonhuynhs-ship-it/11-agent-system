"""
Data Collector — Email Intelligence Pipeline
=============================================
Scan .msg files in outlook/ subfolders, classify and parse them,
store structured data in SQLite, and manage file lifecycle.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import shutil
import sqlite3
from shared.db_connect import get_db
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_repo_root = str(Path(__file__).parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
from shared import paths as sp

OUTLOOK_DIR   = sp.EMAIL_CODE / 'outlook'
DB_PATH       = sp.EMAIL_LOG_DIR / 'shipments.db'
PARQUET_DIR   = sp.EMAIL_LOG_DIR / 'parquet'
MSG_KEEP_DAYS = 7

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = sp.EMAIL_LOG_DIR / 'data_collector.log'

_fmt = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
_console = logging.StreamHandler(sys.stdout)
_console.setFormatter(_fmt)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8",
)
_file_handler.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_console, _file_handler])
log = logging.getLogger(__name__)


class DataCollector:
    """Scan .msg files → classify → parse → SQLite."""

    FOLDER_MAP = {
        'TEAM SUNNY': {'local': OUTLOOK_DIR / 'TEAM_SUNNY', 'type': 'MENTEE'},
        'CNEE':       {'local': OUTLOOK_DIR / 'CNEE',       'type': 'CNEE'},
        'SHIPPER':    {'local': OUTLOOK_DIR / 'SHIPPER',    'type': 'SHIPPER'},
        'AGENT':      {'local': OUTLOOK_DIR / 'AGENT',      'type': 'AGENT'},
        'INTERNAL':   {'local': OUTLOOK_DIR / 'INTERNAL',   'type': 'INTERNAL'},
    }

    MEMBER_FOLDER_MAP = {
        'BLUE': 'BLUE', 'JENNIE': 'JENNIE', 'OTIS': 'OTIS',
        'JUN': 'JUN', 'MARK': 'MARK', 'LINA': 'LINA', 'JOHNNY': 'JOHNNY',
    }

    # ------------------------------------------------------------------
    # init_db
    # ------------------------------------------------------------------
    def init_db(self):
        """Create all SQLite tables."""
        conn = get_db(DB_PATH)
        c = conn.cursor()

        # TABLE 1: email_events — append-only raw log
        c.execute("""CREATE TABLE IF NOT EXISTS email_events (
            event_id         TEXT PRIMARY KEY,
            received_at      TEXT NOT NULL,
            processed_at     TEXT NOT NULL,
            email_type       TEXT NOT NULL,
            member_owner     TEXT,
            folder_context   TEXT,
            sender           TEXT,
            recipients       TEXT,
            subject_raw      TEXT,
            shipment_key     TEXT,
            hbl              TEXT,
            bkg              TEXT,
            member_ref       TEXT,
            customer_name    TEXT,
            customer_type    TEXT,
            primary_stage    TEXT,
            stages_detected  TEXT,
            risk_level       TEXT DEFAULT 'NORMAL',
            risk_reasons     TEXT,
            route            TEXT,
            pol              TEXT,
            pod              TEXT,
            carrier          TEXT,
            container_type   TEXT,
            etd              TEXT,
            incoterm         TEXT,
            commodity        TEXT,
            intent           TEXT,
            next_action      TEXT,
            urgency          TEXT,
            campaign_week    INTEGER,
            campaign_type    TEXT,
            body_preview     TEXT,
            parse_confidence INTEGER,
            needs_review     INTEGER DEFAULT 0,
            msg_filename     TEXT,
            outlook_entry_id TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_shipment_key ON email_events(shipment_key)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_customer ON email_events(customer_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_type ON email_events(email_type, received_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_risk ON email_events(risk_level)")

        # TABLE 2: shipments — one row per shipment_key, upserted
        c.execute("""CREATE TABLE IF NOT EXISTS shipments (
            shipment_key     TEXT PRIMARY KEY,
            hbl              TEXT,
            bkg              TEXT,
            member_ref       TEXT,
            member_owner     TEXT,
            customer_name    TEXT,
            customer_type    TEXT,
            current_stage    TEXT,
            stage_history    TEXT,
            missing_stages   TEXT,
            risk_level       TEXT DEFAULT 'NORMAL',
            risk_flags       TEXT,
            route            TEXT,
            pol              TEXT,
            pod              TEXT,
            carrier          TEXT,
            container_type   TEXT,
            commodity        TEXT,
            incoterm         TEXT,
            etd              TEXT,
            atd              TEXT,
            eta              TEXT,
            payment_status   TEXT DEFAULT 'PENDING',
            sla_hours        INTEGER,
            first_email_at   TEXT,
            last_email_at    TEXT,
            email_count      INTEGER DEFAULT 0,
            days_open        INTEGER,
            is_complete      INTEGER DEFAULT 0,
            alert_count      INTEGER DEFAULT 0,
            created_at       TEXT,
            updated_at       TEXT
        )""")

        # TABLE 3: sales_replies — track cold outreach responses
        c.execute("""CREATE TABLE IF NOT EXISTS sales_replies (
            reply_id         TEXT PRIMARY KEY,
            received_at      TEXT NOT NULL,
            customer_name    TEXT,
            customer_email   TEXT,
            sender           TEXT,
            campaign_week    INTEGER,
            campaign_type    TEXT,
            intent           TEXT,
            next_action      TEXT,
            urgency          TEXT,
            subject_raw      TEXT,
            body_preview     TEXT,
            panjiva_vol_month INTEGER,
            panjiva_carrier  TEXT,
            panjiva_route    TEXT,
            cross_ref_note   TEXT,
            is_actioned      INTEGER DEFAULT 0,
            actioned_at      TEXT,
            actioned_note    TEXT,
            created_at       TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reply_intent ON sales_replies(intent, urgency)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_reply_customer ON sales_replies(customer_name)")

        # TABLE 4: nelson_alerts
        c.execute("""CREATE TABLE IF NOT EXISTS nelson_alerts (
            alert_id         TEXT PRIMARY KEY,
            created_at       TEXT NOT NULL,
            alert_type       TEXT,
            shipment_key     TEXT,
            customer_name    TEXT,
            member_owner     TEXT,
            risk_level       TEXT,
            alert_reason     TEXT,
            primary_stage    TEXT,
            subject_raw      TEXT,
            hbl              TEXT,
            bkg              TEXT,
            is_read          INTEGER DEFAULT 0,
            is_resolved      INTEGER DEFAULT 0
        )""")

        # TABLE 5: customers — enriched customer profiles
        c.execute("""CREATE TABLE IF NOT EXISTS customers (
            customer_name    TEXT PRIMARY KEY,
            customer_type    TEXT,
            outlook_folder   TEXT,
            first_seen_at    TEXT,
            last_contact_at  TEXT,
            total_shipments  INTEGER DEFAULT 0,
            active_shipments INTEGER DEFAULT 0,
            total_replies    INTEGER DEFAULT 0,
            last_reply_at    TEXT,
            last_intent      TEXT,
            panjiva_vol_month INTEGER,
            panjiva_carrier  TEXT,
            panjiva_route    TEXT,
            sla_hours        INTEGER,
            priority         TEXT DEFAULT 'NORMAL',
            status           TEXT DEFAULT 'PROSPECT',
            notes            TEXT,
            updated_at       TEXT
        )""")

        # TABLE 6: email_maybe_review — uncertain emails from PST import
        c.execute("""CREATE TABLE IF NOT EXISTS email_maybe_review (
            review_id      TEXT PRIMARY KEY,
            received_at    TEXT,
            sender         TEXT,
            subject_raw    TEXT,
            folder_context TEXT,
            body_preview   TEXT,
            is_reviewed    INTEGER DEFAULT 0,
            review_verdict TEXT,
            reviewed_at    TEXT,
            created_at     TEXT
        )""")

        conn.commit()
        conn.close()
        log.info("Database initialised at %s", DB_PATH)

    # ------------------------------------------------------------------
    # scan_msg_files  — main entry
    # ------------------------------------------------------------------
    def scan_msg_files(self) -> dict:
        """
        Scan all .msg files in outlook/ subfolders.
        Parse each, insert to DB, move to _processed/.
        Returns summary dict.
        """
        # Import here to allow the rest of the module to work without
        # extract-msg when it's not needed (e.g. import-only for init_db).
        try:
            import extract_msg
        except ImportError:
            log.error("extract-msg not installed. Run: pip install extract-msg")
            return {'error': 'extract-msg not installed'}

        # Ensure we can import email_parser from the same package
        sys.path.insert(0, str(Path(__file__).parent))
        from email_parser import EmailClassifier

        classifier = EmailClassifier()
        stats = {
            'scanned': 0, 'shipments': 0, 'sales': 0,
            'alerts': 0, 'errors': 0, 'skipped': 0,
        }

        # Build list of (msg_file, folder_context, member_owner)
        to_scan: list[tuple[Path, str, str]] = []

        # TEAM SUNNY subfolders → Mentee emails
        team_dir = OUTLOOK_DIR / 'TEAM_SUNNY'
        if team_dir.exists():
            for member_dir in team_dir.iterdir():
                if member_dir.is_dir():
                    member = member_dir.name.upper()
                    for msg_file in member_dir.glob('*.msg'):
                        to_scan.append((msg_file, f'TEAM SUNNY\\{member}', member))

        # CNEE, SHIPPER, AGENT, INTERNAL → Nelson's emails
        for folder_type in ['CNEE', 'SHIPPER', 'AGENT', 'INTERNAL']:
            type_dir = OUTLOOK_DIR / folder_type
            if type_dir.exists():
                for customer_dir in type_dir.iterdir():
                    if customer_dir.is_dir():
                        customer = customer_dir.name.upper()
                        for msg_file in customer_dir.glob('*.msg'):
                            to_scan.append((
                                msg_file,
                                f'{folder_type}\\{customer}',
                                'NELSON',
                            ))
                # Also scan root of folder type
                for msg_file in type_dir.glob('*.msg'):
                    to_scan.append((msg_file, folder_type, 'NELSON'))

        # NELSON folder → Nelson's own emails
        nelson_dir = OUTLOOK_DIR / 'NELSON'
        if nelson_dir.exists():
            for msg_file in nelson_dir.glob('*.msg'):
                to_scan.append((msg_file, 'NELSON', 'NELSON'))

        # Also scan outlook/ root for any .msg files placed directly
        for msg_file in OUTLOOK_DIR.glob('*.msg'):
            to_scan.append((msg_file, 'INBOX', 'NELSON'))

        if not to_scan:
            log.info("No .msg files found to process.")
            return stats

        log.info("Found %d .msg files to process.", len(to_scan))

        # Process each .msg file
        conn = get_db(DB_PATH)

        for msg_file, folder_context, member_owner in to_scan:
            try:
                msg = extract_msg.Message(str(msg_file))
                subject    = msg.subject or ''
                sender     = msg.sender or ''
                recipients = msg.to or ''
                body       = (msg.body or '')[:2000]

                # Date handling: extract_msg may return different types
                received = datetime.now().isoformat()
                if msg.date:
                    try:
                        received = msg.date.isoformat()
                    except Exception:
                        received = str(msg.date)

                entry_id = getattr(msg, 'entryID', None)
                msg.close()

                # Check duplicate
                existing = conn.execute(
                    "SELECT event_id FROM email_events WHERE msg_filename = ?",
                    (msg_file.name,),
                ).fetchone()
                if existing:
                    stats['skipped'] += 1
                    self._move_to_processed(msg_file)
                    continue

                # Classify
                email_type = classifier.classify(subject, sender, folder_context)

                # Parse
                if email_type == 'TYPE_SHIPMENT':
                    parsed = classifier.parse_shipment(
                        subject, sender, recipients, received,
                        member_owner, folder_context,
                    )
                    stats['shipments'] += 1
                elif email_type == 'TYPE_SALES':
                    parsed = classifier.parse_sales_reply(
                        subject, sender, body, received, folder_context,
                    )
                    stats['sales'] += 1
                else:
                    parsed = {
                        'email_type': email_type, 'subject_raw': subject,
                        'sender': sender, 'received_at': received,
                    }

                # Insert to email_events
                event_id = str(uuid.uuid4())
                self._insert_event(conn, event_id, parsed, msg_file.name, entry_id)

                # Update shipments table (if TYPE_SHIPMENT)
                if email_type == 'TYPE_SHIPMENT' and parsed.get('shipment_key'):
                    self._upsert_shipment(conn, parsed)
                    # Generate alert if needed
                    if parsed['risk_level'] in ('CRITICAL', 'HIGH'):
                        self._insert_alert(conn, parsed)
                        stats['alerts'] += 1

                # Update sales_replies table (if TYPE_SALES)
                if email_type == 'TYPE_SALES':
                    self._insert_sales_reply(conn, parsed)
                    if parsed.get('intent') in ('HOT', 'PRICE_FIGHT'):
                        self._insert_alert(conn, parsed, alert_type='SALES_HOT')
                        stats['alerts'] += 1

                # Update customers table
                self._upsert_customer(conn, parsed, folder_context)

                # Move .msg to _processed
                self._move_to_processed(msg_file)
                stats['scanned'] += 1

            except Exception as e:
                log.error("Error processing %s: %s", msg_file.name, e)
                try:
                    dest = OUTLOOK_DIR / '_unmatched' / msg_file.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(msg_file), str(dest))
                except Exception:
                    pass
                stats['errors'] += 1

        conn.commit()
        conn.close()

        # Auto-delete old _processed files (> MSG_KEEP_DAYS)
        self._cleanup_processed()

        log.info("Scan complete: %s", stats)
        return stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _insert_event(self, conn, event_id: str, parsed: dict,
                      msg_filename: str, outlook_entry_id=None):
        """Insert a row into email_events."""
        now = datetime.now().isoformat()
        conn.execute("""INSERT OR IGNORE INTO email_events
            (event_id, received_at, processed_at, email_type,
             member_owner, folder_context, sender, recipients, subject_raw,
             shipment_key, hbl, bkg, member_ref,
             customer_name, customer_type,
             primary_stage, stages_detected, risk_level, risk_reasons,
             route, pol, pod, carrier, container_type, etd, incoterm, commodity,
             intent, next_action, urgency, campaign_week, campaign_type,
             body_preview, parse_confidence, needs_review,
             msg_filename, outlook_entry_id)
            VALUES (?,?,?,?, ?,?,?,?,?, ?,?,?,?, ?,?, ?,?,?,?, ?,?,?,?,?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?)""", (
            event_id,
            parsed.get('received_at', now),
            now,
            parsed.get('email_type', 'UNKNOWN'),
            parsed.get('member_owner'),
            parsed.get('folder_context'),
            parsed.get('sender'),
            parsed.get('recipients'),
            parsed.get('subject_raw'),
            parsed.get('shipment_key'),
            parsed.get('hbl'),
            parsed.get('bkg'),
            parsed.get('member_ref'),
            parsed.get('customer_name'),
            None,  # customer_type filled by _upsert_customer
            parsed.get('primary_stage'),
            json.dumps(parsed.get('stages_detected', [])),
            parsed.get('risk_level', 'NORMAL'),
            json.dumps(parsed.get('risk_reasons', [])),
            parsed.get('route'),
            parsed.get('pol'),
            parsed.get('pod'),
            parsed.get('carrier'),
            parsed.get('container_type'),
            parsed.get('etd'),
            parsed.get('incoterm'),
            parsed.get('commodity'),
            parsed.get('intent'),
            parsed.get('next_action'),
            parsed.get('urgency'),
            parsed.get('campaign_week'),
            parsed.get('campaign_type'),
            parsed.get('body_preview'),
            parsed.get('parse_confidence'),
            1 if parsed.get('needs_review') else 0,
            msg_filename,
            outlook_entry_id,
        ))

    def _upsert_shipment(self, conn, parsed: dict):
        """Update or create shipment record."""
        key = parsed['shipment_key']
        now = datetime.now().isoformat()
        existing = conn.execute(
            "SELECT shipment_key, stage_history, email_count FROM shipments WHERE shipment_key=?",
            (key,),
        ).fetchone()

        if existing:
            history = json.loads(existing[1] or '[]')
            history.append({
                'stage': parsed.get('primary_stage'),
                'ts': parsed['received_at'],
                'member': parsed.get('member_owner'),
                'risk': parsed.get('risk_level'),
            })
            seen_stages = {h['stage'] for h in history if h['stage']}
            full_lifecycle = [
                'BOOKING', 'SI_SUBMITTED', 'DRAFT_BL_ISSUED',
                'ATD', 'DN_SENT', 'INVOICE_ISSUED', 'PAYMENT_CONFIRMED',
            ]
            missing = [s for s in full_lifecycle if s not in seen_stages]

            conn.execute("""UPDATE shipments SET
                current_stage=?, stage_history=?, missing_stages=?,
                risk_level=?, last_email_at=?, email_count=email_count+1,
                days_open=CAST((julianday('now')-julianday(first_email_at)) AS INTEGER),
                is_complete=?, updated_at=?
                WHERE shipment_key=?""", (
                parsed.get('primary_stage'),
                json.dumps(history),
                json.dumps(missing),
                parsed.get('risk_level', 'NORMAL'),
                parsed['received_at'],
                1 if parsed.get('primary_stage') == 'PAYMENT_CONFIRMED' else 0,
                now,
                key,
            ))
        else:
            conn.execute("""INSERT INTO shipments
                (shipment_key, hbl, bkg, member_ref, member_owner, customer_name,
                 current_stage, stage_history, missing_stages, risk_level, risk_flags,
                 route, pol, pod, carrier, container_type, commodity, incoterm, etd,
                 payment_status, first_email_at, last_email_at, email_count,
                 days_open, created_at, updated_at)
                VALUES (?,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,?,?,?, ?,?,?,1, 0,?,?)""", (
                key,
                parsed.get('hbl'), parsed.get('bkg'), parsed.get('member_ref'),
                parsed.get('member_owner'), parsed.get('customer_name'),
                parsed.get('primary_stage'),
                json.dumps([{
                    'stage': parsed.get('primary_stage'),
                    'ts': parsed['received_at'],
                    'member': parsed.get('member_owner'),
                }]),
                json.dumps([
                    'BOOKING', 'SI_SUBMITTED', 'DRAFT_BL_ISSUED',
                    'ATD', 'DN_SENT', 'INVOICE_ISSUED', 'PAYMENT_CONFIRMED',
                ]),
                parsed.get('risk_level', 'NORMAL'),
                json.dumps(parsed.get('risk_reasons', [])),
                parsed.get('route'), parsed.get('pol'), parsed.get('pod'),
                parsed.get('carrier'), parsed.get('container_type'),
                parsed.get('commodity'), parsed.get('incoterm'), parsed.get('etd'),
                'PENDING', parsed['received_at'], parsed['received_at'],
                now, now,
            ))

    def _insert_alert(self, conn, parsed: dict, alert_type: str = 'RISK'):
        """Insert a new alert."""
        now = datetime.now().isoformat()
        reason = ', '.join(parsed.get('risk_reasons', []))
        if alert_type == 'SALES_HOT':
            reason = f"Sales intent: {parsed.get('intent', 'HOT')}"

        conn.execute("""INSERT INTO nelson_alerts
            (alert_id, created_at, alert_type, shipment_key, customer_name,
             member_owner, risk_level, alert_reason, primary_stage,
             subject_raw, hbl, bkg)
            VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?)""", (
            str(uuid.uuid4()), now, alert_type,
            parsed.get('shipment_key'), parsed.get('customer_name'),
            parsed.get('member_owner'),
            parsed.get('risk_level', 'HIGH') if alert_type == 'RISK' else 'HIGH',
            reason,
            parsed.get('primary_stage'),
            parsed.get('subject_raw'),
            parsed.get('hbl'), parsed.get('bkg'),
        ))

    def _insert_sales_reply(self, conn, parsed: dict):
        """Insert into sales_replies table."""
        now = datetime.now().isoformat()
        conn.execute("""INSERT OR IGNORE INTO sales_replies
            (reply_id, received_at, customer_name, customer_email, sender,
             campaign_week, campaign_type, intent, next_action, urgency,
             subject_raw, body_preview, created_at)
            VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?)""", (
            str(uuid.uuid4()),
            parsed.get('received_at', now),
            parsed.get('customer_name'),
            parsed.get('sender'),
            parsed.get('sender'),
            parsed.get('campaign_week'),
            parsed.get('campaign_type'),
            parsed.get('intent', 'UNKNOWN'),
            parsed.get('next_action', 'REVIEW'),
            parsed.get('urgency', 'THIS_WEEK'),
            parsed.get('subject_raw'),
            parsed.get('body_preview'),
            now,
        ))

    def _upsert_customer(self, conn, parsed: dict, folder_context: str):
        """Update or create customer record."""
        name = parsed.get('customer_name')
        if not name:
            return

        now = datetime.now().isoformat()
        email_type = parsed.get('email_type', '')

        # Determine customer_type from folder_context
        folder_upper = folder_context.upper()
        customer_type = 'UNKNOWN'
        for key in ['CNEE', 'SHIPPER', 'AGENT', 'INTERNAL']:
            if key in folder_upper:
                customer_type = key
                break

        existing = conn.execute(
            "SELECT customer_name FROM customers WHERE customer_name=?", (name,)
        ).fetchone()

        if existing:
            if email_type == 'TYPE_SHIPMENT':
                conn.execute("""UPDATE customers SET
                    last_contact_at=?, total_shipments=total_shipments+1, updated_at=?
                    WHERE customer_name=?""", (now, now, name))
            elif email_type == 'TYPE_SALES':
                conn.execute("""UPDATE customers SET
                    last_reply_at=?, total_replies=total_replies+1,
                    last_intent=?, updated_at=?
                    WHERE customer_name=?""", (
                    now, parsed.get('intent'), now, name,
                ))
        else:
            conn.execute("""INSERT INTO customers
                (customer_name, customer_type, outlook_folder,
                 first_seen_at, last_contact_at,
                 total_shipments, total_replies, status, updated_at)
                VALUES (?,?,?, ?,?, ?,?,?,?)""", (
                name, customer_type, folder_context,
                now, now,
                1 if email_type == 'TYPE_SHIPMENT' else 0,
                1 if email_type == 'TYPE_SALES' else 0,
                'ACTIVE' if email_type == 'TYPE_SHIPMENT' else 'PROSPECT',
                now,
            ))

    def _move_to_processed(self, msg_file: Path):
        """Move .msg file to _processed/ folder."""
        dest = OUTLOOK_DIR / '_processed' / msg_file.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(msg_file), str(dest))
        except Exception as e:
            log.warning("Could not move %s to _processed: %s", msg_file.name, e)

    def _cleanup_processed(self):
        """Auto-delete .msg files older than MSG_KEEP_DAYS."""
        cutoff = datetime.now() - timedelta(days=MSG_KEEP_DAYS)
        proc_dir = OUTLOOK_DIR / '_processed'
        if not proc_dir.exists():
            return
        count = 0
        for f in proc_dir.glob('*.msg'):
            try:
                if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                    f.unlink()
                    count += 1
            except Exception:
                pass
        if count:
            log.info("Cleaned up %d old .msg files from _processed/", count)

    # ------------------------------------------------------------------
    # export_parquet
    # ------------------------------------------------------------------
    def export_parquet(self):
        """Export SQLite tables to Parquet for AI/ML use."""
        try:
            import pandas as pd
        except ImportError:
            log.error("pandas not installed. Run: pip install pandas pyarrow")
            return

        PARQUET_DIR.mkdir(parents=True, exist_ok=True)
        conn = get_db(DB_PATH, readonly=True)
        today = datetime.now().strftime('%Y%m%d')

        tables = ['email_events', 'shipments', 'sales_replies',
                   'nelson_alerts', 'customers']
        for table in tables:
            try:
                df = pd.read_sql(f"SELECT * FROM {table}", conn)
                out = PARQUET_DIR / f"{table}_{today}.parquet"
                df.to_parquet(out, index=False, compression='snappy')
                log.info("Exported %s → %s (%d rows)", table, out.name, len(df))
            except Exception as e:
                log.error("Failed to export %s: %s", table, e)

        conn.close()


# ======================================================================
# CLI entry point
# ======================================================================
def main():
    collector = DataCollector()
    collector.init_db()

    if len(sys.argv) > 1 and sys.argv[1] == 'parquet':
        collector.export_parquet()
    else:
        stats = collector.scan_msg_files()
        print(f"\n{'='*50}")
        print("  DATA COLLECTOR — Results")
        print(f"{'='*50}")
        for k, v in stats.items():
            print(f"  {k:>12}: {v}")


if __name__ == '__main__':
    main()
