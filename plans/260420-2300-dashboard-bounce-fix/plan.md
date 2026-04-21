---
name: Dashboard Bounce/Reply Fix v2
created: 2026-04-20
updated: 2026-04-21 (shipped + extended with Class 46 ReportItem fix)
status: shipped
blockedBy: []
blocks: []
related: [260416-email-nelson-solo-platform]
effort: ~4h actual (plan 3-4h estimate)
owner: Nelson
shipped_notes: |
  - Phase A: Unified alerts feed (intel/events.db + CSV) ✅
  - Phase B: Suppression + Cooldown (14d default) + Settings UI ✅
  - Phase C: Move NDR to Deleted Items ✅
  - BONUS: Fixed ReportItem (Class 46) detection — was skipping 131 Microsoft NDR
  - BONUS: Quick Send badge 22,230 → 22,151 (-79 suppressed)
  - Final result: Inbox NDR 131→0, Deleted NDR 99→156, HARD_BOUNCE 4→79
---

# Plan — Dashboard Bounce/Reply Fix v2

**Created:** 2026-04-20 23:00

## Problem Statement

Sau fix bounce scanner (4 fixes earlier — window/folder/force/pattern), scanner đã chạy đúng:
- `226 scanned · 6 bounces · 5 replies` trong 30 ngày

**Nhưng dashboard vẫn hiện 0 bounces / 0 replies** vì:

1. **Data disconnect:** scanner mới ghi vào `intel/events.db` (email_events table) nhưng `/api/email-events/alerts` endpoint CHỈ đọc `logs/followup_alerts.csv` (sinh bởi scanner cũ).
2. **Email lỗi không loại khi Quick Send:** `cnee_master_v2.xlsx.EMAIL_STATUS` được update nhưng Quick Send không filter.
3. **Inbox đầy NDR:** mail lỗi không bị xóa/move sau khi process.

## Goal

Fix 3 vấn đề sao cho:
- Dashboard **hiển thị đúng** số bounces/replies/auto-replies trong Unified feed
- Quick Send **tự bỏ qua** HARD_BOUNCE + UNSUBSCRIBED, hiển thị counter
- Inbox **sạch** — NDR mail tự move vào Deleted Items sau khi process

## Architecture

```
╔═══ CURRENT (BROKEN) ═══════════════════════════════════════════╗
║ run_scan() → handlers.handle_bounce() → intel/events.db      ║
║                                        → cnee_master_v2.xlsx ║
║                                                                ║
║ Dashboard ──→ /api/email-events/alerts ──→ followup_alerts.csv║
║                                             ↑ (empty, legacy) ║
╚════════════════════════════════════════════════════════════════╝

╔═══ AFTER FIX ══════════════════════════════════════════════════╗
║ run_scan() → handlers.handle_bounce() → intel/events.db      ║
║                                        → cnee_master_v2.xlsx ║
║                                        → move item to Deleted║
║                                                                ║
║ Dashboard ──→ /api/email-events/alerts ──→ intel/events.db   ║
║                                         ↓ (merged)            ║
║                                         → followup_alerts.csv║
║                                                                ║
║ Quick Send ──→ filter EMAIL_STATUS NOT IN (HARD_BOUNCE, UNSUB)║
║                ↓                                              ║
║             show counter "Suppressed: X (breakdown)"          ║
╚════════════════════════════════════════════════════════════════╝
```

## Phases

| # | File | Effort | Purpose |
|---|------|--------|---------|
| A | [phase-a-unified-alerts-feed.md](phase-a-unified-alerts-feed.md) | 1.5h | Merge intel/events.db + CSV → unified API response |
| B | [phase-b-auto-suppression-ui.md](phase-b-auto-suppression-ui.md) | 2h | Quick Send filter (suppression + **cooldown dedup**) + counter + Settings list |
| C | [phase-c-ndr-mail-cleanup.md](phase-c-ndr-mail-cleanup.md) | 0.5h | handle_bounce moves NDR mail to Deleted Items |

**Total: ~4h**

## Updated scope — Phase B includes Cooldown

**Use case:** Anh chọn FLOORING batch 200 → gửi xong. 30 phút sau chọn FLOORING lại → hệ thống tự bỏ 195 email vừa gửi (cooldown 14 ngày default), chỉ gửi 5 email chưa gửi.

**Cơ chế:** Filter `email_log.csv` → set LAST_SENT_AT per email → skip nếu `LAST_SENT_AT + cooldown_days > today`.

**Config:** Default 14 ngày. UI có ô số điều chỉnh + checkbox "bỏ qua cooldown" cho trường hợp đặc biệt (re-send urgent).

## Files Touched

| File | Phase | Change |
|------|-------|--------|
| `email_engine/intel/memory.py` | A | Add `query_events(days, limit, types)` function |
| `email_engine/web_server.py` | A+B | Rewrite `_read_alerts_csv` → `_read_unified_alerts`, add Quick Send filter + `/api/suppression/list` |
| `email_engine/core/send_email.py` | B | Pre-send filter checks EMAIL_STATUS |
| `plans/visuals/email-dashboard-v5.html` | B | Add suppressed counter on Quick Send + Settings suppression table |
| `email_engine/scanner/handlers.py` | C | `handle_bounce` moves item to Deleted Items after logging |

## Success Criteria

- [ ] Dashboard Inbox tab shows **6 bounces + 5 replies + 12 auto-replies** (match scanner output)
- [ ] Quick Send 30d shows "Suppressed: X emails (Y hard-bounce, Z unsub)" counter
- [ ] Settings tab has table "Bounced Emails" listing suppressed entries
- [ ] After `run_scan(force=true)`, 6 NDR mails trong Inbox đã MOVE sang Deleted Items
- [ ] Running scan 2 lần → no duplicate events in DB (dedup on (email, type, timestamp))

## Out of Scope

- Re-enable old `followup_alerts.csv` pipeline (sẽ deprecate sau khi A xong)
- Bounce rate analytics dashboard (v3 feature)
- SMTP validation for outbound sends (Phase B only filters post-bounce)
- Re-engagement workflow for SOFT_BOUNCE (retry logic defer)

## Risks

| Risk | Mitigation |
|------|-----------|
| Dedup merge CSV + DB rows sai | Use composite key `(email, type, normalized_timestamp)` |
| Quick Send filter over-aggressive (suppress legit) | Whitelist override: checkbox "Include suppressed" trong UI |
| Move to Deleted fail khi Outlook busy | Try-except + log, không block handle_bounce |
| intel/events.db rất lớn (backfill 17K rows) | Limit query to last 30d + limit 1000 rows |

## Testing

Phase A: `curl /api/email-events/alerts?days=30&limit=100` → count >= 11 events
Phase B: Dashboard Quick Send → counter hiển thị, suppression list show bounced emails  
Phase C: Run scan → count NDR in Inbox drops to 0, Deleted Items has +6

## Dependencies

- Previous bounce scanner fix (4 fixes) already deployed — **required**
- Web server restart after changes (pythonw web_server.py kill + start)
