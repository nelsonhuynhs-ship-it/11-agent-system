# Phase 04 — Daily Overdue Sweep + Telegram Alert

**Priority:** P2 · **Status:** pending · **Effort:** 30m · **Blocked by:** Phase 01, 02

## Context Links

- [plan.md](plan.md)
- [phase-02-scanner-hook.md](phase-02-scanner-hook.md) — `run_overdue_sweep()` CLI entry
- Task Scheduler pattern: `project-task-scheduler.md` (NelsonUnifiedScanner + cnee eta-reminder at 08:00)

## Goal

Daily job 08:05 reads InvoiceLog, finds PENDING rows with DUE_DATE < today, appends OVERDUE state entries to sidecar + sends consolidated Telegram alert.

Runs 5 min after CNEE eta-reminder (08:00) to avoid concurrent xlsm read spike.

## Key Insights

- Sidecar pattern applies to overdue too — cron DOES NOT write xlsm. Sidecar drains via Nelson clicking "Sync Invoices" (Phase 03).
- Dedup: dedup check `{type:"OVERDUE_ALERTED", bkg:X, date:today-within-7d}` prevents Telegram spam — only alert once per week per overdue invoice.
- Read-only openpyxl safe for concurrent access with Nelson's xlsm open.

## Requirements

**F1:** Load InvoiceLog via openpyxl read-only.
**F2:** For each row where STATUS=PENDING AND DUE_DATE < today:
  - If no recent OVERDUE_ALERTED entry in sidecar (<7d) → queue entry + queue Telegram line
  - If already alerted within 7d → skip
**F3:** Telegram message format:
  ```
  Invoice Overdue Sweep (2026-04-21)
  
  3 overdue invoices, total $12,450:
  • ABC Imports — BKG1234 — $4,200 (12d past due)
  • XYZ Corp — BKG5678 — $6,000 (3d past due)
  • DEF LLC — BKG9999 — $2,250 (1d past due)
  
  Run "Sync Invoices" in ERP to apply OVERDUE status.
  ```
**F4:** Exit code 0 always (don't fail Task Scheduler on empty-result).

**NF1:** Max 50 overdue alerts per day (rate limit safeguard).
**NF2:** Idempotent — running twice same day = no duplicate sidecar entries.

## Related Code Files

**Modify:**
- `email_engine/core/invoice_tracker.py`:
  - Add `run_overdue_sweep()` function
  - Extend CLI `if __name__ == "__main__":` block with `overdue-sweep` arg

**New:**
- Task Scheduler XML export: `scripts/task_scheduler/NelsonInvoiceOverdueSweep.xml`

## Implementation Steps

1. **Implement `run_overdue_sweep()`** in `invoice_tracker.py`:
   ```python
   def run_overdue_sweep() -> int:
       """
       Daily cron: scan InvoiceLog for overdue PENDING rows.
       Queue sidecar state + Telegram alert.
       Returns count of new OVERDUE alerts.
       """
       if not _check_kill_switch():
           return 0
       
       if not ERP_PATH.exists():
           log.error("invoice_tracker: ERP not found: %s", ERP_PATH)
           return 0
       
       from ERP.core.invoice_log_cols import COL as IC, HEADER_ROW as IH
       
       import openpyxl
       today = date.today()
       alerts: list[dict] = []
       
       try:
           wb = openpyxl.load_workbook(str(ERP_PATH), read_only=True, data_only=True)
           ws = wb["InvoiceLog"]
           for row in ws.iter_rows(min_row=IH + 1, values_only=True):
               if not any(row):
                   continue
               bkg = str(row[IC["BKG_NO"] - 1] or "").strip()
               if not bkg:
                   continue
               status = str(row[IC["STATUS"] - 1] or "").strip().upper()
               if status != "PENDING":
                   continue
               due_raw = row[IC["DUE_DATE"] - 1]
               due = _parse_due_date(due_raw)
               if not due or due >= today:
                   continue
               # Already alerted recently?
               if _recently_alerted(bkg, cutoff_days=7):
                   continue
               alerts.append({
                   "bkg": bkg,
                   "customer": str(row[IC["CUSTOMER"] - 1] or "").strip(),
                   "amount": float(row[IC["AMOUNT"] - 1] or 0),
                   "due": due,
                   "days_past": (today - due).days,
               })
           wb.close()
       except Exception as e:
           log.error("invoice_tracker: overdue sweep load failed: %s", e)
           return 0
       
       if not alerts:
           log.info("invoice_tracker: no overdue invoices today")
           return 0
       
       # Rate limit
       if len(alerts) > 50:
           log.warning("invoice_tracker: %d alerts, truncating to 50", len(alerts))
           alerts = alerts[:50]
       
       # Write sidecar + build Telegram message
       total_amount = sum(a["amount"] for a in alerts)
       lines = [f"Invoice Overdue Sweep ({today.isoformat()})", ""]
       lines.append(f"{len(alerts)} overdue invoices, total ${total_amount:,.0f}:")
       for a in alerts:
           lines.append(
               f"• {a['customer']} — {a['bkg']} — ${a['amount']:,.0f} "
               f"({a['days_past']}d past due)"
           )
           _write_state(a["bkg"], "", "OVERDUE", today.isoformat(), None)
           _write_alerted_marker(a["bkg"], today.isoformat())
       lines.append("")
       lines.append('Run "Sync Invoices" in ERP to apply OVERDUE status.')
       
       _send_telegram("\n".join(lines)[:4000])
       return len(alerts)
   
   
   def _recently_alerted(bkg: str, cutoff_days: int = 7) -> bool:
       """Check if OVERDUE_ALERTED entry exists in sidecar within cutoff window."""
       if not STATE_FILE.exists():
           return False
       cutoff = (date.today() - timedelta(days=cutoff_days)).isoformat()
       bkg_upper = bkg.strip().upper()
       try:
           with STATE_FILE.open(encoding="utf-8") as f:
               for line in f:
                   try:
                       entry = json.loads(line)
                   except json.JSONDecodeError:
                       continue
                   if (entry.get("type") == "OVERDUE_ALERTED"
                           and entry.get("bkg", "").upper() == bkg_upper
                           and entry.get("date", "") >= cutoff):
                       return True
       except OSError:
           pass
       return False
   
   
   def _write_alerted_marker(bkg: str, event_date: str) -> None:
       """Dedup marker — append OVERDUE_ALERTED entry."""
       _write_state(bkg, "", "OVERDUE_ALERTED", event_date, None)
   
   
   def _parse_due_date(val) -> Optional[date]:
       if not val:
           return None
       if isinstance(val, datetime):
           return val.date()
       if isinstance(val, date):
           return val
       # String fallback
       s = str(val).strip()
       for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
           try:
               return datetime.strptime(s, fmt).date()
           except ValueError:
               continue
       return None
   ```

2. **Extend CLI entry:**
   ```python
   if __name__ == "__main__":
       logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)-8s %(message)s")
       if len(sys.argv) > 1 and sys.argv[1] == "overdue-sweep":
           n = run_overdue_sweep()
           print(f"Overdue alerts queued: {n}")
       else:
           print("Usage: python -m email_engine.core.invoice_tracker overdue-sweep")
           sys.exit(1)
   ```

3. **Create Task Scheduler entry:**
   - Name: `NelsonInvoiceOverdueSweep`
   - Trigger: Daily 08:05 (weekdays only — Monday-Friday)
   - Action: `python.exe -m email_engine.core.invoice_tracker overdue-sweep`
   - Working dir: `D:/NELSON/2. Areas/Engine_test`
   - Run whether user logged in or not: Yes
   - Settings: stop if runs >5min
   - Export XML to `scripts/task_scheduler/NelsonInvoiceOverdueSweep.xml`

4. **Install on PC Home** (where NelsonUnifiedScanner runs):
   ```powershell
   schtasks /Create /XML "scripts\task_scheduler\NelsonInvoiceOverdueSweep.xml" /TN "NelsonInvoiceOverdueSweep"
   ```

5. **Smoke test:**
   - Insert fake InvoiceLog row with DUE_DATE=yesterday, STATUS=PENDING, AMOUNT=5000
   - Run `python -m email_engine.core.invoice_tracker overdue-sweep`
   - Verify: Telegram received, sidecar has OVERDUE + OVERDUE_ALERTED entries
   - Run again immediately → 0 alerts (dedup working)

## Todo List

- [ ] Implement `run_overdue_sweep()`
- [ ] Implement `_recently_alerted()` + `_write_alerted_marker()` + `_parse_due_date()`
- [ ] Extend CLI block
- [ ] Create Task Scheduler XML
- [ ] Install scheduled task on PC Home
- [ ] Smoke test with fixture row
- [ ] Verify Telegram received
- [ ] Verify dedup works on re-run

## Success Criteria

- [ ] Fixture row (DUE_DATE yesterday) → 1 Telegram alert sent
- [ ] Run again same day → 0 new alerts (dedup)
- [ ] Run 8 days later → re-alerts (7-day cutoff)
- [ ] Task Scheduler shows "Last run result: 0x0" after 08:05 weekday run
- [ ] Empty InvoiceLog → exit code 0, no Telegram spam

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Openpyxl read fails because Nelson has xlsm open | Retry 3 times with 30s backoff. If still fails → Telegram "sweep deferred" alert. |
| Date parse fails on xlsm Date cell (returns float serial) | openpyxl returns `datetime` for Date-formatted cells natively. `_parse_due_date` handles str fallback. |
| Telegram API down | `_send_telegram` already logs + returns False. Sidecar still written. Next-day run re-alerts after 7d. Not critical. |
| DST transition causes 08:05 to fire twice | Task Scheduler default handles DST. Low-risk (Vietnam no DST). |
| NelsonUnifiedScanner overlap (both running 08:00-08:05) | CNEE eta-reminder 08:00 uses openpyxl read-only — same as sweep. Concurrent read safe. |
| 50-alert cap hides real overdue | If >50 → Telegram "truncated, see InvoiceLog manually". Nelson triages. |

## Security Considerations

- No outbound email — only Telegram (trust-bounded channel).
- Sidecar write is append-only.
- Task runs as Nelson's user account — inherits file permissions.

## Out of Scope

- Auto-email customer reminder (Nelson always reviews + sends manually)
- Escalation tiers (1d/7d/14d different messages) — future
- Currency conversion (USD assumed)

## Next Steps

Phase 05 covers end-to-end tests including this path.
