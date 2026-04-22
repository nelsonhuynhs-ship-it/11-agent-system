# Sprint 2 — O365 Quota + Suppression Auto (5h, Week 2)

**Goal:** Không vượt Microsoft O365 quota. Suppression list auto-clean dài hạn.

**Success:** Zero 429 throttle errors. Suppression list tự maintain không cần Nelson đụng.

**Constraint:** Microsoft đã lo SPF/DKIM/DMARC/IP reputation. Nelson chỉ cần **không làm hại** bằng overload.

## Paradigm shift từ plan cũ

| Plan cũ (wrong) | Plan mới (right) | Lý do |
|-----------------|------------------|-------|
| SPF/DKIM/DMARC validator | ❌ Skipped | Microsoft setup mặc định cho O365, Nelson không có DNS access |
| Manual warmup 50→100→200/day | ❌ Skipped | MS internal reputation cho Exchange mailbox — auto |
| IP reputation monitor | ❌ Skipped | MS shared IP pool, không control được |
| O365 quota tracker | ✅ Added | 10K/day hard limit — cần warn trước khi chạm |
| Auto-throttle 30/min | ✅ Added | 429 errors phá batch flow |
| Soft/hard bounce retry logic | ✅ Kept | Vẫn relevant |

## 2.1 O365 Quota Tracker (2h)

### Microsoft O365 limits (per mailbox)

```
Outbound Recipients:
  30 recipients/minute (burst)
  10,000 recipients/day (hard cap)

Nelson's realistic volume: 2000-5000/week = 285-715/day
→ Quota 10K/day = 14-35x headroom. OK.

Danger: multi-batch close together may hit 30/min burst limit.
```

### Implementation

```python
# email_engine/core/quota_tracker.py
from datetime import datetime, timedelta

class O365Quota:
    DAILY_LIMIT = 10000
    BURST_PER_MIN = 30
    
    def __init__(self, log_csv_path):
        self.log = log_csv_path
    
    def get_sent_today(self) -> int:
        import pandas as pd
        df = pd.read_csv(self.log)
        df['SENT_AT'] = pd.to_datetime(df['SENT_AT'], errors='coerce')
        today = datetime.now().date()
        return (df['SENT_AT'].dt.date == today).sum()
    
    def get_sent_last_minute(self) -> int:
        import pandas as pd
        df = pd.read_csv(self.log)
        df['SENT_AT'] = pd.to_datetime(df['SENT_AT'], errors='coerce')
        cutoff = datetime.now() - timedelta(minutes=1)
        return (df['SENT_AT'] >= cutoff).sum()
    
    def can_send(self, count: int) -> tuple[bool, dict]:
        sent_today = self.get_sent_today()
        sent_last_min = self.get_sent_last_minute()
        
        remaining_today = self.DAILY_LIMIT - sent_today
        remaining_burst = self.BURST_PER_MIN - sent_last_min
        
        if count > remaining_today:
            return False, {
                'reason': 'DAILY_CAP',
                'sent_today': sent_today,
                'limit': self.DAILY_LIMIT,
                'can_send': remaining_today,
            }
        if count > remaining_burst:
            return False, {
                'reason': 'BURST_CAP',
                'sent_last_min': sent_last_min,
                'limit': self.BURST_PER_MIN,
                'wait_seconds': 60,
            }
        
        return True, {
            'sent_today': sent_today,
            'remaining_today': remaining_today,
            'remaining_burst': remaining_burst,
        }
```

### Dashboard widget (Quick Send header)

```html
<div class="kpi" id="qsQuota">
  <div class="kpi-label">Today's Quota</div>
  <div class="kpi-value"><span id="qsQuotaUsed">347</span> / <span id="qsQuotaLimit">10,000</span></div>
  <div class="kpi-foot">
    <progress value="347" max="10000"></progress>
    <span>Burst: <span id="qsBurstUsed">3</span>/30/min</span>
  </div>
</div>
```

Color coding:
- 0-70% → green
- 70-90% → yellow
- 90%+ → red + Telegram alert

### Pre-send gate

In batch_enqueue endpoint:

```python
can, info = quota.can_send(len(filtered_emails))
if not can:
    return {
        'status': 'QUOTA_BLOCKED',
        'reason': info['reason'],
        'message': f"Chạm {info['reason']}: {info.get('sent_today')}/{info.get('limit')}. "
                   f"Chờ {info.get('wait_seconds', 'đến ngày mai')} rồi thử lại.",
        'quota_info': info,
    }
```

## 2.2 Auto-throttle 30 recipients/min (2h)

### Design

Batch send không send all at once → queue with delay:

```python
import time

def dispatch_throttled(emails: list[dict], throttle_per_min: int = 28):
    """Dispatch emails respecting Microsoft burst cap.
    Using 28/min instead of 30/min for safety margin."""
    interval = 60.0 / throttle_per_min  # seconds between sends
    
    for i, email in enumerate(emails):
        send_email_via_outlook_com(email)
        log_send(email)
        
        if i < len(emails) - 1:
            time.sleep(interval)  # 2.14 seconds between sends at 28/min
```

### Alternative: queue-based worker

Instead of blocking send, use existing `outlook_queue_worker.py`:

```python
# Queue with send_at scheduled in future if burst full
def schedule_with_throttle(emails):
    now = datetime.now()
    delay = 60.0 / 28  # seconds per send
    for i, email in enumerate(emails):
        email['send_at'] = now + timedelta(seconds=i * delay)
        queue_store.insert(email)
    # outlook_queue_worker picks up at send_at time
```

**Recommend:** Queue-based — non-blocking, easier to pause/resume.

## 2.3 Suppression Auto-Management (1h)

### Rules (from earlier plan, kept as-is)

```python
def auto_manage_suppression():
    """Daily 05:00 cron."""
    df = load_cnee()
    now = datetime.now()
    
    # Soft bounce → retry sau 3 ngày (server tạm down, có thể back)
    soft_retry_mask = (
        (df['EMAIL_STATUS'] == 'SOFT_BOUNCE') &
        (pd.to_datetime(df['LAST_BOUNCE_AT']) < now - timedelta(days=3))
    )
    df.loc[soft_retry_mask, 'EMAIL_STATUS'] = 'ACTIVE'
    df.loc[soft_retry_mask, 'RETRY_COUNT'] = df.loc[soft_retry_mask, 'RETRY_COUNT'].fillna(0) + 1
    
    # Soft bounce retry 3 lần vẫn fail → promote to HARD_BOUNCE
    promote_mask = (
        (df['EMAIL_STATUS'] == 'SOFT_BOUNCE') &
        (df['RETRY_COUNT'] >= 3)
    )
    df.loc[promote_mask, 'EMAIL_STATUS'] = 'HARD_BOUNCE'
    
    # Hard bounce > 30 ngày → archive + purge khỏi live master
    hard_purge_mask = (
        (df['EMAIL_STATUS'] == 'HARD_BOUNCE') &
        (pd.to_datetime(df['LAST_BOUNCE_AT']) < now - timedelta(days=30))
    )
    archive_path = BASE_DIR / "data" / "suppressed_archive.csv"
    df[hard_purge_mask].to_csv(archive_path, mode='a', header=not archive_path.exists())
    df = df.drop(df[hard_purge_mask].index)
    
    # Save
    save_cnee(df)
    
    return {
        'soft_retry': soft_retry_mask.sum(),
        'promoted_hard': promote_mask.sum(),
        'hard_purged': hard_purge_mask.sum(),
    }
```

### Unsubscribe → keep forever (legal)

No action, stays in master with EMAIL_STATUS=UNSUBSCRIBED.

### Settings UI

```html
<section id="suppressionConfig">
  <h4>⚙ Suppression Auto-Management</h4>
  <label>
    <input type="checkbox" id="cfgAutoSoftRetry" checked>
    Soft bounce → retry sau <input id="cfgSoftRetryDays" value="3" style="width:40px"> ngày
    (max <input id="cfgMaxRetries" value="3" style="width:40px"> lần)
  </label>
  <label>
    <input type="checkbox" id="cfgAutoHardPurge" checked>
    Hard bounce > <input id="cfgHardPurgeDays" value="30" style="width:40px"> ngày → archive
  </label>
  <label>
    <input type="checkbox" checked disabled>
    Unsubscribe → keep forever (legal)
  </label>
  <button class="btn" id="btnRunSuppressionNow">Run Now</button>
  <pre id="suppressionLog" style="margin-top:12px"></pre>
</section>
```

## Files modified/created

| File | Purpose |
|------|---------|
| `email_engine/core/quota_tracker.py` | NEW |
| `email_engine/core/suppression_manager.py` | NEW |
| `scripts/run-suppression-daily.py` | NEW |
| `email_engine/web_server.py` | MODIFY — quota gate, 2 endpoints |
| `plans/visuals/email-dashboard-v5.html` | MODIFY — Quota widget + Suppression settings |

## Success Criteria

- [ ] Quota widget hiển thị real-time used/limit trong Quick Send
- [ ] Zero 429 throttle errors trong batch test (burst 50 emails)
- [ ] Daily cron suppression chạy, Telegram report kết quả
- [ ] Soft bounce retry logic verified (mock SOFT → 3d pass → ACTIVE)
- [ ] Hard purge archive file tạo đúng format

## Risks

| Risk | Mitigation |
|------|-----------|
| Quota widget lag (đọc CSV 22K rows chậm) | Cache 60s TTL |
| Throttle 28/min quá chậm nếu cần urgent bulk | Override flag `skip_throttle` cho power user |
| Auto-purge xoá nhầm email cần giữ | Archive CSV keeps everything, manual unpurge endpoint |
| Soft→Hard promotion sai (email legit nhưng temp server down) | Config max_retries + Telegram digest cho Nelson review |
