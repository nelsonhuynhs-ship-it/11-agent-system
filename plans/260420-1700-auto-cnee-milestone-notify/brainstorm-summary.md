# Brainstorm Summary — Auto CNEE Milestone Notify

**Date:** 2026-04-20
**Owner:** Nelson
**Status:** Design approved — ready for /ck:plan

---

## 1. Problem Statement

Nelson hiện phải copy-paste mail update trạng thái cho CNEE mỗi khi OPS Pudong gửi ATD notice hoặc khi hàng sắp tới POD. Việc này:
- Tốn thời gian (soạn mail EN bằng tay)
- Hay quên khi bận → CNEE phải hỏi
- Phải tra email CNEE từ nhiều nguồn
- Không chuyên nghiệp như carrier lớn

**Goal:** Tự động hoá 80% workflow — scanner phát hiện sự kiện, compose draft EN, nhắc Nelson review + Send.

---

## 2. Audit Findings (scan Outlook 7,209 emails, 4 tháng)

### Nguồn mail ATD thật sự
| Domain | Hits | Role |
|--------|------|------|
| `@pudongprime.vn` | 126 | Nội bộ OPS Pudong (primary source) |
| `@sirilogistics.vn` | 86 | Coload partner (không care) |
| `@smartlinklogistics.com.vn` | 14 | Partner khác (không care) |
| Carrier direct (ONE/ZIM/MSC...) | **0** | **CNEE tự deal với carrier** |

### Pattern phát hiện
- **Subject:** `ATD// DRAFT B/L#<HBL> // <AGENT> BKG <BKG_NO> // <ROUTING> // <CARRIER>`
- **Keywords:** `vessel depart` (131), `ATD:` (64), `loaded on board` (31)
- **Blacklist:** `VESSEL CHANGE NOTICE`, `RVS ETD`, `REVISED ETD` (= dời lịch, chưa chạy)

### Decision
Scanner filter duy nhất `@pudongprime.vn`. Không care carrier direct vì CNEE có email riêng với carrier.

---

## 3. Approaches Evaluated

### Option A — Nút Excel manual (2h) ❌
- Nelson click chuột phải Active Jobs row → gõ ATD → draft
- **Loại:** Nelson muốn tự động 100%, đã có scanner sẵn

### Option B — Outlook button semi-auto (4h) ❌
- Click mail OPS → button → auto draft CNEE
- **Loại:** Vẫn cần Nelson tương tác, không tận dụng scanner 30p

### Option C — Full Auto Scanner Extension (5h) ✅ **CHOSEN**
- Mở rộng `NelsonUnifiedScanner` có sẵn (không build scanner mới)
- Hook vào job #3 `shipment_brain` đã detect ATD
- Compose draft + Telegram nhắc
- Zero click từ Nelson — chỉ review + Send

**Rationale:** YAGNI — không build thêm gì khi scanner đã có. Reuse infrastructure.

---

## 4. Final Design

### Scope

**2 triggers:**
1. **ATD detected** — mail OPS có ATD real (không phải dời lịch)
2. **ETA − 7 days** — daily check, nhắc CNEE chuẩn bị nhận

**Filter sender:** `@pudongprime.vn` ONLY

**Opt-in model:** Per-customer (CRM column), không per-job

### Data Schema Changes

**CRM sheet:** thêm 1 cột
- `AUTO_NOTIFY` (bool, default False)

**Active Jobs sheet:** thêm 3 cột
- `ATD` — scanner auto-fill
- `ETA` — Nelson nhập manual lúc booking
- `LAST_NOTIFIED` — log format `"ATD YYYY-MM-DD | ETA-7 YYYY-MM-DD"`

### Pipeline

```
[Scanner 30p/lần] → shipment_brain detect ATD
    ↓
[NEW] Match Bkg_No với Active Jobs
    ↓
[NEW] Lookup Customer → CRM.AUTO_NOTIFY = ✅?
    ↓ Yes
[NEW] Update Active Jobs.ATD
    ↓
[NEW] Get CNEE email (CRM → Active Jobs.EMAIL → Telegram báo)
    ↓
[NEW] Fill template EN "Vessel Departed"
    ↓
[NEW] Create Outlook Draft (COM CreateItem + Save)
    ↓
[NEW] Log LAST_NOTIFIED
    ↓
[NEW] Telegram: "N draft ATD chờ review"
```

### Template Strategy

**2 templates cứng EN** với placeholder:
- `{customer}`, `{bkg}`, `{hbl}`, `{vessel}`, `{carrier}`, `{pol}`, `{pod}`, `{etd}`, `{eta}`

**Template 1 — Vessel Departed (ATD):**
```
Subject: Shipment Update — Vessel Departed | Bkg {bkg}

Dear {customer},

We're pleased to confirm your shipment has loaded on board:

  Booking:   {bkg}
  HBL:       {hbl}
  Vessel:    {vessel} ({carrier})
  Routing:   {pol} → {pod}
  ETD:       {etd}
  ETA:       {eta}

We will notify you again 7 days before arrival.

Best regards,
Nelson Huynh
Pudong Prime
```

**Template 2 — Arriving in 7 Days (ETA-7):**
```
Subject: Arriving in 7 Days — Please Prepare | Bkg {bkg}

Dear {customer},

Your shipment is expected to arrive at {pod} in 7 days:

  Booking:   {bkg}
  HBL:       {hbl}
  Vessel:    {vessel}
  ETA:       {eta}

Please prepare for pickup. Let me know if you need any documents.

Best regards,
Nelson Huynh
Pudong Prime
```

---

## 5. Risks & Mitigations

| Rủi ro | Mitigation |
|--------|-----------|
| Parse sai ATD date | Regex dd/mm/yyyy + dd-mm-yyyy + log Telegram nếu ambiguous |
| Bkg không có trong Active Jobs | Skip silent (OPS gửi Bkg của nhiều sales) |
| Gửi trùng draft | Check `LAST_NOTIFIED` prefix trước khi compose |
| Email CNEE rỗng | Telegram báo Nelson bổ sung, skip job |
| VESSEL CHANGE NOTICE bị nhầm ATD | Blacklist regex — skip mail có keyword |
| ETD rescheduled sau ATD notify | Không xử lý — ATD là fact |
| `@pudongprime.vn` gồm Nelson tự send | Filter thêm `SenderName != "Nelson"` để tránh self-loop |

---

## 6. Success Metrics

| Timeline | Metric | Target |
|----------|--------|--------|
| Day 1 | Draft accuracy (manual verify 5-10) | 0 sai |
| Week 1 | ATD→Draft conversion rate | >80% |
| Week 1 | False positive rate | <5% |
| Month 1 | Nelson subjective feedback | "Đỡ công rõ rệt" |

---

## 7. Implementation Phases (handoff to /ck:plan)

1. **Phase 1 — Schema setup** (1h)
   - Thêm cột `AUTO_NOTIFY` vào CRM sheet
   - Thêm 3 cột `ATD`, `ETA`, `LAST_NOTIFIED` vào Active Jobs
   - Script: `scripts/erp-add-notify-columns.py`

2. **Phase 2 — Composer module** (1.5h)
   - `email_engine/core/cnee_milestone_composer.py`
   - 2 template EN
   - Placeholder fill + CRM email lookup + fallback
   - Outlook COM Draft creation

3. **Phase 3 — ATD hook into shipment_brain** (1.5h)
   - Mở rộng `shipment_brain.py` — sau khi detect ATD, call composer
   - Blacklist `VESSEL CHANGE`, `RVS ETD`
   - Dedup via `LAST_NOTIFIED`
   - Update Active Jobs.ATD

4. **Phase 4 — ETA-7 daily job** (1h)
   - `email_engine/core/eta_reminder.py`
   - Thêm vào `scanner_rules.json` job `eta_reminder_daily`
   - Schedule: 08:00 mỗi ngày

5. **Phase 5 — Telegram integration** (0.5h)
   - Reuse telegram module có sẵn
   - Format message: "N draft ATD + M draft ETA-7 chờ review"

6. **Phase 6 — Testing & verify** (0.5h)
   - Test với 2-3 job thật
   - Verify draft correctness
   - Monitor 1 ngày đầu

**Total: ~5h, 1 session**

---

## 8. Out of Scope (KHÔNG làm)

- ❌ Carrier direct email scan (CNEE tự deal)
- ❌ Auto-send mail (chỉ draft, Nelson review)
- ❌ MiniMax AI compose (template cứng đủ rồi)
- ❌ Scanner mới (mở rộng scanner có sẵn)
- ❌ Mobile app / webapp (Outlook + Excel + Telegram đủ)
- ❌ Multi-language (chỉ EN)

---

## 9. Decisions Log

| Decision | Rationale |
|----------|-----------|
| Filter `@pudongprime.vn` only | Audit shows carrier direct = 0. CNEE tự deal với carrier. |
| Per-customer CRM AUTO_NOTIFY | Control theo khách, safer than per-job |
| Template cứng 2 mẫu | Nhất quán, không tốn API call, dễ debug |
| CRM → Active Jobs EMAIL fallback | Flexible cho job mới chưa có CRM entry |
| Mở rộng shipment_brain (không build mới) | YAGNI, reuse đã chạy stable |
| Outlook Draft (không Send) | Nelson keep control, verify trước Send |
| ETA-7 daily 08:00 | Buổi sáng anh check Outlook, thấy draft → send |
