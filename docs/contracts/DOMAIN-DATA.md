# Domain: DATA — Rate parquet (rules-of-the-house)

## Tóm tắt
Data layer là nơi lưu giữ tất cả giá rate tàu. Mỗi khi anh báo giá cho khách, hệ thống đọc từ đây. Parquet format giúp đọc nhanh 28x so với Excel.

---

## Rule 1: "Giá báo khách" luôn dùng Total Ocean Freight

### Anh thấy gì
Khi anh click **QUOTE** hoặc **Mix Quote**, giá hiển thị ở ô **= Sell Rate** (lblSell) là giá đã bao gồm tất cả phí. Đây là giá anh gửi cho khách.

### Quy định
- Giá báo khách **PHẢI** lấy từ dòng có Charge_Name = `Total Ocean Freight`
- **KHÔNG BAO GIỜ** dùng `Basic Ocean Freight`, `HLCU Basic Cost`, `Base Ocean Freight` để báo giá
- Lý do: những dòng đó chỉ là thành phần, chưa bao gồm surcharge

### Total Ocean Freight bao gồm (Anh confirm 2026-04-26)
- ✅ Basic Ocean Freight
- ✅ BAF (Bunker Adjustment Factor)
- ✅ LSS (Low Sulphur Surcharge)
- ✅ EBS (Emergency Bunker Surcharge) / ENS

### Total Ocean Freight KHÔNG bao gồm (Anh confirm 2026-04-26)
- ❌ THC (Terminal Handling Charge)
- ❌ SEAL fee
- ❌ BILL fee
- ❌ TELEX release fee
- ❌ AMS (Automated Manifest System)

→ Các phí này tính riêng, cộng thêm khi quote với khách.

### Khi sai → hậu quả
- Báo giá thiếu phí →亏本 (lỗ tiền)
- HPL SCFI từng bị under-quote $1,561/40HQ vì dùng Basic Ocean Freight thay vì Total Ocean Freight

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 12 rule chi tiết</summary>

- Charge_Name = 'Total Ocean Freight' cho mọi quote operation
- Basic Ocean Freight / HLCU Basic Cost / Base Ocean Freight = chỉ dùng cho debug/analysis
- CARRIER_RATE_MAPPING.json định nghĩa canonical names
- Parquet 6.9M rows với 27 unique charge names
- COMMISION typo → COMMISSION (336 rows fixed Phase 6)
- Group_Code: ONE carriers only (990146, 990117, etc.) — see Rule 6
- Rate_Type enum: FAK / SCFI / FIX — không có loại khác
- Total Ocean Freight components: Basic + BAF + LSS + EBS (Anh confirm 2026-04-26)
- Excluded charges: THC, SEAL, BILL, TELEX, AMS — quote separately
</details>

---

## Rule 2: POD format LAX/LGB — đồng bộ là điều quan trọng nhất

### Anh thấy gì
Khi anh chọn **POD** trong ô tìm kiếm (ví dụ: Los Angeles), hệ thống hiểu LAX/LGB nghĩa là cảng Long Beach + Los Angeles gộp lại.

### Quy định (Anh decide 2026-04-26)
> "Cái nào cũng được nhưng cần thiết là phải đồng bộ cho hệ thống"

→ Em chọn `LAX/LGB` (slash) làm canonical vì khớp format hãng ONE + đồng bộ Phase 6 đã apply.

- POD chuẩn = `LAX/LGB` (dấu slash **/** )
- `LAX-LGB` (dấu dash **-**) → bị reject (Phase 6 đã fix 523,220 rows)
- `USLAX/ USLGB` (space sau slash) → strip space (Phase 6 đã fix 364,772 rows)
- Mọi format khác = drift, cần normalize trước publish

### Khi sai → hậu quả
- Mix Quote không tìm thấy peer → trả sai giá
- POD lookup alias (LAX/LGB → WC) fails
- Freshness colors không highlight đúng rows

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 8 rule chi tiết</summary>

- Canonical: LAX/LGB (slash, no trailing space)
- LAX-LGB (dash): 523,220 rows flagged as violation
- USLAX/ USLGB (space): 62,748 rows flagged
- POD 140 unique values — multiple format types
- Legacy HPL format: 'LOS ANGELES, CA (LONG BEACH, CA)' → normalize to LAX/LGB
- GetLaneFromPOD alias: LAX/LGB → WC (West Coast)
- Non-canonical: 'LAX', 'LGB-LAX' (order reversed)
- POD contamination: 'SUBJECT TO EFS' → recover from Place column
</details>

---

## Rule 3: Container — 40HC + 45HC canonical (Anh decide 2026-04-26)

### Anh thấy gì
Khi báo giá container 40ft hoặc 45ft, hệ thống tự đổi về dạng chuẩn HC.

### Quy định (Anh decide 2026-04-26)
- Container 40ft High Cube = `40HC` (✅ Phase 6 đã apply: 1.76M rows)
- Container 45ft High Cube = `45HC` (⏳ **Pending Phase 7 normalize**: 92K + 33K rows)
- `40HQ` / `45HQ` / `45'HQ` → tất cả đổi về dạng HC

### ⚠ Action item (Phase 7)
Anh đã decide ngày 26/04 normalize 45ft về `45HC` (trước Phase 6 keep 2 form 45'HQ + 45HQ). Cần:
1. Update `scripts/normalize_parquet.py` thêm rule `45'HQ` + `45HQ` → `45HC`
2. Run normalize lần 2 (backup trước)
3. Update validator forbid `45'HQ` + `45HQ`

### Khi sai → hậu quả
- Pivot table sai cột → Mix Quote không tìm peer
- Báo giá sai số tiền

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 4 rule chi tiết</summary>

- 40HQ → 40HC (Phase 6 done: 1,763,608 rows normalized 25/04)
- 45HQ → 45HC (Phase 7 pending: 33,671 rows main + slim ratio)
- 45'HQ → 45HC (Phase 7 pending: 92,061 rows main + slim ratio)
- CONTAINER_NORMALIZE dict trong master_loader_v2.py lines 76-81
- Anh approval thread: phase-05-review-form.html Q3 ngày 2026-04-26
</details>

---

## Rule 4: Nạp rate file mới phải qua master_loader_v2.py

### Anh thấy gì
Khi Harry gửi file rate mới (FAK 01 MAY NO.1.xlsx, FIX NO.24.xlsx, SCFI Contract 43.xlsx), file được nạp vào hệ thống qua một script chuẩn.

### Quy định
- Mọi rate file mới phải đi qua `master_loader_v2.py` (Pricing_Engine/scripts/)
- File nạp vào → append vào `Cleaned_Master_History.parquet`
- Mapping files (V4_FINAL_CHECK_*.csv) định nghĩa cách đọc columns
- Container type normalize + charge name normalize tự động

### Khi sai → hậu quả
- Parquet drift → các ô giá trên ERP không khớp
- Mix Quote fail
- Báo sai giá cho khách

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 6 rule chi tiết</summary>

- master_loader_v2.py: input FAK/FIX/SCFI xlsx → output parquet
- Batch_load.py: wrapper around master_loader_v2
- Mapping files trong D:/OneDrive/NelsonData/pricing/mapping/
- FIX files có 2 layouts: SPECIAL RATE vs Fixed Rate Summary
- SCFI rows: Note = empty string (không có Note column)
- Dedup key = POL + POD + Place + Carrier + Note + Source (không có Commodity)
</details>

---

## Rule 5: Filter 30 ngày — không lấy rate cũ

### Anh thấy gì
Khi làm việc trên ERP, các dòng rate hiển thị chỉ là rate còn hiệu lực (chưa hết hạn).

### Quy định
- Parquet queries LUÔN filter: Eff date >= 30 ngày trước
- Exp < hôm nay = expired → không dùng để báo giá
- Fallback: 60 ngày → 90 ngày nếu 30 ngày không có data

### Khi sai → hậu quả
- Báo giá rate đã hết hạn → khách hỏi tại sao giá không đúng
- Freshness colors (xanh/vàng/đỏ) không hoạt động

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 5 rule chi tiết</summary>

- Eff date format: YYYY-MM-DD canonical
- Eff = NaT → fillna với Exp date (FIX NO.22 fix)
- Exp date format: YYYY-MM-DD canonical
- RateVersions sort by filename upload date không phải Eff date
- AutoExpire: rows có Exp < today được mark/exclude
</details>

---

## Rule 6: Group Code — chỉ hãng ONE (Anh confirm 2026-04-26)

### Anh thấy gì
Trong sheet Pricing Dry/Reefer, cột Group_Code chỉ có giá trị cho rows hãng ONE. Các hãng khác (HPL, CMA, YML, COSCO...) cột này trống.

### Quy định
> "ONE yêu cầu submit group code thì mới link được giá" — Anh confirm 2026-04-26

- Hãng ONE → mỗi contract có Group_Code (vd: 990146, 990117, S25NEA202)
- Các hãng khác → KHÔNG có Group_Code (cột empty)
- Khi quote hãng ONE, hệ thống must include Group_Code trong booking submission

### Khi sai → hậu quả
- Quote ONE thiếu Group_Code → ONE reject submission, mất rate
- Apply Group_Code lên hãng khác → carrier không hiểu, error

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem rule chi tiết</summary>

- Group_Code column: only ONE carrier rows non-null
- ERP Quote workflow: detect carrier=ONE → require Group_Code from Contract column
- ContractGroup_Mapping: Contract # → Group Code lookup
</details>

---

## Rule 7: Mix Quote peer phải COC, KHÔNG phải SOC (Anh confirm 2026-04-26)

### Anh thấy gì
Khi anh bấm **Mix Quote** với 1 lane, hệ thống tìm 1 dòng FIX và 1 dòng FAK của cùng carrier+POL+POD để blend giá. Cả 2 dòng phải là **COC** (Carrier-Owned Container).

### Quy định
> "SOC không phải giá đối trọng cho combo rate mix" — Anh confirm 2026-04-26

- Mix Quote peer-finding: chỉ match rows có Note ≠ 'SOC'
- SOC (Shipper-Owned Container) có cấu trúc giá khác → không thể blend với COC
- Note empty `""` = COC default → match được (xem Rule 4 Note empty)

### Khi sai → hậu quả
- Blend FIX-COC + FAK-SOC → giá sai, lỗ tiền
- Rule này được add ngày 2026-04-22 (commit 93b3c14) sau khi phát hiện bug

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem rule chi tiết</summary>

- ComputeMix() peer-finding: filter rows Note != 'SOC'
- Note canonical: '' (empty) = COC default, 'SOC' = explicit Shipper-Owned
- VBA file: erp-v14-ribbon-callbacks.bas line ~4310
- Bug history: peer-COC rule added 2026-04-22, peer-finding root cause fixed 2026-04-22 (commit 63d67c4)
- Verified work: HPL/CMA/YML Mix Quote test PASS 2026-04-26 (Anh confirm)
</details>

---

## ✅ Anh đang làm tốt
- File rate từ Harry được nạp đều đặn qua script chuẩn
- Refresh All trên ERP đang work đúng sau fix URL bug (2026-04-21)
- Đọc đúng Total Ocean Freight cho quotes (sau incident HPL SCFI)
- Mix Quote work cho cả ONE/HPL/CMA/YML sau Phase 6 fix (Anh test PASS 2026-04-26)