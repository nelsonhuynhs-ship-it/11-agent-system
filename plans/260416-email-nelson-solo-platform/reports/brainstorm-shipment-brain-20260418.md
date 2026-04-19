# Brainstorm — Shipment Brain (Hybrid Parquet + Vault + Telegram Q&A)

**Date:** 2026-04-18
**Status:** Design approved, architecture C chosen — ready for `/ck:plan`
**Prerequisite:** Nelson Customer Sort (ship first, Week 1)
**End goal:** Telegram "Lô ACB của XYZ đến đâu?" → full timeline brief

---

## 1. End-picture

Sếp hỏi Telegram → bot trả về brief đầy đủ 1 lô hàng:

```
📦 ACB2604-0015 · XYZ Co. · HPH→USLAX · HPL SCFI
✅ BKG_ISSUED   (4/10 20:15 — OPS confirmed)
✅ DRAFT_BL     (4/13 09:30 — awaiting signer)
✅ ATD          (4/15 22:00 — vessel departed)
🟡 DN_SENT      (4/17 — waiting invoice)
⏳ INVOICE      (pending)
⚠ RISK: packing list chưa release (4/15)
💬 Last: "please wait till Monday" (4/17 11:20)
```

---

## 2. Architecture C — Hybrid (LOCKED)

```
Outlook .msg
    ↓ extract-msg parser
[Email JSON]
    ↓ MiniMax 2.7 LLM extractor (rules.yaml 8 event types)
    ↓ dual write
┌────────────────────┬─────────────────────────┐
│                    │                         │
[DuckDB shipments]   [Markdown vault]
  • events table     vault/{customer}/{ref}.md
  • structured fact    • timeline narrative
  • fast SQL filter    • [[link]] carrier/POD
│                    │                         │
└────────┬───────────┴─────────────────────────┘
         ↓
  [Retrieval API /api/shipment/brief]
    1. SQL: WHERE ref LIKE '%ACB%' AND customer LIKE '%XYZ%'
    2. Read matching vault file (last 2000 chars)
    3. MiniMax synthesize → markdown brief
         ↓
  [GoClaw Fox Spirit + skill "shipment_brief"]
    Sếp Telegram → Fox Spirit → call API → reply
```

---

## 3. Stack locked

| Layer | Tool | Note |
|-------|------|------|
| Email parser | `extract-msg` | Đã có trong repo |
| LLM extractor + brief | **MiniMax 2.7** | Sếp quota 4500 req/5h = dư cho 100-500 email/đêm |
| Structured DB | **DuckDB** | Tái dùng engine rates |
| Vault | Markdown + Obsidian Desktop | Human-editable + graph view |
| Schema events | `rules.yaml` 8 lifecycle | BKG→DRAFT_BL→ATD→DN→INVOICE→PAYMENT→COMPLETED |
| Retrieval | Thuần Python (SQL + grep + LLM) | Không cần LlamaIndex overhead |
| Telegram | **GoClaw Fox Spirit skill** | Tích hợp agent có sẵn, không kill GoClaw |

---

## 4. Schema DuckDB

### Table `shipments`
| field | type | example |
|-------|------|---------|
| shipment_id | TEXT PK | "ACB2604-0015" |
| customer | TEXT | "XYZ Co." |
| customer_id | TEXT | "XYZ" (FK to customer_rules) |
| carrier | TEXT | "HPL" |
| pol | TEXT | "HPH" |
| pod | TEXT | "USLAX" |
| svc_type | TEXT | "SCFI" |
| created_at, updated_at | TIMESTAMP | |

### Table `shipment_events`
| field | type | example |
|-------|------|---------|
| id | INTEGER PK | |
| shipment_id | FK | "ACB2604-0015" |
| event_type | TEXT | "ATD", "DN_SENT" (từ rules.yaml) |
| event_date | TIMESTAMP | "2026-04-15 22:00" |
| source_msg | TEXT | path tới .msg file |
| raw_excerpt | TEXT | 200 chars |
| confidence | REAL | 0.0-1.0 |
| flagged_risk | BOOL | true nếu detect risk keyword |

### Vault structure
```
vault/
  customers/
    XYZ/
      _index.md              # all shipments of XYZ
      ACB2604-0015.md        # per-shipment timeline
      ACB2604-0016.md
  carriers/
    HPL.md                   # aggregate view carrier HPL
  lanes/
    HPH-USLAX.md
```

---

## 5. Fox Spirit skill "shipment_brief"

```yaml
# GoClaw skill file
name: shipment_brief
description: Brief lô hàng khi user hỏi về shipment reference + customer
trigger_patterns:
  - "lô.*của"
  - "shipment.*status"
  - "đến đâu rồi"
action:
  type: http_call
  url: http://laptop-vp:8100/api/shipment/brief
  params:
    query: "{user_message}"
  response_format: markdown
```

Fox Spirit nhận message → detect pattern "lô... của..." → call API `/brief` → forward response về Telegram.

---

## 6. Implementation phases (ước lượng 10 ngày chia 3 phase)

### Phase 1 — Extractor + Dual Write (3-5 ngày)
- Parser .msg → JSON (reuse process_reply.py)
- LLM extractor với prompt template (8 event types)
- Write DuckDB + markdown vault dual
- Idempotent (re-run không double insert)

### Phase 2 — Retrieval API (2-3 ngày)
- `POST /api/shipment/brief` endpoint
- SQL filter + vault read + LLM synthesize
- Response markdown ready for Telegram formatting
- Cache 60s cho query lặp

### Phase 3 — Fox Spirit Integration (2 ngày)
- Skill YAML + action definition
- Test 10 Telegram query thật
- Morning brief 7:00 auto (top 5 active shipments)

---

## 7. Integration với Customer Sort (ship trước)

**Customer Sort (Week 1, 4-6h)** tạo folder structure sạch:
```
DIRECT/Nafood/, DIRECT/VINARES/, FW/PANDA/, ...
```

**Shipment Brain (Week 2-3)** scan các folder đó:
- Loop qua sub-folders customer
- Extract events từ email mỗi customer
- Populate DB + vault

**Lợi ích khi có Customer Sort trước:**
- Shipment Brain scan có target rõ ràng (skip noise, spam)
- Customer đã classify → customer_id sẵn sàng cho FK
- Folder name = customer name → giảm ambiguity

---

## 8. Success metrics

| Milestone | Target |
|-----------|--------|
| Phase 1 end | ≥95% email từ 8 khách extract đúng event type (audit 50 email tay) |
| Phase 2 end | API trả brief <5s cho 90% query |
| Phase 3 end | Fox Spirit trả lời chính xác ≥8/10 query Telegram test |

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| MiniMax extract sai event type | Fallback rule-based (regex rules.yaml patterns) |
| Vault + DB drift (dual write inconsistency) | Transaction wrapper, markdown vault as single-write source, DB = derived |
| GoClaw Fox Spirit không gọi được API localhost | Nelson VPS tunnel hoặc cloudflared expose API |
| Customer name fuzzy match sai (VD "XYZ" vs "XYZ Co.") | rapidfuzz token_set_ratio >85 threshold |

---

## 10. Decisions locked

| Item | Choice |
|------|--------|
| Architecture | **C. Hybrid** (Parquet + Vault + LLM) |
| Telegram | **GoClaw Fox Spirit** skill (không kill) |
| LLM | **MiniMax 2.7** (quota 4500/5h sẵn) |
| Prerequisite | Nelson Customer Sort ship trước |
| Order triển khai | Customer Sort → Shipment Brain P1 → P2 → P3 |

---

## Next step

→ `/ck:plan --auto` break toàn bộ 4 phase (Customer Sort + Shipment Brain P1/P2/P3) thành detail phase files.

Hoặc: ship Customer Sort tối nay, brainstorm Shipment Brain tiếp tuần sau khi folder đã sạch.

---

**Status:** DONE
**Summary:** Hybrid architecture approved. MiniMax + DuckDB + vault + GoClaw skill. 10 ngày chia 3 phase sau Customer Sort. Target: Telegram "Lô ACB XYZ?" → brief 5s.
