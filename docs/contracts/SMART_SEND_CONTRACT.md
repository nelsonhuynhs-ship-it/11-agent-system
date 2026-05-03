# SMART_SEND Contract — Anti-Spam Guards
**Version:** 1.0 · **Last verified:** 2026-04-28

When developer modifies email pipeline code, every guard in this contract MUST remain functional. Run `GET /api/diagnostics/guards` after changes — all 10 must report `active=true`.

---

## Pipeline Flow (Smart Send → email dispatched)

1. User clicks Smart Send → frontend POST `/api/rotation/preview-html`
2. Backend builds VIP preview, returns html_body + preview_token
3. Modal renders preview. User clicks Confirm & Send All.
4. Frontend POST `/api/rotation/run-today` with preview_token
5. Backend `_run_rotation_background()` → `queue_to_outlook_worker()` builds 110-contact batch
6. Backend spawns `_do_send_built_emails()` thread
7. Each contact runs through 10 guards before send

---

## Guards

### Guard 1: EXCLUDED list
- **Source:** `email_engine/web_server.py:252` (`EXCLUDED_EMAILS` set, loaded from `data/excluded_customers.json`)
- **Blocks:** Active customers + opt-out list
- **Threshold:** Set membership (lowercase)
- **Log signature:** `EXCLUDED -> {email}`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=1` `active=true`
- **If broken:** Active customers receive cold-outreach — REPUTATION RISK

### Guard 2: SUPPRESSED status
- **Source:** `email_engine/web_server.py:735` (`SUPPRESSED_STATUSES = {HARD_BOUNCE, INVALID, NO_MX}`)
- **Blocks:** Bounced / dead / no-MX emails
- **Threshold:** 3 statuses (HARD_BOUNCE, INVALID, NO_MX)
- **Log signature:** `SUPPRESSED -> {email}`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=2` `active=true`
- **If broken:** Hard-bounced emails re-sent — DELIVERY RATE RISK

### Guard 3: Cooldown 14d
- **Source:** `email_engine/web_server.py:760` (`cutoff = now - 14d`)
- **Blocks:** Re-sending to same contact within 14 days
- **Threshold:** 14 days
- **Log signature:** `COOLDOWN -> {email}`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=3` `value=14`
- **If broken:** Same contact spammed multiple times per week

### Guard 4: Hard limit 3/30d
- **Source:** `email_engine/web_server.py:779` (`send_count >= 3`)
- **Blocks:** Contact receiving more than 3 total sends
- **Threshold:** 3 sends per contact
- **Log signature:** `HARD_LIMIT_3 -> {email}`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=4` `value=3`
- **If broken:** Over-communicated contacts unsubscribe

### Guard 5: Typo Shield
- **Source:** `email_engine/web_server.py:788` via `email_engine/core/typo_shield.py`
- **Blocks:** Domain typos (rapidfuzz >= 85 confidence)
- **Threshold:** rapidfuzz confidence >= 85
- **Log signature:** `TYPO_BLOCK -> {email}`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=5` `active=true`
- **If broken:** Emails sent to misspelled domains → BOUNCE RISK

### Guard 6: Smart Send Window
- **Source:** `email_engine/web_server.py:797` via `email_engine/core/smart_send_window.py`
- **Blocks:** Sending outside optimal timezone window
- **Threshold:** `plan_send_time()` defers to next window
- **Log signature:** `DEFERRED -> {email}`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=6` `active=true`
- **If broken:** Emails sent at wrong local time → LOW OPEN RATE

### Guard 7: Competitor blacklist
- **Source:** `email_engine/web_server.py:261` + `is_competitor()` at line ~416
- **Blocks:** Emails to competitor domains/company names
- **Threshold:** Set membership in `COMPETITOR_BL`
- **Log signature:** `competitor blocked ({reason})`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=7` `active=true`
- **If broken:** Sending freight intelligence to competitors — CONFIDENTIALITY RISK

### Guard 8: Priority isolation
- **Source:** `email_engine/core/priority_filter.py:47` (`drop_priority()`)
- **Blocks:** VIP/HOT/replied contacts from blast rotation
- **Threshold:** VIP/HOT rows dropped from batch
- **Log signature:** `rotation: dropped N priority`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=8` `active=true`
- **If broken:** VIP/HOT customers receive blast emails — RELATIONSHIP RISK

### Guard 9: Today_sent guard
- **Source:** `email_engine/web_server.py:912` (`_load_today_sent_set()`), used at line 961 in `_do_send_built_emails`
- **Blocks:** Clicking Send 2x — skips emails already SENT today
- **Threshold:** Set membership in today's sent log
- **Log signature:** `[smart-batch] SKIP duplicate -> {email}`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=9` `active=true`
- **If broken:** Double-send same day → USER COMPLAINTS

### Guard 10: Graph pacing 28/min
- **Source:** `email_engine/senders/graph_sender.py:39` (`MIN_INTERVAL_SEC = 2.1`)
- **Blocks:** Exceeding Microsoft 30/min cap silently
- **Threshold:** 2.1 sec between sends (~28/min)
- **Log signature:** `[silent]` enforced inside `_pace()`
- **Verify alive:** `/api/diagnostics/guards` → `guard.id=10` `value≈2.1`
- **If broken:** Microsoft throttles with 429 → DELIVERY FAILURE

---

## Verification Routine After Code Changes

1. Restart server: `start-dashboard.bat`
2. Hit endpoint: `curl http://localhost:8100/api/diagnostics/guards`
3. Verify all 10 guards return `active: true`
4. (Optional) Click "🛡 Audit Guards" button in dashboard for visual check
5. (Optional) Test mode: send 5-email batch with `test_mode=true` — log shows guards firing

---

## When NOT to Bypass Guards

- **NEVER** `force_send=true` for batches > 10
- **NEVER** disable Today_sent guard (allows click-spam)
- **NEVER** disable Graph pacing (Microsoft throttles 429)
- Test mode is the only safe bypass (redirects to Nelson's Gmail)

---

## Rollback If Guard Breaks

1. Identify failing guard from `/api/diagnostics/guards` (`active=false` or wrong threshold)
2. Revert relevant file via git
3. Restart server
4. Re-run diagnostic to confirm all green
