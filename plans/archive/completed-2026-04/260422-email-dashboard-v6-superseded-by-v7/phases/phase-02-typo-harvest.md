# Phase 2 — Typo Shield + Bounce Harvest v2 + Smart Send Window

**Status:** DONE (2026-04-22)
**Effort:** 8h (was 6h, +2h cho 2B)
**Cost:** $0
**Depends on:** Phase 1

## Overview

(A) Chặn 345 email `.co`/`.cm`/`.og` đang gửi im lặng. (B) Bounce scan 2-chiều: clean dead + harvest replacement từ auto-reply. **(C) Smart Send Window** — gửi theo timezone khách (9h-11h local) → kỳ vọng open rate 3.7% → 8-10%.

## Key insights

- Regex `{2,}` ở `email_verifier.py:9` cho `.co` (Colombia có MX thật) pass qua → gửi fail im lặng
- 3 file .msg auto-reply mẫu chứa 7 replacement email mà scanner cũ không extract
- 2 pattern khác nhau: OOO (temp, defer) vs LEFT (permanent, mark dead + harvest)

## Requirements

- Block `.co` trước khi enqueue send
- Fuzzy match domain top-500 common (gmail.co → suggest gmail.com)
- Auto-reply detector 2 loại: OOO vs LEFT
- Extract 1-3 replacement emails per auto-reply
- Auto-insert replacement vào master với `REPLACEMENT_FOR` metadata
- OOO → defer sends đến return_date
- LEFT → mark EMAIL_STATUS=DEAD original email

## Files to create

- `email_engine/core/typo_shield.py` — fuzzy domain match
- `email_engine/core/bounce_harvest_v2.py` — 2-way scanner upgrade

## Files to update

- `email_engine/core/email_verifier.py` — fix regex, whitelist TLD
- `email_engine/scanner/handlers.py` — add harvest hook
- Inbox tab HTML — add Harvest panel

## Implementation steps

1. Fix regex trong `email_verifier.py` — whitelist TLD com/net/org/vn/... (0.5h)
2. Viết `typo_shield.py` fuzzy match top-500 (1h)
3. 345 suspect review UI + API endpoint (0.5h)
4. Viết `bounce_harvest_v2.py`:
   - OOO pattern detector (regex "out of office", "return on", date parse)
   - LEFT pattern detector ("no longer with", "has left")
   - Replacement email extractor (regex emails trong body, exclude sender's own)
   - POSITION inference (pricing/booking/ops từ context)
   (2h)
5. Hook vào scanner handlers (0.5h)
6. Inbox tab Harvest panel (1h)
7. Unit test với 3 file .msg mẫu (0.5h)

## Todo checklist

- [ ] `email_verifier.py` regex fixed + TLD whitelist
- [ ] `typo_shield.py` fuzzy match works (test gmail.co → gmail.com)
- [ ] 345 suspect review UI in Settings
- [ ] OOO detector pass 3 test .msg
- [ ] LEFT detector pass 3 test .msg
- [ ] Replacement extractor returns 7 emails from 3 samples
- [ ] Auto-insert to master with REPLACEMENT_FOR set
- [ ] Inbox Harvest panel displays queue

## Success criteria

- 345 .co emails blocked before send
- 3 test .msg yield 7 replacement contacts added to master
- OOO defers send to correct return_date
- LEFT marks original EMAIL_STATUS=DEAD

## Risk assessment

| Risk | Mitigation |
|---|---|
| Typo shield false positive (legit .co) | Nelson review UI 1-click approve |
| Replacement extractor grabs sender signature | Exclude sender domain, check position keywords |
| Auto-insert spams master | Require Nelson confirm in Harvest panel before insert |
| Smart send queue delay làm miss urgent | Flag `URGENT=1` bypass queue, gửi ngay |

---

## 2B — Smart Send Window (NEW — approved 2026-04-22)

### Vấn đề hiện tại

Dashboard gửi email bất kể giờ local khách → US/Canada khách đang ngủ khi email tới → email chìm dưới 50 mail khác → open rate 3.7%.

### Giải pháp

Queue thông minh theo TIMEZONE cột sẵn có trong schema v3.

### Rule set

```
PEAK WINDOW (ưu tiên gửi):
  Thứ 3 · Thứ 4 · Thứ 5
  9h00 — 11h00 local time (giờ khách)

AVOID:
  Thứ 2 sáng <10h local  (inbox overload sau weekend)
  Thứ 6 chiều >15h local (ai cũng đi về)
  Thứ 7 + Chủ nhật      (B2B không mở mail)

URGENT override:
  Flag URGENT=1 bypass queue → gửi ngay lập tức

HOLIDAY skip:
  US federal holiday (Memorial Day, July 4th, Thanksgiving, Christmas)
  Auto-skip via python `holidays` lib
```

### Files to create

- `email_engine/core/smart_send_window.py` — timezone-aware queue planner
- `email_engine/core/us_holidays.py` — holiday check wrapper

### Files to update

- `email_engine/web_server.py` — Quick Send endpoint nhận `use_smart_window=True` flag
- `email_engine/scanner/handlers.py` — scheduler pick up queued items at right UTC time
- Tab Send UI — toggle "Smart Send Window" ON/OFF + preview queue distribution

### Logic core

```python
# smart_send_window.py — pseudocode

def plan_send_time(contact, now_utc=None):
    tz        = contact['TIMEZONE']              # e.g., "America/Los_Angeles"
    local_now = now_utc.astimezone(ZoneInfo(tz))
    
    # Start with next 9am local
    target = local_now.replace(hour=9, minute=0)
    if local_now.hour >= 11:                     # missed today's window
        target = target + timedelta(days=1)
    
    # Skip weekend
    while target.weekday() >= 5:                 # Sat=5, Sun=6
        target += timedelta(days=1)
    
    # Skip Monday <10am
    if target.weekday() == 0 and target.hour < 10:
        target = target.replace(hour=10)
    
    # Skip US holiday
    while target.date() in us_holidays():
        target += timedelta(days=1)
    
    return target.astimezone(UTC)                # return UTC for scheduler
```

### Implementation steps (2h)

1. `us_holidays.py` wrapper với `holidays` lib (15 min)
2. `smart_send_window.py` core logic (45 min)
3. Unit test 10 scenarios (California Friday 16h, NY Sunday, Texas holiday...) (30 min)
4. Hook vào web_server.py Quick Send (15 min)
5. UI toggle + preview widget (15 min)

### Todo checklist

- [ ] `smart_send_window.py` returns correct UTC for 10 test cases
- [ ] Weekend skip works (Fri 16h US → next Tue 9am)
- [ ] Holiday skip works (July 3 send → July 5)
- [ ] URGENT flag bypass works
- [ ] UI toggle persists preference
- [ ] Preview widget shows "5 emails queued for Tue 9am PST, 3 for Wed 9am EST..."

### Success criteria

- 100% Quick Send batches honor timezone window khi toggle ON
- A/B test 2 tuần: Smart ON vs OFF → open rate lift ≥ 2x
- Zero email sent outside 8-18h local window (trừ URGENT)

### Expected impact

| Metric | Baseline | Smart Send target |
|---|---|---|
| Open rate | 3.7% | 8-10% |
| Reply rate | 0.8% | 1.5-2% |
| Unsubscribe | 0.5% | 0.3% (ít annoy hơn) |
