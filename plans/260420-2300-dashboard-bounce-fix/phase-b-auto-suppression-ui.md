# Phase B — Auto Suppression + Counter UI + Cooldown Dedup

**Effort:** 2h (thêm 0.5h cho cooldown)
**Priority:** HIGH (bảo vệ reputation, transparency, chống spam)
**Status:** pending
**Depends on:** Phase A (for Settings tab to show full bounced list)

## Overview

Quick Send tự filter **3 loại email**:
1. **Suppressed (permanent):** `EMAIL_STATUS IN ('HARD_BOUNCE', 'UNSUBSCRIBED')`
2. **Cooldown (temporary):** email đã gửi trong N ngày gần đây — chống spam chính khách cũ
3. **Soft retry (future):** soft bounce — retry sau 3 ngày

Hiển thị counter breakdown "Suppressed: X (bounce · unsub · cooldown)" + Settings tab có bảng list + slider điều chỉnh cooldown days.

## Cooldown Requirement (mới add)

**Use case thực tế:**
> Anh chọn FLOORING batch 200 → gửi xong. Lát sau chọn FLOORING batch 200 nữa → hệ thống PHẢI tự bỏ các email đã gửi batch 1, chỉ gửi cho email chưa gửi.

**Logic:**
```python
COOLDOWN_DAYS = 14  # default, configurable in Settings
# Skip email if: LAST_SENT_AT + COOLDOWN_DAYS > today
```

**Data source:** `email_engine/logs/email_log.csv` (đã có sẵn cột SENT_AT per email/campaign/batch)

## Files Modified

## Files Modified

### 1. `email_engine/web_server.py` — new suppression endpoint

```python
@app.get("/api/suppression/list")
def suppression_list(limit: int = 500):
    """Return list of emails suppressed due to bounces/unsubs."""
    try:
        import pandas as pd
        path = BASE_DIR / "data" / "cnee_master_v2.xlsx"
        df = pd.read_excel(path)
        mask = df['EMAIL_STATUS'].isin(['HARD_BOUNCE', 'SOFT_BOUNCE', 'UNSUBSCRIBED'])
        sup = df[mask].copy()
        sup = sup[['EMAIL', 'COMPANY', 'EMAIL_STATUS', 'LAST_BOUNCE_AT', 'LAST_BOUNCE_SEVERITY']]
        sup = sup.fillna('').to_dict('records')
        return {"suppressed": sup[:limit], "total": len(sup)}
    except Exception as e:
        return {"suppressed": [], "total": 0, "error": str(e)}


@app.post("/api/suppression/unsuppress")
def suppression_unsuppress(email: str):
    """Manually clear EMAIL_STATUS for 1 email (anh unsuppress)."""
    try:
        import pandas as pd
        path = BASE_DIR / "data" / "cnee_master_v2.xlsx"
        df = pd.read_excel(path)
        mask = df['EMAIL'].str.lower().str.strip() == email.lower().strip()
        df.loc[mask, 'EMAIL_STATUS'] = 'ACTIVE'
        df.to_excel(path, index=False)
        return {"ok": True, "updated": int(mask.sum())}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

### 2. Quick Send pipeline filter (Suppression + Cooldown)

In `email_engine/core/send_email.py` (or wherever Quick Send batch dispatch lives):

```python
from datetime import datetime, timedelta

SUPPRESSION_STATUSES = {'HARD_BOUNCE', 'UNSUBSCRIBED'}
# SOFT_BOUNCE NOT in this set — retry logic handles
DEFAULT_COOLDOWN_DAYS = 14  # configurable via Settings


def _load_recent_sends(cooldown_days: int) -> set[str]:
    """Return set of emails sent within last cooldown_days (from email_log.csv)."""
    import pandas as pd
    log_path = BASE_DIR / "logs" / "email_log.csv"
    if not log_path.exists():
        return set()
    try:
        df = pd.read_csv(log_path, usecols=['EMAIL', 'SENT_AT'], low_memory=False)
        df['SENT_AT'] = pd.to_datetime(df['SENT_AT'], errors='coerce')
        cutoff = datetime.now() - timedelta(days=cooldown_days)
        recent = df[df['SENT_AT'] >= cutoff]['EMAIL'].str.lower().str.strip()
        return set(recent.dropna().tolist())
    except Exception as e:
        log.warning(f"load recent sends failed: {e}")
        return set()


def filter_suppressed(
    cnee_emails: list[str],
    cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
    skip_cooldown: bool = False,
) -> tuple[list[str], dict]:
    """Split cnee_emails into (allowed, stats).
    
    Filters in order:
    1. Permanent suppression (HARD_BOUNCE / UNSUBSCRIBED from cnee_master_v2)
    2. Cooldown (sent within cooldown_days days)
    """
    import pandas as pd
    path = BASE_DIR / "data" / "cnee_master_v2.xlsx"
    df = pd.read_excel(path, usecols=['EMAIL', 'EMAIL_STATUS'])
    df['EMAIL'] = df['EMAIL'].str.lower().str.strip()
    status_lookup = dict(zip(df['EMAIL'], df['EMAIL_STATUS'].fillna('ACTIVE')))
    
    recent_set = set() if skip_cooldown else _load_recent_sends(cooldown_days)
    
    allowed = []
    suppressed = {'HARD_BOUNCE': 0, 'UNSUBSCRIBED': 0, 'SOFT_BOUNCE': 0, 'COOLDOWN': 0}
    cooldown_sample = []  # first 5 for debug visibility
    
    for email in cnee_emails:
        e = email.lower().strip()
        status = status_lookup.get(e, 'ACTIVE')
        if status in SUPPRESSION_STATUSES:
            suppressed[status] = suppressed.get(status, 0) + 1
            continue
        if e in recent_set:
            suppressed['COOLDOWN'] += 1
            if len(cooldown_sample) < 5:
                cooldown_sample.append(e)
            continue
        allowed.append(email)
    
    return allowed, {
        'total_input': len(cnee_emails),
        'allowed': len(allowed),
        'suppressed_total': sum(suppressed.values()),
        'by_type': suppressed,
        'cooldown_days': cooldown_days,
        'cooldown_sample': cooldown_sample,
    }


# In Quick Send endpoint, before dispatch:
filtered_emails, stats = filter_suppressed(
    recipient_emails,
    cooldown_days=request.get('cooldown_days', DEFAULT_COOLDOWN_DAYS),
    skip_cooldown=request.get('skip_cooldown', False),
)
log.info(f"Quick Send filter: {stats}")
return {
    "queued": len(filtered_emails),
    "suppression_stats": stats,  # UI shows counter
    ...
}
```

**Scenario check (Nelson's use case):**
- 10:00 AM: chọn FLOORING batch 200 → `filter_suppressed(200 emails)` → 200 allowed → all SENT, log email_log.csv
- 10:30 AM: chọn lại FLOORING batch 200 → `filter_suppressed(200 emails)` → 195 trong cooldown → 5 allowed
- Response: `{queued: 5, suppression_stats: {by_type: {COOLDOWN: 195, HARD_BOUNCE: 0}}}`
- Toast: "Skipped 195 (195 cooldown · 0 bounce) — gửi 5"

### 3. Dashboard UI — `plans/visuals/email-dashboard-v5.html`

**Quick Send — add counter badge + cooldown control:**
```html
<!-- In Quick Send header, after existing counter -->
<div class="kpi" id="qsSuppression" style="display:none">
  <div class="kpi-label">Skipped</div>
  <div class="kpi-value" id="qsSuppressedCount">0</div>
  <div class="kpi-foot">
    <span id="qsSuppressedBreakdown">—</span>
  </div>
</div>

<!-- Cooldown control (next to Send button) -->
<label style="display:inline-flex;align-items:center;gap:4px;font-size:12px;margin-left:8px">
  Cooldown: <input type="number" id="qsCooldownDays" value="14" min="0" max="90" style="width:50px"> days
  <input type="checkbox" id="qsSkipCooldown"> bỏ qua cooldown
</label>
```

Quick Send submit — include cooldown params:
```javascript
const cooldownDays = parseInt(document.getElementById('qsCooldownDays').value || 14);
const skipCooldown = document.getElementById('qsSkipCooldown').checked;
const payload = { ..., cooldown_days: cooldownDays, skip_cooldown: skipCooldown };
const result = await api('/api/quick-send/batch', { method: 'POST', body: JSON.stringify(payload) });

if (result.suppression_stats) {
  const s = result.suppression_stats;
  const bt = s.by_type || {};
  document.getElementById('qsSuppression').style.display = '';
  document.getElementById('qsSuppressedCount').textContent = s.suppressed_total;
  const parts = [];
  if (bt.COOLDOWN) parts.push(`${bt.COOLDOWN} cooldown (≤${s.cooldown_days}d)`);
  if (bt.HARD_BOUNCE) parts.push(`${bt.HARD_BOUNCE} bounced`);
  if (bt.UNSUBSCRIBED) parts.push(`${bt.UNSUBSCRIBED} unsub`);
  document.getElementById('qsSuppressedBreakdown').textContent = parts.join(' · ') || '—';
  if (s.suppressed_total > 0) {
    toast(`Skipped ${s.suppressed_total} · Queued ${result.queued}`, 'info', 6000);
  }
}
```

**Settings — add Suppression List section:**
```html
<section id="settingsSuppression" style="margin-top:24px">
  <h3>Suppression List <span class="badge" id="supCount">—</span></h3>
  <p class="muted">Emails tự động bị loại khỏi Quick Send do bounce hoặc unsubscribe.</p>
  <table class="data-table">
    <thead>
      <tr><th>Email</th><th>Company</th><th>Status</th><th>Last Bounce</th><th>Action</th></tr>
    </thead>
    <tbody id="supTableBody"></tbody>
  </table>
</section>
```

```javascript
async function loadSuppression() {
  const r = await api('/api/suppression/list?limit=500');
  document.getElementById('supCount').textContent = r.total || 0;
  const tbody = document.getElementById('supTableBody');
  tbody.innerHTML = (r.suppressed || []).map(s => `
    <tr>
      <td>${esc(s.EMAIL)}</td>
      <td>${esc(s.COMPANY || '')}</td>
      <td><span class="tag tag-${s.EMAIL_STATUS === 'HARD_BOUNCE' ? 'err' : 'warn'}">${s.EMAIL_STATUS}</span></td>
      <td class="mono">${(s.LAST_BOUNCE_AT || '').slice(0, 16)}</td>
      <td><button class="btn btn-xs" onclick="unsuppress('${esc(s.EMAIL)}')">Unsuppress</button></td>
    </tr>
  `).join('');
}

async function unsuppress(email) {
  if (!confirm(`Remove suppression for ${email}?`)) return;
  const r = await api(`/api/suppression/unsuppress?email=${encodeURIComponent(email)}`, {method: 'POST'});
  if (r.ok) { toast('Unsuppressed', 'success'); loadSuppression(); }
  else toast('Failed: ' + (r.error || ''), 'err');
}
```

## Implementation Steps

1. Add 2 suppression endpoints to web_server.py
2. Add `filter_suppressed()` helper, call from Quick Send endpoint
3. Return `suppression_stats` in Quick Send response
4. UI: add counter div to Quick Send + hook on submit
5. UI: add Settings suppression table + wire loadSuppression on Settings tab activate
6. Restart pythonw + test

## Success Criteria

- [ ] Quick Send 30d call: if list contains hard-bounced emails → they removed, counter shows "Skipped X"
- [ ] Settings → Suppression section hiện list các email HARD_BOUNCE + UNSUBSCRIBED
- [ ] Unsuppress button works — email quay lại ACTIVE, có thể gửi lại

## Risks

| Risk | Mitigation |
|------|-----------|
| Pandas read xlsx chậm khi 22K rows | Cache dataframe, reload mỗi 5 phút |
| Concurrent write xlsx conflict | Use lock file + small critical section |
| Over-filter (ACTIVE em email marked HARD by mistake) | Unsuppress button provides manual recovery |

## Next Phase
Phase C — Move NDR mail khỏi Inbox sau khi handle_bounce done.
