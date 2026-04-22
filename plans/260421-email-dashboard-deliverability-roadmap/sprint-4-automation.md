# Sprint 4 — Automation (9h, Week 4)

**Goal:** Không bỏ sót cơ hội, không quên follow-up, reply nhanh 10x.

**Success:** Reply SLA 90% < 2h. Follow-up cadence tự động. Reply compose 10p → 1p.

## 4.1 Reply SLA Tracker + Telegram Alert (3h)

### Logic

```python
@dataclass
class ReplyPendingResponse:
    cnee_email: str
    reply_received_at: datetime
    reply_subject: str
    minutes_pending: int
    alert_level: str  # INFO | WARN | URGENT

REPLY_SLA_MINUTES = {
    'VIP': 30,       # Nelson must reply in 30 min
    'HOT': 60,       # 1 hour
    'WARM': 120,     # 2 hours
    'DEFAULT': 240,  # 4 hours
}

def scan_pending_replies():
    """Find replies received but Nelson hasn't responded yet."""
    events = query_events(days=7, types=['REPLY'])
    sent_log = load_sent_log(days=7)
    
    pending = []
    for reply in events:
        if reply.get('nelson_replied_at'):
            continue
        
        # Check if Nelson sent something to this email AFTER reply_received
        nelson_replies = sent_log[
            (sent_log['TO'] == reply['cnee_email']) &
            (sent_log['SENT_AT'] > reply['timestamp'])
        ]
        if len(nelson_replies) > 0:
            continue
        
        tier = get_cnee_tier(reply['cnee_email'])
        sla = REPLY_SLA_MINUTES.get(tier, REPLY_SLA_MINUTES['DEFAULT'])
        minutes_pending = (datetime.now() - reply['timestamp']).total_seconds() / 60
        
        if minutes_pending > sla:
            pending.append({
                'email': reply['cnee_email'],
                'subject': reply['subject'],
                'minutes_pending': minutes_pending,
                'tier': tier,
                'alert_level': 'URGENT' if minutes_pending > sla * 2 else 'WARN',
            })
    
    return pending
```

### Telegram alert cron

- Every 30 min (reuse scanner infrastructure)
- Dedup: not alert same email twice within 2 hours

### Dashboard UI (Inbox tab header)

```html
<div class="kpi" id="replyPending" style="background:#fff8e1">
  <div class="kpi-label">⚠ Pending Reply</div>
  <div class="kpi-value" id="replyPendingCount">2</div>
  <div class="kpi-foot">
    <span id="replyPendingOldest">Oldest: 3h 22m</span>
  </div>
</div>
```

Click → opens list of pending replies, sorted by tier + age.

## 4.2 Auto Follow-up Sequence Step 2/3 (4h)

### Sequence design

```
Step 1: initial outreach (Ocean Freight Update)
  ↓ sent, no reply in 7d
Step 2: soft reminder (email đã mở nhưng chưa reply? check lại rate)
  ↓ sent, no reply in 14d from step 1
Step 3: break-up email (last attempt, permission-based)
  ↓ sent, no reply in 21d from step 1
STOP: move to cold list (re-engage quarterly)
```

### Templates

`email_engine/templates/followup_step2.txt`:
```
Subject: Re: Ocean Freight Update — HPH to {pod} | Week {week}

Hi {first_name},

Following up on my previous email about ocean freight rates for 
{pod} — wanted to make sure it reached you.

Rates are holding at current levels but Q2 peak surcharges are 
coming. If you have any shipments planned for next 4-6 weeks, 
happy to quote specific lanes.

Quick questions:
  • Are you sourcing from Haiphong or Ho Chi Minh currently?
  • Primary POD: {pod} or multiple destinations?
  • Monthly volume estimate (TEU or containers)?

If timing isn't right, no worries — I'll check back in Q3.

Best,
Nelson Huynh
Pudong Prime
```

`email_engine/templates/followup_step3.txt`:
```
Subject: One last check — HPH to {pod}

Hi {first_name},

I haven't heard back about the ocean freight rates I sent, so 
I'll assume this isn't a priority right now. Totally understand.

Would it be helpful if I remove you from this list, or shall I 
check back in a few months?

Reply "remove" to unsubscribe, or "later" and I'll circle back 
in 3 months.

Thanks for your time,
Nelson
```

### Sequence tracker

Add columns to cnee_master:
- `SEQUENCE_STEP` (0 = not started, 1 = Step 1 sent, 2 = Step 2, 3 = Step 3, 99 = broken/replied)
- `LAST_STEP_SENT_AT` (datetime)

### Daily cronjob

```python
def process_sequences():
    """Daily 08:30 — advance sequences."""
    df = load_cnee()
    now = datetime.now()
    
    # Step 1 sent, 7d elapsed, no reply → Step 2
    ready_step2 = df[
        (df['SEQUENCE_STEP'] == 1) &
        (df['LAST_STEP_SENT_AT'] < now - timedelta(days=7)) &
        ~df['EMAIL'].isin(get_replied_emails())
    ]
    for _, row in ready_step2.iterrows():
        draft = compose_step2(row)
        queue_send(draft, step=2)
    
    # Step 2 sent, 7d elapsed, no reply → Step 3
    ready_step3 = df[
        (df['SEQUENCE_STEP'] == 2) &
        (df['LAST_STEP_SENT_AT'] < now - timedelta(days=7)) &
        ~df['EMAIL'].isin(get_replied_emails())
    ]
    for _, row in ready_step3.iterrows():
        draft = compose_step3(row)
        queue_send(draft, step=3)
    
    # Step 3 sent, 7d elapsed, no reply → move cold
    done = df[
        (df['SEQUENCE_STEP'] == 3) &
        (df['LAST_STEP_SENT_AT'] < now - timedelta(days=7)) &
        ~df['EMAIL'].isin(get_replied_emails())
    ]
    df.loc[done.index, 'ENGAGEMENT_STATUS'] = 'COLD'
    df.loc[done.index, 'SEQUENCE_STEP'] = 99
```

### UI control (Quick Send + Settings)

- Campaign send → auto mark `SEQUENCE_STEP=1, LAST_STEP_SENT_AT=now`
- Settings tab: toggle auto-sequence on/off, change wait days

## 4.3 Reply Draft AI (MiniMax) (2h)

### Flow

```
Click mail reply in Inbox tab
  ↓
POST /api/reply-draft/compose
  { email_id, reply_text, thread_context }
  ↓
MiniMax-M2 compose response EN based on:
  - CNEE's reply intent (booking/price/objection)
  - Original thread context
  - Recent rates from Pricing Dry
  - Nelson's tone guide (friendly, professional, succinct)
  ↓
Return draft text (subject + body)
  ↓
Anh review → edit → Send via Outlook draft
```

### Prompt template

```
You are drafting a response on behalf of Nelson Huynh, an ocean 
freight NVOCC sales rep. Respond to the customer reply below.

Tone: friendly, professional, succinct (<120 words).
Currency: USD. Container types: 20GP/40GP/40HC/45HC.
Lanes: HCM/HPH → USA/Canada.

Previous thread:
{thread_preview}

Customer reply:
{reply_body}

Customer intent: {intent}  # booking/price_inquiry/objection/gratitude
Customer sentiment: {sentiment}

Draft response:
```

### UI integration

In Inbox tab row actions:
```html
<button class="btn btn-xs" onclick="openReplyDraft('{email}', '{msg_id}')">
  💬 AI Draft
</button>
```

Modal pops up with draft, edit area, "Send" button → creates Outlook draft.

## Success Criteria

- [ ] Reply SLA dashboard widget live
- [ ] Telegram alerts fire for pending replies > SLA
- [ ] Auto-sequence cron runs daily, advances Step 1 → 2 → 3
- [ ] Reply Draft AI button works, draft appears in <10s
- [ ] 1 tháng sau: 90% reply SLA compliance, 3x outreach volume

## Risks

| Risk | Mitigation |
|------|-----------|
| Auto follow-up annoys customers | Max 3 steps, auto-stop on any reply, clear unsubscribe in Step 3 |
| AI draft sounds robotic / off-brand | Iterate prompts with Nelson's style samples, show edit diff |
| Sequence tracking breaks if data manually edited | Idempotent: re-check state before send, skip if already replied |
| Reply SLA false alarms (Nelson did reply via phone) | "Mark as handled" button trong UI to suppress alert |
