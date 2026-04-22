# Task Plan — Email Dashboard v4 Build

## Overview
| Field | Value |
|-------|-------|
| Task | Build email-dashboard-v4.html (standalone, API-wired) |
| Output | `plans/visuals/email-dashboard-v4.html` |
| Based on | v3 at `plans/visuals/email-dashboard-v3.html` |
| API target | FastAPI :8100 |

## Acceptance Criteria
- [ ] Send Guard: NEVER send email if no valid rate/POD/POL — rows locked visually
- [ ] Bulk select: Select 50 / Select All Filtered / drag-select
- [ ] Filter contrast fix: dark bg readable
- [ ] VirtualList: 5,000+ contacts render at 60fps
- [ ] 5 tabs: Send, Analytics, AI Model, Alerts, Queue
- [ ] API client layer: all fetch calls use CONFIG.apiBase
- [ ] Module pattern: readable sections with clear separators
- [ ] Opens in browser as standalone HTML (no server needed for UI)

## Phases

| Phase | Scope | Agent | Status |
|-------|-------|-------|--------|
| 1 | Foundation: CSS tokens + HTML skeleton + API + Guard + VLIST | architect | pending |
| 2 | Quick Send tab: rate table + bulk select + send flow | tab-send | pending |
| 3 | Analytics + AI Model tabs | tab-analytics | pending |
| 4 | Alerts + Queue tabs | tab-alerts-queue | pending |
| 5 | Polish: keyboard shortcuts + animations + resize handle | polisher | pending |

## Errors Encountered
| Phase | Error | Resolution |
|-------|-------|-----------|
| — | — | — |
