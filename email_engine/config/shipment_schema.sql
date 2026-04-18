-- shipment_schema.sql — DuckDB DDL for Shipment Brain
-- Idempotent: safe to run multiple times.
-- Tables: shipments (header), shipment_events (lifecycle facts)
--
-- Run via: shipment_db.init_db()

-- ─── Master shipment header ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id     TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    customer_name   TEXT,
    carrier         TEXT,
    pol             TEXT,
    pod             TEXT,
    svc_type        TEXT,      -- FAK / FIX / SCFI / SOC / COC
    first_seen_at   TIMESTAMP,
    last_updated    TIMESTAMP,
    status          TEXT       -- derived from latest event_type
);

-- ─── Lifecycle events ──────────────────────────────────────────────────────────
CREATE SEQUENCE IF NOT EXISTS shipment_events_id_seq;

CREATE TABLE IF NOT EXISTS shipment_events (
    id              BIGINT DEFAULT nextval('shipment_events_id_seq') PRIMARY KEY,
    shipment_id     TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,  -- enum: see EVENT_TYPES in shipment_db.py
    event_date      TIMESTAMP,
    source_msg_id   TEXT,                  -- Outlook entry_id (dedup key)
    source_path     TEXT,                  -- absolute path to .msg file
    raw_excerpt     TEXT,                  -- verbatim ≤200 chars from email body
    confidence      REAL,                  -- LLM confidence 0.0-1.0
    flagged_risk    BOOLEAN     DEFAULT FALSE,
    extracted_at    TIMESTAMP,
    UNIQUE (shipment_id, event_type, source_msg_id)
);

-- ─── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_events_shipment  ON shipment_events(shipment_id);
CREATE INDEX IF NOT EXISTS idx_events_customer  ON shipment_events(shipment_id);
CREATE INDEX IF NOT EXISTS idx_events_type      ON shipment_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_risk      ON shipment_events(flagged_risk);
