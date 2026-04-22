---
name: Daily Rotation Engine + Progress Dashboard
status: pending
priority: P0
created: 2026-04-22
mode: fast
effort_hours: 9
parent: 260422-1800-email-dashboard-v6-master
blockedBy: []
blocks: []
---

# Daily Rotation Engine — Email Dashboard v6

## Vấn đề

Sau scan 14d: 57 email đã gửi ≥ 5 lần (spam). 2,590/22,842 contact bị gửi 3+ lần. Cần rotation logic **tự động**:
- Daily 700 emails spread across commodities theo weight
- Per-email cooldown 7d (hard enforce)
- Per-email lifetime cap 3 / 30d
- Dashboard progress bar: "FLOORING 500/4,265 đã gửi"

## Mục tiêu

1. **Predictable:** mỗi sáng anh thấy "hôm qua gửi X, hôm nay gửi Y"
2. **Anti-spam toàn diện:** không ai nhận > 1 email/7d
3. **Vòng xoay 5 tuần:** 18,440 email chưa gửi ÷ 3,500/tuần = 5.3 tuần hết vòng 1
4. **UI "vơi dần":** progress bar mỗi commodity giảm dần qua thời gian

## Phase breakdown

| Phase | Mô tả | Effort | File chính |
|---|---|---|---|
| 1 | Rotation engine core | 3h | `email_engine/core/rotation_engine.py` |
| 2 | Progress API | 2h | `email_engine/api/routes/rotation_router.py` |
| 3 | Dashboard UI | 3h | `plans/visuals/email-dashboard-v6.html` |
| 4 | Daily scheduler + cron | 1h | Task Scheduler + fallback button |
| 5 | Emergency 57 spam block | ✅ DONE | `excluded_customers.json` (từ scan agent) |

**Total:** 9h · Ship trong 1 session đêm nay nếu OK.

## Success criteria

- [ ] Endpoint `/api/rotation/today` trả plan hôm nay theo quota
- [ ] Dashboard hiển thị 6 commodity progress bar với số "X/Y gửi"
- [ ] Widget "Hôm qua: 650 sent" và "Hôm nay: 700 planned"
- [ ] Cycle indicator "Vòng 1 · tuần 2/5"
- [ ] Click "Start today's batch" → queue 700 email qua Smart Send Window
- [ ] Restart dashboard không ai nhận > 1 email/7d (test với 10 recipient mẫu)

## Depends on

- ✅ Phase 1 Data Migration (contact_unified_v6.xlsx)
- ✅ Phase 2.5 Safety Net (cooldown 14d, hard limit, typo_shield wired)
- ✅ Scan Sent agent (57 spam đã blocked)

## Risks

| Risk | Mitigation |
|---|---|
| Nelson chỉnh quota sai → 1 commodity đói | UI validator + default fallback |
| Scheduler miss window | Manual trigger button + Telegram alert |
| Hết candidate giữa vòng | Auto-redistribute quota sang commodity còn data |
| Recipient nhận 2 email liền do race condition | Lock mechanism trong `_do_send` + unique constraint |

## Next step

Nelson approve plan này → run `/ck:cook plans/260422-2100-daily-rotation-engine` hoặc em kick agent ngay nếu nói "GO".
