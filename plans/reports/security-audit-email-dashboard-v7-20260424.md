# Security Audit — Email Dashboard v7

**Date:** 2026-04-24
**Auditor:** security-auditor agent
**Scope:** web_server.py, rotation_router.py, contacts_router.py, sent_scan_router.py, outlook_queue_worker.py, intel/writeback.py, scanner/handlers.py, email-dashboard.html
**Risk score tổng quan:** HIGH (8.5/10)
**Block gửi email tối nay:** KHÔNG (với điều kiện apply CRITICAL-1)

## Tóm tắt severity

| Severity | Count | Notes |
|----------|-------|-------|
| CRITICAL | 3 | Tất cả liên quan `host="0.0.0.0"` + không auth |
| HIGH | 3 | 1 false alarm (SQL injection — thực tế dùng parameterized) |
| MEDIUM | 5 | |
| LOW | 4 | |

---

## CRITICAL

### CRITICAL-1: Server bind `0.0.0.0` → toàn bộ LAN gọi được API gửi email

- **File:** `email_engine/web_server.py` line ~3802
- **Code hiện tại:** `uvicorn.run(app, host="0.0.0.0", port=8100, log_level="info")`
- **Attack vector:** Bất kỳ thiết bị cùng LAN (laptop khách, điện thoại Wifi office, máy đồng nghiệp) gõ `http://<IP_Nelson>:8100/api/rotation/run-today` với `{"force": true}` → trigger gửi 700 email từ Outlook COM của Nelson, không cần auth.
- **Impact:** Mass-mail từ `nelson@pudongprime.vn` gửi sai thời điểm/sai commodity. Kết hợp CRITICAL-3: body + recipient hoàn toàn do attacker kiểm soát.
- **Fix surgical (1 dòng, 30 giây):**
  ```python
  uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
  ```
- **Verify sau fix:** `netstat -ano | findstr :8100` phải thấy `127.0.0.1:8100`. Dashboard `file://` vẫn gọi `http://localhost:8100` → không ảnh hưởng.

### CRITICAL-2: `force=true` bypass preview_token + CORS `.*` → CSRF mass-mailing

- **File:** `email_engine/api/routes/rotation_router.py` line 339-368 + `web_server.py` line 199-205
- **Code:**
  ```python
  # rotation_router.py
  if not force:
      if not token or not _consume_preview_token(token):
          raise HTTPException(400, detail="Preview required. ...")
  # web_server.py CORS
  allow_origin_regex=".*"
  ```
- **Attack vector:** Nelson mở dashboard `file://` trong Chrome. Trang attacker `http://evil.com` với `<form>` auto-submit hoặc `fetch()` POST `/api/rotation/run-today` với `force=true` — CORS regex `.*` cho phép → 700 email gửi.
- **Fix:** Sau CRITICAL-1 (bind 127.0.0.1) → attacker không reach được port → CRITICAL-2 moot. Defense-in-depth:
  ```python
  allow_origin_regex=r"^(null|file://|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?)$"
  ```

### CRITICAL-3: `/api/send` không cần preview token

- **File:** `email_engine/web_server.py:873-878`
- **Attack vector:** Nếu port reachable, LAN attacker POST 250 email/lần với recipient + subject tự chọn, body build từ `build_email()` → trông như Nelson gửi thật.
- **Fix:** Bind localhost (CRITICAL-1) là đủ cho tối nay.

---

## HIGH

### HIGH-1: SQL injection qua query params (contacts_router)
- **File:** `email_engine/api/routes/contacts_router.py:189-191`
- **Status:** FALSE ALARM — thực tế dùng `UPPER(STATE) = UPPER(?)` parameterized. `tbl` từ whitelist `_table()`. Bỏ qua.

### HIGH-2: `/api/contacts/import-panjiva` không có file size limit
- **File:** `email_engine/api/routes/contacts_router.py:435-472`
- **Attack vector:** Upload 10GB file → OOM (LAN attacker).
- **Fix surgical (3 dòng):**
  ```python
  if len(content) > 50 * 1024 * 1024:
      raise HTTPException(413, "File too large (max 50MB)")
  ```
- **Ưu tiên tối nay:** THẤP nếu CRITICAL-1 fixed.

### HIGH-3: `/api/sent-scan/run` — `_JOBS` dict unbounded
- **File:** `email_engine/api/routes/sent_scan_router.py:32, 121`
- **Attack vector:** Spam POST → unlimited subprocess + OOM.
- **Fix surgical:**
  ```python
  # trong run_scan trước khi add:
  if len(_JOBS) > 100:
      _JOBS.pop(next(iter(_JOBS)))
  ```

### HIGH-4: `/t/o/{job_id}.gif` không rate-limit
- **File:** `email_engine/web_server.py:2353-2371`
- **Status:** KHÔNG cần fix tối nay — `TRACK_BASE_URL` default localhost → pixel không reachable từ recipient inbox → endpoint hiện vô dụng. Defer đến khi deploy VPS public.

---

## MEDIUM

### MED-1: Telegram bot token có thể leak qua exception trace
- **File:** `email_engine/core/cnee_milestone.py:565-573`
- Token ở URL → traceback log có thể chứa. Defer.

### MED-2: `_PREVIEW_TOKENS` cleanup không atomic
- **File:** `email_engine/api/routes/rotation_router.py:469-484`
- Race khi cleanup. Worst case: preview lại. Không cần fix.

### MED-3: `/api/email-rate/queue/kill` + `/kill-clear` không auth
- **File:** `email_engine/web_server.py:2644-2670`
- Fix: bind localhost là đủ.

### MED-4: `/api/customer/exclude` thêm/xóa blacklist không auth
- **File:** `email_engine/web_server.py:461, 496`
- Fix: bind localhost là đủ.

### MED-5: Blacklist có áp dụng ở `/api/contacts/import-panjiva`?
- Cần verify script `scripts/panjiva_clean_v2.py` filter `competitor_blacklist.json` không.
- Action: grep trước import data mới.

---

## LOW

- LOW-1: 9 silent-catch trong dashboard HTML — debug khó, không security.
- LOW-2: `innerHTML` với user data — có `esc()`, low risk.
- LOW-3: `TRACK_BASE_URL` default localhost — pixel vô dụng cho recipients thật.
- LOW-4: `intel/writeback.py:193-204` `_is_locked()` race — data integrity, buffer restored.

---

## Action items — Pre-flight tối nay

**PHẢI làm (5 phút):**
1. `web_server.py:3802` → `host="127.0.0.1"` — restart dashboard

**NÊN làm (10 phút):**
2. CORS whitelist thay regex `.*`

**Verify (2 phút):**
3. `netstat -ano | findstr :8100` → phải `127.0.0.1:8100`
4. Curl từ điện thoại cùng WiFi → phải timeout/refused

**Skip tối nay:** Auth middleware, file-size limits, _JOBS TTL, pixel rate limit.

---

## Status

**Status:** DONE_WITH_CONCERNS
**Summary:** 3 critical, fix 1 dòng (`host="127.0.0.1"`) khử ~80% rủi ro. Defense-in-depth: CORS whitelist.
