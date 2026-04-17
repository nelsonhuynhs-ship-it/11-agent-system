# Phase 06 — Dashboard v4 Integration

**Priority:** MEDIUM (UX polish, after core ships)
**Status:** Pending approval
**Slogan map:** UX — Nelson 1 dashboard thấy hết

## Context

Dashboard v4 HTML hiện có 5 tabs (Send, Analytics, AI Model, Alerts, Queue). Cần integrate:
- Queue progress real-time (Phase 01)
- Market Intel panel per lane (Phase 03)
- Reply feed (Phase 04)
- GoClaw Drafts panel (Phase 05)
- Intel profile per prospect (Phase 02)

## Key Insights

- Dashboard v4 là single HTML file, vanilla JS, polls local API `:8100`
- Add panels không cần rebuild — edit HTML inline
- Poll pattern: SWR-like, 5s for active queue, 30s for intel, manual refresh for drafts

## Requirements

**Functional:**

### 1. Queue Progress Widget (top-right sticky)
```
📬 QUEUE STATUS
Batch: 2026-04-16-A
Pending: 742   Sending: 5
Sent: 251      Failed: 2
Elapsed: 4:32  Rate: 312/min
[⏸ Pause] [🔄 Reset stuck]
```

### 2. Market Intel Panel (in Send tab)
```
📊 MARKET INTEL — Week 16/2026
┌──────────────────────────────────────┐
│ HPH → USLAX  🔴 URGENT  +5.2%  conf 89% │
│   $2,500 vs 90d mean $2,300 (+8.7%) │
│   Forecast next week: $2,575        │
├──────────────────────────────────────┤
│ HPH → USNYC  🟢 STABLE  +0.3%  conf 93% │
│   $2,150 vs 90d mean $2,180         │
├──────────────────────────────────────┤
│ HCM → USLGB  🔴 URGENT  +4.1%  conf 81% │
└──────────────────────────────────────┘
```

### 3. Recent Replies Feed (in Alerts tab)
```
🚨 RECENT REPLIES (30min scan)

[5 min ago] 🔥 john@abc-furniture.com
  Topic: PRICE  Sentiment: POSITIVE
  Snippet: "Can you do better than $2,400? We need 5x..."
  [View] [Reply Draft from GoClaw] [Manual Reply]

[18 min ago] 🟡 alice@xyz-flooring.com
  Topic: SCHEDULE  Sentiment: NEUTRAL
  Snippet: "What's your next sailing to LGB?"
  [View] [Generate Draft] [Manual Reply]
```

### 4. GoClaw Drafts Panel (new tab or in Alerts)
```
🌙 GOCLAW DRAFTS (2 pending overnight)

Draft 1/2 — john@abc-furniture.com
  In reply to: "Can you do better than $2,400?"
  
  Subject: Re: West Coast rates — yes we can
  
  Preview:
  Hi John,
  Thanks for replying. Yes — we can do $2,350/40HQ to USLAX 
  for your usual 5-container shipments. Market forecast +3%  
  next week, so locking in today is smart. Confirm to proceed?
  
  [✅ Approve & Send]  [✏️ Edit]  [❌ Reject]
  
  Why: POSITIVE sentiment + PRICE topic + typical 5-cont 
       pattern + URGENT market → discount + urgency close
```

### 5. Intel Profile Modal (click on prospect row)
```
👤 JOHN SMITH @ ABC FURNITURE CO

Tier: 🔥 HOT (last reply 3 days ago)
Score: 87/100

Email history:
  Total sent: 12 (last 90d)
  Total replied: 4 (33% rate)
  Avg reply delay: 14 hours
  
Typical pattern:
  POL: HPH
  Destinations: USLAX, USLGB
  Cont count: 5x 40HQ
  Preferred carriers: ONE, MSC
  Last rate quoted: $2,400 40HQ (6 days ago)

Recent events:
  2026-04-13 SENT rate update (west_coast_urgent, +5.2%)
  2026-04-13 REPLY positive price-topic "Can you do better..."
  2026-04-10 SENT weekly rates (default template)
```

**Non-functional:**
- Initial page load < 2s
- Poll queue every 5s during active batch, 30s idle
- All panels work on 1920x1080 and 1280x800

## Architecture

```
email-dashboard-v4.html
 │
 ├─ QueueStatusWidget
 │    polls GET /api/email-rate/queue/status every 5s
 │
 ├─ MarketIntelPanel
 │    polls GET /api/intelligence/lanes?pol=HPH every 30s
 │    cache on window focus
 │
 ├─ RepliesFeed
 │    polls GET /api/intel/recent-replies?since=30min every 60s
 │
 ├─ DraftsPanel
 │    polls GET /api/drafts/pending every 5min
 │    Action: POST /api/drafts/{id}/approve | reject | edit
 │
 └─ IntelProfileModal
      on row click: GET /api/intel/profile?email=...
```

## Related Code Files

**Modify:**
- `plans/visuals/email-dashboard-v4.html` — 5 new panels + JS handlers

**New API endpoints (in web_server.py):**
- `GET /api/intel/recent-replies?since=30min`
- `GET /api/intel/profile?email=...`
- `GET /api/intelligence/lanes?pol=HPH` (wraps market_engine)
- `GET /api/drafts/pending`
- `POST /api/drafts/{id}/approve`
- `POST /api/drafts/{id}/reject`
- `POST /api/drafts/{id}/edit`

## Implementation Steps

1. **Queue Status Widget:** Add sticky div top-right, poll logic
2. **Market Intel Panel:** Section in Send tab, grid of lane cards
3. **Replies Feed:** Section in Alerts tab, list + action buttons
4. **Drafts Panel:** New section or tab, full draft preview + actions
5. **Intel Profile Modal:** Bind to row click in contacts table
6. **Shared: toast notification** on approve/reject/error

## Todo List

- [ ] Queue widget HTML + CSS + JS poll
- [ ] Market Intel panel — card grid layout
- [ ] Replies feed — list with action buttons
- [ ] Drafts panel — preview + approve/edit/reject
- [ ] Intel profile modal
- [ ] 6 new API endpoints in web_server.py
- [ ] Toast notification component
- [ ] Loading states + error handling
- [ ] Responsive: mobile layout (optional)
- [ ] Test: all panels render correctly with real data

## Success Criteria

- Nelson mở dashboard thấy NGAY: queue status, market intel, replies, drafts
- Approve draft 1 click → queue updates → worker sends
- Replies feed cập nhật mỗi 60s không refresh page
- Market intel panel reflects current week data
- Intel profile click → modal với đầy đủ data

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Too many polls → laggy dashboard | Smart poll: only when tab focused |
| UI clutter | Collapsible sections, user can hide |
| JS memory leak | Cleanup intervals on tab change |

## Security Considerations

- Dashboard file:// origin — CORS already allows "null"
- Actions (approve/reject) require user interaction (no auto-approve)

## Next Steps

Phase 06 polish → Phase 07 cleanup VPS email routers.
