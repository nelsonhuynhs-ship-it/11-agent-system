# Phase 5A — WhatsApp SANDBOX (FREE tier test)

**Status:** PENDING
**Effort:** 6h (dev) + Nelson setup Meta (1-2 ngày)
**Cost:** $0
**Depends on:** Phase 1
**Duration:** 1 tuần test

## Overview

Test WhatsApp workflow 1 tuần hoàn toàn miễn phí qua Meta test number. Xác nhận template OK, delivery OK, reply OK trước khi upgrade production.

## Nelson preparation (before dev)

1. Truy cập `business.facebook.com` → Create Business Portfolio (giấy tờ Pudong Prime)
2. Truy cập `developers.facebook.com` → My Apps → Create App → Business type
3. Dashboard → Add WhatsApp product → Meta cấp test number
4. Business Settings → System Users → Create → Admin role → Generate token permanent
5. Gửi em: **Phone Number ID** + **Business Account ID** + **Access Token** (bảo mật)

**Chờ Meta verify business:** 2-5 ngày (có thể làm song song dev)

## Files to create

- `email_engine/core/wa_validator.py` — Meta contact check bulk
- `email_engine/core/wa_sender.py` — template send with SANDBOX/PRODUCTION mode flag
- `email_engine/core/wa_config.py` — load Meta credentials from env
- `email_engine/api/routes/wa_router.py` — 6 endpoints
- Tab 6 WhatsApp UI trong `email-dashboard-v6.html`

## 5 test recipients (Nelson confirm)

```
① Nelson          — số cá nhân
② Johnny          — team
③ Blue / Jennie   — team
④ Khách quen 1    — đã hỏi ý kiến OK
⑤ Khách quen 2    — đã hỏi ý kiến OK
```

## 7-day test plan

```
Day 0  Setup account + Meta verify begin
Day 1  Token lấy xong, em code wa_config + wa_sender skeleton
Day 2  Submit 2 template → Meta review (1-24h)
       Templates:
         rate_intro_en_v1 (MARKETING)
         rate_intro_vi_v1 (MARKETING)
Day 3  Templates approved → test gửi 5 số, collect feedback
Day 4  Reply test — 5 số reply template, Nelson reply lại (session 24h free)
Day 5  Opt-out test — 1 số reply STOP → verify block
Day 6  Validator quét 22K số CNEE → fill WA_STATUS column
Day 7  Review results → decision GO/NO-GO production
```

## 2 templates (draft)

```
Template 1: rate_intro_en_v1
-----------------------------
Category: MARKETING
Language: en_US
Body:
  Hi {{1}},
  This is Nelson from Pudong Prime — NVOCC specializing in
  Vietnam → USA/Canada freight. We handle {{2}} shipments daily.
  
  Would you be interested in our latest {{3}} rates for {{4}}?
  
  Reply STOP to unsubscribe.

Variables:
  {{1}} = PIC name (fallback "there")
  {{2}} = commodity (e.g., "furniture")
  {{3}} = container type (e.g., "40HQ")
  {{4}} = route (e.g., "HPH→LGB")

Template 2: rate_intro_vi_v1 (Vietnamese version)
```

## Implementation steps

1. `wa_config.py` + env vars setup (0.5h)
2. `wa_validator.py` — call Meta `/contacts` endpoint bulk (1h)
3. `wa_sender.py` SANDBOX mode (2h)
4. 6 API endpoints:
   - POST `/api/wa/validate` — bulk check
   - GET `/api/wa/templates` — list approved
   - POST `/api/wa/send-test` — gửi tới 5 test numbers
   - GET `/api/wa/conversations` — webhook data
   - POST `/api/wa/webhook` — receive incoming (Meta callback)
   - GET `/api/wa/stats` — quality rating + usage
   (1.5h)
5. Tab 6 UI 4 panel với SANDBOX badge (1h)

## Todo checklist

- [ ] Nelson provides 3 secrets (Phone ID + WABA ID + Token)
- [ ] `.env` variables configured (không commit git)
- [ ] `wa_validator.py` validates 5 test numbers successfully
- [ ] 2 templates submitted to Meta
- [ ] Templates approved (check status via API)
- [ ] Test send to 5 recipients — all receive message
- [ ] Webhook receives incoming reply
- [ ] Opt-out STOP tested
- [ ] Validator quét 22K CNEE → fill WA_STATUS
- [ ] Tab 6 UI shows SANDBOX badge + 5 test contacts only

## Success criteria

- All 5 test recipients receive template within 1 min
- 5 replies received via webhook
- Opt-out correctly blocks future sends
- Validator returns accurate WA_STATUS for 22K numbers
- Quality rating stays GREEN end of week

## Risk assessment

| Risk | Mitigation |
|---|---|
| Meta reject template | Revise wording, resubmit, document rejection reasons |
| Business verification delay | Start Day 0, continue dev while waiting |
| Test recipient doesn't have WA | Validator confirms before test |
| Token leak | Store env only, never commit, use System User (revocable) |

## Go/No-Go decision (end Day 7)

**GO to Phase 5B if:**
- Templates approved
- Delivery rate > 90%
- 5/5 test recipients received + replied
- No quality warnings from Meta
- Nelson satisfied với template wording

**NO-GO — return to fix:**
- Template language issues
- UI bugs
- Webhook reliability
