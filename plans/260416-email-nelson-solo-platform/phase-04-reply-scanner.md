# Phase 04 — Reply Scanner + Auto Data Cleanup

**Priority:** HIGH
**Status:** Pending approval
**Slogan map:** NHANH (reply detection) + Data quality self-maintenance

## 🎯 Context — Anh chốt workflow

Anh muốn scanner:
1. Chạy mỗi 30 phút scan Outlook Inbox
2. Bắt events: BOUNCE / AUTO_REPLY / REAL_REPLY
3. **Tự động clean up data** (update master v2 trên OneDrive):
   - Bounce → EMAIL_QUALITY_SCORE -15, BOUNCE 3x → TIER=PARK
   - Reply positive → TIER promote (WARM_B → WARM_A → HOT)
   - Unsubscribe → TIER=PARK, ACTION=SKIP
   - Update REPLY_STATUS, SEND_COUNT, LAST_SENT_DATE

## Key Insights — Leverage Code Có Sẵn

Code đã có (chưa chạy định kỳ):
- ✅ `email_engine/core/process_reply.py` v3.0 — Intent classifier
- ✅ `email_engine/core/reply_analyzer.py` — sentiment
- ✅ `email_engine/core/reply_detector.py` — CNEE match
- ✅ `email_engine/core/bounce_handler.py` — bounce regex
- ✅ `email_engine/core/sequence_engine.py` — sequence state machine

**Không rewrite. Upgrade + wire:**
- Đầu ra: event log Phase 02 (intel.db)
- Trigger: 30-min scheduler
- Side effects: update master v2 + Telegram alerts

## Requirements

### 1. Scheduler
- Windows Task Scheduler: trigger `run_scanner.bat` every 30 min
- OR embedded APScheduler trong web_server.py (cùng process)
- Default: APScheduler (đơn giản, 1 process)

### 2. Scan scope
- Outlook Inbox items ReceivedTime trong 35 phút gần đây (overlap 5 min safety)
- Mark `Categories += "Nelson-Scanned"` để không re-process
- Limit: max 200 items per scan (tránh slow)

### 3. Classification pipeline

```
For each inbox item:
  sender = item.SenderEmailAddress
  
  # 1. Check bounce patterns
  if sender matches POSTMASTER_PATTERNS or body matches BOUNCE_DSN:
    → BOUNCE handler
    → extract bounced email address
    → log event + update master
  
  # 2. Check auto-reply patterns
  elif subject matches AUTO_REPLY_PATTERNS:
    → AUTO_REPLY handler (light log only)
  
  # 3. Match sender to CNEE master
  elif cnee_row = master.lookup_by_email(sender):
    → REAL_REPLY handler
    → reply_analyzer.classify(item.body)
    → sentiment + intent
    → log event + TIER promotion + Telegram alert
  
  # 4. Irrelevant (not in master, not bounce, not auto)
  else:
    → skip, mark category "Nelson-Irrelevant"
```

### 4. Handlers

**Bounce handler:**
```python
def handle_bounce(item):
    bounced_email = extract_bounced_address(item.body)
    intel.log_event({
        "event_type": "BOUNCE",
        "cnee_email": bounced_email,
        "bounce_type": detect_type(item),  # HARD/SOFT/POLICY
        "bounce_reason": extract_reason(item.body),
    })
    
    master_v2.update(bounced_email, {
        "EMAIL_QUALITY_SCORE": max(0, current - 15),
        "LAST_BOUNCE_DATE": now(),
    })
    
    bounce_count = count_events("BOUNCE", bounced_email)
    if bounce_count >= 3:
        master_v2.update(bounced_email, {
            "TIER": "PARK",
            "ACTION": "SKIP",
            "EMAIL_STATUS": "HARD_BOUNCE",
        })
        telegram.alert(f"🚫 {bounced_email} auto-parked (3 bounces)")
```

**Real reply handler:**
```python
def handle_reply(item, cnee_row):
    sentiment = reply_analyzer.sentiment(item.body)
    intent = reply_analyzer.intent(item.subject + item.body)
    
    # Find matching SENT event (last sent to this CNEE)
    last_sent = intel.get_last_event(cnee_row.EMAIL, "SENT")
    reply_delay = (now - last_sent.timestamp).total_hours if last_sent else None
    
    intel.log_event({
        "event_type": "REPLY",
        "cnee_email": cnee_row.EMAIL,
        "reply_subject": item.Subject,
        "reply_body_snippet": item.Body[:500],
        "sentiment": sentiment,
        "intent": intent,
        "reply_delay_hours": reply_delay,
    })
    
    # TIER promotion (via tier_engine from Phase 02)
    tier_engine.evaluate_reply_event(cnee_row, sentiment, intent)
    
    # Master v2 update
    master_v2.update(cnee_row.EMAIL, {
        "REPLY_STATUS": intent,  # e.g., "price_inquiry"
        "LAST_REPLY_DATE": now(),
    })
    
    # Telegram alert Nelson
    telegram.send(f"""
🚨 REPLY from {cnee_row.COMPANY} ({cnee_row.TIER})
Topic: {intent}  Sentiment: {sentiment}
Subject: {item.Subject[:80]}
Preview: {item.Body[:200]}
""")
    
    # Trigger GoClaw (Phase 05)
    if sentiment == "POSITIVE" and intent in ("price_inquiry", "booking"):
        goclaw.queue_draft(cnee_row, item)
```

**Unsubscribe handler:**
```python
# Detect patterns in reply body: "unsubscribe", "stop", "remove me", "do not email"
if matches_unsubscribe(item.body):
    intel.log_event({"event_type": "UNSUBSCRIBE", "cnee_email": sender})
    master_v2.update(sender, {
        "TIER": "PARK",
        "ACTION": "SKIP",
        "EMAIL_STATUS": "UNSUBSCRIBED",
    })
    telegram.alert(f"⛔ {sender} unsubscribed — auto-parked")
```

### 5. Auto Cleanup Summary (daily report)

End of each day (9pm), Telegram bot sends:
```
📊 EMAIL DATA CLEANUP — 2026-04-16

Today's changes:
  🚫 3 CNEE → PARK (bounce 3x)
  ⛔ 1 CNEE → unsubscribed
  🔥 8 CNEE → promoted HOT (positive reply)
  ⭐ 23 CNEE → promoted WARM_A
  📉 EMAIL_QUALITY_SCORE avg: 96.8 → 96.5 (5 bounces)

Telegram alerts sent: 12 real replies
Auto-drafts queued for GoClaw: 8

Total sent today: 423
  Bounce rate: 1.2% ✅ (healthy)
  Reply rate (today's sends): pending (need 2-3 days)
```

## Architecture

```
┌──────────────────────────────────────┐
│ APScheduler (every 30 min)            │
│   trigger: scanner.run_scan()         │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ inbox_scanner.py                      │
│   1. Outlook COM connect              │
│   2. Fetch inbox last 35 min          │
│   3. Skip items with "Nelson-Scanned" │
│   4. Classify each → handler          │
│   5. Mark Category "Nelson-Scanned"   │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ Classifier (reuses reply_analyzer,    │
│   reply_detector, bounce_handler)     │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ Handlers                              │
│ ├─ BOUNCE → intel log + master update │
│ ├─ AUTO_REPLY → light log             │
│ ├─ REAL_REPLY → intel + tier engine   │
│ │    + Telegram + GoClaw trigger      │
│ └─ UNSUBSCRIBE → park + telegram      │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ Side effects:                         │
│ • intel.db event logged               │
│ • master v2 xlsx updated (debounced)  │
│ • Telegram sent (if applicable)       │
│ • GoClaw triggered (if positive reply)│
└──────────────────────────────────────┘
```

## Related Code Files

**Create:**
- `email_engine/scanner/__init__.py`
- `email_engine/scanner/inbox_scanner.py` — main scheduler + loop
- `email_engine/scanner/handlers.py` — 3 handlers (bounce, reply, unsub)
- `email_engine/scanner/telegram.py` — Telegram API wrapper
- `email_engine/scanner/daily_report.py` — 9pm summary
- `email_engine/config/scanner.yaml` — patterns (bounce regex, auto-reply keywords, unsub keywords)

**Upgrade existing (wire to intel.db):**
- `email_engine/core/process_reply.py` — output to event log, not xlsx
- `email_engine/core/reply_analyzer.py` — return structured dict
- `email_engine/core/bounce_handler.py` — call intel.log_event
- `email_engine/core/reply_detector.py` — match CNEE from master v2 OneDrive

**Modify:**
- `email_engine/web_server.py` — register APScheduler job
- `email_engine/start-dashboard-v4.bat` — ensure scheduler runs

## Implementation Steps

1. **scanner.yaml** patterns:
   - Bounce DSN: `postmaster@`, `mailer-daemon@`, subject contains "Delivery Status Notification"
   - Auto-reply: "Out of Office", "Automatic reply", "I am on vacation"
   - Unsubscribe: "unsubscribe", "stop email", "remove me", "do not email"

2. **Classifier** — dispatch logic, reuse existing analyzer funcs

3. **Handlers** — 3 file + Telegram wrapper

4. **Auto-update rules** in tier_engine.py (Phase 02 dependency)

5. **APScheduler** embedded trong web_server.py:
   ```python
   from apscheduler.schedulers.background import BackgroundScheduler
   sched = BackgroundScheduler()
   sched.add_job(scanner.run_scan, 'interval', minutes=30)
   sched.add_job(daily_report.send, 'cron', hour=21, minute=0)
   sched.start()
   ```

6. **Daily report** 9pm:
   - Query intel.db events last 24h
   - Aggregate: promotions, demotions, bounces, replies
   - Telegram send

## Todo List

- [ ] `scanner.yaml` với 3 pattern sets
- [ ] `scanner/inbox_scanner.py` main loop
- [ ] `scanner/handlers.py` 3 handlers
- [ ] `scanner/telegram.py` wrapper (reuse GoClaw bot token)
- [ ] Wire `bounce_handler.py` → intel.db
- [ ] Wire `reply_analyzer.py` output format
- [ ] `process_reply.py` upgrade output
- [ ] APScheduler in web_server.py (30 min + 9pm)
- [ ] Daily report generator
- [ ] Test: real inbox 10 items → verify classify + update
- [ ] Test: bounce detection regex
- [ ] Test: TIER promotion on reply
- [ ] Test: unsubscribe auto-park
- [ ] Test: master v2 writeback không corrupt file

## Success Criteria

- Scanner chạy 30 min cycle, không crash, <2 phút/cycle
- Bounce từ inbox → master v2 EMAIL_QUALITY_SCORE giảm 15, log event
- 3 bounces cùng CNEE → auto TIER=PARK + Telegram alert
- Real reply → Telegram alert Nelson trong <5 phút
- TIER promotion WARM_B→WARM_A→HOT khi positive reply + intent
- Unsubscribe reply → CNEE → PARK permanent
- Daily report 9pm Telegram có summary

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Outlook COM lock giữa worker (Phase 01) và scanner | Separate Application instance, or serialize by lock |
| False positive real-reply (newsletter) | Whitelist: only sender matches CNEE master |
| Telegram spam (100 replies cùng lúc) | Batch alerts, 1 alert/5min bucket |
| Sentiment wrong → auto-promote nhầm | Confidence threshold; only promote if confidence > 0.7 |
| xlsx writeback conflict với Excel mở | Check file lock, retry after 30s |
| Unsubscribe false positive | Require exact phrase match, not fuzzy |

## Security Considerations

- Reply body snippet (500 chars) stored in intel.db — PII, local only
- Telegram bot token in `.env` (gitignored)
- No export event log outside local

## Next Steps

Phase 04 done → auto-cleanup loop active → data quality tự maintain. Phase 05 GoClaw consumes REPLY events để gen drafts.
