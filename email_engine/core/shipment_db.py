# -*- coding: utf-8 -*-
"""
shipment_db.py — DuckDB helpers for Shipment Brain  v1.0
=========================================================
Handles schema init + CRUD for `shipments` and `shipment_events` tables.

Usage:
    from email_engine.core.shipment_db import init_db, upsert_shipment, insert_event

DB path defaults to  email_engine/data/shipment_brain.duckdb
Override via env SHIPMENT_DB_PATH.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import duckdb

log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────
_HERE = Path(__file__).parent
_REPO_ROOT = _HERE.parent.parent
_DEFAULT_DB = _REPO_ROOT / "email_engine" / "data" / "shipment_brain.duckdb"
_SCHEMA_SQL = _REPO_ROOT / "email_engine" / "config" / "shipment_schema.sql"

# ─── Event type enum ──────────────────────────────────────────────────────────
EVENT_TYPES: tuple[str, ...] = (
    "BKG_ISSUED",
    "DRAFT_BL_ISSUED",
    "DRAFT_BL_CONFIRMED",
    "LOADED",
    "ATD",
    "DN_SENT",
    "INVOICE_ISSUED",
    "PAYMENT_REQUESTED",
    "PAYMENT_CONFIRMED",
    "COMPLETED",
)

# Ordered for status derivation (last occurring event wins)
_EVENT_ORDER: dict[str, int] = {e: i for i, e in enumerate(EVENT_TYPES)}


def _get_db_path() -> Path:
    env_path = os.environ.get("SHIPMENT_DB_PATH")
    if env_path:
        return Path(env_path)
    return _DEFAULT_DB


def _connect(db_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection. Creates file if it does not exist."""
    path = Path(db_path) if db_path else _get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def init_db(db_path: Path | None = None) -> None:
    """
    Initialize DuckDB schema (idempotent).
    Reads SQL from email_engine/config/shipment_schema.sql and executes it.
    """
    if not _SCHEMA_SQL.exists():
        raise FileNotFoundError(f"Schema file not found: {_SCHEMA_SQL}")

    sql = _SCHEMA_SQL.read_text(encoding="utf-8")
    con = _connect(db_path)
    try:
        con.executemany  # ping connection
        # Execute each statement separately (DuckDB executescript not available)
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for stmt in statements:
            try:
                con.execute(stmt)
            except Exception as exc:
                # Sequence/table already exists → tolerate
                msg = str(exc).lower()
                if "already exists" in msg or "duplicate" in msg:
                    log.debug("Schema already exists (skipped): %s", exc)
                else:
                    raise
        con.commit()
        log.info("Shipment DB schema initialised at %s", _get_db_path())
    finally:
        con.close()


def upsert_shipment(
    shipment_id: str,
    customer_id: str,
    customer_name: Optional[str] = None,
    carrier: Optional[str] = None,
    pol: Optional[str] = None,
    pod: Optional[str] = None,
    svc_type: Optional[str] = None,
    db_path: Path | None = None,
) -> None:
    """
    Insert or update a shipment header row.
    Updates customer_name/carrier/pol/pod/svc_type if already exists.
    Always refreshes last_updated.
    """
    now = datetime.utcnow()
    con = _connect(db_path)
    try:
        existing = con.execute(
            "SELECT shipment_id FROM shipments WHERE shipment_id = ?",
            [shipment_id],
        ).fetchone()

        if existing:
            con.execute(
                """
                UPDATE shipments SET
                    customer_name = COALESCE(?, customer_name),
                    carrier       = COALESCE(?, carrier),
                    pol           = COALESCE(?, pol),
                    pod           = COALESCE(?, pod),
                    svc_type      = COALESCE(?, svc_type),
                    last_updated  = ?
                WHERE shipment_id = ?
                """,
                [customer_name, carrier, pol, pod, svc_type, now, shipment_id],
            )
        else:
            con.execute(
                """
                INSERT INTO shipments
                    (shipment_id, customer_id, customer_name, carrier,
                     pol, pod, svc_type, first_seen_at, last_updated, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [shipment_id, customer_id, customer_name, carrier,
                 pol, pod, svc_type, now, now, "ACTIVE"],
            )
        con.commit()
        log.debug("Upserted shipment %s (customer=%s)", shipment_id, customer_id)
    finally:
        con.close()


def insert_event(
    shipment_id: str,
    event_type: str,
    event_date: Optional[datetime] = None,
    source_msg_id: Optional[str] = None,
    source_path: Optional[str] = None,
    raw_excerpt: Optional[str] = None,
    confidence: float = 1.0,
    flagged_risk: bool = False,
    db_path: Path | None = None,
) -> bool:
    """
    Insert a shipment lifecycle event.
    Returns True if inserted, False if duplicate (skipped).

    Deduplication key: (shipment_id, event_type, source_msg_id).
    If source_msg_id is None, falls back to insert (no dedup possible).
    """
    if event_type not in EVENT_TYPES:
        log.warning("Unknown event_type '%s' — skipping insert", event_type)
        return False

    now = datetime.utcnow()
    con = _connect(db_path)
    try:
        # Check duplicate only when source_msg_id is known
        if source_msg_id:
            dup = con.execute(
                """
                SELECT id FROM shipment_events
                WHERE shipment_id = ? AND event_type = ? AND source_msg_id = ?
                """,
                [shipment_id, event_type, source_msg_id],
            ).fetchone()
            if dup:
                log.debug(
                    "Duplicate event skipped: %s / %s / %s",
                    shipment_id, event_type, source_msg_id,
                )
                return False

        con.execute(
            """
            INSERT INTO shipment_events
                (shipment_id, event_type, event_date, source_msg_id,
                 source_path, raw_excerpt, confidence, flagged_risk, extracted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                shipment_id, event_type, event_date, source_msg_id,
                source_path,
                (raw_excerpt[:200] if raw_excerpt else None),
                confidence, flagged_risk, now,
            ],
        )

        # Update shipment.status to latest event
        if event_type in _EVENT_ORDER:
            con.execute(
                """
                UPDATE shipments SET status = ?, last_updated = ?
                WHERE shipment_id = ?
                  AND (status IS NULL
                       OR ? >= COALESCE(
                            (SELECT MAX(e2.event_type) FROM shipment_events e2
                             WHERE e2.shipment_id = ?),
                          ''))
                """,
                [event_type, now, shipment_id, event_type, shipment_id],
            )

        con.commit()
        log.debug(
            "Inserted event %s for %s (confidence=%.2f, risk=%s)",
            event_type, shipment_id, confidence, flagged_risk,
        )
        return True
    finally:
        con.close()


def get_shipment_events(
    shipment_id: str,
    db_path: Path | None = None,
) -> list[dict]:
    """
    Return all events for a shipment, ordered by event_date ASC.
    Each row returned as a dict.
    """
    con = _connect(db_path)
    try:
        rows = con.execute(
            """
            SELECT id, event_type, event_date, source_msg_id, source_path,
                   raw_excerpt, confidence, flagged_risk, extracted_at
            FROM shipment_events
            WHERE shipment_id = ?
            ORDER BY event_date ASC NULLS LAST, extracted_at ASC
            """,
            [shipment_id],
        ).fetchall()
        cols = [
            "id", "event_type", "event_date", "source_msg_id", "source_path",
            "raw_excerpt", "confidence", "flagged_risk", "extracted_at",
        ]
        return [dict(zip(cols, row)) for row in rows]
    finally:
        con.close()
