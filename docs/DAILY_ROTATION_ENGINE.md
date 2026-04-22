# Daily Rotation Engine — Module Documentation

**Last updated:** 2026-04-22 23:00
**Status:** ✅ VERIFIED LIVE (Phase 1 complete, batch ROT_1776868843 validated)
**Module:** `email_engine/core/rotation_engine.py` + `rotation_helpers.py`
**Plan:** `plans/260422-2100-daily-rotation-engine/`

---

## Purpose

Automate daily email send planning for 22,842 CNEE prospects:
- Spread 700 emails/weekday across 8 commodity categories
- Enforce cooldown (7d), hard limit (3/30d), and excluded list
- Support unlimited rotation cycles (5.3 weeks per cycle currently estimated)
- Preview daily plan + auto-redistribute quota when commodities have insufficient candidates

---

## Quick Start

### Endpoint: GET /api/rotation/today

**Returns today's rotation plan as JSON.**

```bash
curl http://localhost:8100/api/rotation/today
```

Example response:
```json
{
  "date": "2026-04-23",
  "target_total": 700,
  "actual_total": 698,
  "by_commodity": {
    "FLOORING": {
      "quota": 150,
      "picked": 150,
      "candidates_remaining": 3500,
      "emails": ["john@flooring.com", "jane@hardwood.com", ...]
    },
    "GARMENT": {
      "quota": 20,
      "picked": 18,
      "candidates_remaining": 95,
      "emails": [...]
    }
  },
  "redistributed": {
    "APPAREL": 2,
    "ELECTRONICS": 8
  },
  "cycle_info": {
    "cycle_number": 1,
    "week_in_cycle": 2,
    "weeks_total_estimate": 5.3,
    "total_unsent_remaining": 17740
  }
}
```

---

## Core API

### build_daily_plan()

**Signature:**
```python
def build_daily_plan(
    target_date: Optional[date] = None,
    quota_override: Optional[dict[str, int]] = None,
    cooldown_days: Optional[int] = None,
    hard_limit: Optional[int] = None,
) -> dict[str, Any]:
```

**Parameters:**
- `target_date` — Plan for specific date (default: today). SKIP weekends/holidays automatically.
- `quota_override` — Temporary quota override (e.g., `{"FLOORING": 200, "CANDLE": 50}`)
- `cooldown_days` — Override default cooldown (default: 7)
- `hard_limit` — Override hard send limit (default: 3/30d)

**Returns:**
```python
{
    "date": "2026-04-23",
    "target_total": 700,
    "actual_total": 698,
    "by_commodity": {
        "COMMODITY_X": {
            "quota": int,
            "picked": int,
            "candidates_remaining": int,
            "emails": [list of email addresses]
        },
        ...
    },
    "redistributed": {"COMMODITY_Y": deficit_count, ...},
    "cycle_info": {
        "cycle_number": int,
        "week_in_cycle": int,
        "weeks_total_estimate": float,
        "total_unsent_remaining": int
    },
    "skipped_reason": None  # or string if weekend/holiday
}
```

**Raises:**
- `FileNotFoundError` — If master contact file missing

**Example:**

```python
from email_engine.core.rotation_engine import build_daily_plan
from datetime import date

# Today's plan
plan = build_daily_plan()

# Specific date with override
plan = build_daily_plan(
    target_date=date(2026, 4, 25),
    quota_override={"FLOORING": 200}  # temp boost
)

# Print commodity breakdown
for commodity, data in plan["by_commodity"].items():
    print(f"{commodity}: {data['picked']}/{data['quota']}")
```

---

## Configuration

### rotation_quota.json

**Path:** `email_engine/config/rotation_quota.json`

**Schema:**
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
  "hard_limit_window_days": 30,
  "_comment": "Sum by_commodity must == daily_total"
}
```

**Rules:**
- Sum `by_commodity` must equal `daily_total` (validation enforced)
- Minimum cooldown: 7 days (non-negotiable per system standards)
- Hard limit: max 3 sends per 30-day rolling window

**Edit via API:**
```bash
POST /api/rotation/quota -H "Content-Type: application/json" \
  -d '{"FLOORING": 180, "CANDLE": 80}'
```

---

## Internal Architecture

### Helper Functions (rotation_helpers.py)

**load_quota_config() → dict**
- Reads `rotation_quota.json`
- Returns dict with keys: `daily_total`, `by_commodity`, `cooldown_days`, `hard_limit_count`, `hard_limit_window_days`
- Fallback: built-in defaults if file missing

**load_master_df() → pd.DataFrame**
- Reads `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx` sheet "CNEE"
- Column names auto-uppercase
- Raises `FileNotFoundError` if file missing

**load_excluded_emails() → set[str]**
- Reads `email_engine/data/excluded_customers.json`
- Returns set of lowercase excluded emails
- Returns empty set if file missing or JSON error

**_get_eligible_candidates(df, commodity, excluded, cd_days, hl_count, hl_window, today) → pd.DataFrame**
- Filter master df:
  1. Match COMMODITY_CATEGORY (case-insensitive)
  2. EMAIL not in excluded set
  3. EMAIL_STATUS != SUPPRESSED/DEAD/HOLD
  4. LAST_SENT_DATE is NULL OR (today - LAST_SENT_DATE) >= cooldown_days
  5. SEND_COUNT < hard_limit OR hasn't reached 3 sends in last 30d
- Sort: SEND_COUNT ASC, LAST_SENT_DATE ASC NULLS FIRST
- Return DataFrame of eligible rows

**_compute_cycle_info(df_unsent) → dict**
- Estimate rotation cycle duration (weeks)
- Formula: (unsent_count / 3500) * 5.3 (rough estimate)
- Return cycle_number, week_in_cycle, weeks_total_estimate, total_unsent_remaining

---

## Data Flow

```
Input: today's date (default: date.today())
       ↓
1. Check: is weekend or VN/US holiday?
   YES → return _empty_plan(reason="Saturday") with skipped_reason
   NO  → continue
       ↓
2. load_quota_config() → cfg dict
   Apply any override args (quota_override, cooldown_days, hard_limit)
       ↓
3. load_master_df() → full contact list
       ↓
4. load_excluded_emails() → set of blocked emails
       ↓
5. For each commodity in cfg["by_commodity"]:
   a. _get_eligible_candidates(df, commodity, ...) → candidates DataFrame
   b. Sample top N rows per quota
   c. Track deficit if candidates < quota
   d. Append to by_commodity result
       ↓
6. Redistribute deficits:
   - FLOORING needs 150, only 145 available → deficit 5
   - GARMENT has 40 available but only needs 20 → surplus 20
   - Cascade redistribute surplus to next commodity
       ↓
7. _compute_cycle_info(remaining_unsent) → cycle metadata
       ↓
8. Save plan JSON → email_engine/data/daily_plans/YYYY-MM-DD.json
       ↓
Output: full rotation plan dict
```

---

## Filtering Logic (5 Layers)

Applied in `_get_eligible_candidates()`:

| Layer | Check | Code |
|-------|-------|------|
| 1. COMMODITY | COMMODITY_CATEGORY match (case-insensitive) | `df["COMMODITY_CATEGORY"].str.upper() == commodity.upper()` |
| 2. EXCLUDED | NOT in excluded_emails set | `email.lower() not in excluded` |
| 3. STATUS | EMAIL_STATUS not SUPPRESSED/DEAD/HOLD | Filter by enum |
| 4. COOLDOWN | LAST_SENT_DATE is NULL or ≥7d ago | Check date arithmetic |
| 5. HARD LIMIT | SEND_COUNT <3 AND <3 sends in last 30d | Check rolling window |

**Logging:**
```
ROTATION: Commodity FLOORING → 4500 eligible, 150 quota, 3500 remaining
ROTATION: Commodity GARMENT → 20 eligible, 20 quota, 0 remaining (deficit 10)
ROTATION: Redistributed GARMENT deficit 10 → APPAREL
```

---

## Holiday Skip Logic

**Weekend:** Saturday/Sunday → skip, return empty plan with `skipped_reason="Weekend (Saturday)"`

**US Holidays:** (via `us_holidays.py`)
- New Year's Day, MLK Jr. Day, Presidents' Day, Memorial Day, Independence Day, Labor Day, Columbus Day, Veterans Day, Thanksgiving, Christmas Day
- Triggered by `is_us_holiday(date)` check

**VN Holidays:** (via `vn_holidays.py`)
- Tết Lunar New Year (5-day block)
- 30/4 (Reunification Day)
- 2/9 (National Day)
- Triggered by `is_vn_holiday(date)` check

---

## Quota Auto-Redistribution

**Scenario:**

```
Config: FLOORING=150, GARMENT=20, APPAREL=10
Master: FLOORING=145 eligible, GARMENT=30 eligible, APPAREL=5 eligible

Step 1: Pick FLOORING 150 → only 145 available → pick 145, deficit=5
Step 2: Pick GARMENT 20 → have 30 available → pick 20, surplus=10
Step 3: Pick APPAREL 10 → only 5 available → pick 5, deficit=5

Redistribution:
  GARMENT surplus 10 → fill FLOORING deficit 5 → remaining 5 → fill APPAREL deficit 5
  Final: FLOORING=150, GARMENT=20, APPAREL=10, total=180 (expected)
```

**Code:**
```python
# Pseudo-code
for commodity, quota in quota_map.items():
    candidates = _get_eligible_candidates(...)
    picked = min(len(candidates), quota)
    deficit = quota - picked
    deficits[commodity] = deficit

for commodity, deficit in deficits.items():
    if deficit > 0:
        for donor_commodity, donor_deficit in deficits.items():
            if donor_deficit < 0:  # surplus
                transfer = min(abs(donor_deficit), deficit)
                candidates[commodity].extend(candidates[donor_commodity][-transfer:])
                redistributed[commodity] += transfer
                deficit -= transfer
```

---

## Testing

### Unit Test (tests/test_rotation_engine.py)

```bash
pytest tests/test_rotation_engine.py -v
```

**Test cases:**
1. `test_build_daily_plan_basic` — Happy path, 3 commodities
2. `test_hard_limit_enforcement` — Email with SEND_COUNT=3 excluded
3. `test_cooldown_enforcement` — Email sent 3 days ago skipped
4. `test_redistribution` — Commodity deficit cascades
5. `test_weekend_skip` — Saturday → empty plan
6. `test_holiday_skip_us` — July 4 → empty plan
7. `test_holiday_skip_vn` — Feb 10 (Tết) → empty plan
8. `test_quota_override` — Temporary override respected
9. `test_cycle_info` — Progress calculation correct

---

## Integration with Web Server

### Endpoint: GET /api/rotation/today

In `email_engine/web_server.py`:

```python
@app.get("/api/rotation/today")
async def get_today_plan():
    plan = build_daily_plan()
    return plan
```

### Endpoint: POST /api/rotation/run-today

Queue today's plan emails for sending:

```python
@app.post("/api/rotation/run-today")
async def run_today_plan():
    plan = build_daily_plan()
    queued_count = 0
    for commodity, data in plan["by_commodity"].items():
        for email_addr in data["emails"]:
            # smart_send_window.plan_send_time()
            # outlook_queue_worker.queue(email_addr, send_time_utc)
            queued_count += 1
    return {"queued": queued_count, "plan": plan}
```

---

## Logging & Monitoring

**Log file:** `email_engine/logs/rotation_YYYY-MM-DD.log`

**Levels:**
```
INFO:  ROTATION: Built plan for 2026-04-23 · target=700 actual=698
WARN:  ROTATION: Commodity GARMENT insufficient (10 short)
ERROR: ROTATION: Master file not found at D:/OneDrive/...
```

**Dashboard widget (email-dashboard-v6.html):**
- Commodity progress bars (X/Y sent)
- "Cycle: 1 · Week 2/5" indicator
- "Yesterday: 650 sent · Today: 700 planned"
- Restart/pause button

---

## Performance

**Speed targets:**
- `load_master_df()`: <1s (22K rows cached)
- `build_daily_plan()`: <2s total
- Filtering: O(n) per commodity, parallelizable

**Current benchmarks (22,230 CNEE):**
- Load+Filter: ~0.8s
- Sort+Pick: ~0.3s
- Redistribute: ~0.1s
- **Total: ~1.2s**

---

## Troubleshooting

### Plan returns empty

**Cause 1:** Today is weekend/holiday
- Check `skipped_reason` in response

**Cause 2:** All commodities exhausted
- Check `total_unsent_remaining` in cycle_info

**Cause 3:** Master file missing
- Verify `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx` exists
- Check OneDrive sync status

### Quota override not applied

**Check:** API call syntax
```bash
# WRONG: plain number
POST /api/rotation/quota -d '{"FLOORING": 150}'

# CORRECT: dict format
POST /api/rotation/quota -d '{"by_commodity": {"FLOORING": 150}}'
```

### Redistribution mismatch

**Verify:** Sum of `actual_total` ≠ target
- Check `redistributed` dict for transfers
- Ensure no rounding errors

---

## Known Issues & Fixes

### Bug Fix 2026-04-22 22:50 — queue_to_outlook_worker integration

**Issue:** `queue_to_outlook_worker()` function in `rotation_engine.py` only logged emails instead of inserting them into the `email_queue` table.

**Root causes:**
1. Function called `queue_store.enqueue_batch()` but code was missing (commented out or skipped)
2. Import path `from auto_rate_builder` was incorrect → should be `from email_engine.core.auto_rate_builder`
3. Rate table builder was called 700 times per batch (once per email) instead of once per unique lane

**Fix applied:**
1. Wired actual `queue_store.enqueue_batch()` call with proper email subject + HTML body from `auto_rate_builder.build_rate_table_for_customer()`
2. Implemented lane-level grouping: group emails by `(pol, destinations)` unique pairs before calling rate builder
3. Corrected import to `from email_engine.core.auto_rate_builder import build_rate_table_for_customer`
4. Verified batch ROT_1776868843 (700 emails) — **700/700 SENT, 0 failed**

**Verification log:**
```
2026-04-22 22:47:30 — ROTATION: queued batch ROT_1776868843 (700 emails, 8 commodity groups)
2026-04-22 22:52:15 — ROTATION: batch ROT_1776868843 completed → 700 SENT, 0 FAILED
ROTATION: Grouped into 24 unique lanes, called rate builder 24 times (1 per lane vs 700 before fix)
```

---

## Performance Optimization

### Caching layers (2026-04-22 23:00)

Added 3 module-level TTL caches in `email_engine/api/routes/rotation_router.py` to reduce database queries on repeated plan checks:

| Cache | TTL | Target |
|-------|-----|--------|
| `_today_cache` | 30s | `GET /api/rotation/today` response JSON |
| `_progress_cache` | 60s | Commodity progress bars + cycle info |
| `_cycle_cache` | 300s | Cycle metadata (weeks remaining, unsent count) |

**Invalidation:** All 3 caches reset via `_invalidate_caches()` when `POST /api/rotation/run-today` completes.

**Performance impact:** Measured latency on cached hit is still 1–2s (likely database lock contention from concurrent worker threads). Further debugging needed in future session.

**Known limitation:** Cache TTL tuning not yet optimized for peak load — may need adjustment after monitoring 2–3 days of live usage.

---

## Related Modules

- `email_engine/core/smart_send_window.py` — Schedule send time per timezone
- `email_engine/core/typo_shield.py` — Validate email before queue
- `email_engine/core/bounce_harvest_v2.py` — Auto-classify replies
- `email_engine/core/auto_rate_builder.py` — Generate rate table HTML per customer (called by rotation queue)
- `email_engine/web_server.py` — FastAPI endpoints
- `docs/SYSTEM_STANDARDS.md` Section 6.5 — Anti-spam rules

---

## Future Enhancements

- [ ] Predictive modeling: prioritize high-engagement commodities
- [ ] A/B testing: dynamic quota split for open rate optimization
- [ ] Multi-channel: extend beyond email to SMS/WhatsApp
- [ ] Smart scheduler: queue emails per timezone distribution
