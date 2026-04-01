"""
kpi_store.py — Sprint 10: KPI Target Storage
Saves and retrieves monthly KPI targets in freight_bot.db.

KPI Fields:
  shipments     — Target số lô hàng trong tháng
  revenue       — Target doanh thu (USD)
  win_rate      — Target win rate (%)
  new_customers — Target số khách mới
"""
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_FILE = None  # set by init_kpi()

KPI_FIELDS = {
    'shipments':     ('Số lô hàng', 'lô'),
    'revenue':       ('Doanh thu', 'USD'),
    'win_rate':      ('Win Rate', '%'),
    'new_customers': ('Khách hàng mới', 'KH'),
}


def init_kpi(db_file: str):
    global DB_FILE
    DB_FILE = db_file
    _ensure_table()


def _conn():
    return sqlite3.connect(DB_FILE)


def _ensure_table():
    """Create kpi_targets table if not exists."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kpi_targets (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                month     TEXT NOT NULL,       -- YYYY-MM
                field     TEXT NOT NULL,       -- shipments / revenue / win_rate / new_customers
                target    REAL NOT NULL,
                set_at    TEXT NOT NULL,
                UNIQUE(month, field)
            )
        """)
        conn.commit()


def set_kpi(field: str, target: float, month: str = None) -> bool:
    """Set or update a KPI target for the given month (default: current month)."""
    if field not in KPI_FIELDS:
        return False
    if month is None:
        month = datetime.now().strftime('%Y-%m')
    try:
        with _conn() as conn:
            conn.execute("""
                INSERT INTO kpi_targets (month, field, target, set_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(month, field) DO UPDATE SET target=excluded.target, set_at=excluded.set_at
            """, (month, field, target, datetime.now().isoformat()))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"[KPI] set_kpi error: {e}")
        return False


def get_kpi(month: str = None) -> dict:
    """Get all KPI targets for a month. Returns dict {field: target}."""
    if month is None:
        month = datetime.now().strftime('%Y-%m')
    try:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT field, target FROM kpi_targets WHERE month = ?", (month,)
            ).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception as e:
        logger.error(f"[KPI] get_kpi error: {e}")
        return {}


def get_kpi_display(month: str = None) -> str:
    """Format KPI targets as a readable string for Telegram."""
    if month is None:
        month = datetime.now().strftime('%Y-%m')
    targets = get_kpi(month)
    if not targets:
        return f"⚠️ Chưa set KPI cho {month}.\nDùng: `/setkpi shipments 60`"

    lines = [f"🎯 **KPI Targets — {month}**", "━━━━━━━━━━━━━━━━━━━━"]
    for field, (label, unit) in KPI_FIELDS.items():
        val = targets.get(field)
        if val is not None:
            fmt = f"${val:,.0f}" if field == 'revenue' else f"{val:,.0f} {unit}"
            lines.append(f"  📌 {label}: **{fmt}**")
    return "\n".join(lines)


# ─────────────────────── LEADS TRACKING (Sprint 10b) ───────────────────────

def _ensure_leads_table():
    """Create kpi_leads table if not exists."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kpi_leads (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                month   TEXT NOT NULL UNIQUE,   -- YYYY-MM
                leads   INTEGER NOT NULL DEFAULT 0,
                set_at  TEXT NOT NULL
            )
        """)
        conn.commit()


def set_leads(count: int, month: str = None) -> bool:
    """Set manual leads count for a month."""
    if month is None:
        month = datetime.now().strftime('%Y-%m')
    try:
        _ensure_leads_table()
        with _conn() as conn:
            conn.execute("""
                INSERT INTO kpi_leads (month, leads, set_at)
                VALUES (?, ?, ?)
                ON CONFLICT(month) DO UPDATE SET leads=excluded.leads, set_at=excluded.set_at
            """, (month, count, datetime.now().isoformat()))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"[KPI] set_leads error: {e}")
        return False


def get_leads(month: str = None) -> int:
    """Get manual leads count for a month."""
    if month is None:
        month = datetime.now().strftime('%Y-%m')
    try:
        _ensure_leads_table()
        with _conn() as conn:
            row = conn.execute(
                "SELECT leads FROM kpi_leads WHERE month = ?", (month,)
            ).fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"[KPI] get_leads error: {e}")
        return 0


# ─────────────────────── KPI FORECAST (Sprint 10b) ───────────────────────

def get_forecast(actual: float, target: float, month: str = None) -> dict:
    """
    Project end-of-month value based on current pace.

    Args:
        actual: Current actual value (e.g. 12 shipments)
        target: KPI target for the month
        month:  'YYYY-MM' — defaults to current month

    Returns dict:
        days_elapsed, days_total, days_remaining,
        daily_avg, projected_eom, pct_of_target,
        status ('on_track'|'at_risk'|'critical')
    """
    import calendar
    now = datetime.now()
    if month is None:
        month = now.strftime('%Y-%m')

    try:
        year, mon = int(month[:4]), int(month[5:7])
    except Exception:
        year, mon = now.year, now.month

    days_total = calendar.monthrange(year, mon)[1]

    # How many days have elapsed in this month (minimum 1 to avoid div/0)
    if year == now.year and mon == now.month:
        days_elapsed = max(now.day, 1)
    else:
        # Historical month — fully elapsed
        days_elapsed = days_total

    days_remaining = max(days_total - days_elapsed, 0)
    daily_avg = actual / days_elapsed if days_elapsed > 0 else 0
    projected_eom = daily_avg * days_total if days_remaining > 0 else actual

    pct_of_target = (projected_eom / target * 100) if target > 0 else 0

    if pct_of_target >= 80:
        status = 'on_track'
        icon = '🟢'
    elif pct_of_target >= 50:
        status = 'at_risk'
        icon = '🟡'
    else:
        status = 'critical'
        icon = '🔴'

    return {
        'days_elapsed':   days_elapsed,
        'days_total':     days_total,
        'days_remaining': days_remaining,
        'daily_avg':      round(daily_avg, 2),
        'projected_eom':  round(projected_eom, 1),
        'pct_of_target':  round(pct_of_target, 1),
        'status':         status,
        'icon':           icon,
    }
