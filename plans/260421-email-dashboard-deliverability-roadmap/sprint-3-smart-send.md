# Sprint 3 — Smart Send (7h, Week 3)

**Goal:** Mỗi email tới đúng timezone, đúng người — open rate +50%.

**Success:** Open rate 22% → 28-32%. Reply rate 1.5% → 2.5%+.

## 3.1 Smart Send Time per Timezone (3h)

### Logic

```
CNEE destination → infer timezone:
  SEA, LAX, OAK, LGB, POR  → Pacific (UTC-8/-7)
  NYC, JFK, NWR, CHS, MIA  → Eastern (UTC-5/-4)
  HOU, DFW, MEM, CHI        → Central (UTC-6/-5)
  MKC, DEN                  → Mountain (UTC-7/-6)
  MON, TOR, VAN, MTL        → Canada

Best send time (receiver local):
  08:00-10:00 = peak open (business starts)
  15:00-16:00 = second peak (post-lunch)

Target: send to arrive in inbox at local 09:00 AM.
```

### Implementation

```python
TIMEZONE_MAP = {
    'SEA': 'US/Pacific', 'LAX': 'US/Pacific', 'OAK': 'US/Pacific',
    'NYC': 'US/Eastern', 'CHS': 'US/Eastern', 'MIA': 'US/Eastern',
    'HOU': 'US/Central', 'DFW': 'US/Central', 'CHI': 'US/Central',
    'DEN': 'US/Mountain', 'MKC': 'US/Central',
    'VAN': 'Canada/Pacific', 'TOR': 'Canada/Eastern',
    # ... defaults to US/Eastern if unknown
}

def optimal_send_time_vn(destination: str) -> datetime:
    """Return next 9am local of destination, expressed in VN time."""
    import pytz
    tz_name = TIMEZONE_MAP.get(destination.upper().split(',')[0].strip(), 'US/Eastern')
    local_tz = pytz.timezone(tz_name)
    vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    
    now_local = datetime.now(local_tz)
    target = now_local.replace(hour=9, minute=0, second=0, microsecond=0)
    if now_local >= target:
        target += timedelta(days=1)  # next day 9am
    
    return target.astimezone(vn_tz)
```

### Queue-based sending

Instead of sending immediately, queue với schedule:

```python
@app.post("/api/quick-send/batch")
def batch_enqueue(req: BatchRequest):
    scheduled = []
    for email_info in filtered:
        dest = email_info['destination']
        send_at_vn = optimal_send_time_vn(dest) if req.smart_send_time else datetime.now()
        scheduled.append({
            'email': email_info['email'],
            'send_at': send_at_vn,
            'campaign': req.campaign,
            ...
        })
    
    queue_store.insert_many(scheduled)
    return {
        'queued': len(scheduled),
        'smart_send_time': req.smart_send_time,
        'schedule_preview': scheduled[:5],  # first 5 for UI
    }
```

A worker (outlook_queue_worker.py — đã có) picks up emails with `send_at <= now()` và send.

### UI control

```html
<!-- In Quick Send batch area -->
<label>
  <input type="checkbox" id="qsSmartSendTime" checked>
  🕐 Smart Send Time (gửi đúng 9am local của CNEE)
</label>
<small class="muted">US East: gửi 21h VN · US West: 00h-01h VN · Canada: same</small>
```

## 3.2 Campaign Performance Dashboard (3h)

### Data query

```python
@app.get("/api/campaigns/performance")
def campaign_performance(days: int = 30):
    """Returns per-campaign: sent, open rate, reply rate, bounce rate, WIN rate."""
    import pandas as pd
    
    # Email log
    log = pd.read_csv(EMAIL_LOG, parse_dates=['SENT_AT'])
    cutoff = datetime.now() - timedelta(days=days)
    log = log[log['SENT_AT'] >= cutoff]
    
    # Events (bounces/replies from intel/events.db)
    events = query_events(days=days, limit=10000)
    events_by_email = defaultdict(list)
    for e in events:
        events_by_email[e['cnee_email'].lower()].append(e)
    
    # WIN from ERP Active Jobs (join via email match)
    # ... (optional, if ERP wired)
    
    result = []
    for campaign, group in log.groupby('CAMPAIGN'):
        sent = len(group)
        opened = sum(1 for _, row in group.iterrows() if row['OPENED'] == 'Y')
        replied = sum(1 for email in group['EMAIL'] 
                     if any(e['event_type'] == 'REPLY' for e in events_by_email.get(email.lower(), [])))
        bounced = sum(1 for email in group['EMAIL']
                     if any(e['event_type'] == 'BOUNCE' for e in events_by_email.get(email.lower(), [])))
        
        result.append({
            'campaign': campaign,
            'sent': sent,
            'open_rate': round(opened/sent*100, 1) if sent else 0,
            'reply_rate': round(replied/sent*100, 2) if sent else 0,
            'bounce_rate': round(bounced/sent*100, 2) if sent else 0,
            'win_rate': 0,  # future
            'health': health_label(opened, replied, bounced, sent),
        })
    
    return sorted(result, key=lambda x: -x['reply_rate'])


def health_label(opened, replied, bounced, sent):
    if sent == 0: return '⚫ no data'
    br = bounced/sent
    rr = replied/sent
    if br > 0.02: return '🔴 kill'
    if rr > 0.03: return '🔥 hot'
    if rr > 0.01: return '🟢 good'
    if rr > 0: return '🟡 low'
    return '⚫ no reply'
```

### Dashboard UI (Insights tab)

```html
<section id="campaignPerformance">
  <h3>📊 Campaign Performance (last 30d)</h3>
  <table class="data-table">
    <thead>
      <tr>
        <th>Campaign</th>
        <th>Sent</th>
        <th>Open %</th>
        <th>Reply %</th>
        <th>Bounce %</th>
        <th>Health</th>
      </tr>
    </thead>
    <tbody id="campaignTable">
      <!-- 🔥 hot campaigns on top, 🔴 kill at bottom -->
    </tbody>
  </table>
</section>
```

## 3.3 Engagement Scoring + Cold List (1h)

### Score formula

```python
def engagement_score(email: str, events: list) -> int:
    """Score per CNEE based on interaction history.
    Range: -100 (disengaged/bad) → +100 (hot lead)
    """
    score = 0
    for e in events:
        t = e['event_type']
        if t == 'OPEN':       score += 1
        elif t == 'REPLY':    score += 10
        elif t == 'AUTO_REPLY': score -= 0  # neutral
        elif t == 'BOUNCE':   score -= 20
        elif t == 'UNSUBSCRIBE': score -= 100
    
    return max(-100, min(100, score))
```

### Cold list logic

```python
COLD_THRESHOLD_SCORE = -5
COLD_THRESHOLD_SENDS_NO_ENGAGE = 3

def maintain_cold_list():
    """Mark CNEE as cold if no engagement despite multiple sends."""
    df = load_cnee()
    for idx, row in df.iterrows():
        events = get_events_for(row['EMAIL'])
        score = engagement_score(row['EMAIL'], events)
        sends = row.get('SENDS_COUNT', 0)
        engaged_sends = sum(1 for e in events if e['event_type'] in ('OPEN', 'REPLY'))
        
        if score < COLD_THRESHOLD_SCORE:
            df.loc[idx, 'ENGAGEMENT_STATUS'] = 'COLD'
        elif sends >= COLD_THRESHOLD_SENDS_NO_ENGAGE and engaged_sends == 0:
            df.loc[idx, 'ENGAGEMENT_STATUS'] = 'COLD'
        else:
            df.loc[idx, 'ENGAGEMENT_STATUS'] = 'ACTIVE'
        df.loc[idx, 'ENGAGEMENT_SCORE'] = score
    
    save_cnee(df)
```

### Quick Send filter update

Add `ENGAGEMENT_STATUS != 'COLD'` to active recipient query. Counter includes "X cold skipped" in breakdown.

## Success Criteria

- [ ] Smart send time queue hoạt động, emails gửi đúng timezone
- [ ] Campaign dashboard live, anh thấy 18 campaigns ranked by reply rate
- [ ] Engagement scoring populates ENGAGEMENT_SCORE column
- [ ] Cold list auto-generated, Quick Send skip cold CNEE
- [ ] 2 tuần sau deploy: open rate +30% (measurable)

## Risks

| Risk | Mitigation |
|------|-----------|
| Queue worker crash → mails stuck | Heartbeat monitoring, Telegram alert if queue grows > 500 |
| Timezone map incomplete (unknown destinations) | Default US Eastern, log unknowns for manual review |
| Cold list auto-mark false positives | Unsuppress button in Settings, manual review page |
