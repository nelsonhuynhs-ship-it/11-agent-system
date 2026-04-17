# Findings — Email Dashboard v4

## v3 Structure (3,086 lines)
- 3 tabs: quickSendView, historyView, aiModelView
- Nav items: Quick Send, Analytics/History, AI Model
- JS: ~1,100 lines vanilla JS (no modules), all global functions
- CSS: ~1,400 lines inline, dark palette --bg:#07090f

## v3 Pain Points Confirmed
1. Send guard missing — sends even with no rate found
2. No bulk select (must tick each row)
3. Filter dropdown bị bôi trắng trên dark bg
4. No Follow-up Queue tab
5. Analytics = mock data only
6. No rate-change alerts

## API Endpoints (FastAPI :8100)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/rates | GET | Load rate table by campaign/pol/dest |
| /api/email/send-bulk | POST | Batch email send |
| /api/email-log | GET | Email send history |
| /api/follow-up-queue | GET | Follow-up queue |

## Skill Match
- `web-artifacts-builder` — self-contained HTML artifacts ✅ PRIMARY
- `frontend-development` — JS module patterns ✅
- `ui-styling` — CSS design system ✅

## Design Decisions
- Single HTML file, no build step
- JS type="module" with explicit layer objects (CONFIG, API, GUARD, STORE, VLIST, UI.*)
- VirtualList for contact rows (only render visible rows)
- Send Guard validates before checkbox is even enabled
- API_BASE = 'http://localhost:8100' — configurable at top of file
