# 📦 Pricing Engine

Hệ thống tự động nạp, xử lý và tổng hợp dữ liệu cước vận chuyển từ nhiều hãng tàu (FAK, SCFI, SPECIAL RATE) vào một file báo cáo duy nhất: **MasterFullPricing_v2.xlsx**.

---

## 🚀 Sử dụng nhanh (One-Click)

Chỉ cần chạy **một lệnh duy nhất** để cập nhật toàn bộ dữ liệu và tái tạo báo cáo:

```bash
python scripts/run_all.py
```

Hoặc nhấn **Run** trực tiếp trong VS Code khi mở file `scripts/run_all.py`.

Script này sẽ tự động:
1. **Bước 1** – Load tất cả file Excel trong `data/` → ghi vào `Cleaned_Master_History.parquet`
2. **Bước 2** – Đọc parquet → tạo `MasterFullPricing_v2.xlsx` với 3 sheet: **Master**, **Recent_History**, **PUC**

---

## 📁 Cấu trúc thư mục

```
Pricing_Engine/
├── data/                          # Dữ liệu đầu vào & đầu ra
│   ├── FAK_*.xlsx                 # File cước FAK (US & Canada)
│   ├── SCFI_*.xlsx                # File cước SCFI (HPL)
│   ├── SPECIAL_RATE_*.xlsx        # File cước đặc biệt
│   ├── PUC_SOC.xlsx               # Bảng phụ phí PUC cho SOC
│   ├── Port_Code_Mapping_Final.xlsx  # Bảng mã cảng (tên → mã)
│   ├── Cleaned_Master_History.parquet  ← OUTPUT tự động tạo
│   └── MasterFullPricing_v2.xlsx      ← OUTPUT tự động tạo
│
├── Mapping/                       # CSV mapping cho từng loại file
│   ├── V4_FINAL_CHECK_FAK_*.csv   # Cột mapping cho file FAK
│   └── V4_FINAL_CHECK_SCFI_*.csv  # Cột mapping cho file SCFI
│
├── scripts/                       # Scripts chính
│   ├── run_all.py                 # ⭐ ONE-CLICK: chạy toàn bộ pipeline
│   ├── master_loader_v2.py        # Bước 1: Excel → Parquet
│   └── create_master_dashboard.py # Bước 2: Parquet → Excel
│
├── OCR_Engine/                    # Module OCR (xử lý ảnh báo giá)
├── OCR_Input/                     # Thư mục drop ảnh vào để OCR
├── OCR_Output/                    # Ảnh OCR đã xử lý
└── Backup_parquet/                # Backup file parquet cũ
```

---

## 🔄 Quy trình hoạt động

```
File Excel (FAK/SCFI/SPECIAL)
        ↓
  master_loader_v2.py
  (dùng Mapping CSV để parse đúng cột)
        ↓
  Cleaned_Master_History.parquet
  (~350,000 records)
        ↓
  create_master_dashboard.py
  (pivot, dedup, PUC formula, port mapping)
        ↓
  MasterFullPricing_v2.xlsx
  ┌─ Sheet: Master          (~14,000 routes)
  ├─ Sheet: Recent_History  (dữ liệu 30 ngày gần nhất)
  └─ Sheet: PUC             (bảng phụ phí SOC)
```

---

## ➕ Thêm dữ liệu mới

1. Copy file Excel mới (FAK / SCFI / SPECIAL RATE) vào thư mục `data/`
2. Chạy `python scripts/run_all.py`
3. Xong! File `MasterFullPricing_v2.xlsx` sẽ được cập nhật tự động.

> **Lưu ý:** Loader sẽ tự động detect loại file qua tên (`FAK`, `SCFI` trong tên file).
> Smart Dedup đảm bảo không bị duplicate: FAK > FIX > SCFI > SPECIAL > OCR.

---

## 🗂️ Logic Smart Dedup (ưu tiên nguồn dữ liệu)

| Ưu tiên | Rate Type | Mô tả |
|---------|-----------|-------|
| 1 | FAK | File cước chính – luôn thắng |
| 2 | FIX | Giá cố định |
| 3 | SCFI | HPL SCFI market index |
| 4 | SPECIAL | Giá đặc biệt |
| 5 | OCR | Nguồn thấp nhất – bị ghi đè bởi FAK |

---

## 🛠️ Yêu cầu cài đặt

```bash
pip install pandas openpyxl pyarrow numpy
```

Python 3.8+

---

## 📊 Output: MasterFullPricing_v2.xlsx

| Sheet | Nội dung |
|-------|---------|
| **Master** | Tất cả routes, pivot theo loại container (20GP/40GP/40HQ...). SOC rows có Excel formula tính PUC tự động |
| **Recent_History** | Records 30 ngày gần nhất, đầy đủ breakdown phụ phí |
| **PUC** | Bảng tham chiếu phụ phí PUC theo cảng đích |
