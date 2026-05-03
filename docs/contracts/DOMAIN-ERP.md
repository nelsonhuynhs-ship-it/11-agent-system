# Domain: ERP — Excel pricing + Active Jobs (rules-of-the-house)

## Tóm tắt
ERP là file Excel chính anh dùng hàng ngày. Nó kết nối với parquet rate data và tự động refresh giá. Ribbon có các nút để tìm giá, báo giá, và theo dõi jobs.

---

## Rule 1: Quy trình báo giá — Search → Pick → Margin → Quote → WIN

### Anh thấy gì
Khi anh cần báo giá cho khách:
1. **Search**: Chọn Carrier + POL + POD + Place trong ribbon tìm kiếm
2. **Pick**: Click vào dòng rate phù hợp trên sheet Pricing Dry/Reefer
3. **Margin**: Điền số margin vào ô **+ Margin** (20GP +, 40GP +, v.v.)
4. **Quote**: Click **QUOTE** (hoặc **Batch** nếu nhiều dòng)
5. **WIN/LOST**: Sau khi khách xác nhận, click **WIN** hoặc **LOST**

### Quy định
- **Quote insert VÀO ROW 5** — đẩy quotes cũ xuống. Quote mới nhất luôn ở trên top.
- **QuoteGroupID reuse**: Nếu cùng khách + cùng ngày, quotes được gom nhóm
- **CRM lookup**: CODE hoặc NAME → luôn resolve về canonical NAME (không phải internal code)
- **Container detect**: WIN tự động detect container type từ vị trí cột (12-18 Dry, 29-35 Reefer)

### Khi sai → hậu quả
- Quote mới không hiện ở top → anh không thấy
- Khách trùng tên bị resolve sai → Active Jobs sai customer name

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 12 rule chi tiết</summary>

- QUOTES_DATA_START = row 5 (insert at top)
- QuoteGroupID reuse same-day same-customer
- OnAction_MarkQuoteWin: CRM lookup by CODE or NAME → canonical NAME (col 2)
- Container detect: cols 12-18 (Dry), 29-35 (Reefer)
- TEU calc: 20GP=1, 40GP/40HC/45HC=2, RF=2
- Hidden cols 15-17: Contract, Group Rate, Group Code (ONE only)
- OnAction_GenerateQuote: reads hidden cols 15/16/17
- Auto-detect container from selected cell column
- QuoteImage / QuoteImageBulk: tạo image từ Quotes sheet
- g_TestMode silences MsgBox during testing
- OnChange_SearchCarrier/POL/POD/Place: reset toggle filters on sheet switch
</details>

---

## Rule 2: Mix Quote — blend FIX + FAK cho giá tốt nhất

### Anh thấy gì
Khi anh muốn blend giữa **FIX** (giá cố định) và **FAK** (giá thị trường) để có giá tốt nhất:
1. Điền **FIX x** và **FAK x** trong nhóm **Rate Mix**
2. Click **Mix Quote**
3. Hệ thống blend 2 nguồn giá → hiển thị ở **Mix Sell**

### Quy định
- **FIX peer BẮT BUỘC cùng COC** — không blend với SOC rates
- MixQuote peer selection: COC only (bug fix 2026-04-22)
- Markup lookup: keyed by (Carrier, Lane) → Lane derive from POD via GetLaneFromPOD
- Lane mapping: LAX/LGB → WC, NYC → EC, ATL/SAV/HOU/CHI → EC/WC/GULF

### Khi sai → hậu quả
- Mix Quote trả sai giá (blend với SOC rate không hợp lệ)
- Markup không áp đúng cho lane → margin sai

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 7 rule chi tiết</summary>

- OnAction_MixQuote: FIX peer COC only (2026-04-22 fix)
- Dedup key: POL + POD + Place + Carrier + Note + Source (không có Commodity)
- GetLaneFromPOD: LAX/LGB alias → WC, NYC → EC
- Markup_Store keyed by (Carrier, Lane), fallback = '*'
- LoadMarkupForCarrier: fills margin inputs từ stored values per (Carrier, Lane)
- RateFreshnessColors: green/yellow/red based on expiry
- DRY/REEFER/ShowAll preset buttons: 2-sheet aware
</details>

---

## Rule 3: Refresh All — cập nhật giá từ parquet vào Excel

### Anh thấy gì
Khi anh cần cập nhật giá mới từ Harry:
1. Click **Refresh All** trong nhóm Rate Data
2. Hệ thống chạy refresh-v14.py → cập nhật 5 sheets: Pricing Dry, Pricing Reefer, ChargeBreakdown, RateVersions, PUC_Lookup
3. Labels **RateVer1-4** hiển thị version info

### Quy định
- **Refresh All** = Refresh Rates + Outlook scan + milestone sync
- **Refresh Rates** = chỉ update giá (nhanh hơn, không scan inbox)
- URL detection: ThisWorkbook.FullName trả URL khi mở từ Teams/O365 → fallback correctly
- AutoSave OFF khi file mở từ OneDrive (xlsm + AutoSave = VBA corruption)

### Khi sai → hậu quả
- Rate_versions không update → anh không biết giá mới từ file nào
- VBA corruption nếu AutoSave = ON + OneDrive

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 8 rule chi tiết</summary>

- OnAction_RefreshAll: calls refresh-all-bootstrap.bat via WMI Win32_Process.Create
- OnAction_RefreshRates: parquet → 5 sheets (Dry, Reefer, ChargeBreakdown, RateVersions, PUC_Lookup)
- FindScript: tìm bootstrap.bat trong 3 bases
- Stale detection: _CRITICAL_FILES list vs SERVER_START_TS
- URL detection for RefreshAll (2026-04-21 fix lần 3)
- AutoSave OFF on OneDrive (2026-04-15 discovered)
- SelectionChange workbook-level: only Sheet1 fired (fix 2026-04-22)
- cmbMonth reads Archive col 15, header row 2
</details>

---

## Rule 4: Active Jobs — theo dõi tất cả shipments

### Anh thấy gì
Tab **Active Jobs** hiển thị tất cả bookings đang hoạt động. Anh thấy:
- Customer name, POL_POD, Bkg_No (booking number)
- 7-stage tracking dots: Request → Booked → To Customer → Docs → ATD → ETA → Delivered
- **Sync Milestones**: click để đồng bộ ATD/ETA từ email inbox

### Quy định
- **Bkg_No = primary key** — không phải Job_ID (Job_ID là internal ID)
- **Col H = Bkg_No** — milestone sync tìm Bkg_No trong col H
- **MONTH col = col 15** — dùng cho VBA month combo filter
- Tracking dots: colored string + tooltip (SI Cut, CY Close, Vessel/Voyage, PO#)
- ATD/ETA7 sync: JSONL → VBA reads+flushes (Python write, VBA read)

### Khi sai → hậu quả
- Milestone sync fail → ATD/ETA không được update
- MONTH filter không hoạt động → tìm job theo tháng sai

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 10 rule chi tiết</summary>

- Active Jobs col H = Bkg_No (primary key, 2026-04-21 decision)
- Job_ID col (1): hidden column, internal ID, not primary
- MONTH col (15): ISO label 'APR-26' cho Archive filter
- 7-stage: Request→Booked→To Customer→Docs→ATD→ETA→Delivered
- ApplyTrackingDots: colored dot string + cell comment tooltip
- Btn_SyncMilestones: reads milestone_state.jsonl → Active Jobs cols 46-48
- ATD within ±30d of ReceivedTime (date sanity window)
- OPS allowlist, kill switch, bulk detect (>3 Bkg = skip)
- Booking Pool: New Keep Space, Sync Pool, Mark Expired
- New row at row 8+ when WIN
</details>

---

## Rule 5: Hidden columns — Contract / Group Rate / Group Code

### Anh thấy gì
Anh không thấy 3 cột này trên sheet Pricing, nhưng chúng có dữ liệu quan trọng:
- **Contract** (col 15): số contract — dùng khi WIN
- **Group Rate** (col 16): text label cho group rate
- **Group Code** (col 17): **CHỈ ONE carrier** có group code

### Quy định
- Hidden cols 15-17: viết vào nhưng hidden khỏi Nelson's view
- **Group_Code: ONE carrier only** — non-ONE carriers empty
- OnAction_MarkQuoteWin đọc hidden cols 15-17 để preserve trong Active Jobs
- CostBreakdown.BuildCostBreakdown: group line cho ONE only

### Khi sai → hậu quả
- WIN không preserve Contract/Group Rate/Group Code
- Group line không hiện trong CostBreakdown email cho non-ONE carriers

### Detailed validation (technical, em handle)
<details>
<summary>Click để xem 5 rule chi tiết</summary>

- refresh-v14.py: col 15 = Contract, col 16 = Group Rate, col 17 = Group Code
- Group_Code 8 unique: 990146, 990117, 990154, 990104, 990302, 1, PUDSCF001 (ONE only)
- CostBreakdown.bas: groupLine for ONE only (2026-04-13+)
- CostBreakdown.bas: R.account = carrier + ' (FALLBACK)' khi fallback used
- HDL fallback: warning line appended to email body khi fallback used
</details>

---

## ✅ Anh đang làm tốt
- ERP Excel các sheet đang work đúng (anh confirm)
- Refresh All sau URL bug fix (2026-04-21)
- WIN/LOST workflow đang đúng
- Mix Quote sau 2026-04-22 fix đúng COC peers