# Phase 06 — Test + Verify

**Effort:** 0.5h (Claude) + 1 ngày monitoring (Nelson)
**Priority:** HIGH
**Status:** pending
**Depends on:** Phase 01-05

## Overview

End-to-end test với 2-3 job thật + 1 ngày monitoring sau khi deploy. Verify correctness trước khi rollout full.

## Test Plan

### Test 1 — ATD End-to-End (manual trigger)

1. **Setup:**
   - Pick 1 customer trong CRM → set AUTO_NOTIFY = TRUE
   - Customer có ít nhất 1 active job trong Active Jobs
   - Forward 1 mail OPS có ATD cho Bkg đó vào Inbox
2. **Run:** `python email_engine/core/outlook_scanner.py --job shipment_brain`
3. **Verify:**
   - [ ] Outlook Drafts có 1 mail mới
   - [ ] To = CNEE email đúng
   - [ ] Subject + Body điền placeholder đúng
   - [ ] Active Jobs.ATD có date mới
   - [ ] Active Jobs.LAST_NOTIFIED = "ATD YYYY-MM-DD"
   - [ ] Telegram nhận summary

### Test 2 — Dedup Check

1. Run scanner lần thứ 2 ngay sau Test 1
2. Verify:
   - [ ] Không tạo draft mới
   - [ ] Log: "Skip — already notified ATD"

### Test 3 — Blacklist Check

1. Forward mail OPS có "VESSEL CHANGE NOTICE"
2. Run scanner
3. Verify:
   - [ ] KHÔNG tạo draft
   - [ ] Log: "Skip — blacklisted pattern VESSEL CHANGE"

### Test 4 — CRM Opt-out

1. Pick customer có AUTO_NOTIFY = FALSE
2. Forward mail ATD cho Bkg của customer đó
3. Run scanner
4. Verify:
   - [ ] KHÔNG tạo draft
   - [ ] Log: "Skip — AUTO_NOTIFY disabled"

### Test 5 — Missing CNEE Email

1. Pick customer có AUTO_NOTIFY=TRUE nhưng EMAIL rỗng cả CRM + Active Jobs
2. Forward mail ATD
3. Run scanner
4. Verify:
   - [ ] KHÔNG tạo draft
   - [ ] Telegram: "⚠ Missing CNEE email for ..."

### Test 6 — ETA-7 Daily

1. Set 1 job có ETA = today + 7, AUTO_NOTIFY=TRUE
2. Manual trigger: `python email_engine/core/outlook_scanner.py --job eta_reminder_daily`
3. Verify:
   - [ ] Draft ETA-7 tạo đúng template
   - [ ] LAST_NOTIFIED append "| ETA-7 YYYY-MM-DD"

## Monitoring Checklist (1 ngày sau deploy)

- [ ] Scanner log không crash
- [ ] Draft tạo hợp lệ (Nelson manual verify 5 draft)
- [ ] Không false positive (draft không phù hợp)
- [ ] Không missing cases (ATD không được detect)
- [ ] Telegram summary đầy đủ

## Rollback Plan

Nếu phát hiện issue critical:

1. Disable job trong `scanner_rules.json`: `"enabled": false`
2. Restart Task Scheduler
3. Fix issue → re-enable

Rollback CRM/Active Jobs schema (nếu cần):
- Phase 01 script có flag `--rollback` để xoá 4 cột mới

## Todo List

- [ ] Chạy Test 1 — ATD end-to-end
- [ ] Chạy Test 2 — Dedup
- [ ] Chạy Test 3 — Blacklist
- [ ] Chạy Test 4 — CRM opt-out
- [ ] Chạy Test 5 — Missing email
- [ ] Chạy Test 6 — ETA-7 daily
- [ ] 1 ngày monitoring
- [ ] Update SYSTEM_STANDARDS.md với inventory mới
- [ ] Update memory file với feature status

## Success Criteria

- [ ] Toàn bộ 6 test pass
- [ ] 0 false positive trong ngày đầu
- [ ] 0 draft sai placeholder
- [ ] Nelson verify: "Mail tạo đúng style, send được"

## Next Steps (Post-Ship)

1. Memory update: tạo file `project-cnee-milestone-notify-shipped.md`
2. Update MEMORY.md index
3. Commit tất cả changes (conventional commit)
4. NEXT_SESSION_PROMPT.md update với status shipped
5. Monitor 1 tuần → collect metrics cho success criteria
