# Phase 03 — Retrieval API `/api/shipment/brief`

**Effort:** 2-3 days
**Priority:** HIGH
**Status:** pending (blocked by Phase 02)

## Context Links

- Brainstorm: `../260416-email-nelson-solo-platform/reports/brainstorm-shipment-brain-20260418.md`
- DB schema: Phase 02 DuckDB `shipments` + `shipment_events`
- Vault path: `vault/customers/{customer_id}/{shipment_ref}.md`

## Overview

FastAPI endpoint nhận query text → trích xuất shipment_ref + customer từ query → SQL filter DB events → đọc matching vault file → MiniMax synthesize brief → return markdown response.

Endpoint sẽ được gọi bởi Phase 04 GoClaw Fox Spirit skill.

## Key Insights

- Query pattern từ Sếp: "Lô ACB của XYZ đến đâu?" — 90% câu hỏi chỉ cần SQL lookup + timeline
- Cache hit rate cao: cùng shipment hỏi nhiều lần trong session → Redis không cần, Python dict TTL 60s đủ
- LLM synthesize phải GIỮ event ordering (BKG→ATD→INVOICE) — prompt cần hint explicit

## Requirements

### Functional
- F1: Endpoint `POST /api/shipment/brief` với body `{query: str}`
- F2: Parse query → extract candidate shipment_ref (regex) + customer hint (keyword match)
- F3: SQL filter: `SELECT * FROM shipments JOIN shipment_events WHERE shipment_id LIKE ... AND customer_id LIKE ...`
- F4: Nếu 0 match → return `{"status": "not_found", "suggestions": [top 3 closest]}`
- F5: Nếu 1 match → read vault file + LLM synthesize → return markdown
- F6: Nếu N>1 match → return list shipments, no brief
- F7: 60s in-memory cache for identical queries
- F8: Support alternate endpoint `GET /api/shipment/{shipment_ref}` for direct lookup

### Non-functional
- N1: Response time p95 ≤5s (SQL 10ms + vault read 50ms + LLM 3-4s)
- N2: Concurrent 5 requests (FastAPI async)
- N3: Token usage: 1 request = 1 MiniMax call max
- N4: Graceful degradation: LLM down → return raw event list

## Architecture

```
POST /api/shipment/brief
   │
   ▼
parse_query(text)
   ├── shipment_ref regex: \b[A-Z]{2,6}\d{6,10}\b
   ├── customer hint: keyword match vs customer_rules.json
   └── returns {ref: "ACB2604", customer: "XYZ"} or {} if ambiguous
   │
   ▼
sql_lookup(ref, customer)
   ├── exact match by shipment_id → 1 row
   ├── fuzzy LIKE '%ref%' AND customer LIKE '%cust%' → N rows
   └── returns list of (shipment, events[])
   │
   ▼
if len == 1:
    read vault/customers/{customer_id}/{ref}.md (last 2000 chars)
    llm_synthesize(events, vault_text) → markdown brief
else if len > 1:
    return list summary
else:
    suggest fuzzy match top 3
```

## Related Code Files

### Create
- `email_engine/api/shipment_brief.py` — FastAPI router
- `email_engine/core/query_parser.py` — regex + keyword extractor
- `email_engine/core/brief_synthesizer.py` — LLM prompt for brief

### Modify
- `email_engine/web_server.py` — mount shipment_brief router
- `email_engine/core/llm_client.py` (Phase 02) — add method `synthesize_brief()`

## Implementation Steps

### Day 1 — Parser + SQL layer
```python
# query_parser.py
SHIPMENT_REF_RE = re.compile(r"\b[A-Z]{2,6}\d{6,10}\b", re.I)

def parse_query(text: str) -> dict:
    refs = SHIPMENT_REF_RE.findall(text.upper())
    customer = None
    for cid in load_customer_rules()["customers"].keys():
        if cid.lower() in text.lower():
            customer = cid
            break
    return {"ref": refs[0] if refs else None, "customer": customer}
```

```python
# shipment_brief.py
@router.post("/api/shipment/brief")
async def get_brief(req: BriefRequest):
    parsed = parse_query(req.query)
    if not parsed["ref"] and not parsed["customer"]:
        raise HTTPException(400, "Cannot extract shipment ref or customer from query")

    shipments = sql_lookup(parsed["ref"], parsed["customer"])
    if not shipments:
        return {"status": "not_found", "suggestions": fuzzy_suggest(req.query)}
    if len(shipments) > 1:
        return {"status": "multiple", "shipments": shipments[:10]}

    vault_text = read_vault(shipments[0])
    brief_md = await brief_synthesizer.synthesize(shipments[0], vault_text)
    return {"status": "ok", "brief": brief_md}
```

### Day 2 — LLM brief synthesizer
Prompt template:
```
System: Bạn là trợ lý freight forwarder. Given shipment events + vault context,
produce concise Telegram brief in Vietnamese.

Format:
📦 {shipment_ref} · {customer} · {pol}→{pod} · {carrier}
[For each event in chronological order:]
{emoji} {event_type} · ({date} — 1 line excerpt)
[If any risk_flag=true events, add:]
⚠ RISK: {risk details}
[Last line:]
💬 Last: "{latest excerpt}" ({date})

Keep total ≤15 lines, use emojis: ✅ (completed), 🟡 (in progress), ⏳ (pending), ⚠ (risk).
```

### Day 3 — Cache + test
- Python LRU cache với TTL 60s
- Test 10 sample queries:
  - "Lô ACB của PANDA đến đâu?"
  - "Status shipment EBKG2604"
  - "SIRI có vướng gì không?"
- Measure p95 latency
- Unit test parser edge cases

## Todo List

- [ ] query_parser.py regex + customer hint
- [ ] shipment_brief.py FastAPI router
- [ ] sql_lookup() DuckDB query
- [ ] fuzzy_suggest() using rapidfuzz
- [ ] read_vault() last 2000 chars
- [ ] brief_synthesizer.py LLM prompt + call
- [ ] LRU cache 60s
- [ ] Mount router in web_server.py
- [ ] Unit test parser
- [ ] Integration test with 10 real queries
- [ ] Latency benchmark
- [ ] Add endpoint to OpenAPI docs

## Success Criteria

- ✅ 10/10 sample queries return correct shipment (accuracy)
- ✅ p95 latency ≤5s
- ✅ Cache hit rate ≥60% for repeated queries
- ✅ Markdown brief render đẹp trên Telegram preview
- ✅ Graceful 404 with suggestions khi not found

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Regex miss shipment ref format mới | MED | MED | Collect misses in log, iterate |
| LLM brief hallucinates status | LOW | HIGH | Prompt constraint "only use provided events" |
| Multiple shipment match ambiguous | HIGH | LOW | Return top 3 for user to pick |
| MiniMax rate limit hit during Q&A | LOW | MED | Cache + fallback to raw event list |

## Security Considerations

- API currently localhost:8100 only — NOT exposed externally
- Phase 04 Fox Spirit calls localhost → safe
- Input sanitization: query field bounded 500 chars, SQL uses parameterized queries

## Next Steps

Phase 03 ship → Phase 04 Fox Spirit có endpoint ready để call.

**Status:** detailed enough to code after Phase 02 ships
