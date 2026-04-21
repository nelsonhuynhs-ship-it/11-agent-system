# Phase 05 — Telegram Integration

**Effort:** 0.5h
**Priority:** MEDIUM
**Status:** pending
**Depends on:** Phase 03, 04

## Overview

Gộp Telegram notifications thành 1 summary message cuối mỗi scan run (không spam từng draft). Reuse existing Telegram module từ `shipment_brain.py`.

## Files Modified

| File | Change |
|------|--------|
| `email_engine/core/cnee_milestone_hook.py` | Buffer alerts, flush cuối scan |
| `email_engine/core/eta_reminder.py` | Same pattern |

## Alert Aggregation Pattern

Thay vì gửi Telegram mỗi lần compose, buffer trong scan run → flush 1 lần cuối:

```python
# Module-level buffer
_alert_buffer = {
    "atd_drafts": [],       # [(customer, bkg), ...]
    "eta7_drafts": [],
    "missing_emails": [],
    "errors": [],
}

def queue_alert(category: str, item):
    _alert_buffer[category].append(item)

def flush_alerts():
    lines = []
    if _alert_buffer["atd_drafts"]:
        lines.append(f"✅ ATD drafts ({len(_alert_buffer['atd_drafts'])}):")
        for cust, bkg in _alert_buffer["atd_drafts"][:5]:
            lines.append(f"  • {cust} / {bkg}")
        if len(_alert_buffer["atd_drafts"]) > 5:
            lines.append(f"  ... +{len(_alert_buffer['atd_drafts']) - 5} more")

    if _alert_buffer["eta7_drafts"]:
        lines.append(f"⏰ ETA-7 drafts ({len(_alert_buffer['eta7_drafts'])}):")
        for cust, bkg in _alert_buffer["eta7_drafts"][:5]:
            lines.append(f"  • {cust} / {bkg}")

    if _alert_buffer["missing_emails"]:
        lines.append(f"⚠ Missing CNEE email ({len(_alert_buffer['missing_emails'])}):")
        for cust, bkg in _alert_buffer["missing_emails"]:
            lines.append(f"  • {cust} / {bkg}")

    if _alert_buffer["errors"]:
        lines.append(f"❌ Errors: {len(_alert_buffer['errors'])}")

    if lines:
        lines.insert(0, "📬 CNEE Milestone Scan Summary")
        lines.append("\nReview drafts in Outlook Drafts folder.")
        send_telegram("\n".join(lines))

    # Reset buffer
    for k in _alert_buffer:
        _alert_buffer[k].clear()
```

## Wire into Scanner Flow

In `outlook_scanner.py` after all jobs complete:

```python
def run_all_jobs():
    for job_name in JOB_ORDER:
        run_job(job_name)

    # 🆕 Flush CNEE milestone alerts
    from email_engine.core.cnee_milestone_hook import flush_alerts
    flush_alerts()
```

## Telegram Message Format Example

```
📬 CNEE Milestone Scan Summary

✅ ATD drafts (3):
  • PANDA HCM / ZIMUHCM80623198
  • SORACHI / ESLVNESAL003948
  • HML / HANG17369900

⏰ ETA-7 drafts (2):
  • VITACOCO / SGN3089986
  • NAFOODS / 6451184790

⚠ Missing CNEE email (1):
  • CREATIVE LIGHT / HANG10341600

Review drafts in Outlook Drafts folder.
```

## Implementation Steps

1. Add `_alert_buffer` module-level dict
2. Replace individual `telegram_alert()` calls with `queue_alert()`
3. Add `flush_alerts()` function
4. Call `flush_alerts()` at end of `run_all_jobs()` in `outlook_scanner.py`
5. Test: trigger multiple events → verify 1 consolidated Telegram message

## Todo List

- [ ] Implement buffer + queue/flush pattern
- [ ] Replace inline telegram calls
- [ ] Wire flush into scanner run
- [ ] Test summary format

## Success Criteria

- [ ] 3 ATD + 2 ETA-7 events → 1 Telegram message tổng kết
- [ ] Missing email cases hiển thị trong summary
- [ ] Không spam Telegram từng draft riêng

## Risks

| Risk | Mitigation |
|------|-----------|
| Buffer leak giữa scan runs | Reset trong flush_alerts() end |
| Message quá dài (>4096 chars Telegram limit) | Truncate at 5 items per category, show count |
| Scan crash trước flush | Try-finally để flush kể cả khi crash |

## Next Phase

Phase 06 — Test + verify với job thật.
