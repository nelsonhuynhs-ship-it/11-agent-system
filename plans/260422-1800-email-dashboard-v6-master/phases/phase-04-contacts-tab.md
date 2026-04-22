# Phase 4 — Contacts Tab UI

**Status:** DONE — 2026-04-22
**Effort:** 4h
**Cost:** $0
**Depends on:** Phase 1, 3

## Overview

Tab 5 Contacts — 2-sheet browser thay thế cách mở Excel. Filter/sort/edit inline. Refresh master with diff preview. Drag-drop Panjiva import. 1-click rollback.

## Files to create

- `email_engine/api/routes/contacts_router.py` — 8 endpoints
- UI trong `plans/visuals/email-dashboard-v6.html` — Tab 5 Contacts

## UI components

```
┌─ TAB HEADER ────────────────────────────────────┐
│ [CNEE (26,431)] [SHIPPER (6,890 HOLD)]          │
├─────────────────────────────────────────────────┤
│ Filters: TIER [HOT▼] COMMODITY [All▼] TZ [All▼] │
│          has_WhatsApp [Any▼] STATE [All▼]       │
├─────────────────────────────────────────────────┤
│ Actions bar:                                    │
│ [🔍 Search] [➕ Add] [📥 Import Panjiva]        │
│ [🔄 Refresh master] [📤 Export] [⏪ Rollback]   │
├─────────────────────────────────────────────────┤
│ Data table (virtualized, 100 rows/page):        │
│ EMAIL | COMPANY | PIC | STATE | TIER | ACTIONS  │
│ ...                                              │
└─────────────────────────────────────────────────┘
```

## API endpoints

- `GET /api/contacts?sheet=CNEE&tier=HOT&page=1` — paginated list
- `GET /api/contacts/:email` — detail
- `PATCH /api/contacts/:email` — edit inline
- `POST /api/contacts` — manual add
- `DELETE /api/contacts/:email` — soft delete (mark dead)
- `POST /api/contacts/refresh-master` — trigger migration + diff preview
- `POST /api/contacts/import-panjiva` — drag-drop raw file
- `POST /api/contacts/rollback` — restore last backup

## Implementation steps

1. `contacts_router.py` 8 endpoints with DuckDB query (2h)
2. Tab 5 HTML + JS pagination + filter (1.5h)
3. Drag-drop Panjiva import flow (0.5h)

## Todo checklist

- [x] 8 endpoints functional
- [x] Tab toggle CNEE/SHIPPER works
- [x] Filter combinations work
- [x] Inline edit saves correctly (honors 5-col LOCK)
- [x] Refresh master shows diff preview before apply
- [x] Rollback 1-click restores backup
- [x] SHIPPER tab shows HOLD badge

## Success criteria

- Nelson có thể làm việc 100% trong dashboard, không cần mở Excel
- Performance: 30K rows virtualized, scroll mượt
- Refresh master with diff preview before commit
