---
name: Shipment Brain — Hybrid Parquet + Vault + Telegram Q&A
created: 2026-04-18
status: pending
blockedBy: []
blocks: []
related: [260416-email-nelson-solo-platform]
---

# Plan — Shipment Brain

**Created:** 2026-04-18
**Effort:** ~10 working days (3 weeks calendar) split across 4 phases
**End goal:** Sếp Telegram "Lô ACB của XYZ đến đâu?" → bot brief timeline đầy đủ trong 5s

## Context

Extension của `260416-email-nelson-solo-platform`. 2 brainstorm reports approved 2026-04-18:
- `../260416-email-nelson-solo-platform/reports/brainstorm-customer-sort-20260418.md`
- `../260416-email-nelson-solo-platform/reports/brainstorm-shipment-brain-20260418.md`

## Architecture (locked)

```
Outlook → Customer Sort (Phase 01) → DIRECT/FW/CNEE folders
    ↓
Parser + MiniMax LLM Extractor (Phase 02)
    ↓
DuckDB shipments/events + Markdown vault (dual-write)
    ↓
Retrieval API /api/shipment/brief (Phase 03)
    ↓
GoClaw Fox Spirit skill "shipment_brief" (Phase 04)
    ↓
Telegram 2-way Q&A
```

## Stack

| Layer | Tool | Source |
|-------|------|--------|
| Email parser | extract-msg | existing |
| Sort | outlook_scanner.py (new job) | existing infra |
| LLM | MiniMax 2.7 (4500 req/5h quota) | Sếp account |
| Structured | DuckDB | existing engine |
| Narrative | Markdown + Obsidian | new |
| Lifecycle events | rules.yaml 8 types (BKG→PAYMENT) | existing |
| Customers | customer_rules.json (8 khách) | existing |
| Retrieval | FastAPI endpoint | existing server |
| Telegram | GoClaw Fox Spirit skill | existing agent |

## Phases

| # | File | Effort | Status |
|---|------|--------|--------|
| 01 | [Nelson Customer Sort](phase-01-customer-sort.md) | 4-6h | pending |
| 02 | [Extractor + Dual Write](phase-02-extractor-dual-write.md) | 3-5 days | pending |
| 03 | [Retrieval API /brief](phase-03-retrieval-api.md) | 2-3 days | pending |
| 04 | [Fox Spirit Skill](phase-04-fox-spirit-skill.md) | 2 days | pending |

## Dependencies

Phase 01 ship → Phase 02 (folder cleanliness, customer_id FK ready)
Phase 02 ship → Phase 03 (DB + vault must exist before retrieval)
Phase 03 ship → Phase 04 (API endpoint must exist before Fox Spirit calls it)

## Success metrics (cumulative)

- **W1 end**: ≥90% email 8 khách tự vào folder đúng; false positive ≤1%
- **W2 end**: ≥95% email extract đúng event type (audit 50 email tay)
- **W3 end**: Telegram "Lô ABC của XYZ?" → brief <5s; accuracy ≥8/10 test queries

## Out of scope (defer)

- Second Brain vault for CNEE (28K) — chỉ 8 khách trước
- Click-tracking link wrap (Phase C #8e đã defer)
- Multi-language support cho extractor (chỉ English + Vietnamese)
- Web UI cho shipment search — Telegram-first

## References

- `email_engine/scanner/inbox_scanner.py` (APScheduler pattern)
- `email_engine/core/outlook_scanner.py` (job framework)
- `email_engine/config/rules.yaml` (event schema)
- `D:/OneDrive/NelsonData/email/customer_rules.json` (8 khách)
- `email_engine/core/process_reply.py` (.msg parser template)
