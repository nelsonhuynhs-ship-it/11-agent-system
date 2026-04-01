# CARRIER CONVENTIONS
> Tài liệu quy ước xử lý dữ liệu giá theo từng hãng tàu  
> Cập nhật lần cuối: 27-Feb-2026  
> Mục đích: Tham chiếu khi cần mở rộng hoặc chỉnh sửa logic trong `master_loader_v2.py` và `create_master_dashboard.py`

---

## Mục lục
1. [Quy ước chung (All Carriers)](#1-quy-ước-chung)
2. [ONE — Ocean Network Express](#2-one)
3. [CMA — CMA CGM](#3-cma)
4. [YML — Yang Ming Line](#4-yml)
5. [ZIM](#5-zim)
6. [HPL — Hapag-Lloyd (SCFI)](#6-hpl-scfi)
7. [Placeholder: Rules theo Commodity](#7-placeholder-rules-theo-commodity)
8. [Placeholder: Freetime theo cảng](#8-placeholder-freetime-theo-cảng)
9. [Placeholder: Rules theo POL/POD](#9-placeholder-rules-theo-polpod)

---

## 1. Quy ước chung

### 1.1 Note Normalization (áp dụng cho tất cả carrier)
Tất cả note được rút gọn khi tạo `MasterFullPricing_v2.xlsx`.  
**File thực thi:** `create_master_dashboard.py` → hàm `normalize_notes()`

| Pattern (gốc từ FAK) | Normalized | Ghi chú |
|---|---|---|
| `via Yantian/Kaohsiung/Hong Kong/Singapore/Shanghai` | `SOC TRANSIT` | Note có SOC prefix |
| `via Yantian/...` (không có SOC) | `TRANSIT` | Non-SOC transit |
| `SOC via Cai Mep (EC3)`, `SOC Cai Mep (EC3)` | `SOC Cai Mep (EC3)` | |
| `via Cai Mep` (không có SOC) | `Cai Mep (EC3)` | |
| `SOC direct service`, `SOC DIRECT HPH`, `SOC Haiphong (Direct service)` | `SOC DIRECT` | |
| `Direct service HAI PHONG`, `Direct HPH` (không có SOC) | `DIRECT` | |

### 1.2 PUC Stripping — khi nào apply
**File thực thi:** `master_loader_v2.py` → hàm `strip_puc_from_soc_rows()`  
**Điều kiện:** Carrier ∈ {ONE, CMA, YML} **VÀ** Note chứa "SOC" **VÀ** Charge = Base charge

Xem thêm chi tiết từng carrier bên dưới.

### 1.3 Sheet Structure
| Sheet | Nội dung |
|---|---|
| **Master** | Giá final (Base O/F + PUC via formula VLOOKUP → cộng từ sheet PUC) |
| **Basic Cost** | Giá breakdown: BASIC O/F + từng phụ phí → cộng = Master |
| **PUC** | Lookup table phụ phí PUC theo điểm đến |
| **Version** | Metadata: FAK version, ngày chạy, RAW files nguồn |

---

## 2. ONE

### 2.1 SOC — PUC Stripping ✅
- **Lý do:** File FAK của ONE đã **bao gồm PUC** trong giá SOC quoted
- **Rule:** Khi load parquet, trừ PUC từ `PUC_SOC.xlsx` khỏi Base charge của mọi row có `Note` chứa "SOC"
- **Kết quả tại sheet Master:** Formula `= (base - PUC_stripped) + VLOOKUP(Place, PUC, col, 0)` → giá final chính xác
- **Carriers áp dụng:** ONE, CMA, YML (xem chi tiết từng carrier)

### 2.2 Note Normalization (ONE SOC)
ONE dùng nhiều dạng note SOC khác nhau, tất cả được rút gọn:

| Note gốc ONE | Normalized |
|---|---|
| `SOC via Yantian/Kaohsiung/Hong Kong/Singapore/Shanghai` | `SOC TRANSIT` |
| `SOC Yantian/Kaohsiung/...` | `SOC TRANSIT` |
| `SOC direct service` | `SOC DIRECT` |
| `SOC Haiphong (Direct service)` | `SOC DIRECT` |
| `SOC via Cai Mep (EC3)` | `SOC Cai Mep (EC3)` |
| `SOC Cai Mep (EC3)` | `SOC Cai Mep (EC3)` |
| `SOC EC4` | `SOC EC4` (giữ nguyên) |
| `SOC` | `SOC` (giữ nguyên) |

### 2.3 Commodity Normalization
| Pattern gốc | Normalized |
|---|---|
| `REEFER FAK (...)` | `REEFER FAK` |
| `FAK: TPE1 - FAK Straight (Excluding...)` | `FAK: TPE1` |
| `SHORT TERM GDSM (GENERAL DEPARTMENT...)` | `SHORT TERM GDSM` |
| `GARMENT...` | `GARMENT` |
| `Group SOC: ...` | `Group SOC` (cắt phần sau dấu `:`) |

### 2.4 Container Type
- ONE REEFER: `20'` → `20RF`, `40'` → `40RF`

### 2.5 Placeholder — Rules tương lai ONE
```
[ ] Freetime POL: HCM = ? ngày, Haiphong = ? ngày
[ ] Freetime POD: US Main port = ? ngày, US Inland = ? ngày  
[ ] Surcharge riêng theo commodity (Garment, Reefer)
[ ] ONE Short Term vs Long Term rate priority
```

---

## 3. CMA

### 3.1 SOC — PUC Stripping ✅
- Cùng logic với ONE (xem mục 2.1)
- **Carriers áp dụng:** CMA, ONE, YML

### 3.2 Note Normalization (CMA SOC)
| Note gốc CMA | Normalized |
|---|---|
| `SOC` | `SOC` |
| `SOC direct service` | `SOC DIRECT` |

### 3.3 Placeholder — Rules tương lai CMA
```
[ ] Freetime POL: HCM = ? ngày
[ ] Surcharge theo hàng đặc biệt (DG, OOG)
[ ] CMA NILE / POINTE-NOIRE vessel schedule note
```

---

## 4. YML

### 4.1 SOC — PUC Stripping ✅
- Cùng logic với ONE (xem mục 2.1)

### 4.2 Note Normalization
| Note gốc YML | Normalized |
|---|---|
| `SOC` | `SOC` |

### 4.3 Placeholder — Rules tương lai YML
```
[ ] Freetime policy
[ ] YML service code mapping
```

---

## 5. ZIM

### 5.1 Note Normalization — Service + OWS Status
**File thực thi:** `create_master_dashboard.py` → `normalize_notes()` → ZIM block  
**Logic 2 chiều độc lập:** [Service Code] + [OWS Status]

#### Service Codes
| Keyword trong note | Label |
|---|---|
| `Z7S` | `Z7S` |
| `ZXB` | `ZXB` |
| `ZEX` | `ZEX` |
| Không có code cụ thể | `ZIM` |

#### OWS Status (kiểm tra theo thứ tự này)
| Điều kiện | OWS suffix | Ghi chú |
|---|---|---|
| Chứa `subject to OWS` | ` OWS EXTRA` | Kiểm tra TRƯỚC |
| Chứa `OWS` (tất cả còn lại) | ` OWS INCL` | User xác nhận: mọi non-subject-to OWS đều là inclusive |
| Không nhắc OWS | `` (trống) | |

#### Cảnh báo Tonnage
- Nếu note chứa tonnage limit **< 22 tons** (ví dụ `up to 21.5 tons`) → append `[!OWS<22T:21.5t]`
- Threshold hiện tại: **22 tons** (chuẩn ZIM thị trường hiện tại)
- **Để thay đổi threshold:** sửa giá trị `22` trong hàm `_tonnage_warn()` tại `create_master_dashboard.py`

#### Kết quả normalize mẫu
| Note gốc | Normalized |
|---|---|
| `Z7S only Inclusive OWS upto 22 tons for 20DV` | `Z7S OWS INCL` |
| `ZXB / Inclusive OWS upto 22tons for 20DV` | `ZXB OWS INCL` |
| `Inclusive OWS up to 22 tons for 20DV` | `ZIM OWS INCL` |
| `Z7S only up to 21.5 tons OWS` | `Z7S OWS INCL [!OWS<22T:21.5t]` |
| `ZXB subject to OWS` | `ZXB OWS EXTRA` |
| `ZEX` | `ZEX` |
| `3923.00.0000 / 9403.00.0000` | Giữ nguyên — giá riêng theo HS code |

### 5.2 PUC Stripping
- ZIM **không** áp dụng PUC strip (PUC không embedded trong FAK ZIM)

### 5.3 Placeholder — Rules tương lai ZIM
```
[ ] Freetime POL/POD cho ZIM
[ ] ZIM OWS — nếu có thêm service code mới (ngoài Z7S/ZXB/ZEX)
[ ] ZIM tonnage threshold thay đổi (hiện tại: 22T)
[ ] ZIM surcharge theo HS code (3923/9403 và các mặt hàng khác)
```

---

## 6. HPL (SCFI)

### 6.1 Container Normalization
| Gốc | Normalized |
|---|---|
| `20'` | `20GP` |
| `40'` | `40GP` |
| `40'HC` | `40HQ` |

### 6.2 Charge Normalization
| Charge gốc SCFI | Mapped to |
|---|---|
| `HLCU Offer` | `Base Ocean Freight` |
| `BASE O/F` | `Total Ocean Freight` |
| `EMF` | `EIC/GFS/BAF/FDI` |
| `DLF` | `PCS` |
| `COMMISSION` | `HANDLING FEE FOR CARRIER` |

### 6.3 Note
- SCFI Note luôn được **để trống** (force blank) — tránh service notes chung chung ghi đè

### 6.4 Placeholder — Rules tương lai HPL
```
[ ] HPL SCFI N35+ — kiểm tra thay đổi template cột
[ ] HPL Reefer pricing nếu xuất hiện
```

---

## 7. Placeholder: Rules theo Commodity

> Phần này sẽ được mở rộng khi cần báo giá theo mặt hàng cụ thể

```
## Template cho mỗi commodity rule:

### [Tên mặt hàng] — [Carrier]
- Carrier áp dụng: ...
- Surcharge thêm: ...
- Note đặc biệt: ...
- Commodity filter keyword: ...
- Priority vs FAK regular: ...

---
Ví dụ tương lai:
### GARMENT — ONE
- Phụ thu Garment Add On: theo cột riêng trong FAK
- Note: "GARMENT" (sau normalize)
- Commodity filter: str.startswith("GARMENT")

### REEFER — ONE/COSCO
- Container type: 20RF, 40RF (tự động convert từ 20GP/40GP nếu commodity = REEFER)
- Surcharge reefer: tách biệt với dry cargo
```

---

## 8. Placeholder: Freetime theo cảng

> Phần này sẽ được thêm khi tích hợp freetime vào báo giá

```
## Template:

### [Carrier] — Freetime
| Port Type | POL (ngày) | POD (ngày) | Ghi chú |
|---|---|---|---|
| HCM (Main) | ? | ? | |
| Haiphong (Main) | ? | ? | |
| US Main Port | - | ? | |
| US Inland (IPI) | - | ? | Thêm detention inland |
| Canada Main | - | ? | |

---
Ví dụ tương lai:
### ONE — Freetime
| Port | POL | POD | Note |
|---|---|---|---|
| HCM | 5 ngày | - | |
| USWC Main | - | 5 ngày | |
| USEC Main | - | 5 ngày | |
| Chicago (IPI) | - | 2 ngày + inland detention | |
```

---

## 9. Placeholder: Rules theo POL/POD

> Phần này sẽ được thêm khi cần logic routing/surcharge phụ thuộc cảng

```
## Template:

### [Carrier] — POD Special Rules
- US IPI (Inland) destinations:
  - POD codes: CHICAGO, DALLAS, ATLANTA, KANSAS CITY...
  - Thêm ARB/OLF charge
  - Freetime inland khác Main port

- Canada Inland:
  - CALGARY, TORONTO, EDMONTON
  - PUC cao hơn Main port Vancouver/Prince Rupert

---
Ví dụ tương lai:
### ONE — Routing note theo POD
| POD Group | Routing | Note normalize |
|---|---|---|
| US East Coast Main | Direct | `EC DIRECT` |
| US East Coast via transit | Via Yantian/... | `EC TRANSIT` |
| US West Coast | Direct | `WC DIRECT` |
| Canada Inland | Via Vancouver + IPI | — |
```

---

## Changelog

| Ngày | Thay đổi | File ảnh hưởng |
|---|---|---|
| 27-Feb-2026 | Khởi tạo CARRIER_CONVENTIONS.md | — |
| 27-Feb-2026 | Strip PUC cho ONE/CMA/YML SOC rows | `master_loader_v2.py` |
| 27-Feb-2026 | Normalize SOC notes (DIRECT/TRANSIT/Cai Mep) | `create_master_dashboard.py` |
| 27-Feb-2026 | ZIM smart normalization (Z7S/ZXB/OWS status) | `create_master_dashboard.py` |
| 27-Feb-2026 | Cảnh báo OWS < 22T | `create_master_dashboard.py` |
| 27-Feb-2026 | Thêm cột Group Rate từ cột I FAK | `master_loader_v2.py` |
| 27-Feb-2026 | Sheet Recent_History → Basic Cost | `create_master_dashboard.py` |
| 27-Feb-2026 | Sheet Version (FAK version + RAW files) | `create_master_dashboard.py` |
