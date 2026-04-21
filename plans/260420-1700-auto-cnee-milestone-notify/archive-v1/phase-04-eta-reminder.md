# Phase 04 — ETA-7 Daily Reminder

**Effort:** 1h
**Priority:** MEDIUM
**Status:** pending
**Depends on:** Phase 02

## Overview

New scanner job `eta_reminder_daily` — runs once per day at 08:00, loops Active Jobs, finds jobs with ETA - today = 7, composes ETA-7 draft.

## Files Modified

| File | Change |
|------|--------|
| `email_engine/core/eta_reminder.py` | NEW — daily job handler |
| `email_engine/core/outlook_scanner.py` | Register new job handler |
| `email_engine/core/scanner_rules.json` | Add `eta_reminder_daily` entry |

## Scanner Rules Config

Add to `scanner_rules.json`:

```json
"eta_reminder_daily": {
    "enabled": true,
    "description": "Daily 08:00 — check Active Jobs for ETA - 7 days, compose reminder drafts",
    "timeout_seconds": 180,
    "notify_on_error": true,
    "schedule_override": {
        "hour": 8,
        "minute": 0
    },
    "_note": "Only runs once/day at 08:00. Idempotent via LAST_NOTIFIED."
}
```

## Job Handler

`email_engine/core/eta_reminder.py`:

```python
from datetime import date, timedelta
from email_engine.core.cnee_milestone_composer import (
    MilestoneType, MilestoneContext, compose_draft
)

def run_eta_reminder():
    jobs = load_active_jobs()
    today = date.today()
    target = today + timedelta(days=7)

    composed_count = 0
    for job in jobs:
        eta = parse_date(job.get("ETA"))
        if not eta or eta != target:
            continue

        customer = job["CUSTOMER"]
        if not crm_auto_notify_enabled(customer):
            continue

        # Dedup
        last_notified = job.get("LAST_NOTIFIED", "")
        if "ETA-7" in last_notified:
            continue

        # Email
        cnee_email = lookup_cnee_email(customer, job["BKG"])
        if not cnee_email:
            telegram_alert(f"⚠ Missing CNEE email for ETA-7: {customer} / {job['BKG']}")
            continue

        # Compose
        ctx = build_context_from_job(job)
        result = compose_draft(MilestoneType.ETA_7, ctx, cnee_email)

        if result["success"]:
            new_log = f"{last_notified} | ETA-7 {today.isoformat()}".strip(" |")
            update_active_job(job["BKG"], {"LAST_NOTIFIED": new_log})
            composed_count += 1

    if composed_count:
        telegram_alert(f"✅ ETA-7 drafts ready: {composed_count}")
    return composed_count
```

## Register in outlook_scanner.py

Add handler mapping:

```python
# In outlook_scanner.py
def run_eta_reminder_daily():
    """Run daily ETA-7 reminder check."""
    try:
        from email_engine.core.eta_reminder import run_eta_reminder
        count = run_eta_reminder()
        log.info("ETA-7 scan completed: %d drafts", count)
    except Exception as e:
        log.error("ETA-7 reminder failed: %s", e, exc_info=True)

JOB_HANDLERS = {
    # existing ...
    "eta_reminder_daily": run_eta_reminder_daily,
}
```

## Schedule Override Logic

`outlook_scanner.py` needs to respect `schedule_override`:

```python
def should_run_job(job_name, job_config):
    override = job_config.get("schedule_override")
    if override:
        now = datetime.now()
        if "hour" in override and now.hour != override["hour"]:
            return False
        if "minute" in override and not (override["minute"] <= now.minute < override["minute"] + 30):
            return False
        # Check if already ran today
        last_run = get_last_run(job_name)
        if last_run and last_run.date() == now.date():
            return False
    return True
```

## Implementation Steps

1. Write `eta_reminder.py` with main loop
2. Add `run_eta_reminder_daily` handler to `outlook_scanner.py`
3. Add config entry to `scanner_rules.json`
4. Implement `schedule_override` + `should_run_job` logic
5. Track `last_run` via `scanner_state.json`
6. Test: manually set job ETA = today + 7 → run handler → verify draft

## Todo List

- [ ] Write `eta_reminder.py`
- [ ] Add handler to `outlook_scanner.py`
- [ ] Update `scanner_rules.json`
- [ ] Implement schedule_override logic
- [ ] Implement last_run tracking
- [ ] Test with manual ETA=today+7
- [ ] Verify idempotent (run 2x → 1 draft)

## Success Criteria

- [ ] Job chạy 1 lần/ngày lúc 08:00
- [ ] Compose draft cho job có ETA-today=7 + AUTO_NOTIFY=✅
- [ ] Skip job đã notify ETA-7 trước đó
- [ ] LAST_NOTIFIED append đúng format
- [ ] Telegram báo sau scan run

## Risks

| Risk | Mitigation |
|------|-----------|
| Scanner chạy nhiều lần/ngày | `last_run` tracking + date check |
| ETA col empty | Skip silent |
| Timezone issues | Use local time (Asia/Ho_Chi_Minh) |
| Date parse fail | Log + skip job |

## Next Phase

Phase 05 — Telegram integration polish.
