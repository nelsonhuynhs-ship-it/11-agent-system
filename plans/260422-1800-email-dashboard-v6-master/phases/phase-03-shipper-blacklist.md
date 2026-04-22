# Phase 3 — Shipper Blacklist System

**Status:** PENDING
**Effort:** 4h
**Cost:** $0
**Depends on:** Phase 1

## Overview

Shipper VN trùng với team Johnny/Blue đang làm. Build blacklist system để không đụng khách team nội bộ. SHIPPER sheet default HOLD cho đến khi Nelson Activate.

## Files to create

- `email_engine/core/shipper_blacklist.py` — 3-layer match engine
- `email_engine/api/routes/shipper_blacklist_router.py` — 5 endpoints
- `D:/OneDrive/NelsonData/email/vn_team_overlap.xlsx` template (3 sheets)

## 3-Layer match logic

```
Lớp 1 EXACT    company_name.lower().strip() == blacklist[COMPANY_NAME_EXACT]
                → BLOCK + flag VN_TEAM_OVERLAP_FLAG=Y

Lớp 2 FUZZY    fuzz.ratio(company, blacklist[FUZZY]) > 85
                → HOLD for Nelson review (không block hẳn)

Lớp 3 CONTACT  domain match hoặc phone E.164 match
                → BLOCK luôn
```

## Implementation steps

1. Tạo template `vn_team_overlap.xlsx` 3 sheet (0.5h)
2. Viết `shipper_blacklist.py` với `rapidfuzz` lib (1.5h)
3. 5 API endpoints (import/add/scan/activate/report) (1.5h)
4. Settings UI Shipper Blacklist Builder (0.5h)

## Todo checklist

- [ ] `vn_team_overlap.xlsx` template 3 sheet created
- [ ] `shipper_blacklist.py` 3-layer match
- [ ] `rapidfuzz` dependency added
- [ ] 5 API endpoints:
  - POST `/api/shipper-blacklist/import` — upload team list
  - POST `/api/shipper-blacklist/add` — manual entry
  - POST `/api/shipper-blacklist/scan` — scan toàn SHIPPER sheet
  - POST `/api/shipper-blacklist/activate` — unlock SHIPPER sending
  - GET `/api/shipper-blacklist/report` — overlap xlsx export
- [ ] Activate gate: SHIPPER queue check `STATUS != HOLD_PENDING_VN_BLACKLIST` before send
- [ ] UI 5 nút in Settings tab

## Success criteria

- Scan toàn SHIPPER sheet returns overlap count
- Activate requires Nelson confirm prompt
- Send queue honors HOLD flag
- Fuzzy match 85% catches "ABC Wood" vs "ABC Wood Co Ltd"

## Risk assessment

| Risk | Mitigation |
|---|---|
| False positive fuzzy match | Lớp 2 = HOLD review, không block thẳng |
| Nelson activate without building blacklist | UI require coverage >= X% before enable button |
| Team list outdated | Scheduled re-scan mỗi 30 ngày + alert |
