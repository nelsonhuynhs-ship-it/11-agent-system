-- ============================================================================
-- 001_initial_schema.sql — Nelson Freight PostgreSQL Schema
-- ============================================================================
-- Run: psql -d nelson_freight -f 001_initial_schema.sql
-- Or via Supabase SQL editor
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── TENANTS ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    plan        VARCHAR(50) DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    settings    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default tenant (single-tenant phase)
INSERT INTO tenants (id, name, plan) VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Nelson Freight',
    'pro'
) ON CONFLICT DO NOTHING;

-- ── USERS ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           VARCHAR(255) UNIQUE NOT NULL,
    name            VARCHAR(255),
    role            VARCHAR(50) DEFAULT 'operator' CHECK (role IN ('admin', 'operator', 'viewer')),
    auth_provider   VARCHAR(50) DEFAULT 'supabase',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default admin
INSERT INTO users (tenant_id, email, name, role) VALUES (
    '00000000-0000-0000-0000-000000000001',
    'nelson@freight.local',
    'Nelson',
    'admin'
) ON CONFLICT (email) DO NOTHING;

-- ── SESSIONS ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sessions (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(512) NOT NULL,
    client_type VARCHAR(50) DEFAULT 'web' CHECK (client_type IN ('web', 'bot', 'erp')),
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

-- ── QUOTES ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quotes (
    id               VARCHAR(50) PRIMARY KEY,  -- Q-YYYYMMDD-NNN
    tenant_id        UUID NOT NULL REFERENCES tenants(id),
    created_by       UUID REFERENCES users(id),
    customer         VARCHAR(255),
    service_type     VARCHAR(50) DEFAULT 'CY-CY',
    pol              VARCHAR(50) NOT NULL,
    pod              VARCHAR(100),
    place            VARCHAR(100),
    routing          VARCHAR(255),
    status           VARCHAR(50) DEFAULT 'DRAFT'
                     CHECK (status IN ('DRAFT', 'SENT', 'ACCEPTED', 'REJECTED', 'CONVERTED', 'EXPIRED')),
    markup_mode      VARCHAR(50) DEFAULT 'global',
    global_markup    REAL DEFAULT 0,
    win_probability  REAL,
    parent_quote_id  VARCHAR(50) REFERENCES quotes(id),
    version          INTEGER DEFAULT 1,
    converted_shipment_id VARCHAR(50),
    optional_charges JSONB DEFAULT '[]',
    charges_total    REAL DEFAULT 0,
    transit          VARCHAR(100),
    freetime         VARCHAR(100),
    validity         VARCHAR(100),
    eff              DATE,
    exp              DATE,
    price_alerts     JSONB DEFAULT '[]',
    metadata         JSONB DEFAULT '{}',
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quotes_customer ON quotes(customer);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status);
CREATE INDEX IF NOT EXISTS idx_quotes_tenant ON quotes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_quotes_pol_place ON quotes(pol, place);
CREATE INDEX IF NOT EXISTS idx_quotes_created ON quotes(created_at DESC);

-- ── QUOTE CARRIERS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quote_carriers (
    id              SERIAL PRIMARY KEY,
    quote_id        VARCHAR(50) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    carrier         VARCHAR(50) NOT NULL,
    badge           VARCHAR(20),  -- SOC, COC, FIXED
    transit         VARCHAR(100),
    freetime        VARCHAR(50),
    container_rates JSONB DEFAULT '{}',   -- {"20GP": {"ocean_freight": 1200, "sell_rate": 1400, ...}}
    carrier_markup  JSONB DEFAULT '{}',   -- {"20GP": 50, "40HQ": 75}
    note            TEXT,
    effective       DATE,
    expiry          DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_qc_quote ON quote_carriers(quote_id);
CREATE INDEX IF NOT EXISTS idx_qc_carrier ON quote_carriers(carrier);

-- ── QUOTE VERSIONS ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quote_versions (
    id          SERIAL PRIMARY KEY,
    quote_id    VARCHAR(50) NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
    version     INTEGER NOT NULL,
    snapshot    JSONB NOT NULL,  -- full quote state at this version
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(quote_id, version)
);

-- ── SHIPMENTS ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shipments (
    id               VARCHAR(50) PRIMARY KEY,  -- S-YYYYMMDD-NNN
    tenant_id        UUID NOT NULL REFERENCES tenants(id),
    source_quote_id  VARCHAR(50) REFERENCES quotes(id),
    customer         VARCHAR(255),
    carrier          VARCHAR(50),
    routing          VARCHAR(255),
    container_type   VARCHAR(20),
    quantity         INTEGER DEFAULT 1,
    stage            VARCHAR(100) DEFAULT 'BOOKING_PENDING',
    service_type     VARCHAR(50) DEFAULT 'CY-CY',
    etd              DATE,
    eta              DATE,
    ata              DATE,
    selling_rate     REAL DEFAULT 0,
    buying_rate      REAL DEFAULT 0,
    profit           REAL DEFAULT 0,
    profit_margin    VARCHAR(20),
    delay_count      INTEGER DEFAULT 0,
    source           VARCHAR(50) DEFAULT 'email' CHECK (source IN ('quote', 'email', 'manual')),
    risks            JSONB DEFAULT '[]',
    all_containers   JSONB DEFAULT '{}',
    optional_charges JSONB DEFAULT '[]',
    last_subject     TEXT,
    last_sender      VARCHAR(255),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shipments_customer ON shipments(customer);
CREATE INDEX IF NOT EXISTS idx_shipments_stage ON shipments(stage);
CREATE INDEX IF NOT EXISTS idx_shipments_tenant ON shipments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_shipments_carrier ON shipments(carrier);
CREATE INDEX IF NOT EXISTS idx_shipments_created ON shipments(created_at DESC);

-- ── EVENTS (Event Sourcing) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    entity_type     VARCHAR(50) NOT NULL,  -- shipment, quote, rate, system
    entity_id       VARCHAR(100) NOT NULL,
    event_type      VARCHAR(100) NOT NULL,  -- stage_changed, status_changed, alert
    payload         JSONB NOT NULL DEFAULT '{}',
    source          VARCHAR(50) DEFAULT 'system',  -- email, api, bot, erp, system
    actor           VARCHAR(100) DEFAULT 'system',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_entity ON events(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_tenant ON events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC);

-- ── EMAIL MATCHES ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS email_matches (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    shipment_id     VARCHAR(50) REFERENCES shipments(id),
    email_hash      VARCHAR(64) UNIQUE,  -- SHA256 for dedup
    subject         TEXT,
    sender          VARCHAR(255),
    matched_by      VARCHAR(50),  -- hbl, bkg, customer_route
    extracted_ids   JSONB DEFAULT '{}',  -- {"hbl": [], "bkg": [], "container": []}
    detected_stages JSONB DEFAULT '[]',
    detected_risks  JSONB DEFAULT '[]',
    email_date      TIMESTAMPTZ,
    processed_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_em_shipment ON email_matches(shipment_id);
CREATE INDEX IF NOT EXISTS idx_em_hash ON email_matches(email_hash);
CREATE INDEX IF NOT EXISTS idx_em_tenant ON email_matches(tenant_id);

-- ── CUSTOMERS ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id          SERIAL PRIMARY KEY,
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    code        VARCHAR(50) NOT NULL,
    name        VARCHAR(255),
    ports       JSONB DEFAULT '[]',    -- ["Denver", "El Paso"]
    cargo_type  VARCHAR(255),
    notes       TEXT,
    tags        JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, code)
);
