# Phase 03 — Test + Verify + Monitor

**Effort:** 1h active + 1 week passive monitoring
**Priority:** HIGH
**Status:** pending
**Depends on:** Phase 02

## Key Changes vs v1

- **+ Automated unit tests** (red-team D1)
- **Binary measurable metric** instead of 80%/5% theatre (red-team D3)
- **1 week soak test** with kill switch ready

## Smoke Test Suite (6 scenarios)

Each runs live against ERP + Outlook. Pass = checkmark.

### T1. Happy path — ATD end-to-end
- Setup: 1 customer CRM.AUTO_NOTIFY=Y, 1 Active Job with Bkg in CRM
- Forward 1 genuine OPS mail with ATD to Inbox
- Run: `python -m email_engine.core.shipment_brain` (existing)
- Expect: Outlook Draft created with `[AUTO]` prefix, correct placeholders, sidecar has entry

### T2. Dedup
- Run scanner twice in a row
- Expect: 2nd run creates 0 drafts (dedup hit)

### T3. Blacklist
- Forward "VESSEL CHANGE NOTICE" mail
- Expect: 0 drafts, log "skip — blacklist"

### T4. Spoofed auth
- Forward mail with broken/missing Authentication-Results header
- Expect: 0 drafts, log "auth fail"

### T5. Bulk mail rejection
- Forward mail containing 5+ Bkg numbers
- Expect: 0 drafts, Telegram "bulk detected"

### T6. Kill switch
- `touch email_engine/data/AUTO_NOTIFY_DISABLED`
- Run scanner
- Expect: 0 drafts, log "kill switch active"
- `rm AUTO_NOTIFY_DISABLED` to re-enable

## Automated Unit Tests

Already in Phase 02 `tests/test_cnee_milestone.py`. Run:

```bash
pytest tests/test_cnee_milestone.py -v
```

Expect: 5/5 pass (date parsing × 5, sanitize × 5, blacklist × 3, atd window × 1).

## Deployment

1. Enable Task Scheduler entry for ETA-7 daily
2. Verify `shipment_brain.py` hook is live (next 30-min scanner tick)
3. Telegram first summary should arrive within 30 min (may be "0 drafts" if no ATD)

## 1 Week Soak Test

Daily check (5 min each morning):

| Day | Check |
|-----|-------|
| D1 | Outlook Drafts count, review 1-by-1. Log any wrong ones. |
| D2 | Same. Check sidecar JSONL for orphan entries. |
| D3 | Review Telegram summaries. Note any false negatives (ATD mail received but no draft). |
| D4 | Mid-week: are numbers trending reasonable? |
| D5 | Nelson subjective: "đỡ công chưa?" — log yes/no. |
| D6-7 | Weekend off — check Monday for catch-up. |

## Success Criteria (binary, measurable)

- [ ] **Week 1: Nelson actually Sends ≥5 auto-drafts** (not deletes them)
- [ ] **Week 1: Zero drafts with wrong customer or wrong Bkg**
- [ ] **Week 1: Zero xlsm corruption** (open ERP daily, VBA + ribbon intact)
- [ ] **Week 1: Zero Outlook freeze complaints**
- [ ] **Week 1: Auth-Results filter rejects ≥1 test spoof** (Nelson or Claude sends 1 test spoof)

## Weekly Digest Job (optional, recommend)

Separate small script, runs Monday 07:00:

```python
# scripts/milestone_weekly_digest.py
# - Count mails matching ATD keywords from NON-allowlisted senders
# - Send Telegram: "X mails from <unknown> not auto-processed, review?"
# - Helps Nelson grow OPS_ALLOWLIST over time
```

## Rollback Plan

### Soft rollback (disable without data loss)
```bash
touch email_engine/data/AUTO_NOTIFY_DISABLED
# Scanner keeps running but creates 0 drafts. Review logs. Fix. Delete file to re-enable.
```

### Hard rollback (remove code)
```bash
# 1. Export current sidecar state
cp email_engine/data/milestone_state.jsonl plans/reports/milestone_state_rollback_$(date +%Y%m%d).jsonl

# 2. Remove hook call from shipment_brain.py (git revert 1 line)

# 3. Disable Task Scheduler entry

# 4. Optionally remove cols via:
python scripts/erp-add-milestone-cols.py --rollback
# (exports to CSV first, then drops cols)
```

## Post-Week Review (next Monday)

Document in memory file:
- Total drafts composed
- Total Sent (vs deleted)
- False positives (wrong customer/Bkg/date)
- False negatives (missed ATD mails)
- OPS_ALLOWLIST additions from weekly digest
- Nelson overall sentiment

Decide: ship v2 stable, or iterate on v3.

## Todo

- [ ] Run pytest → all pass
- [ ] Smoke test T1-T6 → all check
- [ ] Deploy: enable Task Scheduler + hook
- [ ] D1-D7 daily checks
- [ ] Weekly digest run Monday
- [ ] Write memory file `project-cnee-milestone-shipped.md`
- [ ] Update MEMORY.md index
- [ ] Update SYSTEM_STANDARDS with new inventory

## Success Signal

If all criteria met: ship status = STABLE. Commit: `feat(email): ship CNEE milestone auto-notify v2 (1 week soak pass)`.
