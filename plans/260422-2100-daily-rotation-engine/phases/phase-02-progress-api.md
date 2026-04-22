# Phase 2 — Progress Tracking API

**Status:** PENDING
**Effort:** 2h
**File:** `email_engine/api/routes/rotation_router.py`

## Endpoints

### GET /api/rotation/today
Return today's plan + live progress.

Response:
```json
{
  "date": "2026-04-23",
  "target": 700,
  "sent_so_far": 423,
  "pending": 277,
  "status": "in_progress",
  "by_commodity": [
    {"name": "FLOORING", "target": 150, "sent": 100, "pct": 66},
    {"name": "CANDLE", "target": 100, "sent": 80, "pct": 80}
  ],
  "eta_complete": "2026-04-23 14:30"
}
```

### GET /api/rotation/progress
Cumulative progress across ALL data (anchor metric for UI bars).

Response:
```json
{
  "cycle_number": 1,
  "week_in_cycle": 2,
  "weeks_to_finish_cycle": 5.3,
  "by_commodity": [
    {
      "name": "FLOORING",
      "total": 4265,
      "sent_cycle": 1750,
      "remaining": 2515,
      "pct_done": 41.0,
      "days_to_finish": 17
    },
    {"name": "CANDLE", "total": 2187, "sent_cycle": 987, "remaining": 1200, "pct_done": 45.1, "days_to_finish": 12}
  ],
  "grand_total": {"all": 22842, "sent": 4402, "remaining": 18440}
}
```

### GET /api/rotation/history?days=7
Past N days summary.

Response:
```json
{
  "days": [
    {"date": "2026-04-22", "sent": 650, "by_commodity": {"FLOORING": 150, ...}},
    {"date": "2026-04-21", "sent": 700, "by_commodity": {"FLOORING": 150, ...}}
  ],
  "total_week": 3500,
  "avg_per_day": 700
}
```

### POST /api/rotation/quota
Update default quota (Nelson chỉnh UI).

Body:
```json
{"daily_total": 800, "by_commodity": {"FLOORING": 200, ...}}
```

Validates sum(by_commodity) == daily_total.

### POST /api/rotation/run-today
Manually trigger today's batch (bypass scheduler).

### GET /api/rotation/cycle
Return cycle metadata (week #, progress bar global).

## Implementation steps

1. Router skeleton + include vào `web_server.py` (0.5h)
2. 5 endpoints với pandas aggregation (1h)
3. Cache cycle_info 15 phút (0.5h)

## Tests

- GET /api/rotation/today after scheduler run → status correct
- POST /api/rotation/quota invalid sum → 422 error
- GET /api/rotation/progress → pct tính đúng

## Success criteria

- 5 endpoints live
- Response <500ms mỗi call (cached)
- Không lỗi 422 (học từ bug prefix `/api/contacts`)
- Integration với frontend ở Phase 3
