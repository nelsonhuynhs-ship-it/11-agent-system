-- intel.db — Email Event Chain (Phase 02)
-- Append-only log of every per-CNEE email event (SENT, REPLY, BOUNCE, TIER changes).
-- Source of truth for tier_engine + scanner; debounced writeback to cnee_master_v2.xlsx.

CREATE TABLE IF NOT EXISTS email_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cnee_email          TEXT    NOT NULL,
    event_type          TEXT    NOT NULL,
        -- SENT | REPLY | AUTO_REPLY | BOUNCE | UNSUBSCRIBE
        -- TIER_PROMOTED | TIER_DEMOTED | GOCLAW_DRAFTED | MANUAL_NOTE
    timestamp           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- SENT-specific
    subject             TEXT,
    template_id         TEXT,
    market_state        TEXT,            -- URGENT | STABLE | DECLINING
    delta_pct           REAL,
    batch_id            TEXT,
    campaign_id         TEXT,

    -- REPLY-specific
    reply_subject       TEXT,
    reply_body_snippet  TEXT,            -- first 500 chars
    sentiment           TEXT,            -- POSITIVE | NEUTRAL | NEGATIVE | UNKNOWN
    intent              TEXT,            -- booking | price_inquiry | negotiating | gratitude | objection | general
    reply_delay_hours   REAL,

    -- BOUNCE-specific
    bounce_type         TEXT,            -- HARD | SOFT | POLICY
    bounce_reason       TEXT,

    -- TIER change-specific
    old_tier            TEXT,
    new_tier            TEXT,
    change_reason       TEXT,

    -- Generic / extension
    raw_meta            TEXT             -- JSON for extra fields
);

CREATE INDEX IF NOT EXISTS idx_events_cnee_time
    ON email_events(cnee_email, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_events_type_time
    ON email_events(event_type, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_events_batch
    ON email_events(batch_id);

-- Per-CNEE bounce counter cache (avoid full-scan on every BOUNCE).
-- Authoritative count is still in email_events; this is just a fast lookup.
CREATE TABLE IF NOT EXISTS cnee_state (
    cnee_email          TEXT PRIMARY KEY,
    bounce_count        INTEGER NOT NULL DEFAULT 0,
    unsubscribed        INTEGER NOT NULL DEFAULT 0,
    last_tier_change_at TIMESTAMP,
    updated_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
