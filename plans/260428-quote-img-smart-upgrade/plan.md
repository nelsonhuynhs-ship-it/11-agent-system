---
title: Quote Img Smart Upgrade
slug: quote-img-smart-upgrade
created: 2026-04-28
owner: Nelson
status: pending
mode: hard
blockedBy: []
blocks: []
---

# Plan — Quote Img Smart Upgrade

## Goal
Nâng cấp 1 nút `btnQuoteImage` (label "Quote Img") sẵn có thành smart-aware, KHÔNG thêm nút mới. Restore search filter state khi quay lại sheet Pricing. Pass E2E test trước khi merge.

**Source spec (HTML approved by Sếp 2026-04-28):**
`D:/OneDrive/NelsonData/reports/2026-04-28/quote-workflow-upgrade.html`

## Success Criteria (Sếp will accept when)
1. Sếp đứng ở **Pricing sheet**, bấm Quote Img → hệ thống tự nhảy sang Quotes + render ảnh nhóm quote mới nhất (cùng customer + cùng ngày).
2. Sếp đứng ở **Quotes sheet** không select dòng nào → render nhóm quote mới nhất.
3. Sếp đứng ở **Quotes sheet** select N dòng cụ thể → render N dòng đó (backward compat).
4. Hôm nay chưa có quote nào → MsgBox thân thiện, không crash.
5. Sếp filter HPH→USLAX trên Pricing → sang Quotes → quay lại Pricing → bảng giá hiện y nguyên (không phải gõ lại).
6. `scripts/verify-erp.bat` exit code 0.
7. `e2e_runner.py` pass tất cả new cases.

## Out of Scope (KHÔNG đụng)
- `btnQuoteImageBulk` (chức năng gửi N khách qua sheet BulkRecipients)
- `OnAction_GenerateQuote` (Sếp đã reject auto-jump sau quote — multi-port use case)
- Schema Quotes sheet (cols, headers giữ nguyên)
- Ribbon XML structure (chỉ cập nhật screentip, label giữ "Quote Img")

## Phases

| # | Phase | File | Effort | Owner |
|---|-------|------|--------|-------|
| 1 | Smart logic cho OnAction_QuoteImage | [phase-01-quote-img-smart.md](phase-01-quote-img-smart.md) | ~40 LOC VBA | MM M2.7 |
| 2 | Filter restore khi Sheet Deactivate/Activate | [phase-02-filter-restore.md](phase-02-filter-restore.md) | ~30 LOC VBA | MM M2.7 |
| 3 | E2E test cases + verify | [phase-03-e2e-test.md](phase-03-e2e-test.md) | ~60 LOC pytest + 4 e2e cases | MM M2.7 |

Total: ~130 LOC. Estimated MM execution: 15-25 min.

## Files Touched
**Canonical (OneDrive — edit here first):**
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` (modify `OnAction_QuoteImage` at line 3224)
- `D:/OneDrive/NelsonData/erp/erp-v14-thisworkbook.txt` → ThisWorkbook module (add `Workbook_SheetDeactivate`, modify `Workbook_SheetActivate`)

**Mirror (sync after edit via `cp` per ERP/vba-v14-mirror/README.md):**
- `Engine_test/ERP/vba-v14-mirror/erp-v14-ribbon-callbacks.bas`
- `Engine_test/ERP/vba-v14-mirror/erp-v14-thisworkbook.txt`

**New tests:**
- `Engine_test/tests/test_quote_img_smart.py` (unit + integration around state/group detection)
- Append 4 cases to `Engine_test/plans/260426-erp-e2e-test-automation/e2e_test_cases.json`
- Add 4 wrapper macros to `D:/OneDrive/NelsonData/erp/erp-v14-test-e2e.bas`

## Risk + Rollback
- Backup canonical .bas before edit: `cp erp-v14-ribbon-callbacks.bas erp-v14-ribbon-callbacks.bas.bak.260428`
- Rollback (5 min): restore .bak file → reimport via `scripts/reimport-erp-vba-modules.py`
- E2E test ensures no regression on existing 6 cases (search/highlight/gateway).

## Compliance Gates
- ERP_STANDARDS.md §1.1 source-of-truth imports (no hardcoded col integers — use AJ_/Q_ constants already defined)
- vba-gotchas #4 (Break on All Errors disabled before run)
- vba-gotchas #6 (`save_preserving_ribbon` after any python-side workbook write)
- DOMAIN-ERP Rule 1 (Quote insert row 5, QuoteGroupID col 43) — used READ-only, not modified

## Delegation
Execution delegated to MiniMax M2.7 sidecar (`~/.claude/bin/mm-claude.sh`).
Opus role: brain (this plan, final verify). MM role: implement + run tests until green.
