# Phase 02 — Scanner Hook + Payment Detection

**Priority:** P2 · **Status:** pending · **Effort:** 2h · **Blocked by:** Phase 01

## Context Links

- [plan.md](plan.md)
- [cnee_milestone.py](../../email_engine/core/cnee_milestone.py) — template to mirror
- [shipment_brain.py:170-207](../../email_engine/core/shipment_brain.py) — stage detection (verified file structure)
- [red-team findings A1-A5, B1-B5](../260420-1700-auto-cnee-milestone-notify/red-team-findings.md) — security lessons to apply

## Goal

1. Add `PAYMENT_REMINDER` stage pattern to `shipment_brain.py`
2. Create `invoice_tracker.py` (~120 LOC) modeled on `cnee_milestone.py`
3. Wire hook in `scan_and_update()` after existing CNEE hook

## Verified Hook Point

`shipment_brain.py:585-591` already has CNEE hook pattern:
```python
if any(s in {"ATD", "LOADED"} for s in stages):
    try:
        from email_engine.core.cnee_milestone import on_atd_detected
        on_atd_detected(item, stages, ids, sender)
    except Exception as _milestone_err:
        log.error("cnee_milestone hook failed: %s", _milestone_err)
```

New hook added directly after (same pattern, same error isolation).

## Key Insights

- `detect_stages()` at line 222 is simple keyword match — add new entry to `_STAGE_PATTERNS` list (line 170). Reuse directly, no new detection module.
- `ids: dict[str, list[str]]` comes from `extract_identifiers()` — already has `"BKG"` key. INVOICE_NUMBER is NEW — we add a regex in `invoice_tracker.py` (don't touch shipment_brain's identifier extraction — out of scope).
- `sender: str` is SMTP from `get_sender_smtp()` line 444 — already passed to CNEE hook.
- `flush_telegram_summary()` at line 604 is CNEE-specific. Option A: add separate flush call for invoice. Option B: merge buffers. **Decision: Option A** (separate — clearer Telegram output formatting "Invoice Summary\n..." vs "CNEE Summary\n...").

## Requirements

**Functional:**
- F1: Detect "payment received/paid/đã thanh toán/đã nhận thanh toán/đã vào tiền" → classify as PAID
- F2: Detect "nhắc thanh toán/reminder/overdue/past due/đòi tiền/chưa thanh toán" → classify as REMIND
- F3: Extract invoice number via regex `INV[-\s]?\d{4,10}` (Vietnamese common format) as fallback identifier
- F4: Match to InvoiceLog by BKG first, INVOICE_NUMBER second
- F5: Append to `invoice_state.jsonl` (append-only, idempotent)
- F6: Queue Telegram line per event
- F7: Flush Telegram summary at scan end

**Non-functional:**
- NF1: Hook must NOT raise — wrap in try/except (match CNEE pattern line 589)
- NF2: <10 LOC added to `shipment_brain.py` (minimal surface)
- NF3: Kill switch check first (fail-fast)

## Architecture

```
invoice_tracker.py layout (mirror cnee_milestone.py):

# Config
ACCOUNTING_ALLOWLIST: set[str] = set()  # TODO Nelson seed
KILL_SWITCH = data_dir / "INVOICE_TRACKER_DISABLED"
STATE_FILE = data_dir / "invoice_state.jsonl"
DAILY_COUNTER = data_dir / "invoice_daily.json"
MAX_EVENTS_PER_RUN = 10
MAX_EVENTS_PER_DAY = 50
BULK_IDENTIFIER_LIMIT = 5

# Regex
INVOICE_NO_PATTERN = re.compile(r"\bINV[-\s]?(\d{4,10})\b", re.I)
PAID_KEYWORDS   = ("payment received", "paid", "đã nhận thanh toán",
                   "đã thanh toán", "đã vào tiền", "xác nhận thanh toán")
REMIND_KEYWORDS = ("nhắc thanh toán", "reminder", "overdue", "past due",
                   "đòi tiền", "chưa thanh toán", "due date reached")

# Functions
_check_kill_switch()
_daily_count() / _increment_daily()
_check_auth_results(mail_item) -> bool  # with fallback for internal mail
_classify_payment_type(text) -> Optional[str]  # returns "PAID" | "REMIND" | None
_extract_invoice_numbers(text) -> list[str]
_queue_telegram(line)
_write_state(bkg, invoice_no, event_type, event_date, mail_entry_id)

# Main hook
on_payment_event(mail_item, stages, identifiers, sender_smtp) -> bool

# CLI entry (used by Phase 04)
run_overdue_sweep() -> int

# Flush
flush_telegram_summary()  # separate buffer from CNEE
```

## Security Gates (reused from CNEE, 1 deviation)

| Gate | Same as CNEE? | Notes |
|---|---|---|
| Kill switch | ✓ | Separate file so invoice can be disabled without killing CNEE |
| Allowlist | ✓ (explicit SMTP) | `ACCOUNTING_ALLOWLIST` not `OPS_ALLOWLIST` |
| Auth-Results | **DEVIATION** | Internal Pudong mail may not have DKIM. Fallback: if header absent AND sender in explicit allowlist → allow (log reason). If header present → strict check. |
| Bulk detect | ✓ (tuned to 5) | Payment mails often reference 2-3 invoices legit; statements >5 |
| Rate limit | ✓ (higher caps) | 10/run, 50/day |
| Placeholder sanitize | **SKIP** | We don't compose email — only Telegram alert (no BEC surface) |
| Sidecar pattern | ✓ | `invoice_state.jsonl` — scanner never touches xlsm |
| ActiveInspector check | **SKIP** | We don't use Outlook COM to create drafts |

## Related Code Files

**Create:**
- `email_engine/core/invoice_tracker.py` (~120 LOC)

**Modify:**
- `email_engine/core/shipment_brain.py`:
  - Line 170-183: Add `("PAYMENT_REMINDER", ["nhắc thanh toán", "reminder", "overdue", "past due", "đòi tiền", "chưa thanh toán"])` to `_STAGE_PATTERNS`
  - Line 203: Add `"PAYMENT_REMINDER": -3,` to `_STAGE_PRECEDENCE` (non-lifecycle, like DELAY_NOTICE)
  - Line ~592: After existing CNEE hook block, add invoice hook (5 lines)
  - Line ~608: After existing CNEE flush, add invoice flush (3 lines)

## Implementation Steps

1. **Read actual current `shipment_brain.py`** lines 170-210, 580-615 (re-verify before edit — don't trust plan if file drifted)

2. **Add stage pattern** to `_STAGE_PATTERNS` — PAYMENT_REMINDER entry. Add PAYMENT_REMINDER to `_STAGE_PRECEDENCE` dict with value -3 (so it doesn't advance lifecycle).

3. **Create `invoice_tracker.py`:** Copy-adapt from `cnee_milestone.py`. KEY DIFFS:
   - No Outlook draft creation — only sidecar write + Telegram
   - No template/placeholder system
   - No `_build_context()` / `_lookup_cnee_emails()` / `_crm_auto_notify()` (not needed)
   - No ERP file read in hot path (keep scanner fast; overdue sweep reads xlsm)
   - Auth-results with allowlist fallback

4. **Wire hook** in `scan_and_update()`:
   ```python
   # ── Invoice Tracker hook ───────────────────────────────────────
   if any(s in {"PAYMENT_CONFIRMED", "PAYMENT_REMINDER"} for s in stages):
       try:
           from email_engine.core.invoice_tracker import on_payment_event
           on_payment_event(item, stages, ids, sender)
       except Exception as _invoice_err:
           log.error("invoice_tracker hook failed: %s", _invoice_err)
   # ── End Invoice Tracker hook ───────────────────────────────────
   ```

5. **Add flush call** at end of `scan_and_update()`:
   ```python
   try:
       from email_engine.core.invoice_tracker import flush_telegram_summary as _flush_invoice
       _flush_invoice()
   except Exception:
       pass
   ```

6. **Compile check:** `python -c "import email_engine.core.invoice_tracker; import email_engine.core.shipment_brain"` — must import clean.

7. **Lint (soft):** match CNEE style (type hints, log format).

## Todo List

- [ ] Re-verify shipment_brain.py line numbers before edit
- [ ] Add PAYMENT_REMINDER to `_STAGE_PATTERNS` + `_STAGE_PRECEDENCE`
- [ ] Create `invoice_tracker.py` skeleton
- [ ] Implement `_classify_payment_type()`
- [ ] Implement `_extract_invoice_numbers()`
- [ ] Implement auth-results check with allowlist fallback
- [ ] Implement `on_payment_event()` main
- [ ] Implement `_write_state()` + dedup
- [ ] Implement Telegram buffer + flush
- [ ] Wire hook in `shipment_brain.py`
- [ ] Wire flush call in `shipment_brain.py`
- [ ] Compile check
- [ ] Dry-run with synthetic mail fixture

## Success Criteria

- [ ] Both module imports clean (no syntax / import errors)
- [ ] Synthetic "payment received BKG12345" mail → writes JSONL entry `{"type":"PAID","bkg":"BKG12345",...}`
- [ ] Synthetic "nhắc thanh toán INV-0042" → writes entry `{"type":"REMIND","invoice_no":"0042",...}`
- [ ] Kill switch file present → `on_payment_event()` returns False without side effects
- [ ] Sender not in allowlist → skipped, logged
- [ ] 6 BKG in one mail → bulk-rejected, Telegram warning queued
- [ ] Existing CNEE hook still fires (regression guard)

## Risk Assessment

| Risk | Mitigation |
|---|---|
| PAYMENT_REMINDER pattern false-positive (e.g. "overdue library book" thread) | Allowlist filter catches — accounting team only. Also secondary keyword "đòi tiền" is unambiguous internal. |
| Bkg extracted from forwarded mail thread (belongs to diff customer) | Recency filter in sync (DATE_ISSUED > today-180d). Same pattern as CNEE. |
| Sidecar JSONL grows unbounded | Phase 04 "Sync invoices" VBA truncates processed entries. Add monitoring: Telegram alert if JSONL > 1000 lines. |
| Import cycle `invoice_tracker` ↔ `shipment_brain` | Hook uses local import inside try block (same as CNEE) — no module-level circular import. |
| `PAYMENT_CONFIRMED` stage already wired to `alert_payment()` at line 574 — double Telegram | Keep `alert_payment` (it's per-event inline alert for DIRECT customers, different purpose). Invoice tracker adds to summary buffer. Not duplicate — different messages. |

## Security Considerations

- ACCOUNTING_ALLOWLIST populated lazily (empty at start). While empty → skip all. Nelson must seed via Telegram digest review.
- Auth-results fallback is DELIBERATE deviation — documented. Risk: spoofed internal mail from compromised Pudong account. Mitigation: allowlist is explicit addresses, not wildcard domain.
- No outbound email composition → no BEC injection risk → sanitizer skipped.
- JSONL append-only → no race during concurrent scans (Windows file append is atomic for <4KB lines).

## Next Steps

- Phase 03 adds VBA sync button to drain JSONL
- Phase 04 adds daily overdue sweep
- Phase 05 writes unit tests
