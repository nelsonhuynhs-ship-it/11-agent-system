-- ============================================================================
-- 002_views_triggers.sql — Event Sourcing Views + Triggers
-- ============================================================================

-- ── View: Current Shipment Stage (derived from events) ───────────────────────
CREATE OR REPLACE VIEW shipment_current_stage AS
SELECT DISTINCT ON (entity_id)
    entity_id AS shipment_id,
    (payload->>'to_stage') AS current_stage,
    created_at AS stage_since,
    source
FROM events
WHERE entity_type = 'shipment'
  AND event_type = 'stage_changed'
  AND (payload->>'to_stage') NOT IN ('DELAY_NOTICE', 'CHANGE_VESSEL')
ORDER BY entity_id, created_at DESC;

-- ── View: Quote Summary ──────────────────────────────────────────────────────
CREATE OR REPLACE VIEW quote_summary AS
SELECT
    q.id,
    q.customer,
    q.pol,
    q.pod,
    q.place,
    q.status,
    q.global_markup,
    q.version,
    q.created_at,
    q.updated_at,
    q.converted_shipment_id,
    COUNT(qc.id) AS carrier_count,
    MIN((qc.container_rates->>'20GP')::float) AS min_20gp,
    MIN((qc.container_rates->>'40HQ')::float) AS min_40hq
FROM quotes q
LEFT JOIN quote_carriers qc ON qc.quote_id = q.id
GROUP BY q.id;

-- ── View: Shipment Dashboard ─────────────────────────────────────────────────
CREATE OR REPLACE VIEW shipment_dashboard AS
SELECT
    s.id,
    s.customer,
    s.carrier,
    s.routing,
    s.stage,
    s.etd,
    s.eta,
    s.ata,
    s.selling_rate,
    s.buying_rate,
    s.profit,
    s.delay_count,
    s.source,
    s.created_at,
    s.updated_at,
    (SELECT COUNT(*) FROM events e WHERE e.entity_id = s.id) AS event_count,
    (SELECT COUNT(*) FROM email_matches em WHERE em.shipment_id = s.id) AS email_count
FROM shipments s;

-- ── Trigger: Auto-update shipment stage from events ──────────────────────────
CREATE OR REPLACE FUNCTION update_shipment_stage()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.entity_type = 'shipment' AND NEW.event_type = 'stage_changed' THEN
        UPDATE shipments
        SET stage = NEW.payload->>'to_stage',
            updated_at = NEW.created_at,
            delay_count = CASE
                WHEN NEW.payload->>'to_stage' = 'DELAY_NOTICE'
                THEN COALESCE(delay_count, 0) + 1
                ELSE delay_count
            END
        WHERE id = NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_shipment_stage ON events;
CREATE TRIGGER trg_shipment_stage
    AFTER INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION update_shipment_stage();

-- ── Trigger: Auto-update quote status from events ────────────────────────────
CREATE OR REPLACE FUNCTION update_quote_status()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.entity_type = 'quote' AND NEW.event_type = 'status_changed' THEN
        UPDATE quotes
        SET status = NEW.payload->>'to_status',
            updated_at = NEW.created_at
        WHERE id = NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_quote_status ON events;
CREATE TRIGGER trg_quote_status
    AFTER INSERT ON events
    FOR EACH ROW
    EXECUTE FUNCTION update_quote_status();

-- ── Trigger: updated_at auto-touch ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_quotes_updated ON quotes;
CREATE TRIGGER trg_quotes_updated
    BEFORE UPDATE ON quotes
    FOR EACH ROW
    EXECUTE FUNCTION touch_updated_at();

DROP TRIGGER IF EXISTS trg_shipments_updated ON shipments;
CREATE TRIGGER trg_shipments_updated
    BEFORE UPDATE ON shipments
    FOR EACH ROW
    EXECUTE FUNCTION touch_updated_at();
