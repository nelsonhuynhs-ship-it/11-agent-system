-- ============================================================================
-- 003_email_platform.sql — Email Platform Tables
-- ============================================================================
-- New tables for Email Campaign SaaS layer:
--   cnee_master, email_log, email_queue, customer_behavior, customer_rules
-- ============================================================================

-- ── CNEE MASTER ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cnee_master (
    id              SERIAL PRIMARY KEY,
    company_name    VARCHAR(255),
    contact_name    VARCHAR(255),
    email           VARCHAR(255),
    campaign        VARCHAR(100),
    country         VARCHAR(100),
    port            VARCHAR(50),
    status          VARCHAR(50) DEFAULT 'active'
                    CHECK (status IN ('active', 'unsubscribed', 'bounced', 'invalid')),
    lead_score      FLOAT DEFAULT 0,
    last_contacted  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cnee_campaign ON cnee_master(campaign);
CREATE INDEX IF NOT EXISTS idx_cnee_email    ON cnee_master(email);
CREATE INDEX IF NOT EXISTS idx_cnee_status   ON cnee_master(status);

-- ── EMAIL LOG ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_log (
    id              SERIAL PRIMARY KEY,
    cnee_id         INTEGER REFERENCES cnee_master(id) ON DELETE SET NULL,
    email           VARCHAR(255) NOT NULL,
    subject         TEXT,
    template_used   VARCHAR(100),
    status          VARCHAR(50) DEFAULT 'sent'
                    CHECK (status IN ('sent', 'failed', 'bounced', 'opened', 'clicked')),
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    sent_by         VARCHAR(100),
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_email_log_cnee   ON email_log(cnee_id);
CREATE INDEX IF NOT EXISTS idx_email_log_status ON email_log(status);
CREATE INDEX IF NOT EXISTS idx_email_log_sent   ON email_log(sent_at DESC);

-- ── EMAIL QUEUE ──────────────────────────────────────────────────────────────
-- Worker bridge: WebApp approves → inserts here → Outlook COM worker picks up
CREATE TABLE IF NOT EXISTS email_queue (
    id              SERIAL PRIMARY KEY,
    cnee_id         INTEGER REFERENCES cnee_master(id) ON DELETE SET NULL,
    email           VARCHAR(255) NOT NULL,
    subject         TEXT NOT NULL,
    html_body       TEXT NOT NULL,
    status          VARCHAR(50) DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sending', 'sent', 'failed')),
    retry_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    picked_at       TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_email_queue_status  ON email_queue(status);
CREATE INDEX IF NOT EXISTS idx_email_queue_created ON email_queue(created_at);

-- ── CUSTOMER BEHAVIOR ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_behavior (
    id              SERIAL PRIMARY KEY,
    cnee_id         INTEGER REFERENCES cnee_master(id) ON DELETE SET NULL,
    behavior_type   VARCHAR(50),   -- reply, open, click, bounce, unsubscribe
    email_subject   TEXT,
    response_summary TEXT,
    classification  VARCHAR(50),   -- hot, warm, cold, neutral
    detected_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_behavior_cnee ON customer_behavior(cnee_id);
CREATE INDEX IF NOT EXISTS idx_behavior_type ON customer_behavior(behavior_type);

-- ── CUSTOMER RULES ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_rules (
    id          SERIAL PRIMARY KEY,
    rule_name   VARCHAR(255) NOT NULL,
    rule_type   VARCHAR(100),      -- carrier, markup, cooldown, template
    rule_data   JSONB DEFAULT '{}',
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_rules_type   ON customer_rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_customer_rules_active ON customer_rules(active);
