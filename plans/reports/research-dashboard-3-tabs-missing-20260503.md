# Research Report: Email Dashboard — 3 Missing Tabs

**Date:** 2026-05-03 | **Session:** Dashboard v7 gaps research

---

## Executive Summary

Email Dashboard v7 có 3 tab rỗng: **Contacts**, **Followup**, **Insights**. Nghiên cứu trên GitHub repos + industry best practices cho thấy 3 tab này cần features cụ thể để trở thành real intelligence tools. Contacts tab cần searchable/filterable table. Followup cần visual timeline. Insights cần chart components — phổ biến nhất là bar chart cho campaign comparison, line chart cho trends.

---

## Research Sources

- [upstackpilot0710/email-campaign-automation-saas](https://github.com/upstackpilot0710/email-campaign-automation-saas) — Next.js + AG Grid, PostgreSQL + Drizzle ORM, 11 tables
- [NetSendo/NetSendo](https://github.com/NetSendo/NetSendo) — Laravel + Vue.js, MySQL 8.0, enterprise CRM
- Industry: Mailchimp, HubSpot, Apollo.io, Campaign Monitor

---

## Tab 1: Contacts Management

### What industry expects

| Feature | Description |
|---------|-------------|
| **Search + Filter** | Real-time search by name/email/company, filter by campaign/tier/status |
| **Sort** | Multi-column sort (company, last sent, reply status, tier) |
| **Bulk actions** | Select multiple → tag / export / delete |
| **Import/Export** | CSV import với validation preview, CSV export |
| **Tagging** | Tag contacts by source/campaign/tier |
| **Pagination** | Paginate large lists (AG Grid virtual scrolling) |

### Nelson's gap vs industry

Nelson's `viewContacts` (line 663) hiện chỉ có 2 buttons Import/Export. Không có:
- Search table (filter theo company/email)
- Filter dropdown (campaign, tier, country)
- Sort (click header để sort)
- Bulk select checkboxes
- Pagination

### Implementation priority

Contacts tab = **highest priority** vì đây là nơi Sếp review prospect list. Không có search/filter = không work được với 22K contacts.

---

## Tab 2: Follow-up Sequences

### What industry expects

| Feature | Description |
|---------|-------------|
| **Visual timeline** | Step-by-step sequence displayed as horizontal timeline |
| **Step states** | Pending → Done → Skipped (color-coded) |
| **Step timing** | Day 0 (initial), Day 7 (follow-up 1), Day 14 (follow-up 2), Day 30 (final) |
| **Stats per step** | Emails sent / replies / bounces per step |
| **Preview** | Click step → preview email content |
| **Pause/Resume** | Pause sequence for a contact |

### Nelson's gap vs industry

Nelson's `viewFollowup` (line 687) chỉ có 3 KPI numbers. `fuCards` empty. Industry Mailchimp/HubSpot đều có visual sequence builder với timeline.

### Nelson's current follow-up steps (hardcoded at lines 559-563):

```
Step 1: Day 0 — Initial (DONE marker when sent)
Step 2: Day 7 — Follow-up 1 (PENDING)
Step 3: Day 14 — Follow-up 2 (PENDING)
Step 4: Day 30 — Final (PENDING)
```

### Implementation priority

Followup tab = **medium priority**. Nelson có hardcoded follow-up sequence trong Preview tab (line 559-563), nhưng không có dedicated view để track. Cần `sequence_engine` data + render timeline cards.

---

## Tab 3: Insights / Analytics

### What industry expects

| Feature | Chart Type | Description |
|---------|------------|-------------|
| **Reply rate trend** | Line chart | Reply rate over time (7d / 30d / 90d) |
| **Campaign comparison** | Bar chart | Compare sent / opens / bounces across campaigns |
| **Bounce rate gauge** | Gauge/Donut | Current bounce rate with target threshold |
| **Delivery stats** | Simple numbers | Delivered / Inbox / Spam |
| **Top performing campaigns** | Table | Rank campaigns by open rate |

### Nelson's gap vs industry

Nelson's `viewInsights` (line 710) chỉ có 3 KPI numbers (Total Sent, Open Rate, Bounce Rate). Không có chart.

### Data sources available in Nelson's system

- `intel.db email_events` — SENT, REPLY, BOUNCE events với timestamps
- `email_log.csv` — send history
- `contact_unified_v7.xlsx` — REPLY_STATUS per contact

### Implementation priority

Insights tab = **medium-low priority** (vì data đã có, chỉ cần visualize). Có thể dùng simple bar chart library (Chart.js lightweight, no build needed).

---

## Feature Comparison Matrix

| Feature | Nelson v7 Dashboard | upstackpilot SaaS | NetSendo | Mailchimp |
|---------|---------------------|-------------------|----------|-----------|
| Contact search | ❌ | ✅ AG Grid | ✅ CRM | ✅ |
| Contact filter | ❌ | ✅ by city/industry | ✅ by group/tag | ✅ |
| Bulk select | ❌ | ✅ | ✅ | ✅ |
| Import/Export | ✅ (buttons only) | ✅ w/ validation | ✅ | ✅ |
| Follow-up timeline | ❌ | ⚠️ Automations | ⚠️ Workflows | ✅ |
| Follow-up stats | ❌ | ✅ | ✅ | ✅ |
| Reply rate chart | ❌ | ✅ real-time | ✅ | ✅ |
| Bounce rate chart | ❌ | ✅ | ✅ | ✅ |
| Campaign comparison | ❌ | ✅ | ✅ | ✅ |

---

## Implementation Recommendations

### Contacts Tab (Priority 1)

```
Components:
├── Search bar (text input → filter table in real-time)
├── Filter dropdowns (Campaign, Tier, Status)
├── Sortable table (click header → sort ASC/DESC)
├── Bulk checkbox column
└── Pagination (virtual scroll for 22K rows)
```

### Followup Tab (Priority 2)

```
Components:
├── Sequence cards (1 card per active sequence)
│   ├── Campaign name + total contacts
│   ├── Step timeline (horizontal dots)
│   └── Stats per step (sent/replied/bounced)
└── Contact detail panel (click card → drill down)
```

### Insights Tab (Priority 3)

```
Components:
├── Time range selector (7d / 30d / 90d)
├── Reply rate line chart (intel.db query)
├── Bounce rate gauge
├── Campaign comparison bar chart
└── Top campaigns table
```

---

## Libraries to Use

- **Charts**: Chart.js (CDN, no build) — lightweight, good for dashboard
- **Grid/Table**: Native HTML table với JS filter (no AG Grid needed for Nelson's scale)
- **Timeline**: Custom CSS (horizontal stepper design already exists at line 56-61)

---

## Unresolved Questions

1. `sequence_engine.py` có data store cho follow-up steps không? Cần check xem data flow nào cập nhật `fuActive`, `fuPending`, `fuCompleted`
2. `intel.db` có query endpoint cho reply rate trend chưa? Hay cần tạo mới

---

## Next Steps

1. **Build Contacts tab** (highest ROI — 22K contacts không searchable = unusable)
2. **Wire up Followup data** — check `sequence_engine.py` data flow
3. **Add Chart.js** — simple CDN include, render from intel.db queries