---
name: Email Dashboard Deliverability Roadmap v2 — Outlook COM reality
created: 2026-04-21
updated: 2026-04-21 (revised — no DNS access, Outlook COM only)
status: pending
blockedBy: []
blocks: []
related: [260416-email-nelson-solo-platform, 260420-2300-dashboard-bounce-fix]
effort: ~26h across 4 sprints (4 weeks)
owner: Nelson
strategic_goal: |
  1. Giảm bounce rate 0.35% → <0.15% qua DNS-level pre-flight + role/disposable detection
  2. Tối ưu inbox placement (O365 đã lo auth/reputation — focus vào ENGAGEMENT signals)
  3. Scale 2000-5000 email/tuần ổn định, không vượt O365 quota
  4. Automation workflow tiết kiệm 9h/tuần

constraints:
  - Nelson KHÔNG có DNS access → không sửa được SPF/DKIM/DMARC pudongprime.vn
  - Nelson KHÔNG có SMTP admin → gửi qua Outlook COM (Exchange Online)
  - Microsoft O365 lo: SPF/DKIM/DMARC, IP reputation, outbound SMTP
  - O365 enforce: 30 recipients/min, 10K recipients/day per mailbox
  - SMTP probe outbound RISKY (Microsoft có thể block + blacklist máy anh)
---

# Email Dashboard Deliverability Roadmap v2

**Reality check:** Nelson dùng Outlook COM (Exchange Online), không phải SMTP trực tiếp. Nhiều thứ "reputation building" trong SaaS email tool (SendGrid, Mailchimp) vô nghĩa ở đây — Microsoft đã lo.

**Focus mới:** Những gì Nelson CONTROL được = data quality + engagement quality + automation.

## 🎯 Paradigm shift

| Cái cũ nghĩ cần | Sự thật |
|-----------------|---------|
| Setup SPF/DKIM/DMARC | ❌ Microsoft đã lo cho mọi O365 tenant |
| Warmup IP reputation | ❌ MS có internal reputation cho Exchange mailbox |
| Manual daily cap tracking | ⚠ MS enforce 10K/day hard — chỉ cần WARNING trước khi chạm |
| SMTP probe toàn bộ 22K email | ❌ Rủi ro bị Microsoft + target server blacklist |
| Control IP outbound | ❌ Microsoft route qua shared IP pool |

## 🎯 Focus thực tế (Nelson có 100% control)

| Lever | Impact | How |
|-------|--------|-----|
| **Email đích valid** | 🔥 giảm bounce direct | Sprint 1 DNS MX + role/disposable filter |
| **Open rate** | 🔥 O365 signal inbox vs spam | Sprint 3 Smart send time |
| **Reply rate** | 🔥 O365 trust signal | Sprint 4 Follow-up cadence + AI draft |
| **Không spam khách cũ** | 🔥 retention | Cooldown 14d (đã ship) |
| **Không gửi cho email hard bounce** | 🔥 reputation protect | Suppression filter (đã ship) |

## 📅 Timeline (revised)

| Sprint | Week | Focus | Effort | File |
|--------|------|-------|--------|------|
| 1 | Week 1 | **Data Hygiene (DNS-only)** | 7h | [sprint-1-data-hygiene.md](sprint-1-data-hygiene.md) |
| 2 | Week 2 | **O365 Quota + Suppression auto** | 5h | [sprint-2-reputation-building.md](sprint-2-reputation-building.md) |
| 3 | Week 3 | **Smart Send + Analytics** | 7h | [sprint-3-smart-send.md](sprint-3-smart-send.md) |
| 4 | Week 4 | **Automation** | 9h | [sprint-4-automation.md](sprint-4-automation.md) |
| | | **Total** | **28h** | |

## 🎯 North Star metrics (revised expectations)

| Metric | Baseline | After Sprint 1 | After Sprint 4 |
|--------|----------|----------------|----------------|
| Bounce rate | 0.35% | <0.15% | <0.1% |
| Invalid emails flagged | ~8% | <4% | <3% (w/ retry) |
| Open rate | ~18% | 20% | 28-30% |
| Reply rate | ~0.9% | 1.2% | 2.5-3% |
| O365 quota usage | Untracked | Tracked + alert | Optimized |
| Reply SLA < 2h | manual | — | 90% |

## 🧱 Sprint breakdown

### Sprint 1 — Data Hygiene DNS-only (7h)
- [ ] DNS MX check 22K emails (5 phút runtime)
- [ ] Role-based detect (info@, admin@, support@ → lower priority)
- [ ] Disposable domain detect (10minutemail, temp-mail, guerrillamail...)
- [ ] Data Health widget trong Settings
- [ ] Weekly cronjob Monday 06:00 re-verify

**Skip (risky):** SMTP probe outbound — Microsoft có thể block + blacklist máy anh

**Accuracy target:** ~75-80% (60-70% DNS + 10-15% from role/disposable detect)

### Sprint 2 — O365 Quota + Suppression (5h)
- [ ] O365 quota tracker widget (sent today / 10K limit, sent this hour / 1800)
- [ ] Auto-throttle 30 recipients/min (tránh 429 rate limit)
- [ ] Warn Telegram khi quota > 80%
- [ ] Suppression auto-management (soft retry 3d, hard purge 30d)

**Skip (MS đã lo):** SPF/DKIM/DMARC validator — Microsoft setup mặc định cho O365

### Sprint 3 — Smart Send + Analytics (7h)
- [ ] Smart send time per timezone (US East/West → queue đúng giờ local)
- [ ] Campaign performance dashboard (18 campaigns open/reply/bounce)
- [ ] Engagement scoring + cold list auto (score < -5 → cold)

### Sprint 4 — Automation (9h)
- [ ] Reply SLA tracker + Telegram alert (VIP 30p, HOT 1h, default 4h)
- [ ] Auto follow-up Step 2/3 (7d + 14d + 21d cutoff)
- [ ] Reply Draft AI (MiniMax compose với thread context)

## 🔗 Dependencies

- Sprint 1 **unblocks** Sprint 2+3 (cần data sạch để quota tracker và engagement metric đáng tin)
- Sprint 2 **standalone** — có thể làm parallel với 3
- Sprint 3 + 4 sequential (Sprint 4 dùng engagement score từ Sprint 3)

## 🚫 Explicit NOT-DOING

- SPF/DKIM/DMARC setup (Microsoft lo, Nelson không có DNS access)
- Custom SMTP server / IP warmup (Outlook COM → no control)
- SMTP probe verifier (risky outbound, MS có thể block)
- Daily cap > 10K (MS hard enforce)
- Outbound IP reputation monitoring (MS shared pool)

## 🎓 Key insight — tại sao v1 plan wrong

V1 plan ảnh hưởng từ SaaS email marketing best practices (SendGrid/Mailchimp/custom SMTP). Nelson dùng Outlook COM + Office 365 → khác **completely**:

- SaaS: Nelson control mọi thứ → cần build reputation từ đầu
- O365: Microsoft control hạ tầng → Nelson chỉ cần **không làm hại reputation** (bounce thấp, engagement cao, không spam)

**Rule vàng:** Với O365, **gửi ít mà chất hơn gửi nhiều mà bẩn**. Sprint 1-4 đều hướng tới điều này.
