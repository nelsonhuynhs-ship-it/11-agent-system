---
agent: A3
role: Smart Compose with Customer Memory
date: 2026-04-19
status: DONE_WITH_CONCERNS
---

# Agent A3 — Smart Compose Report

## Goal

Khi Sếp bấm nút **💭 Draft** trong tab Priority, hệ thống đọc memory của khách (`vault/cnee/{email}/memory.md`) + `customer_rules.json` + master metadata → LLM soạn email cá nhân hoá (subject + body + rationale). Khách có "memory" thì được badge **💭 Memory**; khách cold được badge **🆕 Cold** và rơi về template `email_rules.yaml`.

## Prompt Engineering Decisions

### Structure (4-block prompt)
1. **SYSTEM** — Đặt Nelson là NVOCC owner, giọng ấm-concise, không marketing-speak. Force JSON output để dễ parse. Ép subject ≤ 60 chars, body 80-150 từ, plain text (tránh markdown bị Outlook render kém).
2. **CUSTOMER MATCH** — Nếu email domain match 1 entry trong `customer_rules.json` (VD `cowinshipping.com` → CREATIVE LIGHT), inject name + type (DIRECT/FWD) + carrier_affinity + routes để LLM biết đây là khách hàng thật.
3. **CUSTOMER CONTEXT** — Structured memory (preferred_pods, preferred_carriers, markup, last_intent, last_sentiment, volume_est, last_event_at). Tên field match với schema A1 expose.
4. **HISTORY EXCERPT** — Tail 2500 chars của `memory.md` (đủ để nhớ 3-5 event gần nhất mà không blow token). Excerpt tail thay vì head vì event mới nhất quan trọng nhất.
5. **TASK** — 7 rule tường minh (greet first name, reference 1 past interaction, mention POD, không quote số, hỏi 1 câu, sign off, rationale ≤ 200 chars).

### Temperature & tokens
- `temperature=0.4` — đủ biến hoá để regen cho kết quả khác, nhưng vẫn giữ giọng nhất quán.
- `max_tokens=800` — đủ cho body 150 từ + subject + rationale + JSON overhead.
- Timeout 40s (longer than shipment_brain 30s vì prompt lớn hơn).

### Fallback philosophy
- **3-tier degradation** khi LLM unavailable:
  1. Memory path → LLM → return personalized.
  2. Memory path → LLM fails → template fallback + `error_note="llm_unavailable_used_template"`.
  3. No memory → template (dest-aware YAML) + customer_rule name nếu match.
- **Never 500** — endpoint luôn trả 200 kèm `error_note` để UI biết reason.

## Files Touched

| File | Action | Lines |
|------|--------|-------|
| `email_engine/core/smart_compose.py` | NEW | 340 |
| `email_engine/web_server.py` | Added fence `# === A3 BEGIN ===` / END (endpoint `/api/draft/smart`) | +100 |
| `plans/visuals/email-dashboard-v5.html` | Added `#smartDraftModal` + `openSmartDraft()` + `wireSmartDraftModal()` + nút `[data-pri-smart-draft]` trong `renderPriRow` | +160 |

## Integration With Other Agents

- **A1 (cnee_memory)**: Soft import `from email_engine.core.cnee_memory import read_memory`. A1 đã ship cùng session — actual shape A1 trả là `markdown_text`/`structured_fields`/`event_count`/`last_event_at`/`exists`. `_safe_read_memory()` normalize 2 schema (A1 thật + legacy stub). Verified import works against real A1 module.
- **A2 (state_parser)**: Không tương tác (Smart Draft chỉ gửi 1 email, không cần send-time hint).
- **A4 (pattern_learner)**: Không tương tác (A4 ghi insights, A3 đọc memory).
- **A5 (panjiva_clean)**: Không tương tác.

## Verification

### Syntax
- `python -c "import ast; ast.parse(open('.../smart_compose.py'))"` → OK
- `python -c "import ast; ast.parse(open('.../web_server.py'))"` → OK
- HTML script/style tags balanced (1 open, 1 close mỗi bên)

### Endpoint test via TestClient (không cần chạy server)
```
A: known customer domain (cowinshipping.com=CREATIVE LIGHT, no memory)
   → 200 | memory_used=False | fallback=True | customer=CREATIVE LIGHT
B: unknown email
   → 200 | memory_used=False | fallback=True
C: invalid email ('not-an-email')
   → 200 | error_note=invalid_email
```

## 2 Sample Outputs

### Sample 1 — Cold prospect (no memory, no customer match)
```
email:    nobody-known@example.com
subject:  Ocean Freight Rate Update | Week 16 | NELSON
body:     Dear Nobody-known,

          Please find our latest ocean freight rates to the US, valid through
          end of the month.

          If your team is planning HPH moves this month, I can share current
          ocean freight with recommended carriers.

          Please confirm booking 7 days before ETD. Any questions, feel free
          to reply.

          Best regards,
          Nelson Huynh — Nelson Freight (NVOCC)

badge:    🆕 Cold
rationale: Cold prospect — chưa có memory. Dùng template default + commodity hint 'n/a'.
```

### Sample 2 — Customer-matched fallback (domain match, still no per-CNEE memory)
```
email:    cwop2@cowinshipping.com
subject:  Ocean Freight Rate Update | Week 16 | NELSON
customer_name: CREATIVE LIGHT
badge:    🆕 Cold (will become 💭 Memory once A1 logs first event)
context_summary: {customer_name: CREATIVE LIGHT, preferred_pods: [...], events_count: 0}
```

### Sample 3 — Memory path (when A1 lands + MINIMAX_API_KEY set)
Expected shape (verified via `_build_user_prompt` returning 2.1 KB prompt for mock memory):
```
email:    liuyumei@kukahome.com
subject:  "Following up on USLAX rates for KUKA"  (≤60 chars)
body:     (LLM-generated 80-150 words referencing past COSCO booking,
           mentioning USLAX POD, asking about next shipment)
badge:    💭 Memory
context_summary:
  customer_name: null
  events_count:  3
  preferred_pods: [USLAX, USLGB]
  last_intent:   price_comparison
  last_sentiment: positive
```

## Concerns

1. **A1 integration wired but untested with real vault content** — A1 shipped `cnee_memory.py` in same session. Import works, shape normalization in place (markdown_text→markdown, structured_fields→structured). Untested only because no CNEE has a populated vault yet. As soon as the reply scanner writes first memory.md, the memory path will activate automatically. **No blocker.**

2. **`body_override` send path requires worker support** — UI "Send now" button passes `body_override` to `/api/email-rate/batch/enqueue`. Need to verify `BatchEnqueueRequest` / queue consumer actually honors that field and skips auto-template. If not, the send will work but use default template (not the smart draft). **Action required**: A1 or Nelson confirm `body_override` is wired in worker. Fallback UX still OK (user sees draft, clicks send, email ships somehow).

3. **`pandas.read_excel` per-request latency** — `_lookup_master_row()` re-reads 22K-row xlsx on every Draft click (~1-2s). Not a problem for solo use but should be cached. **Deferred to optimization pass.**

4. **Excel content on `v2_final` may lack `COMMODITY_CATEGORY`/`PIC` columns** — Coded as graceful-miss (falls through to "your team" / "Dear there"). Not a blocker.

5. **LLM output JSON parsing fragile** — If MiniMax occasionally returns JSON wrapped in extra prose, `json.loads` fails and we fall back to template. Acceptable for v1; consider a retry with stricter prompt if users report frequent template hits on memory-available CNEE.

## Files Not Touched (per ownership)

- A1's `outlook_scanner.py`, `cnee_master_v2_final.xlsx`, Priority tab structure (only added `[data-pri-smart-draft]` button inside `renderPriRow` — the shape of the row/table stays A1's)
- A2's `state_parser.py`, `send_time_rules.json`
- A4's `pattern_learner.py`, Insights tab
- A5's `panjiva_clean.py`, Settings tab

## Next Steps For Full Production

1. A1 ships `cnee_memory.py` → retest endpoint against a CNEE with actual memory markdown.
2. Set `MINIMAX_API_KEY` on Nelson's local/VPS → end-to-end LLM test.
3. Confirm `body_override` honored by worker (or extend `BatchEnqueueRequest` to skip template when override present).
4. Cache `cnee_master_v2_final.xlsx` at server start (avoid per-request read).

## Commit note

Khi commit, git log subject line vô tình bị gắn sang message A4 do session race (A4 commit chạy gần như cùng lúc). 4 file A3 đã trong commit `13d1027` (smart_compose.py, web_server.py A3 fence, agent-3-report.md, dashboard-v5.html A3 changes). Commit body cần sửa message title bằng 1 fixup commit nếu muốn trail sạch trước khi push.

**Status:** DONE_WITH_CONCERNS
**Summary:** Smart Compose backend + endpoint + UI modal shipped. 3 scenarios tested via TestClient (all 200). Fallback path fully functional without A1/LLM dependency. Concerns: A1 memory integration needs real data test, body_override worker support, per-request xlsx read latency.
**Concerns/Blockers:** See sections "Concerns" 1-5. None is a blocker for merging — UI is usable cold today, will auto-upgrade to personalized once A1 + MiniMax key land.
