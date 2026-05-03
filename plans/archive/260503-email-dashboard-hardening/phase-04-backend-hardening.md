# Phase 4: Backend Hardening

## Overview
Fix state management, memory leaks, global store fragility, and API robustness in `web_server.py` (4495 lines) — prepare for multi-user + high-concurrency production use.

## Requirements
- Functional: `Store` object uses immutable update pattern (no direct mutation)
- Functional: Event listeners use AbortController pattern — cleaned up on tab switch
- Functional: `setInterval` intervals are cleared on cancel
- Functional: Send flow progress is queryable via `/api/send-status/{id}` — already done, verify robustness
- Functional: `_get_cnee_df()` is called at most once per request (not 3+ times)
- Non-functional: Backend handles 22K contact file + multiple concurrent sends without memory growth

## Architecture

### State Management — Replace Global Mutable Store with Closure Pattern
```python
# web_server.py — replace mutable module-level Store dict
# CURRENT (fragile):
Store = {"campaigns": [], "selected": set(), ...}
Store["campaigns"] = new_data  # Direct mutation — race condition risk

# PROPOSED (immutable closure):
class AppState:
    _state = {
        "campaigns": [],
        "selected": set(),
        "send_progress": {},
        "current_batch_id": None,
    }
    _listeners: list[callable] = []

    @classmethod
    def get(cls, key: str, default=None):
        return cls._state.get(key, default)

    @classmethod
    def set(cls, updates: dict):
        cls._state.update(updates)
        for listener in cls._listeners:
            listener(cls._state)

    @classmethod
    def subscribe(cls, fn: callable):
        cls._listeners.append(fn)
        return fn  # return for use as cleanup handle
```

### Multiple `_get_cnee_df()` Calls
Current `selectCampaign()` calls `_get_cnee_df()` potentially 4+ times (once per check, once per prospect load, once per suppression lookup). Consolidate to single call.

```python
# In selectCampaign — call once, reuse:
_cnee = _get_cnee_df()
# then use _cnee for all subsequent operations
```

### Memory Leak — `setInterval` never cleared
```python
# CURRENT:
Store.sendInterval = setInterval(doSendBatch, 1000)

# FIX: track interval ID in a scoped variable, add cleanup method
def cancel_send(campaign_id: str):
    prog = SEND_PROGRESS.get(campaign_id)
    if prog and prog.get("interval_id"):
        clearInterval(prog["interval_id"])
    prog["status"] = "cancelled"
```

### Send Progress — make it a class instead of dict
Replace `SEND_PROGRESS: dict = {}` with a `SendProgress` dataclass or Pydantic model:
```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SendProgress:
    campaign_id: str
    total: int
    sent: int = 0
    errors: list = field(default_factory=list)
    skipped_cooldown: int = 0
    skipped_hard_limit: int = 0
    status: str = "queued"  # queued/running/done/cancelled
    started_at: datetime = field(default_factory=datetime.now)
    interval_id: int | None = None
```

### Cleanup Pattern — add to navigation in frontend
When tab switch happens, the frontend should call an abort endpoint or set a flag to cancel pending operations. For now, add `abort` flag to `Store` in JS.

## Related Code Files
- Modify: `email_engine/web_server.py`

## Implementation Steps

### 1. Deduplicate `_get_cnee_df()` calls
In `_do_send()`, `_do_send_built_emails()`, and `select_campaign()` — each calls `_get_cnee_df()` multiple times. Add `_cnee = _get_cnee_df()` once at function top, reuse.

### 2. Create `SendProgress` dataclass
```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SendProgress:
    campaign_id: str
    total: int
    sent: int = 0
    errors: list = field(default_factory=list)
    status: str = "queued"
    skipped_cooldown: int = 0
    skipped_hard_limit: int = 0
    skipped_typo: int = 0
    deferred_smart_send: int = 0
    skipped_duplicate: int = 0
    interval_id: int | None = None
    started_at: datetime = field(default_factory=datetime.now)
```

### 3. Replace `SEND_PROGRESS[campaign_id] = dict(...)` with dataclass
Replace all `SEND_PROGRESS[campaign_id] = {"sent": 0, ...}` with `SEND_PROGRESS[campaign_id] = SendProgress(campaign_id=..., total=...)`.

### 4. Add `interval_id` tracking to progress
In `_do_send()`, track `setInterval` ID and store in `prog.interval_id`. Add `clearInterval(prog.interval_id)` when send completes or is cancelled.

### 5. Add `DELETE /api/send/{campaign_id}/cancel` endpoint
```python
@app.delete("/api/send/{campaign_id}")
def cancel_send(campaign_id: str):
    prog = SEND_PROGRESS.get(campaign_id)
    if not prog:
        raise HTTPException(404, "Campaign not found")
    if prog.interval_id:
        clearInterval(prog.interval_id)
    prog.status = "cancelled"
    return {"status": "cancelled", "campaign_id": campaign_id}
```

### 6. Add `GET /api/send-progress/{campaign_id}` (already exists at line 1065 — verify it returns full progress including all skip counts)
Check `/api/send-status/{campaign_id}` returns: `sent`, `total`, `errors`, `skipped_cooldown`, `skipped_hard_limit`, `skipped_typo`, `deferred_smart_send`, `skipped_duplicate`, `status`.

### 7. Verify `/api/send-stats` TTL cache works correctly
Review `_SEND_STATS_CACHE` logic (lines 1091-1128) — verify it handles the 15s TTL correctly and returns proper data for the KPI row.

## Success Criteria
- [ ] `_get_cnee_df()` called ≤1 time per send operation
- [ ] `SendProgress` dataclass replaces dict throughout `_do_send` and `_do_send_built_emails`
- [ ] Interval ID tracked in progress, cleared on cancel/done
- [ ] `DELETE /api/send/{id}` cancels a running campaign
- [ ] `GET /api/send-status/{id}` returns all skip counts (typo, cooldown, hard_limit, deferred, duplicate)
- [ ] `_SEND_STATS_CACHE` correctly serves cached data within 15s window