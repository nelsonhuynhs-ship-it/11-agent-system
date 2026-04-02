---
name: erp-master
description: >
  Toàn bộ nghiệp vụ ERP — ERP_Master.xlsm rules, locked VBA functions,
  pricing formula, data refresh workflow, UI layout rules.
  TRIGGER khi: sửa VBA, chạy refresh ERP, hỏi về pricing formula,
  tạo quote trong ERP, hoặc bất kỳ thao tác trên ERP_Master.xlsm.
---

# ERP Master Skill

> **File mục tiêu:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\ERP\data\ERP_Master.xlsm`
> **MANDATORY:** Luôn đọc `erp-code-rules` workflow trước khi sửa code ERP

---

## 🔒 Sub-Skill: vba-rules — Quy tắc VBA bất di bất dịch

### LOCKED FUNCTIONS — KHÔNG SỬA KHÔNG CÓ LÝ DO
1. `ApplyQuickSearch` — Auto-filter từ A2/B2/C2, dùng `FindSheet("Pricing")`
2. `ClearQuickSearch` — Clear filters + search cells
3. `HandlePricingSheetChange` — Event router cho I2, J2-P2, J3-P3, A2-C2
4. `SaveCarrierMarkup / LoadCarrierMarkup` — Persist markup vào Markup_Store
5. `SaveGlobalMarkup` — Persist global markup (Row 3)
6. `GenerateQuote` — Tạo quote từ visible rows, buying rate = base + PUC
7. `MarkQuoteWin` — Tạo Job với cost breakdown, profit calc, email template
8. `FindSheet` — Safe sheet lookup by partial name (tránh emoji encoding)
9. `GetContainerPriceCol / GetContainerBaseCol` — Column mapping helpers

### Rules tuyệt đối
- ❌ KHÔNG dùng emoji sheet name: `Sheets("📊 Pricing")` → dùng `FindSheet("Pricing")`
- ❌ KHÔNG xóa `Application.EnableEvents = True` trong CleanUp blocks
- ❌ KHÔNG thay đổi cấu trúc pricing formula không có approval
- ✅ Feature mới → Tạo Sub/Function MỚI, không sửa locked functions
- ✅ Bug fix → Chỉ sửa đúng bug đó, không refactor code xung quanh

---

## 💰 Sub-Skill: pricing-formula — Công thức tính giá

### Formula chuẩn (KHÔNG ĐỔI)
```
Selling Price = Base + Global($J$3) + CarrierMarkup(IF I2 match) + PUC(hybrid)
```

**Giải thích:**
- `Base` — Net cost từ hãng tàu (Parquet/ERP Pricing sheet)
- `Global($J$3)` — Global markup Sếp set (áp dụng tất cả rows)
- `CarrierMarkup` — Markup riêng theo carrier (chỉ áp dụng carrier match I2)
- `PUC` — Price Unit Cost (chi phí nội địa Mỹ, hybrid SUMPRODUCT từ PUC_Lookup)

**PUC Hybrid Logic:**
```python
IF(SEARCH(D2, Place), E2, SUMPRODUCT(PUC_Lookup))  # cho SOC rows
```

**Python (ERP/core/refresh.py):**
- `BasicCost_Lookup` — Dedup by Exp desc, key=POL|POD|Place|Carrier|Cont
- `Markup_Store` read/write — Persistent carrier markups across refreshes
- `PUC_Lookup sheet` — Written from PUC data in Parquet

---

## 🏗️ Sub-Skill: erp-ui — Layout rules

### Row 1-8: LAYOUT — AI KHÔNG ĐƯỢC ĐỘNG VÀO
```
Row 1-8 = Header, buttons, search cells, markup controls
VBA hoạt động cực mạnh tại đây
Xóa/ghi đè = phá toàn bộ VBA functionality
```

### Sheets quan trọng
| Sheet | Dùng FindSheet keyword | Vai trò |
|-------|------------------------|---------|
| Pricing | "Pricing" | Main pricing data + ERP interface |
| Quotes | "Quotes" | Lịch sử báo giá |
| Jobs | "Jobs" / "Active" | Active shipments |
| Markup_Store | "Markup" | Persistent carrier markups |
| PUC_Lookup | "PUC" | Price Unit Cost lookup table |

---

## 🔄 Sub-Skill: data-refresh — Quy trình refresh ERP

### Khi nào chạy
- Nhận file báo giá mới từ hãng tàu
- Cần update Parquet → ERP

### Steps (xem workflow `/data-refresh` để chi tiết đầy đủ)
1. Chạy `python ERP/core/refresh.py`
2. Verify: Quick Search vẫn hoạt động, PUC dynamic đúng
3. Verify: Carrier markup persist sau refresh
4. Verify: GenerateQuote tạo quote đúng giá

### Pre-deploy checklist
- [ ] Quick Search A2/B2/C2 → no VBA errors
- [ ] PUC Dynamic → chỉ matching Place rows update
- [ ] Carrier markup → chỉ matching carrier rows update
- [ ] Global markup → all rows update
- [ ] Generate Quote → correct selling/buying rates
- [ ] Mark WIN → profit = (selling-buying) × qty
- [ ] `FindSheet("Pricing")` dùng ở mọi nơi

---

## 📋 Sub-Skill: quote-job-flow — Quy trình Quote → Job

```
QUOTE (Báo giá)          WIN (Chốt đơn)           ACTIVE JOB
──────────────           ─────────────            ──────────────
Sếp chat Bot     →       /win QUOTE_ID    →       Sheet Jobs
Bot query Parquet         Bot → ERP Writer         Cost breakdown
markup_engine             erp_writer.py            Email booking prep
GenerateQuote VBA         MarkQuoteWin VBA         Revenue tracking
Sheet: Quotes             Profit calculated        KPI update
```

---

## 🔗 References
- **Workflow:** `/erp-code-rules` — Rules đầy đủ trước khi sửa code
- **Workflow:** `/data-refresh` — Quy trình chuẩn refresh ERP data
- **Guide:** `ERP/ERP_SYSTEM_GUIDE.md` — Full module map

---

## 🏢 Sub-Skill: erp-structure — ERP Module Map (Post-Refactor)

| Directory | Vai trò | Key Files |
|-----------|---------|------------|
| `ERP/core/` | Refresh + system control | `refresh.py`, `control.py` |
| `ERP/quotes/` | Quote CRUD + image gen | `manager.py`, `image_generator.py` |
| `ERP/jobs/` | Job ops + email + tracking | `enrichment.py`, `email_builder.py`, `eta_alerts.py` |
| `ERP/crm/` | Customer management | `master.py`, `dashboard.py`, `relationships.py` |
| `ERP/intelligence/` | Analytics + market reports | `daily_sync.py`, `price_alerts.py`, `weekly_report.py` |
| `ERP/carrier_rules/` | Business rules config | `builder.py`, `booking_rules.json`, weight JSONs |
| `ERP/data/` | All operational data | `ERP_Master.xlsm`, `CRM_Master.xlsx`, `Jobs_Master.xlsx` |
| `ERP/vba/` | VBA macro source | `QuoteJobWorkflow.bas`, `SheetEvent` |

**Đường dẫn mới cho AI:** Tất cả script ERP đều trong `ERP/` subdirectories. KHÔNG có CRM/, Jobs/, Integration/ riêng nữa.
