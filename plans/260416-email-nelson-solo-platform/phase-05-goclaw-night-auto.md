# Phase 05 — GoClaw Night Auto (NHANH đêm)

**Priority:** MEDIUM (depends on Phase 04)
**Status:** Pending approval
**Slogan map:** NHANH — khách hỏi đêm → GoClaw gen reply → queue → sáng Nelson duyệt/send

## Context

Nelson muốn:
- Khách hỏi giá buổi tối (sau 10pm) → GoClaw tự gen email phản hồi
- Reply nhận từ Phase 04 scanner → GoClaw gen draft reply
- Draft queued (không send auto) → Nelson review sáng

GoClaw hiện tại: v3.x trên VPS (Docker), có Telegram bot, có skill system. Đã có memory nhắc "GoClaw Standard v2.67.3 on Laptop VP" + "GoClaw VPS deploy" + "goclaw_reporter.py".

## Key Insights

- GoClaw KHÔNG gửi email trực tiếp (VPS không có Outlook). Nó chỉ **gen draft** rồi đẩy vào queue local (Phase 01 queue)
- Bridge VPS → local: GoClaw POST `http://laptop-ip:8100/api/drafts/enqueue` (cần Cloudflare Tunnel hoặc VPN — hoặc reverse: local poll GoClaw API)
- Simpler: GoClaw write draft to OneDrive → local scanner pulls → enqueue
- Hoặc: GoClaw generate → push vào GoClaw's own DB, local fetches via API

**Simplest: GoClaw tạo draft trên VPS DB → local poll `GET /api/goclaw/drafts/pending` mỗi 5 phút → import vào local queue as DRAFT status → Nelson review trong dashboard v4 → bấm APPROVE → worker send.**

## Requirements

**Functional:**
1. GoClaw skill `intel-auto-reply` — triggered by Phase 04 scanner REPLY event
2. GoClaw skill input: `{cnee_email, reply_body, sentiment, topic, reply_subject}`
3. GoClaw skill output: draft email `{to, subject, html_body, reasoning}` saved to PG
4. Local web_server.py `GET /api/drafts/pending` — poll VPS GoClaw API
5. Queue store: new status `DRAFT` (not yet approved)
6. Dashboard v4: Drafts panel with Approve/Reject/Edit buttons
7. Approve → status changes to `pending` → worker picks up
8. Reject → status = `rejected_draft`, intel log event

**Night auto flow:**
```
Scanner detects REPLY from john@abc.com (topic=PRICE, sentiment=POSITIVE)
  ↓ trigger
GoClaw skill intel-auto-reply:
  1. profile = intel.get_profile(john)
  2. lanes = extract from reply body (if mentioned) OR profile.typical
  3. rates = query market data (via existing rate API)
  4. template = template_selector.match(lanes, states)
  5. body = template_renderer.render(template, {profile, lanes, reply_context})
  6. draft = {to: john, subject: "Re: {original}", html_body: body, reasoning: "..."}
  7. save_to_db(draft) with status=DRAFT
  ↓
Local poll fetches draft every 5 min
  ↓
Dashboard v4 shows: "🌙 2 drafts from GoClaw overnight — review"
  ↓ Nelson approve morning
  ↓
Queue status=pending → worker sends → normal flow
```

**Non-functional:**
- GoClaw skill runs < 30 seconds per draft
- Poll cycle 5 min
- Max drafts per CNEE per night: 1 (don't flood)

## Architecture

```
VPS GoClaw
┌────────────────────────────────────────┐
│ skill: intel-auto-reply                 │
│                                          │
│ input: {cnee, reply, sentiment, topic}  │
│                                          │
│ 1. Fetch profile from intel API         │
│ 2. Query rates /api/rates (VPS)         │
│ 3. Render template (reuse YAML rules)   │
│ 4. Save to PG drafts table              │
│ 5. Telegram: "Draft ready for review"   │
└────────────────────────────────────────┘
      │
      │ stored in drafts table
      ▼
┌────────────────────────────────────────┐
│ GET /api/goclaw/drafts/pending          │
│ returns: [{id, to, subject, body,      │
│   reasoning, created_at, ...}]          │
└────────────────────────────────────────┘
      ▲
      │ polled every 5 min
      │
Local (laptop)
┌────────────────────────────────────────┐
│ drafts_fetcher.py (local)               │
│                                          │
│ every 5 min:                             │
│   drafts = GET /api/goclaw/drafts/pending│
│   for d in drafts:                       │
│     queue.enqueue_draft(d)               │
│     GoClaw mark_fetched(d.id)            │
└────────────────────────────────────────┘
      │
      ▼
┌────────────────────────────────────────┐
│ SQLite queue with status=DRAFT          │
│                                          │
│ Dashboard v4: Drafts panel               │
│   Show: to, subject, body preview, why  │
│   Actions: [Approve] [Edit] [Reject]    │
└────────────────────────────────────────┘
```

### Drafts Table (GoClaw PG)

```sql
CREATE TABLE email_drafts (
  id UUID PRIMARY KEY,
  cnee_email TEXT NOT NULL,
  reply_to_message_id TEXT,
  subject TEXT,
  html_body TEXT,
  reasoning TEXT,
  market_state TEXT,
  confidence FLOAT,
  created_at TIMESTAMP DEFAULT NOW(),
  fetched_at TIMESTAMP,
  fetched_by TEXT
);
```

### Reply-Trigger Bridge

Scanner in Phase 04 detects REPLY → how does it trigger GoClaw skill?

**Option A (simple):** Scanner writes reply event to local intel DB. GoClaw polls intel API (new endpoint `/api/intel/pending-replies`) every 2 min, processes, marks done.

**Option B (realtime):** Scanner POSTs to GoClaw webhook directly.

→ Pick Option A (decoupled, more reliable).

## Related Code Files

**Create (VPS GoClaw):**
- `goclaw/skills/intel-auto-reply/SKILL.md`
- `goclaw/skills/intel-auto-reply/handler.py` — main logic
- PG migration: `email_drafts` table

**Create (Local):**
- `email_engine/drafts_fetcher.py` — poll + import
- `email_engine/scanner/goclaw_trigger.py` — post reply event

**Modify:**
- Phase 04 scanner `handle_reply()` — call `goclaw_trigger.notify()`
- Phase 01 queue_store — support status=DRAFT
- Phase 06 dashboard v4 — Drafts panel

**Extend:**
- GoClaw API: `GET /api/intel/pending-replies`, `GET /api/goclaw/drafts/pending`, `POST /api/goclaw/drafts/{id}/mark-fetched`

## Implementation Steps

1. **Drafts schema** — migration on GoClaw PG
2. **GoClaw skill `intel-auto-reply`:**
   - Load profile + rates + template
   - Gen draft with reasoning
   - Save to DB
3. **Reply trigger API:**
   - Local scanner POST `/api/intel/reply-event` with payload
   - GoClaw listener enqueues skill invocation
4. **Local fetcher:**
   - Poll `/api/goclaw/drafts/pending` every 5 min
   - For each draft: queue_store.enqueue_draft (status=DRAFT)
   - Mark fetched on GoClaw side
5. **Dashboard v4 Drafts Panel:**
   - List pending drafts with preview
   - Approve → PATCH queue status=pending
   - Edit → open modal, edit HTML, save, approve
   - Reject → status=rejected_draft + log

## Todo List

- [ ] PG migration `email_drafts` table (VPS)
- [ ] GoClaw skill scaffold + handler
- [ ] Reply event API endpoint (VPS)
- [ ] Local scanner → post reply event (Phase 04 integration)
- [ ] Drafts fetcher script (local cron or embedded)
- [ ] queue_store support DRAFT status (Phase 01 extend)
- [ ] Dashboard v4 Drafts panel UI
- [ ] Approve/Edit/Reject actions wired
- [ ] Intel event log: `GOCLAW_DRAFTED`, `DRAFT_APPROVED`, `DRAFT_REJECTED`
- [ ] Test: Manually trigger reply event → verify draft appears in dashboard

## Success Criteria

- Khách reply đêm → sáng Nelson thấy draft pre-gen trong dashboard
- Draft quality: intro đúng tone (positive/negative), lane đúng, rate fresh
- Reasoning field explains tại sao GoClaw chọn template đó
- Approve 1 click → worker send trong 30s
- Reject → log, không send
- Daily drafts count < 20 (không bị spam)

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| GoClaw gen reply dở (tone sai) | Nelson always reviews, never auto-send |
| Rate data VPS lag vs Parquet local | Daily rclone sync ensures <12h freshness |
| Trigger flood (1 reply → N drafts) | Rate limit 1 draft per CNEE per night |
| Bridge VPS↔local fragile | Fallback: OneDrive sync drafts (sync lag ok đêm) |
| Cost: Claude API for smart gen | Cap tokens per draft + use only for POSITIVE sentiment first |

## Security Considerations

- Drafts not sent until Nelson approves
- Reply body transmitted VPS → storage in PG (local) → review only by Nelson
- Redact PII from logs

## Next Steps

Phase 05 + Phase 04 + Phase 02 form complete "intelligent reply loop". Phase 06 brings it all to dashboard.
