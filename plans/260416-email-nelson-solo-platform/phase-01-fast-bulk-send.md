# Phase 01 — Batch Send (Nelson chia 4-5 đợt × 200)

**Priority:** HIGH (foundation)
**Status:** Pending approval
**Slogan map:** NHANH — 1000 email tối chia batch, queue nhớ, worker gửi parallel

## 🎯 Context — Anh chốt workflow (2026-04-16)

Anh KHÔNG muốn bấm 1 nút → 1000 email bay cùng lúc. Anh muốn:
- **Tối anh chọn 1000 prospects** (filter theo TIER/ACTION trong OneDrive master v2)
- **Tự chia thành 4-5 batch** × 200 mỗi batch
- **Mỗi batch bấm Send riêng** → queue ghi lại với batch_id
- **Worker FAST mode** pop job từ queue, parallel 3-5 threads, gửi Outlook COM
- **Scanner 30 phút** scan Inbox → auto cleanup data (bounce/reply/unsub)

## Key Insights

- Data source: `D:/OneDrive/NelsonData/email/cnee_master_v2.xlsx` (28,169 CNEE)
- Filter default: `TIER ∈ (VIP, HOT, WARM_A, WARM_B) AND ACTION = 'SEND_NOW'` → ~23K eligible
- Batch 200 là sweet spot: Outlook không throttle, worker xử lý <5 phút, fail isolation tốt
- 4-5 batch cho anh quyền dừng giữa chừng (VD: đợt 2 thấy template sai → pause)

## Requirements

**Functional:**

### 1. Dashboard filter + select
- Filter: TIER + ACTION + CAMPAIGN + POL + DESTINATION
- Sort: PRIORITY_SCORE desc, EMAIL_QUALITY_SCORE desc
- Multi-select: tick 1000 prospects
- Show totals: "Selected: 1,000 | VIP: 15 | HOT: 50 | WARM_A: 400 | ..."

### 2. Batch chunking UI
- Slider "Batch size": 100 / 150 / 200 (default 200)
- Auto-split: 1000 prospects → 5 batches (200 each)
- Preview: "Batch 1: rows 0-199 | Batch 2: rows 200-399 | ..."
- **Each batch gets unique `batch_id` = `{yyyyMMdd}_{HHmm}_{batch_num}`**
- Nelson bấm "Queue Batch 1" → chỉ batch 1 vào queue
- Sau đó "Queue Batch 2" — có thể cùng lúc hoặc giãn ra tùy anh

### 3. Queue storage (SQLite)
```sql
CREATE TABLE email_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  cnee_email TEXT NOT NULL,
  subject TEXT NOT NULL,
  html_body TEXT NOT NULL,
  cc TEXT,
  tier TEXT,                    -- từ master v2
  priority_score INTEGER,        -- từ master v2
  campaign_id TEXT,              -- từ master v2
  status TEXT DEFAULT 'pending', -- pending | sending | sent | failed | retry
  attempts INTEGER DEFAULT 0,
  max_attempts INTEGER DEFAULT 3,
  error_message TEXT,
  enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  picked_at TIMESTAMP,           -- khi worker pick
  sent_at TIMESTAMP,             -- khi send thành công
  meta_json TEXT                 -- template_id, market_state, delta_pct
);
CREATE INDEX idx_queue_status ON email_queue(status, priority_score DESC);
CREATE INDEX idx_queue_batch ON email_queue(batch_id);
```

### 4. Worker FAST mode
- 3-5 threads parallel (configurable `--workers 5`)
- Mỗi thread: pop 1 job at a time với atomic update
- Order: ORDER BY priority_score DESC (VIP/HOT trước, WARM_B sau)
- Outlook COM: `win32com.client.Dispatch("Outlook.Application")` mỗi thread
- On success: mark_sent + log event (Phase 02)
- On fail: attempts++, if < max → status='pending' (retry), else 'failed'

### 5. Batch status endpoint
```
GET /api/email-rate/batch/{batch_id}/status
→ {
  "batch_id": "20260416_2030_1",
  "total": 200,
  "pending": 45,
  "sending": 5,
  "sent": 148,
  "failed": 2,
  "started_at": "2026-04-16T20:30:00",
  "eta_finish": "2026-04-16T20:35:00",
  "rate_per_min": 35
}
```

### 6. Safety layers (Phase 01 MUST include)
- **Kill Switch**: file `email_engine/data/KILL_SWITCH.flag` tồn tại → worker refuse mọi pop
- **Unique constraint**: `(cnee_email, batch_id)` unique → không duplicate
- **Dry-run mode**: query flag `?dry_run=true` → worker log "WOULD SEND" không gọi Outlook
- **Batch approval gate**: batch >500 require explicit `?confirm=yes` (phòng nhỡ tay)
- **Per-worker rate limit**: max 60 sends/phút/worker → tránh Exchange throttle

## Architecture

```
[Dashboard v4 — Send Tab]
  User:
  1. Filter prospects theo TIER+ACTION+CAMPAIGN
  2. Sort by PRIORITY_SCORE desc
  3. Select 1000
  4. Click "Split into batches" → batch_size=200
  5. Click "Queue Batch 1" (rows 0-199)
       ↓ POST /api/email-rate/batch/enqueue
         body: {batch_id, emails: [...], template_id}
       ↓
┌─────────────────────────────────────────┐
│ web_server.py                            │
│   validate:                              │
│     - kill_switch check                  │
│     - batch size ≤500                    │
│     - no duplicate (cnee+batch)          │
│   for each email:                        │
│     - build HTML (Phase 03)              │
│     - INSERT email_queue (status=pending)│
│   return {queued: 200, batch_id: "..."}  │
└─────────────────────────────────────────┘
       ↓
  Dashboard show: "Batch 1 queued ✅"
  Click "Queue Batch 2" (rows 200-399)
  ... repeat ...
       ↓
┌─────────────────────────────────────────┐
│ outlook_queue_worker.py (FAST MODE)      │
│                                           │
│ ThreadPoolExecutor(max_workers=5)        │
│   each thread:                            │
│     while not kill_switch:                │
│       job = pop_one_atomic(order_by=     │
│         priority_score DESC)              │
│       if not job: sleep(2); continue     │
│       try:                                │
│         outlook.Send(job)                 │
│         mark_sent(job.id)                 │
│         intel.log_event(SENT, ...)        │
│       except ThrottleError:               │
│         sleep(60); retry                  │
│       except:                             │
│         mark_retry(job.id, error)         │
└─────────────────────────────────────────┘
       ↓
  Dashboard poll batch status every 5s
  Show: "Batch 1: 148/200 sent, 2 failed"
```

## Related Code Files

**Create:**
- `email_engine/queue_store.py` (~120 dòng)
- `email_engine/data/outlook_queue.db` (auto-created)

**Modify:**
- `email_engine/web_server.py` — add batch endpoints
- `email_engine/outlook_queue_worker.py` — rewrite ThreadPoolExecutor
- `email_engine/start-dashboard-v4.bat` — start worker --workers 5
- `plans/visuals/email-dashboard-v4.html` — batch chunking UI

**Use directly (no copy, read from OneDrive):**
- `D:/OneDrive/NelsonData/email/cnee_master_v2.xlsx` — source of truth

## Implementation Steps

1. **`queue_store.py`** — 7 functions: init_db, enqueue_batch, pop_one, mark_sent, mark_failed, get_batch_status, reset_stuck
2. **`web_server.py`** — 5 new endpoints:
   - `POST /api/email-rate/batch/enqueue`
   - `GET /api/email-rate/queue/pending` (worker poll)
   - `POST /api/email-rate/queue/mark-sent/{id}`
   - `POST /api/email-rate/queue/mark-failed/{id}`
   - `GET /api/email-rate/batch/{batch_id}/status`
3. **Worker rewrite** — ThreadPoolExecutor, atomic pop via SQLite UPDATE RETURNING, per-thread Outlook instance
4. **Dashboard batch UI** — select 1000 → slider 200 → show 5 batch cards với "Queue" button each
5. **Kill switch** — check `KILL_SWITCH.flag` exists before every pop + enqueue
6. **Test:**
   - Queue 200 emails → verify queue có 200 rows status=pending
   - Start worker → verify sent 200 trong <5 phút
   - Kill worker mid-batch → verify 'sending' jobs reset về pending after 10 min
   - Dry-run 200 → verify không gọi Outlook

## Todo List

- [ ] `queue_store.py` với WAL mode
- [ ] Web_server.py 5 new endpoints
- [ ] Worker ThreadPoolExecutor rewrite
- [ ] Dashboard batch chunking UI
- [ ] Kill switch flag check
- [ ] Unique constraint + dedup
- [ ] Dry-run mode flag
- [ ] Batch approval gate (>500 confirm)
- [ ] Test 200 real emails
- [ ] Test kill mid-batch recovery

## Success Criteria

- Nelson bấm "Queue Batch 1 (200)" → queue có 200 rows trong 1 giây
- Worker 5 threads → 200 emails gửi xong <5 phút (40+/phút)
- Kill switch flag → worker dừng ngay trong 2s
- Dry-run → log "WOULD SEND" không gọi Outlook
- Batch status poll trả real-time counts
- Batch 2 queue được trong khi batch 1 đang gửi (concurrent OK)

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Outlook throttle khi 5 threads | Per-thread rate limit 60/min; sleep on 421 |
| Double-send cùng CNEE nếu queue 2 batch trùng | Unique constraint (cnee_email, date) |
| Worker crash mid-batch | reset_stuck after 10min → status pending, retry |
| Nelson tick nhầm 5000 prospects | Batch >500 require explicit confirm=yes |
| Outlook security prompt per send | Trust Center setup manual (1 lần) |

## Security Considerations

- SQLite local only (localhost bind)
- Kill switch file local → không remote
- Dry-run mode visible trong log "DRY RUN" flag để debug
