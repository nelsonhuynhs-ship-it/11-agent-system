# Perf Analysis — Email Dashboard v7

**Date:** 2026-04-24
**Auditor:** perf-analyzer agent
**Score:** 68/100 (Needs Work)
**Verdict tối nay:** AN TOÀN gửi sau khi apply 4 fix P0 (35 phút tổng)

## Root cause 17s cold-load

`intel/writeback._apply_updates()` gọi `os.replace(tmp, path)` mỗi 5–10 phút → xlsx mtime đổi → **cả 3 cache invalidate đồng loạt** (`_CNEE_CACHE`, `_MASTER_CACHE`, DuckDB) → dashboard poll tiếp theo hit cold-load 17s × 3.

**Prewarm daemon (commit 5d3ca15) chỉ chạy 1 lần lúc startup, KHÔNG re-warm sau mỗi flush.**

Evidence từ log: `[11:23:12] writeback flushed 32 rows` → `[11:23:55] CNEE master cached: 22,854 rows` (43s gap). Lặp lại 4 lần trong 1.5h uptime.

## Verified facts

| Metric | Value |
|--------|-------|
| Master xlsx size | 18.0 MB |
| Cold-load `/api/send-stats` | 16.1s |
| Cold-load `/api/rotation/progress` | 16.3s |
| Cold-load `/api/analytics/overview` | 10.5s |
| Prewarm daemon | Chạy 1 lần lúc startup, sequential 43s |
| Cache reload count (1.5h) | 5 lần |
| Writeback flush count (1.5h) | 4 lần |
| pythonw.exe RAM | 211 MB |
| Outlook RAM | 625 MB |
| 3-thread Outlook COM throughput | ~75 emails/min thực tế |
| 700 emails/ngày | ~9 phút thực tế — AN TOÀN |

## P0 — Fix tối nay (≤15 phút mỗi cái)

### PERF-001: Re-prewarm sau writeback flush (CRITICAL)
- **File:** `email_engine/intel/writeback.py` sau line 259 (`os.replace`)
- **Impact:** Hết 17s lag mỗi 5–10 phút
- **Fix (Option B — an toàn, ít coupling):** Spawn re-prewarm thread sau flush:
  ```python
  # Cuối _apply_updates() sau os.replace
  import threading, urllib.request
  def _rewarm():
      for ep in ("/api/send-stats","/api/rotation/progress","/api/analytics/overview"):
          try: urllib.request.urlopen(f"http://127.0.0.1:8100{ep}", timeout=60).read()
          except: pass
  threading.Thread(target=_rewarm, daemon=True).start()
  ```
- **Effort:** 15 phút

### PERF-002: `loadSessionProgress` polling 2s không có view-guard
- **File:** `plans/visuals/email-dashboard.html:4960`
- **Impact:** 30 calls/min vô ích khi Nelson ở tab khác
- **Fix:**
  ```javascript
  setInterval(function() {
    var active = document.querySelector('.nav-item.active');
    if (active && (active.dataset.view === 'viewSend' || active.dataset.view === 'viewRotation')) {
      loadSessionProgress();
    }
  }, 2000);
  ```
- **Effort:** 5 phút

### PERF-003: `/api/send-stats` thiếu TTL cache
- **File:** `email_engine/web_server.py:906-943`
- **Impact:** Recompute `pd.to_numeric + pd.to_datetime` mỗi 10s
- **Fix:** Thêm 15s TTL cache (pattern như analytics/overview line 1299)
- **Effort:** 10 phút

### PERF-004: Browser parallel fetch lúc F5 → cold-load tuần tự
- **File:** `email_engine/web_server.py` + `email-dashboard.html`
- **Impact:** 4 endpoint × 42.9s tổng → browser fetch timeout 10s
- **Fix (quick):** Thêm endpoint `/api/health/ready` trả `_PREWARM_DONE`, dashboard block fetch chính cho đến khi ready
- **Effort:** 15 phút (optional — có thể defer nếu đã có PERF-001)

## P1 — Tuần sau

### PERF-101: Parquet companion file thay xlsx cho read-only
- Root cause thật sự. Xlsx 18MB openpyxl = 13-16s; parquet = <500ms
- Fallback xlsx nếu xlsx.mtime > parquet.mtime (Nelson edit tay vẫn OK)
- Effort: half-day

### PERF-102: Unified cache module `core/cnee_cache.py`
- Refactor 3 cache → 1. Defer vì risk cao.
- Effort: 1-2 ngày

### PERF-103: `batch-status` dùng `queue_store._connect` để có WAL
- File: `rotation_router.py:371`
- Effort: 5 phút — có thể nâng P0

### PERF-104: `_get_cycle_info_cached` TTL tăng 600s
- File: `rotation_router.py:67-83`
- Effort: 3 phút

## P2 — Backlog

- PERF-201: Pre-compute `to_datetime` trong cache
- PERF-202: Cache `_load_email_log` (no TTL hiện tại)
- PERF-203: `contacts_router._save_to_xlsx` IO 2× — cache other_sheet
- PERF-204: 5 setInterval chưa guard view-active

## Threading + queue

- **3-thread Outlook COM:** Outlook serializes → thực tế ~75/min không 180/min. 700/ngày = 9 phút. AN TOÀN.
- **SQLite WAL:** Đúng (`journal_mode=WAL`, `busy_timeout=30000`) trừ `batch-status` bypass.
- **Lock contention:** `_DB_LOCK` global — pop_one + mark_sent <5ms → không đáng kể.

## Dashboard polling load khi tab Send active

| Interval | Endpoint | Calls/min |
|----------|----------|-----------|
| 2s | batch-status | 30 |
| 10s | send-stats + rotation/today + rotation/progress + loadSendStats | ~24 |
| 15s | kill-status | 4 |
| 30s | version + sent-scan/pending | 4 |
| 60s | alert-count + Open Tracker | 2 |
| **Total** | | **~64 calls/min** |

## Ranking quick wins

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | PERF-002 view-guard | 5 phút | Giảm 30 calls/min vô ích |
| 2 | PERF-003 TTL send-stats | 10 phút | Giảm CPU spike |
| 3 | PERF-001 re-prewarm after flush | 15 phút | **Hết 17s lag** |
| 4 | PERF-103 WAL cho batch-status | 5 phút | WAL bảo vệ contention |

**35 phút tổng → tối nay mượt.**

## Status

**Status:** DONE_WITH_CONCERNS
**Summary:** Root cause xác định, 4 fix P0 surgical, KHÔNG cần refactor tối nay.
