"""
SQLite Database — Customer Memory, Commissions, Price Snapshots
"""
import sqlite3
import os
from datetime import datetime
from config import DB_FILE


def get_db():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS customer_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            rule_value TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS commissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            customer TEXT,
            carrier TEXT,
            container TEXT,
            quantity INTEGER DEFAULT 1,
            amount REAL DEFAULT 0,
            total REAL DEFAULT 0,
            status TEXT DEFAULT 'PENDING',
            invoice_date DATE,
            paid_date DATE,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS shipment_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            event_type TEXT,
            event_date DATETIME,
            location TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS price_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date DATE,
            carrier TEXT,
            container TEXT,
            pol TEXT,
            pod TEXT,
            place TEXT,
            price REAL,
            source TEXT
        );

        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT,
            request TEXT,
            status TEXT DEFAULT 'PENDING',
            quote_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            reminded_at DATETIME
        );

        CREATE INDEX IF NOT EXISTS idx_rules_customer ON customer_rules(customer);
        CREATE INDEX IF NOT EXISTS idx_com_status ON commissions(status);
        CREATE INDEX IF NOT EXISTS idx_snap_carrier ON price_snapshots(carrier, container, pod);
    """)
    conn.commit()
    conn.close()
    print(f"[DB] Initialized: {DB_FILE}")


# ════════════════════════════════════════════
# CUSTOMER RULES
# ════════════════════════════════════════════

def add_customer_rule(customer, rule_type, rule_value):
    """Add a customer preference rule."""
    conn = get_db()
    conn.execute(
        "INSERT INTO customer_rules (customer, rule_type, rule_value) VALUES (?, ?, ?)",
        (customer.upper(), rule_type, rule_value)
    )
    conn.commit()
    conn.close()


def get_customer_rules(customer):
    """Get all rules for a customer."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM customer_rules WHERE customer = ? ORDER BY created_at",
        (customer.upper(),)
    ).fetchall()
    conn.close()
    return rows


def delete_customer_rule(rule_id):
    """Delete a rule by ID."""
    conn = get_db()
    conn.execute("DELETE FROM customer_rules WHERE id = ?", (rule_id,))
    conn.commit()
    conn.close()


def get_all_customers_with_rules():
    """Get list of customers who have any rules."""
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT customer, COUNT(*) as rule_count FROM customer_rules GROUP BY customer ORDER BY customer"
    ).fetchall()
    conn.close()
    return rows


def get_excluded_carriers(customer):
    """Get list of carriers excluded for a customer."""
    conn = get_db()
    rows = conn.execute(
        "SELECT rule_value FROM customer_rules WHERE customer = ? AND rule_type = 'exclude_carrier'",
        (customer.upper(),)
    ).fetchall()
    conn.close()
    return [r['rule_value'] for r in rows]


# ════════════════════════════════════════════
# PRICE SNAPSHOTS
# ════════════════════════════════════════════

def save_price_snapshot(carrier, container, pol, pod, place, price, source=""):
    """Save a price point for drop detection."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    # Check if already has snapshot today
    existing = conn.execute(
        "SELECT id FROM price_snapshots WHERE snapshot_date=? AND carrier=? AND container=? AND pod=? AND place=?",
        (today, carrier, container, pod, place)
    ).fetchone()
    if existing:
        conn.execute("UPDATE price_snapshots SET price=?, source=? WHERE id=?", (price, source, existing['id']))
    else:
        conn.execute(
            "INSERT INTO price_snapshots (snapshot_date, carrier, container, pol, pod, place, price, source) VALUES (?,?,?,?,?,?,?,?)",
            (today, carrier, container, pol, pod, place, price, source)
        )
    conn.commit()
    conn.close()


def get_previous_price(carrier, container, pod, place, days_back=7):
    """Get the most recent price before today for comparison."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        """SELECT price, snapshot_date, source FROM price_snapshots 
           WHERE carrier=? AND container=? AND pod=? AND place=? AND snapshot_date < ?
           ORDER BY snapshot_date DESC LIMIT 1""",
        (carrier, container, pod, place, today)
    ).fetchone()
    conn.close()
    return row


# ════════════════════════════════════════════
# COMMISSIONS
# ════════════════════════════════════════════

def add_commission(job_id, customer, carrier, container, quantity, amount):
    """Create a commission entry."""
    total = amount * quantity
    conn = get_db()
    conn.execute(
        "INSERT INTO commissions (job_id, customer, carrier, container, quantity, amount, total) VALUES (?,?,?,?,?,?,?)",
        (job_id, customer, carrier, container, quantity, amount, total)
    )
    conn.commit()
    conn.close()


def get_pending_commissions():
    """Get all pending commissions."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM commissions WHERE status = 'PENDING' ORDER BY created_at"
    ).fetchall()
    conn.close()
    return rows


def mark_commission_paid(com_id):
    """Mark a commission as paid."""
    conn = get_db()
    conn.execute(
        "UPDATE commissions SET status='PAID', paid_date=? WHERE id=?",
        (datetime.now().strftime("%Y-%m-%d"), com_id)
    )
    conn.commit()
    conn.close()
