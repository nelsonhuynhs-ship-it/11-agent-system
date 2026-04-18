# Phase 02 — Shipment Brain Extractor + Dual Write

**Effort:** 3-5 days
**Priority:** HIGH
**Status:** pending (blocked by Phase 01)

## Context Links

- Brainstorm: `../260416-email-nelson-solo-platform/reports/brainstorm-shipment-brain-20260418.md`
- Event schema: `email_engine/config/rules.yaml` (8 lifecycle types)
- Existing parser: `email_engine/core/process_reply.py`

## Overview

Đọc email đã sorted vào `DIRECT/{name}/` và `FW/{name}/` folders. Parse bằng extract-msg → gọi MiniMax 2.7 extract structured events → dual-write vào DuckDB (structured facts) + Markdown vault (narrative).

Dual-write pattern: Markdown vault = source of truth (human readable), DuckDB = derived index cho fast SQL.

## Key Insights

- `rules.yaml` đã định nghĩa 8 event types: `BKG_ISSUED`, `DRAFT_BL_ISSUED`, `DRAFT_BL_CONFIRMED`, `LOADED`, `ATD`, `DN_SENT`, `INVOICE_ISSUED`, `PAYMENT_REQUESTED`, `PAYMENT_CONFIRMED`, `COMPLETED` — prompt LLM dùng enum này, không hallucination
- MiniMax quota 4500 req/5h = đủ cho 500 email/đêm (1 email = 1 call)
- `process_reply.py` đã có pattern đọc .msg + extract metadata — reuse 70%
- Shipment reference format: `{CARRIER_HBL_PREFIX}{6-8 digits}` — dùng regex từ rules.yaml

## Requirements

### Functional
- F1: Scan folders `DIRECT/*/` và `FW/*/` (not recursive deeper)
- F2: Parse each .msg → email JSON (sender, recipients, subject, body, attachments list, date)
- F3: Call MiniMax 2.7 với prompt template → extract `{shipment_ref, event_type, event_date, confidence, risk_flag, excerpt}`
- F4: Resolve `customer_id` từ folder name (FW/PANDA/ → customer_id=PANDA)
- F5: Write to DuckDB `shipment_events` table (upsert by shipment_ref+event_type)
- F6: Append to vault `vault/customers/{customer_id}/{shipment_ref}.md` (markdown timeline block)
- F7: Skip if already processed (dedup by email entry_id + category "Nelson-Scanned")
- F8: Batch mode — process all emails in folder, commit every 10

### Non-functional
- N1: Idempotent — reprocess same email = no duplicate DB row, no duplicate markdown block
- N2: Graceful LLM failure — retry 3x với exponential backoff, rồi skip log error
- N3: Processing speed: ≥100 emails/hour (LLM latency ~2-3s each)
- N4: Token usage log: track req count vs MiniMax 4500/5h quota

## Architecture

```
email_engine/core/shipment_extractor.py
    ├── scan_customer_folders()        # yields (customer_id, msg_path)
    ├── parse_msg(path) -> dict         # extract-msg
    ├── llm_extract(email) -> events[]  # MiniMax 2.7
    ├── write_db(events)                # DuckDB upsert
    ├── write_vault(events, narrative)  # markdown append
    └── main() -> run all
```

### DuckDB Schema
```sql
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id     TEXT PRIMARY KEY,
    customer_id     TEXT NOT NULL,
    customer_name   TEXT,
    carrier         TEXT,
    pol             TEXT,
    pod             TEXT,
    svc_type        TEXT,  -- SCFI, FAK, FIX
    first_seen_at   TIMESTAMP,
    last_updated    TIMESTAMP,
    status          TEXT   -- derived from latest event
);

CREATE TABLE IF NOT EXISTS shipment_events (
    id              INTEGER PRIMARY KEY,
    shipment_id     TEXT NOT NULL,
    event_type      TEXT NOT NULL,  -- enum from rules.yaml
    event_date      TIMESTAMP,
    source_msg_id   TEXT,           -- Outlook entry_id (for dedup)
    source_path     TEXT,           -- .msg file path
    raw_excerpt     TEXT,           -- 200 chars
    confidence      REAL,           -- 0.0-1.0
    flagged_risk    BOOL DEFAULT 0,
    extracted_at    TIMESTAMP,
    UNIQUE(shipment_id, event_type, source_msg_id),
    FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id)
);

CREATE INDEX idx_events_shipment ON shipment_events(shipment_id);
CREATE INDEX idx_events_customer ON shipment_events(shipment_id);
```

### Vault structure
```
vault/
  customers/
    PANDA/
      _index.md                      # auto-gen: list all shipments
      ACB2604-0015.md                # per-shipment timeline
      ACB2604-0016.md
    Nafood/
      _index.md
      EBKG2604-0003.md
  carriers/
    HPL.md                           # aggregate view
  lanes/
    HPH-USLAX.md
```

### Per-shipment markdown template
```markdown
# {shipment_ref} · {customer_name}

**Lane:** {pol} → {pod} · **Carrier:** {carrier} · **Svc:** {svc_type}
**First seen:** {first_seen} · **Last update:** {last_updated}

## Timeline

### {event_date} · {event_type} {emoji}
> {raw_excerpt}

*Source: [{msg_filename}]({relative_path})*

---
```

### LLM Prompt (MiniMax 2.7)
```
System: You extract shipment lifecycle events from freight forwarder emails.

Output valid JSON only:
{
  "shipment_ref": "string (format: CARRIER_PREFIX + 6-8 digits, e.g. ACB26040015)",
  "event_type": "enum: BKG_ISSUED|DRAFT_BL_ISSUED|DRAFT_BL_CONFIRMED|LOADED|ATD|DN_SENT|INVOICE_ISSUED|PAYMENT_REQUESTED|PAYMENT_CONFIRMED|COMPLETED",
  "event_date": "ISO 8601 datetime or null",
  "confidence": 0.0-1.0,
  "risk_flag": bool (true if keywords: delay, problem, complaint, urgent),
  "excerpt": "string (max 200 chars verbatim from email body)"
}

If no shipment event detected, output {"shipment_ref": null}.

User: [email subject + body here]
```

## Related Code Files

### Create
- `email_engine/core/shipment_extractor.py` — main
- `email_engine/core/vault_writer.py` — markdown write/append
- `email_engine/core/llm_client.py` — MiniMax HTTP wrapper

### Modify
- `email_engine/core/outlook_scanner.py` — add job `shipment_extract`
- `email_engine/config/scan_config.json` — config block

### Read (reference)
- `email_engine/core/process_reply.py` — .msg parsing pattern
- `email_engine/config/rules.yaml` — event enum
- `email_engine/db/duckdb_engine.py` — connection helper

## Implementation Steps

### Day 1 — Schema + parser
1. Create DuckDB schema file, run init
2. Build `parse_msg(path)` reusing process_reply.py helpers
3. Unit test với 5 .msg file mẫu

### Day 2 — LLM client
1. Write `llm_client.py` MiniMax HTTP wrapper (env var MINIMAX_API_KEY)
2. Prompt template as constant
3. Retry + token counter
4. Mock test với 3 emails

### Day 3 — Dual writer
1. `write_db(event)` — upsert logic với UNIQUE constraint
2. `write_vault(event, narrative)` — append block to markdown, create file if not exist
3. `_index.md` regeneration cho customer folder
4. Test idempotency (re-run same email = zero duplicate)

### Day 4 — Main loop + integration
1. `scan_customer_folders()` generator
2. Main orchestrator với progress bar
3. Wire vô `outlook_scanner.py` as job `shipment_extract`
4. Dry-run mode

### Day 5 — Testing + observability
1. Run full extraction trên toàn bộ PANDA folder (biggest sample)
2. Manual audit 50 events — accuracy target ≥95%
3. Token usage report
4. Fix prompt template if event_type wrong >5%

## Todo List

- [ ] Init DuckDB schema (2 tables)
- [ ] Build parse_msg() — reuse process_reply.py logic
- [ ] Build llm_client.py — MiniMax wrapper + retry
- [ ] Define LLM prompt template constant
- [ ] Build write_db() with UPSERT
- [ ] Build write_vault() with idempotent append
- [ ] Generate _index.md per customer
- [ ] Main orchestrator + progress log
- [ ] Wire job vào outlook_scanner.py
- [ ] Dry-run test 20 emails
- [ ] Full extraction PANDA folder
- [ ] Audit 50 events for accuracy
- [ ] Token usage dashboard (MiniMax quota monitor)

## Success Criteria

- ✅ ≥95% email PANDA extract đúng event type (50-sample audit)
- ✅ 0 duplicate rows sau 3 reruns
- ✅ Vault markdown render OK trong Obsidian
- ✅ Token usage ≤1000 req per full run (7 customers × ~100 emails)
- ✅ Extraction speed ≥100 emails/hour

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MiniMax extract wrong event_type | MED | MED | Fallback: regex rules.yaml patterns khi confidence <0.7 |
| Shipment ref regex miss edge cases | HIGH | MED | Collect misses, iterate prompt |
| Vault dual-write drift with DB | MED | HIGH | Vault = single-write source, DB rebuild script |
| Token quota exceeded | LOW | MED | Log + alert at 80%; slow-down mode |
| .msg file locked by Outlook | MED | LOW | Try/except, retry after 5s |

## Security Considerations

- MINIMAX_API_KEY in .env (not committed)
- PII in emails → vault stored locally only (no VPS sync tới Week 4)
- LLM provider ToS: MiniMax allows business data processing

## Next Steps

Phase 02 ship → Phase 03 can query DB + read vault → synthesize brief.

**Status:** detailed enough to code after Phase 01 ships
