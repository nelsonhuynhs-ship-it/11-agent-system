# Red Team Findings — 2026-04-20

4 hostile reviewers spawned via `/ck:plan red-team`. 40 raw findings deduped to 15 critical clusters.

## Session Summary

| Reviewer Lens | Findings | Critical | High | Medium |
|---------------|----------|----------|------|--------|
| Security Adversary | 10 | 4 | 4 | 2 |
| Failure Mode Analyst | 10 | 3 | 5 | 2 |
| Assumption Destroyer | 10 | 3 | 5 | 2 |
| Scope & Complexity Critic | 10 | 1 | 3 | 6 |

**Total:** 40 raw → 15 deduplicated

**User disposition (2026-04-20):** REWRITE plan as MVP 1-file + security hardening. All 15 findings accepted.

---

## Cluster A — Security Hardening (Critical)

### A1. Sender spoof — no SPF/DKIM/DMARC check
Plan filters `sender_domain == "pudongprime.vn"` via plain text match. Outlook `SenderEmailAddress` can be spoofed in internet mail. BEC attack vector: spoofed OPS mail → auto-draft with fake ETA to real CNEE.

**Fix:** Parse `Authentication-Results` header via `PropertyAccessor`. Require `spf=pass` + `dkim=pass` + `dmarc=pass`. Log reject reason on fail.

### A2. Bkg_No trust boundary broken
Bkg public identifier (on B/L, coload mails). One mail with 50 Bkg → 50 auto-drafts. No customer-match verification between mail context and Active Jobs row.

**Fix:** Reject mail if >3 Bkg detected (bulk sheet). Cross-check vessel/ETD in mail against booking in Active Jobs — mismatch = alert, no draft.

### A3. Placeholder injection → BEC
Template fill uses `format_map(defaultdict)` with NO sanitization. Attacker controls `{vessel}` = "...wire payment to account 1234..." via compromised OPS mail. Nelson sends blind → CNEE wires to attacker.

**Fix:** Sanitize every placeholder: strip `\n\r\t`, length cap (vessel ≤40, hbl ≤20), regex whitelist (`hbl ~ ^[A-Z0-9]{8,16}$`). Reject compose if fail. Subject prefix `[AUTO]`.

### A4. No rate limit = mass send on bad input
No MAX_DRAFTS_PER_RUN / DAY. No kill switch. One bulk rate sheet input → 50-100 drafts. Office 365 throttle → reputation damage.

**Fix:** `MAX_DRAFTS_PER_RUN = 5`, `MAX_DRAFTS_PER_DAY = 20`. Kill switch file `AUTO_NOTIFY_DISABLED`. Abort + Telegram critical if exceeded.

### A5. Self-send filter too narrow
`NELSON_EMAILS = {"nelson@pudongprime.vn"}` — but 6 mentees + 2 leadership all on same domain. Mentee forward → hook triggers.

**Fix:** Explicit OPS allowlist (actual OPS addresses, not domain). Blocklist mentees + Nelson aliases.

---

## Cluster B — Correctness Bugs (High)

### B1. `shipment_brain.py` hook point doesn't exist
Plan references `process_email` function and "line 480-520" — actual file has `scan_and_update()` at line 482 with different structure. `sender_domain`, `detected_text` vars don't exist.

**Fix:** Read `shipment_brain.py` properly. Hook once per email AFTER stage loop (not inside). Use `any(s in {"ATD","LOADED"} for s in stages)`.

### B2. xlsm write race with Nelson open
Scanner writes ERP_Master_v14.xlsm every 30 min while Nelson edits daily. No locking. Corruption risk: VBA module gone (28 commits lost), OneDrive conflict copy, partial writes.

**Fix:** Write to JSON sidecar `email_engine/data/milestone_state.jsonl` (append-only). Scanner NEVER writes xlsm. VBA button on ERP "Sync milestones" reads sidecar under Nelson control. Or auto-sync on Workbook_Open.

### B3. Outlook COM steals active session
`CreateItem().Save()` while Nelson types reply → UI freeze, lost keystrokes, corrupt in-progress draft.

**Fix:** Check `Outlook.Application.ActiveInspector()` — if not None, defer draft to next scan. Log "user busy, defer".

### B4. Date regex dd/mm vs mm/dd ambiguity
Regex matches both, assumes dd/mm. Mail from carriers may use mm/dd → ATD stored wrong 6 months off.

**Fix:** (a) Cross-check against mail `ReceivedTime` — ATD must be within ±30 days of receive. (b) Parse both candidates, if both valid → reject + alert. (c) Support `.` separator (real format `26.04.2026`).

### B5. Substring dedup breaks on reschedule
`if "ATD" in last_notified: continue` — substring match blocks legit re-ATD when vessel actually re-departs after roll.

**Fix:** Two explicit boolean columns `NOTIFIED_ATD` + `NOTIFIED_ETA7`. On vessel re-depart, clear flag + re-compose with subject "Revised Departure".

---

## Cluster C — YAGNI Cuts (Strong)

### C1. 6 phases + dataclass + Enum for 80 LOC
Solo user, <20 jobs/week. Plan builds `MilestoneType(Enum)`, `@dataclass MilestoneContext`, `dry_run` flag, return-shape dict, hook module separate from composer — for `if atd: outlook.CreateItem().Save()`.

**Fix:** 1 file `cnee_milestone.py`, 2 functions, 200 LOC total. Pass dict → return bool. No Enum, no dataclass.

### C2. Telegram buffer/flush pattern is premature optim
Module-level `_alert_buffer` dict, 4 categories, truncation, try-finally — to "prevent spam" for <20 events/week.

**Fix:** Delete. Local `list` during scan, one `send_telegram("\n".join(lines))` at end.

### C3. `schedule_override` framework for 1 daily job
30-min window hack (`override["minute"] <= now.minute < +30`) hardcoded scanner cadence into config.

**Fix:** Delete. Either separate Task Scheduler entry `python -m email_engine.cnee_milestone eta` at 08:00, OR simple `if date.today() == last_run_date: return`.

### C4. Archive sheet schema change
Speculative "khỏi miss migration tương lai" — no code in scope reads Archive.

**Fix:** Drop. Add cols when actual migration is written.

### C5. Effort 5h understated
Realistic is 10-12h with proper security. OR cut scope to match 4-5h.

**Fix:** After cuts C1-C4 + security hardening, realistic = 4h for MVP.

---

## Cluster D — Test + Robustness (Medium)

### D1. Manual tests miss regex edge cases
6 scenarios manual, zero automated assertions. Regex bug for dot-format date → silent miss for weeks.

**Fix:** `tests/test_cnee_milestone.py` — unit tests for date formats, blacklist, sanitizer. 40 lines.

### D2. Rollback deletes Nelson's manual data
Dropping cols after Nelson edited 100 rows = data loss. No pre-rollback export.

**Fix:** Migration on xlsm COPY first. Pre-rollback export to CSV. Use `win32com` (per SYSTEM_STANDARDS §5), NOT openpyxl for xlsm with VBA.

### D3. Unmeasurable success metrics
"ATD→Draft >80%" needs ground truth that doesn't exist.

**Fix:** Replace with binary measurable: "1 tuần Nelson actually Send ≥5 auto-drafts (not delete)."

---

## Rejected Findings

None — all 15 accepted after user disposition.

**Out of scope (defer):**
- Security #10: Telegram token leak — Nelson solo, chat_id private, low probability. Keep rotation practice.
- Security #4: Email history compare for integrity — good idea, but requires separate Phase for history indexing. Defer to v2.
