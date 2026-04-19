---
phase: 08
name: Open Tracker Tab — Dashboard v5
status: IN PROGRESS
priority: HIGH
estimate: 2 ngày
decisions_locked: 2026-04-19
---

# Phase 08 — Open Tracker Tab

## Context Links
- Brainstorm memory: `memory/idea-open-tracker-tab.md`
- Dashboard v5 HTML: `plans/visuals/email-dashboard-v5.html`
- Backend: `email_engine/web_server.py`
- Data source: `email_engine/data/outlook_queue.db` (`email_queue` table)
- Existing endpoint: `/api/email-rate/analytics/opens` (aggregate only)

## Decisions Locked (Sếp 2026-04-19)
| # | Decision | Chọn |
|---|----------|------|
| 1 | Layout | **C. Hybrid 3-panel** (KPI + Hot + Feed + Campaign) |
| 2 | Row action | **Follow-up + Preview email cũ** (2 buttons) |
| 3 | Default scope | **30 ngày** |

## Goal

Tab mới `Open Tracker ✉` trong sidebar dashboard v5 — cho Sếp biết CHÍNH XÁC ai mở email,
mở mấy lần, lúc nào. Khi thấy khách HOT → click Follow-up (mở Quick Send pre-filled) hoặc
Preview email cũ đã gửi.

## Architecture

```
Sidebar nav (between Alerts & Queue)
    ↓ click
viewOpenTracker section
    ├─ KPI strip       (GET /api/opens/feed?days=30 → aggregate client-side)
    ├─ Scope toggle    [●30d ○7d ○24h] + Campaign filter
    ├─ Left column:
    │   ├─ HOT Top 20  (GET /api/opens/hot?days=30)
    │   └─ By Campaign (GET /api/opens/by-campaign?days=30)
    └─ Right column:
        └─ Recent Feed (GET /api/opens/feed?limit=50&days=30)
            └─ row click: modal preview (subject + body + sent_at)
            └─ Follow-up button: switch to viewSend + CNEE pre-filled
```

Polling: 60s (match alerts pattern).

## Related Files

### Modify
- `email_engine/web_server.py` — thêm 3 endpoints sau line 1921 (sau `analytics_opens`)
- `plans/visuals/email-dashboard-v5.html` — thêm nav item + section + JS

### Read for context (no edits)
- `email_engine/queue_store.py` — schema reference
- `email_engine/data/outlook_queue.db` — runtime DB

## Implementation Steps

### Step 1 — Backend endpoints (web_server.py)

Thêm 3 endpoint sau `analytics_opens` (line 1921). Dùng raw `sqlite3.connect` vì
`queue_store` chưa expose list query helpers.

**Endpoint 1: Recent feed** — `GET /api/opens/feed?limit=50&days=30`
Returns: list of opens sorted by opened_at DESC. Fields: id, cnee_email, subject,
sent_at, opened_at, open_count, campaign_id.

**Endpoint 2: Hot leaderboard** — `GET /api/opens/hot?limit=20&days=30`
Returns: list grouped by cnee_email, MAX(open_count), MAX(opened_at), filter opens ≥ 2.

**Endpoint 3: By campaign** — `GET /api/opens/by-campaign?days=30`
Returns: list grouped by campaign_id with sent count, opened count, rate_pct.

All 3 return `{"items": [...], "count": N, "generated_at": iso}` for consistency.

### Step 2 — Frontend nav + section (email-dashboard-v5.html)

**Nav item** — chèn sau line 217 (`viewAlerts`), trước `viewQueue`:
```html
<div class="nav-item" data-view="viewOpenTracker">
  <span><span class="nav-icon">✉</span>Open Tracker</span>
  <span class="nav-badge" id="navBadgeOpens">—</span>
</div>
```

**Section** — chèn sau `viewAlerts` section. Structure 3-panel grid:
- Top: KPI strip (4 metrics) + scope toggle + campaign filter
- Bottom: 2-col grid (40% left: hot + campaign, 60% right: feed)

### Step 3 — Frontend JS

Add `loadOpenTracker()` function:
1. Fetch 3 endpoints in parallel (`Promise.all`)
2. Render KPI strip, hot list, campaign bars, feed rows
3. Wire scope toggle → re-fetch with `days=X`
4. Wire row click → `openEmailPreview(jobId)` modal
5. Wire Follow-up button → switch to viewSend + pre-fill CNEE email
6. Badge update: nav badge = count of opens today
7. Polling: `setInterval(loadOpenTracker, 60000)` khi tab active

Modal for preview: reuse existing modal pattern if có, or lightweight inline div.

### Step 4 — Validate

1. Start dev server: `python email_engine/web_server.py`
2. Browser → dashboard
3. Click Open Tracker nav → verify 3 panels load
4. Toggle scope 24h/7d/30d → verify re-fetch
5. Click row → verify modal opens with email content
6. Click Follow-up → verify switches to Quick Send with email prefilled
7. Wait 60s → verify polling refresh

## Todo List

- [ ] 1. Backend: add `/api/opens/feed` endpoint
- [ ] 2. Backend: add `/api/opens/hot` endpoint
- [ ] 3. Backend: add `/api/opens/by-campaign` endpoint
- [ ] 4. Backend: smoke test 3 endpoints via curl
- [ ] 5. Frontend: add nav item `viewOpenTracker`
- [ ] 6. Frontend: add section with 3-panel layout + CSS
- [ ] 7. Frontend: implement `loadOpenTracker()` JS
- [ ] 8. Frontend: wire row click modal (Preview email)
- [ ] 9. Frontend: wire Follow-up button (switch tab + prefill)
- [ ] 10. Frontend: wire scope toggle + polling 60s
- [ ] 11. Manual test all flows in browser
- [ ] 12. Commit + push

## Success Criteria

- Click Open Tracker → 3 panels render trong < 500ms
- Hot list shows CNEE với open_count ≥ 2
- Recent feed shows latest 50 opens
- Campaign bars show open rate % per COMMODITY
- Row click → modal preview works
- Follow-up button → Quick Send tab open với CNEE prefilled
- No console errors, polling 60s stable

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| DB schema không có `subject`/`html_body` column | Verify `queue_store.py` schema trước khi query; fall back nếu thiếu |
| 10K+ opens làm slow query | LIMIT 50 + index on `opened_at` (already unique `opened_at` partial) |
| CNEE email không link với cnee_master | Phase 2 enrich với COMPANY + PIC; Phase 1 ship email-only |
| Modal preview HTML bị XSS | Sanitize subject; render body trong iframe sandbox |

## Out of Scope (Phase 2)
- JOIN với cnee_master_v2_final.xlsx cho COMPANY + PIC + TIER color
- Mark VIP toggle (pin lên đầu)
- Morning Telegram brief 7:00
- A/B subject compare
- Export CSV
- Heatmap giờ-mở
