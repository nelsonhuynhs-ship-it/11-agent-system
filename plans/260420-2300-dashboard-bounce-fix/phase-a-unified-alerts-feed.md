# Phase A — Unified Alerts Feed

**Effort:** 1.5h
**Priority:** CRITICAL (root cause — dashboard hiện đủ data)
**Status:** pending

## Overview

Sửa `/api/email-events/alerts` để đọc từ CẢ 2 nguồn:
- `email_engine/intel/events.db` (SQLite, scanner mới ghi)
- `email_engine/logs/followup_alerts.csv` (legacy, scanner followup cũ)

Merge, dedup, sort theo time desc. Return uniform schema.

## Files Modified

### 1. `email_engine/intel/memory.py` — add query function

```python
def query_events(
    days: int = 7,
    limit: int = 100,
    types: list[str] | None = None,
) -> list[dict]:
    """Query email_events table. Returns list of event dicts.
    
    Args:
        days: Window (24h, 168h, 720h mapped from UI)
        limit: Max rows
        types: Filter by event_type. Default ['BOUNCE', 'REPLY', 'AUTO_REPLY', 'UNSUBSCRIBE']
    """
    if types is None:
        types = ['BOUNCE', 'REPLY', 'AUTO_REPLY', 'UNSUBSCRIBE']
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    placeholders = ','.join('?' * len(types))
    sql = f"""
        SELECT id, cnee_email, event_type, timestamp,
               subject, reply_subject, reply_body_snippet,
               sentiment, intent, bounce_type, bounce_reason
        FROM email_events
        WHERE timestamp >= ?
          AND event_type IN ({placeholders})
        ORDER BY timestamp DESC
        LIMIT ?
    """
    with _DB_LOCK:
        with _connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, [cutoff, *types, limit]).fetchall()
    return [dict(r) for r in rows]
```

### 2. `email_engine/web_server.py` — rewrite `_read_alerts_csv` → `_read_unified_alerts`

```python
def _read_unified_alerts(limit: int = 100, days: int = 7) -> list[dict]:
    """Merge alerts from intel/events.db + legacy followup_alerts.csv."""
    results = []
    
    # Source 1: intel/events.db (scanner NEW)
    try:
        from email_engine.intel.memory import query_events
        for ev in query_events(days=days, limit=limit, types=['BOUNCE','REPLY','AUTO_REPLY','UNSUBSCRIBE']):
            results.append({
                'type': ev['event_type'].lower(),
                'time': ev['timestamp'],
                'from': ev['cnee_email'],
                'subject': ev.get('subject') or ev.get('reply_subject') or '',
                'snippet': (ev.get('reply_body_snippet') or '')[:200],
                'bounce_type': ev.get('bounce_type'),
                'sentiment': ev.get('sentiment'),
                'intent': ev.get('intent'),
                'source': 'intel_db',
            })
    except Exception as e:
        log.warning(f"intel/events.db read failed: {e}")
    
    # Source 2: legacy CSV (followup alerts)
    try:
        csv_alerts = _read_alerts_csv_legacy(limit=limit, days=days)
        for a in csv_alerts:
            a['source'] = 'legacy_csv'
            results.append(a)
    except Exception as e:
        log.warning(f"legacy csv read failed: {e}")
    
    # Dedup composite key (email, type, hour-bucket of timestamp)
    seen = set()
    deduped = []
    for a in results:
        key = (
            (a.get('from') or '').lower().strip(),
            (a.get('type') or '').lower(),
            (a.get('time') or '')[:13],  # hour granularity
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(a)
    
    # Sort time desc
    deduped.sort(key=lambda a: a.get('time', ''), reverse=True)
    return deduped[:limit]


# Keep old function but rename for fallback
def _read_alerts_csv_legacy(limit: int = 50, days: int = 7) -> list[dict]:
    # ... existing CSV reading code ...


# Update endpoints
@app.get("/api/email-events/alerts")
def v4_alerts(limit: int = 50, days: int = 7):
    return {"alerts": _read_unified_alerts(limit=limit, days=days)}


@app.get("/api/email-events/alerts/count")
def v4_alerts_count(days: int = 7):
    alerts = _read_unified_alerts(limit=1000, days=days)
    return {
        "total": len(alerts),
        "replies": sum(1 for a in alerts if a.get("type") == "reply"),
        "bounces": sum(1 for a in alerts if a.get("type") == "bounce"),
        "auto_replies": sum(1 for a in alerts if a.get("type") == "auto_reply"),
        "unsubscribes": sum(1 for a in alerts if a.get("type") == "unsubscribe"),
    }
```

## Implementation Steps

1. Add `query_events()` to `intel/memory.py` — ~25 lines
2. Add `_read_unified_alerts()` to `web_server.py` — keep legacy fn, rename
3. Update 2 endpoints to use new fn
4. Restart `pythonw web_server.py`
5. Test: `curl localhost:8100/api/email-events/alerts?days=30&limit=100`
   - Expect: ≥11 alerts (6 bounce + 5 reply from our scan)
6. Verify dashboard Inbox tab shows data

## Success Criteria

- [ ] `query_events(days=30)` returns all events from last run_scan
- [ ] `_read_unified_alerts` dedups correctly (no duplicate email+type+hour)
- [ ] Dashboard Inbox KPI: Bounces=6, Replies=5, Auto=12 (match scanner)
- [ ] Unified feed table has rows with correct type icons

## Risks

| Risk | Mitigation |
|------|-----------|
| `_DB_LOCK` import path fail | Try-except + log, fallback to CSV only |
| Timestamp format mismatch | Normalize via `datetime.fromisoformat` parse-then-reformat |
| CSV column names drift | Keep legacy fn isolated, schema-aware mapping |

## Next Phase
Phase B — Quick Send filter (uses same EMAIL_STATUS data that bounce handler writes).
