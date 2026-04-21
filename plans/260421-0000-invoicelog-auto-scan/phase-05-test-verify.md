# Phase 05 — Test + Verify

**Priority:** P2 · **Status:** pending · **Effort:** 30m · **Blocked by:** Phase 02, 03, 04

## Context Links

- [plan.md](plan.md)
- [phase-02-scanner-hook.md](phase-02-scanner-hook.md)
- [phase-03-win-integration.md](phase-03-win-integration.md)
- [phase-04-overdue-daily.md](phase-04-overdue-daily.md)
- CNEE test pattern: `tests/test_cnee_milestone.py`

## Goal

Automated pytest coverage for invoice_tracker.py + manual smoke for VBA paths. Gate: all tests GREEN before Nelson uses live.

## Test Matrix

### Unit (pytest — `tests/test_invoice_tracker.py`)

| # | Function | Input | Expected |
|---|---|---|---|
| U1 | `_classify_payment_type` | "payment received for INV-0042" | "PAID" |
| U2 | `_classify_payment_type` | "nhắc thanh toán — BKG123" | "REMIND" |
| U3 | `_classify_payment_type` | "đã nhận thanh toán của đơn này" | "PAID" |
| U4 | `_classify_payment_type` | "booking confirmation" | None |
| U5 | `_classify_payment_type` | "đã vào tiền 5000 USD" | "PAID" |
| U6 | `_extract_invoice_numbers` | "INV-0042 and INV 1234567" | ["0042", "1234567"] |
| U7 | `_extract_invoice_numbers` | "no invoice here" | [] |
| U8 | `_parse_due_date` | datetime(2026,4,20) | date(2026,4,20) |
| U9 | `_parse_due_date` | "20/04/2026" | date(2026,4,20) |
| U10 | `_parse_due_date` | "invalid" | None |
| U11 | `_check_kill_switch` with file present | — | False |
| U12 | `_check_kill_switch` without file | — | True |
| U13 | `_recently_alerted` with 3d-old marker | bkg="X", cutoff=7 | True |
| U14 | `_recently_alerted` with 10d-old marker | bkg="X", cutoff=7 | False |

### Integration (pytest with fixtures)

| # | Scenario | Setup | Expected |
|---|---|---|---|
| I1 | Full hook — PAID detection | Fake MailItem class w/ Subject="Payment received BKG12345", sender in allowlist, auth passes | Sidecar has `{"type":"PAID","bkg":"BKG12345"}` |
| I2 | Full hook — REMIND detection | MailItem Subject="Nhắc thanh toán INV-0099" | Sidecar has `{"type":"REMIND","invoice_no":"0099"}` |
| I3 | Sender not in allowlist | MailItem sender="outsider@gmail.com" | Skipped, no sidecar write |
| I4 | Bulk mail reject | 6 BKGs in text | Rejected, Telegram warn queued |
| I5 | Kill switch active | Touch KILL_SWITCH file | Hook returns False immediately |
| I6 | Overdue sweep — fixture InvoiceLog | Temp xlsx with 2 overdue rows + 1 paid row | 2 sidecar entries + Telegram |
| I7 | Overdue dedup | Run sweep twice same day | 2nd run: 0 new alerts |

### Manual VBA Smoke

| # | Action | Expected |
|---|---|---|
| V1 | Open ERP, mark a test quote as WIN | New InvoiceLog row appended, STATUS=PENDING, DATE_ISSUED=today, DUE_DATE=today+30 |
| V2 | Mark same quote WIN again | Immediate window shows "already present, skip" — no duplicate row |
| V3 | Manually edit sidecar JSONL with `{"type":"PAID","bkg":"TEST1","date":"2026-04-21"}` | Click "Sync Invoices" → row STATUS=PAID, PAID_DATE=21/04/2026, sidecar truncated |
| V4 | Click "Sync Invoices" with sidecar entry for non-existent BKG | MsgBox "1 skipped (not found)" |
| V5 | Open Alt+F11 after migration | All existing VBA modules intact, no "missing references" |

### End-to-End Soak (1 week live)

| Metric | Target |
|---|---|
| Zero xlsm corruption | Nelson never reports "file damaged" message |
| Zero false-positive PAID flips | Manual audit of InvoiceLog STATUS=PAID rows weekly — all should have matching real payment |
| At least 1 overdue Telegram | Dependent on real overdue invoices — test criterion: fixture row if none real |
| Sidecar drains | `invoice_state.jsonl` < 100 lines after Nelson clicks Sync weekly |

## Implementation Steps

1. **Create `tests/test_invoice_tracker.py`:**
   - Import invoice_tracker
   - Unit tests U1-U14 (straightforward assertions)
   - Integration I1-I7: use `unittest.mock.MagicMock` for MailItem (mirror CNEE test approach)
   - Use `tmp_path` pytest fixture to isolate sidecar + kill switch + daily counter
   - Monkeypatch `STATE_FILE`, `KILL_SWITCH`, `DAILY_COUNTER` to temp paths

2. **Run pytest:**
   ```bash
   python -m pytest tests/test_invoice_tracker.py -v
   ```
   Gate: all green before Phase 03 VBA reload.

3. **Execute manual VBA smokes V1-V5** with test quote data.

4. **Kick off 1-week soak:**
   - Populate `ACCOUNTING_ALLOWLIST` with best-guess seed (accounting team Pudong addresses)
   - Leave system running
   - Check Telegram digest daily
   - Day 7 audit: correctness + Telegram fidelity + sidecar drain

## Todo List

- [ ] Write 14 unit tests
- [ ] Write 7 integration tests with MagicMock + tmp_path
- [ ] Run pytest → green
- [ ] Execute V1-V5 manually
- [ ] Seed ACCOUNTING_ALLOWLIST
- [ ] Start 1-week soak
- [ ] Day 3 + Day 7 audits

## Success Criteria

- [ ] `pytest tests/test_invoice_tracker.py` → 21 passed
- [ ] All 5 manual VBA smokes pass
- [ ] 1-week soak passes all 4 soak metrics
- [ ] Update `plan.md` status to `completed` after soak green

## Rollback

If soak fails:
- Touch `INVOICE_TRACKER_DISABLED` → hook becomes no-op
- Disable Task Scheduler entry
- Existing WIN rows stay in InvoiceLog (harmless Nelson can delete manually)

## Next Steps

After soak success:
- Document in `docs/SYSTEM_STANDARDS.md` (new section: Invoice Tracker)
- Consider v2 features from "Out of Scope" list (dashboard cell, PAID_AMOUNT reconcile)
