# Phase 1 — Rotation Engine Core

**Status:** PENDING
**Effort:** 3h
**File:** `email_engine/core/rotation_engine.py`

## Chức năng

Tính toán daily plan 700 email:
1. Đọc `contact_unified_v6.xlsx` sheet CNEE
2. Filter: SEND_COUNT < 3, LAST_SENT_DATE > 7 ngày trước (hoặc NULL), EMAIL không trong `excluded_customers.json`
3. Group theo COMMODITY_CATEGORY
4. Pick candidates theo quota:
   - FLOORING 150, FURNITURE_INDOOR 150, CANDLE 100, RUBBER 100, PLASTIC 100, others 100
5. Sort mỗi commodity: SEND_COUNT ASC, LAST_SENT_DATE ASC NULLS FIRST
6. Auto-redistribute: nếu commodity không đủ candidate → dồn sang commodity kế
7. Output JSON: today's plan + metadata

## API function

```python
def build_daily_plan(
    target_date: date = None,
    quota_override: dict[str, int] = None,
    cooldown_days: int = 7,
    hard_limit: int = 3,
) -> dict:
    """
    Returns:
    {
        "date": "2026-04-23",
        "target_total": 700,
        "actual_total": 698,
        "by_commodity": {
            "FLOORING": {
                "quota": 150,
                "picked": 150,
                "candidates_remaining": 3500,
                "emails": ["john@abc.com", ...]
            },
            ...
        },
        "redistributed": {"GARMENT": 48},  # under-filled → redistributed
        "cycle_info": {
            "cycle_number": 1,
            "week_in_cycle": 2,
            "weeks_total_estimate": 5.3,
            "total_unsent_remaining": 17740
        }
    }
    """
```

## Implementation steps

1. Helper `_get_eligible_candidates(commodity)` — filter + sort (1h)
2. Helper `_compute_cycle_info()` — progress across weeks (0.5h)
3. Main `build_daily_plan()` — orchestrate + redistribute (1h)
4. Save today's plan → `email_engine/data/daily_plans/YYYY-MM-DD.json` (archive) (0.5h)

## Tests

- Unit test `tests/test_rotation_engine.py`:
  - 10 mock contacts 3 commodity → build plan → verify quota honored
  - Commodity không đủ → redistribute hoạt động
  - 1 email SEND_COUNT=3 → KHÔNG được pick (hard limit)
  - 1 email LAST_SENT < 7 days → KHÔNG được pick (cooldown)

## Default quota config

Stored in `email_engine/config/rotation_quota.json`:
```json
{
  "daily_total": 700,
  "by_commodity": {
    "FLOORING": 150,
    "FURNITURE_INDOOR": 150,
    "CANDLE": 100,
    "RUBBER": 100,
    "PLASTIC": 100,
    "PLYWOOD": 50,
    "FOOD_AMBIENT": 30,
    "OTHERS": 20
  },
  "cooldown_days": 7,
  "hard_limit_count": 3,
  "hard_limit_window_days": 30
}
```

## Success criteria

- `build_daily_plan()` returns plan trong <2 giây
- Output JSON schema đúng
- 4 unit test pass
- Log verbose: `ROTATION: Built plan for 2026-04-23 · target=700 actual=698 redistributed={GARMENT:48}`
