# ERP Architecture Evaluation — Excel vs Google Sheets (automation testability)

**Date:** 2026-04-11 | **Author:** Claude (brainstorm mode) | **Decision owner:** Nelson

## Problem
ERP_Master_v14.xlsm (D:/OneDrive/NelsonData/erp/) — mỗi lần chốt design phải mở Excel, click ribbon, verify bằng mắt. Không có automation test → iteration chậm, em (Claude) không tự verify được.

## Current state (facts)
- `ERP_Master_v14.xlsm` 1.6MB, 3,753 rows, 84K charge entries
- VBA stack: 4 modules (~110KB code) — ERPv14Core, ERPv14Ribbon, ERPv14Preset, CostBreakdown
- Custom ribbon via `CustomUI_v14.xml` (2 tabs: Pricing + Operations)
- Data pipeline: Parquet (6.75M rows) → DuckDB 15-day filter → `refresh-v14.py` (openpyxl) → xlsm
- "Stealth mode" — anh dùng Excel tại văn phòng để che việc tự build system
- Office 365 account: nelson@pudongprime.vn
- Python modules đã có ở `ERP/core/`, `ERP/intelligence/`, `ERP/quotes/` — business logic đã tách một phần

## Option A — Migrate to Google Sheets
**Pros**
- Apps Script chạy headless qua clasp + Apps Script API → em có thể test trực tiếp
- Iteration tốc độ 3-5x (no desktop Excel COM flakiness)
- Không cần Windows để test
- Built-in version history, collab

**Cons (brutal)**
- **Giết stealth mode** — Google Sheets trên browser = coworker thấy ngay
- Ribbon không tồn tại → phải rebuild UX thành custom menu + sidebar HTML (UX tệ hơn ribbon nhiều)
- Rewrite 110KB VBA → Apps Script (~2-3 tuần solid work, high bug risk)
- Apps Script timeout 6 phút/execution → refresh flow 84K charges sẽ break
- VLOOKUP performance trên 84K rows kém → Google Sheets chậm hơn Excel cho dataset này
- Office 365 → Google Workspace = đổi account, billing, governance pricing data
- Mất CopyPicture (quote image to clipboard), QueryTables, VBA event model
- Mất tooling hiện có: `refresh-v14.py`, `rate_importer.py`, DuckDB pipeline → rewrite hết
- Data governance: upload pricing data ~6.75M rows lên Google = rủi ro NDA carrier

**Verdict:** Net negative. Cái lợi (AI testability) KHÔNG đủ bù cho cái mất (stealth + tooling hiện có + rewrite effort).

## Option B — Stay on Excel + real test automation stack
**Tooling có sẵn (2026):**
| Layer | Tool | Role | Headless? |
|-------|------|------|-----------|
| 1 | **pytest** | Unit test pure Python logic | ✅ |
| 2 | **xlwings** | Drive Excel COM từ Python, gọi macro, đọc cell | ✅ (background Excel) |
| 3 | **Rubberduck VBA** | Unit test VBA trong VBE (free addin) | ⚠ GUI nhưng runnable |
| 4 | **pywinauto** | Click ribbon buttons programmatically (fallback) | ✅ |

## Recommended architecture — Excel + 3-tier test stack

### Tier 1 — Pure Python unit (80% coverage target)
**Move business logic ra Python:**
- HDL rules per carrier → `ERP/core/hdl_rules.py` (from CostBreakdown.bas)
- Markup calculation → `ERP/core/markup_engine.py`
- TEU calc, dedup, FAK classification → `ERP/core/pricing_utils.py`
- Quote generation → `ERP/quotes/quote_engine.py` (đã có base)

VBA còn lại chỉ là thin wrapper: `Call Shell("python -m erp.cli quote " & row)` hoặc xlwings UDF.
Test: `pytest tests/unit/` — chạy trong 2 giây, em tự verify được.

### Tier 2 — xlwings integration test
```python
# tests/integration/test_ribbon_callbacks.py
import xlwings as xw
import shutil

def test_generate_quote_creates_quotes_sheet_row():
    shutil.copy(MASTER_XLSM, TEST_XLSM)
    with xw.App(visible=False) as app:
        wb = app.books.open(TEST_XLSM)
        wb.sheets["Pricing Dashboard"].range("A2").select()
        wb.macro("ERPv14Ribbon.GenerateQuote")()
        assert wb.sheets["Quotes"].range("A2").value is not None
        wb.close()
```
- Chạy Excel background (visible=False)
- Fresh copy xlsm mỗi test → không hỏng file master
- ~30-60 sec/test → chấp nhận được cho integration
- Em gọi `pytest tests/integration/` trên Laptop VP → tự verify

### Tier 3 — Rubberduck VBA unit (optional)
- Cho pure VBA functions không move được (ribbon callbacks dùng IRibbonControl, Sheet events)
- Free addin https://rubberduckvba.com
- Chỉ cần khi tier 1+2 không đủ

## Phase plan (nếu anh chọn Option B)
| Phase | Scope | Effort |
|-------|-------|--------|
| **P1 — Test skeleton** | Cài xlwings + pytest, viết 3 test integration (refresh, quote, margin persist) | 1 ngày |
| **P2 — Logic extraction** | Port HDL rules + markup + dedup sang Python, VBA thành thin wrapper | 3-5 ngày |
| **P3 — Unit test backfill** | Pytest cover 80% logic Python | 2 ngày |
| **P4 — CI hook** | Task Scheduler trên Laptop VP chạy `pytest` mỗi lần git pull | 0.5 ngày |

Total: ~1-1.5 tuần, không phá workflow hiện tại.

## Recommendation: **Option B**
**Lý do:**
1. Stealth mode giữ nguyên
2. Không phá 110KB VBA đã chạy ổn
3. Pipeline Parquet/DuckDB/openpyxl intact
4. Em vẫn tự verify được qua `pytest` (không cần Excel GUI)
5. Logic dần dần drift về Python → tương lai migrate WebApp/API dễ hơn (shared engine)

**Điều duy nhất KHÔNG làm được với Option B:** test ribbon XML thay đổi visual (cần mắt người). Nhưng đó là 5% workflow, 95% còn lại automatable.

## Unresolved questions
1. Laptop VP có rảnh CPU để chạy pytest integration (Excel COM tốn RAM) không?
2. Có muốn CI hook chạy trên VPS không? (VPS không có Excel → chỉ chạy tier 1 được)
3. Test data: dùng fresh xlsm template (empty) hay snapshot .xlsm thực (có data)?
4. Quote Image bug (CopyPicture multi-row) — fix trước P1 hay gộp vào P2?
