# Research Report: ERP Excel — Professional Ribbon UI & Modern Implementation

## Executive Summary

GitHub có **rất ít** repo Excel VBA ERP chất lượng cao với ribbon UI. Khảo sát 30+ repo chỉ tìm được **1 repo ribbon chính thức** (Script-Help, 103 stars) và vài repo tham khảo hữu ích. Hầu hết Excel ERP trên GitHub thuộc loại: basic CRUD, single-user, không có ribbon, giao diện form đơn giản. **Kết luận: Muốn professional ribbon UI → tự build từ XML ribbon, không có template/framework readymade.**

---

## Research Methodology

- **Sources consulted:** GitHub search (4 queries), GitHub repo deep-dive (7 repos)
- **Date range:** Hiện tại (2026) — không giới hạn năm vì repo Excel VBA ERP rất ít
- **Key search terms:** `excel vba erp ribbon`, `excel ribbon xml vba`, `excel vba inventory management system`, `excel vba professional dashboard`, `excel vba framework modular erp`

---

## Key Findings

### 1. Tổng quan Landscape

| Loại | Số lượng repo | Chất lượng | Ribbon UI |
|------|--------------|------------|-----------|
| Excel VBA ERP nghiêm túc | ~10 repo | Thấp-trung bình | Không có |
| Excel Ribbon XML tool | 3 repo | Trung bình | Có (tool tạo ribbon) |
| Excel VBA dashboard/finance | ~15 repo | Trung bình | Không |
| VSTO Add-in (C#/VB.NET) | 2 repo | Cao (Script-Help) | Có (mẫu reference) |

### 2. Repo Nổi Bật

#### 🎯 Script-Help (103 ⭐) — BEST REFERENCE
- **URL:** https://github.com/Excel-projects/Script-Help
- **Mô tả:** VSTO Add-In (C# + VBA) cho batch load data SQL/Oracle. Ribbon UI chuẩn professional.
- **Ribbon tabs:** Clipboard, Format Data Table, Script Formula (submenu T-SQL/PL-SQL/DQL), Annotate, Help, About
- **Điểm hay:** Group structure rõ ràng, icon chuẩn, tooltip, keyboard shortcut

#### 🔧 Excel-Code-Export (19 ⭐)
- **URL:** https://github.com/Excel-projects/Excel-Code-Export
- **Mô tả:** Add-In export VBA modules + Ribbon XML cho source control
- **Điểm hay:** Hỗ trợ version control cho ribbon XML — reference tốt cho cách tổ chức ribbon code

#### 📦 ExcelAccountingSystem (1 ⭐)
- **URL:** https://github.com/aliqayid/ExcelAccountingSystem
- **Mô tả:** Full accounting system — login, sales, quote, invoice, client, inventory
- **Ribbon:** Không có (dùng UserForm truyền thống)
- **Ghi chú:** Template reference cho data model + workflow

#### 📦 Personal-Finance-Tracker-VBA (0 ⭐)
- **URL:** https://github.com/Sercan-Ayvaz/Personal-Finance-Tracker-VBA
- **Mô tả:** Financial management tool với modular architecture
- **Ribbon:** Không có
- **Điểm hay:** Modular architecture pattern (Logic/Navigation/Reports separation)

#### 📦 VBA_basded_ERP (1 ⭐)
- **URL:** https://github.com/vishnuprasadva/VBA_basded_ERP
- **Mô tả:** Lightweight ERP cho manufacturing — BOM, job cards, raw material, quotations
- **Ribbon:** Không có
- **File-based:** Dùng nhiều file .xlsx riêng biệt (customer_master, material_master, etc.)

#### 📦 Excel-VBA-ERP (0 ⭐)
- **URL:** https://github.com/anwer-qureshi/Excel-VBA-ERP
- **Mô tả:** MCS ERP — modular framework cho SMB
- **Ribbon:** Không có
- **Điểm hay:** Module design approach

#### 🔧 ExcelRibbonXMLEditor (0 ⭐)
- **URL:** https://github.com/charin-nawaritloha/ExcelRibbonXMLEditor
- **Mô tả:** Tool tạo/sửa Ribbon XML bằng VBA
- **Ribbon:** Có (chính là tool này)
- **Hạn chế:** Chỉ 1 commit, không maintain

#### 📦 Excel-VBA-Inventory-Management-System (6 ⭐)
- **URL:** https://github.com/abidshafee/Excel-VBA-Inventory-Management-System
- **Mô tả:** CRUD app cho business clients
- **Ribbon:** Không có

#### 📦 havishmad/excel_custom_ribbon_xml (3 ⭐)
- **URL:** https://github.com/havishmad/excel_custom_ribbon_xml
- **Mô tả:** Create + deploy VBA với Custom Ribbon XML như .xlam
- **Điểm hay:** Step-by-step tạo ribbon từ XML (có YouTube tutorial)

### 3. Ribbon XML — Technical Deep Dive

**Cách hoạt động:**
- Excel Ribbon UI được định nghĩa bằng XML markup (customUI XML)
- Load qua: File > Options > Customize Ribbon > Import/Export
- Hoặc embedded trong .xlsm/.xlam file

**Cấu trúc cơ bản:**
```xml
<customUI xmlns="http://schemas.microsoft.com/office/2009/07/customui">
  <ribbon>
    <tabs>
      <tab id="Tab1" label="My ERP">
        <group id="grpMain" label="Main">
          <button id="btnDashboard" label="Dashboard" imageMso="ChartAreaChart"
                  onAction="Dashboard_Click" size="large"/>
          <button id="btnReports" label="Reports" imageMso="PrintPreview"
                  onAction="Reports_Click"/>
        </group>
      </tab>
    </tabs>
  </ribbon>
</customUI>
```

**Key elements:**
- `<tab>` — Tạo tab riêng trên Ribbon
- `<group>` — Nhóm button trong tab
- `<button>` — Nút bấm (size: normal/large)
- `<menu>` / `<splitButton>` — Dropdown menu
- `imageMso` — Dùng icon có sẵn của Microsoft (1000+ icons)
- `image` — Dùng icon tự tạo (PNG 16x16, 32x32)
- `onAction` — Callback macro khi click

**Icon nguồn:**
- `imageMso` — Built-in: [https://learn.microsoft.com/en-us/office/vba/api/office.msocommand](/)
- Custom `image` — PNG file embedded hoặc linked

### 4. Modern UI Alternatives

#### a) VBA UserForm Modern
- Không có native "modern" controls trong VBA
- Cách cải thiện: Use `MSForms.DataObjects` for autocomplete, `RefEdit` for range selection
- Thư viện: `KAD-FormsCollection` (GitHub) — enhanced VBA forms

#### b) VSTO Add-in (C#/VB.NET)
- Full .NET UI capabilities (WPF, WinForms)
- Deploy như .xlam hoặc .exe
- **Script-Help là reference tốt nhất** cho cách structure ribbon + code
- Nhược điểm: Cần Visual Studio, complexity cao hơn

#### c) Web-based Overlay (WebView2)
- Nhúng WebView2 control vào Excel
- UI hoàn toàn tự do (React/Vue/Svelte)
- Nelson hiện tại dùng Python/FastAPI web_server — có thể extend the pattern
- **Reference:** [github.com/kridl/ExcelWebView2](https://github.com/search?q=excel+webview2+vsto)

### 5. Design Patterns từ các Repo

| Pattern | Repo | Mô tả |
|---------|------|-------|
| Modular architecture | Personal-Finance-Tracker-VBA | Logic/Navigation/Reports tách biệt |
| Multi-file workbook | VBA_basded_ERP | Mỗi domain = file riêng (customer_master, material_master) |
| Ribbon + source control | Excel-Code-Export | Export ribbon XML cùng VBA code |
| Data-driven UI | ExcelAccountingSystem | Login → Role → filtered menu |

---

## Comparative Analysis

### Framework/Template Availability

| Tên | Loại | Ribbon | Stars | Đánh giá |
|-----|------|--------|-------|----------|
| Script-Help | VSTO Add-in | ✅ Full | 103 | ⭐⭐⭐⭐⭐ Best reference |
| Excel-Code-Export | VBA Add-in | ✅ Export | 19 | ⭐⭐⭐⭐ Source control |
| ExcelRibbonXMLEditor | VBA Tool | ✅ Built-in | 0 | ⭐⭐ Cần dev |
| havishmad/excel_custom_ribbon_xml | VBA Template | ✅ Tutorial | 3 | ⭐⭐⭐ Hữu ích |
| Excel-VBA-ERP | VBA Framework | ❌ | 0 | ⭐⭐ Module design ref |

### Chi phí & Effort

| Approach | Effort | UI Quality | Maintainability |
|----------|--------|------------|-----------------|
| Ribbon XML thuần | Trung bình | ★★★★ | ★★★★ |
| VSTO C# Add-in | Cao | ★★★★★ | ★★★ |
| WebView2 overlay | Cao | ★★★★★ | ★★★★ |
| Enhanced VBA UserForm | Thấp | ★★ | ★★★ |

---

## Recommendations

### Quick Start Path
1. **Bắt đầu:** Học ribbon XML từ `havishmad/excel_custom_ribbon_xml` (có YouTube tutorial)
2. **Reference UI:** Clone `Script-Help` để xem cách structure ribbon tabs + groups
3. **Source control:** Dùng `Excel-Code-Export` để export ribbon XML cùng code
4. **Áp dụng cho ERP hiện tại:** Viết `customUI.xml` cho Nelson ERP, embed vào .xlsm

### Ribbon Design Suggested Structure cho Nelson ERP

```
Tab: "Nelson ERP" (hoặc icon/logo)
├── Group: "Dashboard" (large icon)
│   └── Dashboard, KPIs, Alerts
├── Group: "Rates"
│   └── Import Rates, Rate List, Compare
├── Group: "Quotes"
│   └── New Quote, Quote List, Smart Quote
├── Group: "Email" (nếu cần)
│   └── Compose, Queue, Sent
└── Group: "Tools"
    └── Settings, Refresh Data, Export
```

### Unresolved Questions
1. Nelson ERP hiện tại có bao nhiêu worksheets/modules? Cần map ribbon theo domain.
2. Có muốn multi-tab (1 tab per domain) hay single-tab với group?
3. Icon strategy: dùng `imageMso` (built-in) hay custom PNG?

---

## Resources & References

### Official Documentation
- [MS Ribbon XML Reference](https://learn.microsoft.com/en-us/office/vba/api/office.customui)
- [Office ribbon imageMso catalog](https://learn.microsoft.com/en-us/office/vba/api/office.msocommand)
- [Excel Campus — Custom Ribbon Tutorial](https://www.excelcampus.com/ribbon/)

### Repositories Referenced
- [Excel-projects/Script-Help](https://github.com/Excel-projects/Script-Help) — 103 stars, best ribbon reference
- [Excel-projects/Excel-Code-Export](https://github.com/Excel-projects/Excel-Code-Export) — 19 stars, ribbon XML source control
- [havishmad/excel_custom_ribbon_xml](https://github.com/havishmad/excel_custom_ribbon_xml) — 3 stars, ribbon tutorial
- [anwer-qureshi/Excel-VBA-ERP](https://github.com/anwer-qureshi/Excel-VBA-ERP) — 0 stars, modular ERP framework
- [aliqayid/ExcelAccountingSystem](https://github.com/aliqayid/ExcelAccountingSystem) — 1 star, full accounting system
- [Sercan-Ayvaz/Personal-Finance-Tracker-VBA](https://github.com/Sercan-Ayvaz/Personal-Finance-Tracker-VBA) — modular architecture
- [vishnuprasadva/VBA_basded_ERP](https://github.com/vishnuprasadva/VBA_basded_ERP) — manufacturing ERP

---

**Research date:** 2026-05-02
**Scope:** Excel VBA ERP Ribbon UI & Professional Implementation
