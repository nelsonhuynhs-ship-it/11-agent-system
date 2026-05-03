# Domain: EMAIL — Rate & Send pipeline (rules-of-the-house)

## Tóm tắt
Email system gửi rate hàng loạt cho khách hàng. Dashboard chính là giao diện web anh dùng để bấm "Rate & Send". Pipeline từ contact list → rate table → email → tracking.

---

## Rule 1: Rate Table v2 — dual HPH+HCM, YOUR LANE highlight

### Anh thấy gì
Khi bấm **Rate & Send** trên dashboard, email gửi cho khách có rate table với:
- **2 cột**: HPH (Hải Phòng) và HCM (Hồ Chí Minh) side-by-side
- **"YOUR LANE"** pill màu amber: destination quen thuộc của khách
- **TOP 3 carriers** per POD
- Inland routing via LAX/SAV/CHS

### Quy định
- Rate Table v2 (2026-04-17): dual POL layout
- FAK + ONE/CMA/YML/HPL → SOC container
- FAK + others → COC container
- FIX + HPL → SOC, FIX + others → 'Provide commodity'
- ARB surcharge cho cross-origin inland (USATL = RIPI via SAV/CHS/NOR)
- 10 lanes default trong fast bulk (USLAX + USSAV + USNYC + USHOU + USMIA + USTIW + 4 inland)

### Khi sai → hậu quả
- Khách không thấy "YOUR LANE" → không biết họ được báo đúng lane
- SOC/COC label sai → khách hiểu nhầm container type

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 8 rule chi tiết</summary>

- Rate Type Carrier Matrix: FAK COC={CMA,ONE,HMM,YML,ZIM,HPL,WHL}, FAK SOC={HPL,YML}, SPECIAL SOC={HPL,YML}
- SVC derivation: FAK+ONE/CMA/YML/HPL→SOC, FIX+HPL→SOC
- arb_origin: cross-origin surcharge cho inland destinations
- inland gateway: USATL=RIPI (via CHS/NOR/SAV), USCHI/USDAL/USDEN=IPI (via LAX/OAK)
- YOUR LANE amber pill: primary_dest highlight
- Destinations MERGE: 10 default lanes always shown (2026-04-23 Nelson decision)
- Template precedence: default_cross_sell placed FIRST, fallback LAST
- default_routes.yaml: loads from OneDrive (not hardcoded)
</details>

---

## Rule 2: Send quota — 420/day, 60/campaign, cooldown 14d

### Anh thấy gì
Mỗi ngày hệ thống gửi tối đa 420 email. Chia theo commodity:
- FLOORING, FURNITURE_INDOOR, CANDLE, RUBBER, PLASTIC, PLYWOOD, FOOD_AMBIENT: mỗi loại 60 email
- Các campaign khác: 0

### Quy định
- **Daily quota**: 420 emails tổng
- **Cooldown**: 14 ngày (2026-04-24 thay đổi từ 48h)
- **Hard limit**: 3 sends trong 30 ngày cho cùng 1 CNEE
- Redistribution: deficit trong 1 commodity → spread proportional sang surplus commodities

### Khi sai → hậu quả
- Gửi quá nhiều → spam complaints → email bị block
- Gửi trong cooldown → khách không đọc, reply lại spam

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 6 rule chi tiết</summary>

- rotation_quota.json: daily_total=420, by_commodity, cooldown_days=14, hard_limit=3/30d
- cooldown check: last_sent > (now - 14d)
- hard_limit: 3 sends max trong 30-day window
- Priority isolation: blast list EXCLUDES VIP/HOT/replied/personal contacts
- skip_cooldown=True: bypass cooldown check (still blocks HARD_BOUNCE/UNSUBSCRIBED)
- _SUPPRESSION_STATUSES: HARD_BOUNCE, UNSUBSCRIBED — permanent blocks
</details>

---

## Rule 3: Bounce detection — HARD / SOFT / POLICY

### Anh thấy gì
Khi email bị trả lại (bounce), hệ thống tự phân loại:
- **HARD_BOUNCE**: hộp thư không tồn tại → permanent block
- **SOFT_BOUNCE**: hộp thư đầy / tạm thời → retry được
- **SOFT_SUPPRESSED**: policy violation → không gửi nữa

### Quy định
- **7 dead statuses**: HARD_BOUNCE, DEAD, INVALID, NO_MX, UNSUBSCRIBED, SOFT_SUPPRESSED, SPAM
- HARD_BOUNCE count = HARD + SOFT + SOFT_SUPPRESSED (tracked per campaign)
- **UNSUBSCRIBED**: permanent block — không bao giờ bypass được
- Per-subscriber bounce count cho suppression decisions
- POSTMASTER_PATTERNS: real postmaster domains only (postmaster@, mailer-daemon@)

### Khi sai → hậu quả
- Gửi tiếp đến dead email → spam complaints
- HARD_BOUNCE không block → email reputation bị hỏng

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 7 rule chi tiết</summary>

- HARD keywords: 'does not exist', 'unknown user', 'invalid address', 'no such user', 'rejected'
- SOFT keywords: 'mailbox full', 'temporarily', 'try again later', 'quota exceeded'
- AUTO_REPLY patterns: 'out of office', 'automatic reply', 'i am on vacation', 'đang nghỉ phép'
- UNSUBSCRIBE patterns: 'unsubscribe', 'stop email', 'remove me', 'không nhận email'
- Telegram batching: collect 300s trước khi flush, rate limit 20/minute
- sender_domains covers YML/Maersk/MSC tracking bots
- Email format cleanup: reject junk prefixes (em@, te@, me@)
</details>

---

## Rule 4: CNEE master v7 — 22,854 contacts, fallback chain

### Anh thấy gì
Contact list trên dashboard (campaigns, prospects) được đọc từ `contact_unified_v7.xlsx`.

### Quy định
- **Primary**: D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx (22,854 CNEE, 62 cols)
- **Fallback chain**: v7 → v6 → v5 → cnee_master_v2_final.xlsx → local
- xlsx mtime change → invalidates 3 caches (_CNEE_CACHE, _CNEE_DF_CACHE, _CAMPAIGN_CACHE)

### Khi sai → hậu quả
- Dashboard không thấy contacts → không gửi được email
- Stale cache → contacts không cập nhật sau khi thêm mới

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 4 rule chi tiết</summary>

- _resolve_cnee_master_v2() tries 5 paths in order
- 22,854 CNEE × 62 cols + SHIPPER 2,338
- COMMODITY_CATEGORY: 18 clean categories
- ORIGIN_COUNTRIES: multi-value country field parsed
</details>

---

## Rule 5: Outlook scanner → shipment tracking → milestone notify

### Anh thấy gì
Hệ thống tự động:
1. **Scan inbox** (35 phút/lần): tìm email từ carrier về shipment status
2. **Update shipment_state**: theo dõi 10-stage lifecycle
3. **Notify CNEE**: khi có ATD (Departed) hoặc ETA 7 ngày → tạo draft email thông báo

### Quy định
- **10-stage lifecycle**: BOOKING_CONFIRMED → SI_SUBMITTED → DRAFT_BL_ISSUED → DRAFT_BL_CONFIRMED → LOADED → ATD → ETA_UPDATE → DN_SENT → INVOICE_ISSUED → PAYMENT_CONFIRMED
- **Milestone daily limit**: 20/day, 5/run — prevent notification overload
- **JSONL pattern**: Python write → VBA read+flush (milestone_state.jsonl)
- **ATD date sanity**: within ±30d of ReceivedTime

### Khi sai → hậu quả
- Khách không được notify ATD/ETA → không biết hàng đã đi
- Milestone spam → khách complain về quá nhiều email

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 6 rule chi tiết</summary>

- shipment_brain.py: inbox scan 35 min, max 500 items, folders [Inbox, Junk]
- shipment_state.json: atomic write via .tmp file
- cnee_milestone.on_atd_detected(): creates Outlook Draft
- Auth-Results header (SPF/DKIM/DMARC), OPS allowlist, kill switch
- bulk detect >3 Bkg = skip
- si_48h_alert merged INTO shipment_brain (2026-04-22)
</details>

---

## Rule 6: Smart Send Window — gửi đúng giờ local recipient

### Anh thấy gì
Email được lên lịch gửi sao cho đến hộp thư khách lúc **9h sáng local** (giờ làm việc).

### Quy định
- VN send hours: 18h-2h tùy state (timezone offset)
- Alaska: 9h local = 18h UTC = 1h VN next day
- Hawaii: 9h local = 19h UTC = 2h VN next day
- Special handling cho states không có DST

### Khi sai → hậu quả
- Email đến lúc 3h sáng → khách không đọc
- Open rate thấp → chiến dịch không hiệu quả

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 2 rule chi tiết</summary>

- send_time_rules.json: states mapped to VN send hours
- AK: optimal_send_hour_vn=23, HI: optimal_send_hour_vn=1
</details>

---

## 🔴 KNOWN ISSUES

### Issue 1: Smart Send — preview OK, send FAIL
- **Status**: ĐANG FIX
- **Triệu chứng**: Khi anh bấm "Rate & Send" trên dashboard, preview hiển thị đúng nhưng khi gửi thì thất bại. Không có error message rõ ràng.
- **Nguyên nhân**: Đang investigation — có thể do cooldown check hoặc SMTP configuration
- **Workaround**: Thử lại sau 5 phút, hoặc kiểm tra email_log.csv để xem chi tiết lỗi

---

## Rule 7: Outlook COM mandatory (Anh confirm 2026-04-26)

### Anh thấy gì
Khi gửi email rate, hệ thống mở Outlook desktop trên Laptop VP và inject email qua COM API. KHÔNG dùng SMTP relay.

### Quy định
> "IT không cấp pass SMTP" — Anh confirm 2026-04-26

- Pipeline send phải đi qua **Outlook Application COM object** (`win32com.client.Dispatch("Outlook.Application")`)
- KHÔNG dùng `smtplib` / `aiosmtplib` để send email production
- Lý do business: VP IT không cấp SMTP admin password cho `@pudongprime.vn`
- Constraint: VPS / GoClaw / cron KHÔNG gửi email được (Outlook chỉ live trên Laptop VP)

### Khi sai → hậu quả
- Code dùng SMTP → AuthenticationError, bypass IT policy
- Email gửi từ VPS → fail vì không có Outlook
- Pipeline phải design xung quanh constraint này (queue + scan model)

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem rule chi tiết</summary>

- `email_engine/web_server.py` /api/send → Outlook COM dispatch
- VPS deploy: chỉ webapp + API, không bao gồm send pipeline
- Memory record: `project-email-outlook-com-constraint.md`
- Anh approval: phase-05-review-form.html Q14 ngày 2026-04-26
</details>

---

## ✅ Anh đang làm tốt
- Rate Table v2 (dual HPH+HCM) đang hoạt động đúng sau 2026-04-17
- Daily rotation 420 emails đang work (700/700 verified 2026-04-22)
- Cooldown 14d đã ngăn được Xerox auto-reply spam (2026-04-24)
- Safety Net: 57 spam auto-blocked
- Outlook COM constraint understood + designed around (Anh confirm 2026-04-26)