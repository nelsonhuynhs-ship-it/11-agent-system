# PUC_SOC RULES — CARRIER PRICING SYSTEM
# =========================================
# Last updated: 2026-03-10
# Author: System — confirmed by Sếp Nelson

## Tổng quan

Chỉ áp dụng cho 3 hãng tàu có hợp đồng SOC:
- **CMA** (CMA CGM)
- **ONE** (Ocean Network Express)
- **YML** (Yang Ming Line)

File nguồn: `data/PUC_SOC.xlsx`
  - Cột PlaceOfDelivery = địa điểm giao hàng (mapping theo cột Place trong FAK)
  - Cột 20GP, 40 (= 40GP + 40HQ), 45 = giá PUC đúng hiện tại theo container

## 3 Rules xử lý PUC khi build Parquet

Khi loader đọc FAK file, với mỗi row **CMA/ONE/YML SOC**, áp dụng:

### Rule 1 — FAK PUC column = trống (0)
```
Total Ocean Freight = Basic O/F + PUC_SOC
```
Ví dụ: YML HPH-LAX, Basic = $1,400, PUC cột trống
→ PUC_SOC LA = $1,000/40HQ
→ Total = $1,400 + $1,000 = **$2,400**

### Rule 2 — FAK PUC < PUC_SOC (cộng chưa đủ)
```
delta = PUC_SOC - FAK_PUC
Total Ocean Freight = Basic O/F + FAK_PUC + delta  =  Basic + PUC_SOC
```
Ví dụ: Basic = $1,400, FAK PUC = $400, PUC_SOC = $800
→ delta = $400
→ Total = $1,400 + $400 + $400 = **$2,200**

### Rule 3 — FAK PUC >= PUC_SOC (đã đủ, bỏ qua)
```
Total Ocean Freight = Basic O/F + FAK_PUC  (không thay đổi)
```
Ví dụ: Basic = $1,400, FAK PUC = $800, PUC_SOC = $800
→ Total = $1,400 + $800 = **$2,200** (đã đúng)

## Tóm tắt công thức chung

```
puc_to_use = max(FAK_PUC, PUC_SOC)
Total = Basic + puc_to_use
```

## FAK mapping columns

| Excel Col | Charge_Group | Cont_Type |
|-----------|-------------|-----------|
| AM        | PSS/PUC     | 20GP      |
| AN        | PSS/PUC     | 40GP      |
| AO        | PSS/PUC     | 40HQ      |
| AP        | PSS/PUC     | 45'HQ     |

→ Loader đọc PSS/PUC từ các cột này làm FAK_PUC.

## Hãng KHÔNG áp dụng (không có SOC contract)

MSC, MSK, ZIM, WHL, HMM, COSCO, EMC, OOCL, HPL
→ Các hãng này dùng COC, PUC không liên quan.
→ Bot query Total Ocean Freight cho các hãng này là đúng nguyên xi FAK.

## Code reference

`master_loader_v2.py` → function `apply_puc_soc_correct()`
`PUC_CARRIERS = {'CMA', 'ONE', 'YML', 'HPL'}`

## Cập nhật PUC_SOC

Khi giá PUC thay đổi:
1. Mở `data/PUC_SOC.xlsx` → cập nhật cột 40/20/45 theo địa điểm
2. Chạy lại `python scripts/master_loader_v2.py` với file FAK mới nhất
3. Parquet tự rebuild với PUC đúng
