# Phase 4 — Daily Scheduler + Manual Trigger

**Status:** PENDING
**Effort:** 1h

## Chức năng

- Mỗi sáng 8:00 AM → auto-build daily plan + queue
- Nelson có thể manual trigger nếu lỡ miss
- Skip weekend (Sat/Sun)

## Implementation

### Option 1 — Windows Task Scheduler (RECOMMEND)

Script `scripts/daily-rotation-trigger.bat`:
```batch
@echo off
cd /d "D:\NELSON\2. Areas\Engine_test"
python -c "from email_engine.core.rotation_engine import build_daily_plan, queue_to_outlook_worker; plan = build_daily_plan(); queue_to_outlook_worker(plan)"
```

Register task:
```powershell
schtasks /Create /TN "NelsonEmailRotation" /TR "D:\NELSON\2. Areas\Engine_test\scripts\daily-rotation-trigger.bat" /SC DAILY /ST 08:00 /RU Nelson
```

### Option 2 — In-process scheduler

APScheduler trong `web_server.py`:
```python
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(daily_rotation_job, 'cron', hour=8, minute=0, day_of_week='mon-fri')
scheduler.start()
```

Prefer Option 1 — simple, không cần keep Python running 24/7.

## Manual trigger UI

Button `[▶ Start batch]` đã plan ở Phase 3 → call POST /api/rotation/run-today.

## Telegram notification

Sau khi scheduler run (8:05 AM):
```python
from scripts.notify_telegram import send
send(f"📅 Daily rotation ready: {plan['actual_total']} emails queued ({date})")
```

## Holiday skip

Đã có `us_holidays.py` từ Phase 2. Extend thêm `vn_holidays`:
- Tết Nguyên Đán
- Lễ 30/4 – 1/5
- Quốc Khánh 2/9

Nếu hôm đó là holiday → skip, log `ROTATION_SKIP_HOLIDAY`.

## Implementation steps

1. Script `daily-rotation-trigger.bat` (15 min)
2. Register Windows Task Scheduler (5 min)
3. Telegram notify hook (15 min)
4. VN holiday wrapper (15 min)
5. Test manual run (10 min)

## Success criteria

- 8:00 AM tomorrow → scheduler runs → Telegram notify
- Skip Sat/Sun
- Skip VN holiday
- Manual trigger button works end-to-end
