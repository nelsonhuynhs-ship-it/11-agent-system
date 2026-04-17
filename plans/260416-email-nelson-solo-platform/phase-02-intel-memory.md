# Phase 02 — Intel Memory + REUSE Existing TIER System

**Priority:** HIGH (foundation)
**Status:** Pending approval
**Slogan map:** Foundation — POWER mọi feature khác

## ⚠️ Key Insight (2026-04-16 correction)

**Hệ thống ĐÃ CÓ SẴN tier + action system:**
- Data: `D:/OneDrive/NelsonData/email/cnee_master_v2.xlsx` (28,169 CNEE)
- TIER: VIP (23) / HOT (82) / WARM_A (4,378) / WARM_B (20,724) / COOL (2,412) / PARK (550)
- ACTION: SEND_NOW / SEQUENCE_NEXT / COOLDOWN / SKIP / FOLLOW_UP / PERSONALIZED
- Columns: PRIORITY_SCORE, EMAIL_QUALITY_SCORE, REPLY_STATUS, SEND_COUNT

**KHÔNG build lại.** Phase 02 chỉ cần:
1. **Event chain table** (cái thật sự thiếu)
2. **Auto-update TIER/ACTION** từ events (promotion/demotion logic)
3. **Populate REPLY_STATUS + SEND_COUNT** real-time
4. **Nâng cấp `process_reply.py`** cho chạy định kỳ

## Context

Nelson muốn:
- Hệ thống nhớ 10+ email qua lại per CNEE
- Tự động promote/demote TIER khi có event mới (reply → HOT, bounce → PARK)
- Code `process_reply.py v3.0` + `reply_analyzer.py` + `sequence_engine.py` đã có, cần wire lại + chạy định kỳ

## Requirements

### 1. Event Chain Schema (NEW — the real gap)

```sql
-- SQLite at email_engine/data/intel.db

CREATE TABLE email_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  cnee_email TEXT NOT NULL,
  event_type TEXT NOT NULL,
    -- SENT | REPLY | AUTO_REPLY | BOUNCE
    -- TIER_PROMOTED | TIER_DEMOTED
    -- UNSUBSCRIBE | GOCLAW_DRAFTED
    -- MANUAL_NOTE
  timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- For SENT events
  subject TEXT,
  template_id TEXT,
  market_state TEXT,       -- URGENT|STABLE|DECLINING
  delta_pct REAL,
  batch_id TEXT,
  campaign_id TEXT,

  -- For REPLY events
  reply_subject TEXT,
  reply_body_snippet TEXT, -- first 500 chars
  sentiment TEXT,           -- POSITIVE|NEUTRAL|NEGATIVE|UNKNOWN
  intent TEXT,              -- booking | price_inquiry | negotiating | gratitude | objection | general
  reply_delay_hours REAL,

  -- For BOUNCE
  bounce_type TEXT,         -- HARD | SOFT | POLICY
  bounce_reason TEXT,

  -- For TIER change
  old_tier TEXT,
  new_tier TEXT,
  change_reason TEXT,

  -- Generic
  raw_meta TEXT             -- JSON for extra fields
);

CREATE INDEX idx_events_cnee_time ON email_events(cnee_email, timestamp DESC);
CREATE INDEX idx_events_type_time ON email_events(event_type, timestamp DESC);
CREATE INDEX idx_events_batch ON email_events(batch_id);
```

### 2. Aggregate View — query helpers

```python
def get_cnee_timeline(cnee_email: str, limit: int = 20) -> list:
    """Full conversation chain — 10+ events back and forth."""

def get_cnee_summary(cnee_email: str) -> dict:
    """Returns:
    {
      "total_sent": 12,
      "total_replied": 4,
      "last_sent_at": "2026-04-10",
      "last_reply_at": "2026-04-13",
      "days_since_last_reply": 3,
      "avg_reply_delay_hours": 14.2,
      "last_subject": "West Coast rates +5%",
      "last_reply_snippet": "Can you do better than...",
      "reply_rate": 0.33,
      "current_tier": "HOT",
      "current_action": "FOLLOW_UP",
      "intent_distribution": {
        "price_inquiry": 2, "booking": 1, "general": 1
      }
    }
    """

def get_stale_prospects(days: int = 7, tier: str = None) -> list:
    """Khách anh update tuần trước CHƯA PHẢN HỒI.
    Returns list of cnee_email who got SENT event > N days ago without REPLY since."""
```

### 3. TIER Auto-Update Rules

Wire into scanner (Phase 04) + worker (Phase 01):

```python
# Promotion rules (fire on event)
IF event=REPLY AND sentiment=POSITIVE AND intent in (booking, price_inquiry):
    IF current_tier in (WARM_B, COOL):
        promote → WARM_A
    ELIF current_tier = WARM_A:
        promote → HOT

IF event=REPLY (any):
    IF current_tier = COOL:
        promote → WARM_B
    UPDATE last_reply_at

IF event=SENT:
    UPDATE last_sent_at, SEND_COUNT++

# Demotion rules
IF event=BOUNCE (HARD):
    bounce_count++
    IF bounce_count >= 3:
        demote → PARK (ACTION=SKIP)
    ELSE:
        EMAIL_QUALITY_SCORE -= 15

IF event=UNSUBSCRIBE:
    demote → PARK (ACTION=SKIP) permanent

IF days_since_last_reply > 180 AND current_tier in (HOT, WARM_A):
    demote → COOL

# Action routing (post TIER change)
TIER=VIP       → ACTION=PERSONALIZED
TIER=HOT       → ACTION=FOLLOW_UP
TIER=WARM_A    → ACTION=SEQUENCE_NEXT (if in sequence) else SEND_NOW
TIER=WARM_B    → ACTION=SEND_NOW
TIER=COOL      → ACTION=SEND_NOW (but cooldown 5 days)
TIER=PARK      → ACTION=SKIP
```

### 4. Write-back to OneDrive master v2

Sau mỗi event triggered:
- Update in-memory intel.db (fast)
- Batch write-back to `cnee_master_v2.xlsx` every 5 minutes (debounce)
- Fields updated: TIER, ACTION, SEND_COUNT, REPLY_STATUS, LAST_SENT_DATE, SEQ_STEP, SEQ_STATUS, EMAIL_QUALITY_SCORE

### 5. Upgrade existing `process_reply.py`

Hiện tại code có nhưng chưa chạy định kỳ. Cần:
- Wire vào scheduler (Task Scheduler or scanner loop Phase 04)
- Output → email_events table (thay vì chỉ Excel)
- Intent classifier → persist per event

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ intel.db (SQLite local)                                  │
│                                                          │
│ email_events table (append-only event log)              │
│   ├─ SENT events (from worker Phase 01)                 │
│   ├─ REPLY/BOUNCE/AUTO_REPLY (from scanner Phase 04)    │
│   ├─ TIER_CHANGE events (from auto-update rules)        │
│   └─ GOCLAW_DRAFTED (from Phase 05)                     │
└─────────────────────────────────────────────────────────┘
              │                              │
              │ read                          │ trigger
              ▼                              ▼
┌──────────────────────┐      ┌──────────────────────────┐
│ Query API (fast)      │      │ TIER auto-update engine  │
│ - get_timeline(cnee)  │      │ - on REPLY → promote     │
│ - get_summary(cnee)   │      │ - on BOUNCE → demote     │
│ - get_stale(days=7)   │      │ - on UNSUB → park        │
│ - rank_for_send()     │      └──────────────────────────┘
└──────────────────────┘                    │
              │                              │
              │                              │ write-back every 5 min
              ▼                              ▼
┌──────────────────────────────────────────────────────┐
│ cnee_master_v2.xlsx (OneDrive, source of truth)      │
│ update: TIER, ACTION, SEND_COUNT, REPLY_STATUS,      │
│         EMAIL_QUALITY_SCORE, LAST_SENT_DATE          │
└──────────────────────────────────────────────────────┘
```

## Related Code Files

**Create:**
- `email_engine/intel/__init__.py`
- `email_engine/intel/schema.sql`
- `email_engine/intel/events.py` — event type enums + builders
- `email_engine/intel/memory.py` — SQLite CRUD + query helpers
- `email_engine/intel/tier_engine.py` — promotion/demotion rules
- `email_engine/intel/writeback.py` — update master v2 xlsx
- `email_engine/data/intel.db` (auto-created)

**Leverage existing (upgrade):**
- `email_engine/core/process_reply.py` v3.0 — wire output to intel.db
- `email_engine/core/reply_analyzer.py` — intent classifier
- `email_engine/core/reply_detector.py`
- `email_engine/core/bounce_handler.py`
- `email_engine/core/sequence_engine.py`

**Modify:**
- Phase 01 worker `mark_sent` → `intel.log_event(SENT, ...)`
- Phase 04 scanner → `intel.log_event(REPLY|BOUNCE|AUTO_REPLY)`

## Implementation Steps

1. **Schema + memory.py:**
   - `init_db()` with WAL
   - CRUD: log_event, get_timeline, get_summary, get_stale
   - Performance: index on (cnee_email, timestamp)

2. **Tier engine:**
   - Rule table (data-driven, YAML config)
   - `evaluate(event) → [actions_to_apply]`
   - Write TIER_CHANGE event + update master v2

3. **Writeback to OneDrive:**
   - Debounce 5 min (no excessive xlsx writes)
   - Atomic: write to temp, rename
   - Backup `cnee_master_v2.{yyyymmdd}.xlsx` weekly

4. **Backfill from email_log.csv (17K rows):**
   - Script: `scripts/backfill_intel.py`
   - Import all SENT events
   - Update `send_count` aggregate per CNEE

5. **Backfill from Outlook Inbox (60 days):**
   - Run `process_reply.py` upgraded → output events
   - Populate REPLY events for CNEE có reply gần đây

6. **Integration hooks:**
   - Phase 01 mark-sent → log SENT event
   - Phase 04 scanner → log REPLY/BOUNCE events
   - Tier engine → log TIER_CHANGE event + write master v2

## Todo List

- [ ] `intel/schema.sql` với 3 indexes
- [ ] `intel/memory.py` — log_event + 4 query functions
- [ ] `intel/events.py` — event type constants + builders
- [ ] `intel/tier_engine.py` — rules YAML + evaluate()
- [ ] `intel/writeback.py` — debounced xlsx write
- [ ] `scripts/backfill_intel_from_csv.py` — import 17K historical
- [ ] `scripts/backfill_intel_from_inbox.py` — run process_reply upgraded
- [ ] Hook Phase 01 worker mark-sent
- [ ] Hook Phase 04 scanner
- [ ] Query test: `get_cnee_timeline("test@x.com")` → chain events
- [ ] Test: REPLY event triggers TIER promote WARM_B→WARM_A
- [ ] Test: writeback updates master v2 correctly

## Success Criteria

- Query `SELECT * FROM email_events WHERE cnee_email='X'` trả về 10+ events chain
- Gửi SENT → event logged + SEND_COUNT++ trong master v2 sau 5 phút
- Scanner detect REPLY → event logged + TIER promoted + master v2 updated
- `get_stale(days=7)` trả về list CNEE đã update tuần trước chưa reply
- Query `get_cnee_summary("john@abc.com")` trả về dict đầy đủ 10+ fields
- Backfill: 17K historical SENT events trong < 2 phút

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| xlsx writeback lock conflict với anh open file | Writeback to temp, check file lock before rename |
| intel.db concurrent write (worker + scanner) | WAL mode (đã OK), short transactions |
| Promotion loop (same CNEE promote/demote liên tục) | Cooldown 24h on TIER change |
| Backfill slow (17K rows) | Batch 1000/insert transaction |
| master v2 schema drift | Validate columns on writeback; log warning |

## Security Considerations

- intel.db local only
- Event log có reply_body_snippet (PII) → không export/log ra ngoài
- Backup intel.db daily to OneDrive

## Next Steps

Phase 02 shipped → Phase 03 template engine query intel for personalization. Phase 04 scanner write events. Phase 05 GoClaw query timeline for context.
