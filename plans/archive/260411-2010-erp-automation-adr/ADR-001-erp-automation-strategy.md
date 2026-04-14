# ADR-001: ERP Automation Strategy — Excel vs Google Sheets

**Status:** Proposed
**Date:** 2026-04-11
**Decider:** Nelson (1 người, final call)
**Stakeholder:** Nelson (dùng hàng ngày), Claude CLI (tool)

---

## 1. Context

Nelson đang chạy ERP_Master_v14.xlsm với full workflow:
Pricing check → Generate Quote → Mark Win/Lost → Tạo Active Job.

**Đã đầu tư production-ready**:
- `CustomUI_v14.xml` — ribbon 2 tabs × 7 groups × ~50 controls
- `erp-v14-ribbon-callbacks.bas` — 71KB VBA, ~50 callbacks, module state vars
- `refresh-v14.py` — Parquet 6.6M rows → Pricing Dry/Reefer + ChargeBreakdown + RateVersions
- `customui_utils.py` — inject ribbon XML vào .xlsm ZIP
- Formula locked: `Sell = Base + Global + CarrierMarkup + PUC`

**Pain points của Nelson**:
1. Không có test loop tự động — phải thủ công mở Excel, click nút, xem kết quả, lặp lại
2. Plan dài, HTML preview xem mệt, không khả thi — "cứ phải có human check"
3. Iteration chậm → bug fix chậm → Nelson mệt
4. Claude CLI hỏi permission từng tool call — Nelson click approve liên tục phát điên

**Constraints**:
- **Thời gian**: nhanh nhất có thể (không đợi được tuần)
- **Thống nhất**: chốt 1 lần dùng tiếp, không muốn loay hoay giữa 2 stack
- **Nelson 1 mình**: không có team collab realtime requirement hiện tại
- **Không break**: pricing formula + 71KB VBA đã production, không được sai giá
- **Hand-off**: Nelson muốn Claude tự làm, không click approve từng cái

---

## 2. Decision

> **Chốt: Option A — Excel local + Claude CLI automation helpers + permission bypass.**

Không migrate Google Sheets. Viết 4 Python helper (pywin32) để Claude drive Excel tự động (import .bas, run macro, verify output). Cấu hình `settings.json` allow list để Claude không hỏi permission nữa cho các tool/path ERP.

**Time to completion**: ~2-3 ngày làm việc thực tế. Bắt đầu làm được ngay sau khi Nelson approve ADR.

---

## 3. Options Considered

### Option A — Excel local + Claude helpers (RECOMMENDED)

Giữ nguyên stack hiện tại, thêm 4 Python helper tự động hoá test loop + set permission allow list.

| Dimension | Đánh giá |
|---|---|
| Thời gian hoàn thành | **2-3 ngày** |
| Cost dev | Thấp — reuse toàn bộ VBA + Python hiện có |
| Risk break pricing | Rất thấp — không đụng công thức |
| Scalability (data) | Cao — Parquet 6.6M rows chạy local 28x Pandas |
| Team familiarity | Cao — Nelson đã biết stack |
| Maintenance | Thấp — ít component mới |
| Test loop speed | Nhanh — pywin32 COM ~2-5s/iteration |
| UI richness | Giữ nguyên ribbon 2 tabs × 7 groups |
| Nelson effort | Zero setup thêm — chỉ approve + chạy |

**Pros**:
- Reuse 100% đầu tư hiện có (71KB VBA + ribbon + refresh pipeline)
- pywin32 là stable, Windows-native, miễn phí
- Test loop tự động: edit .bas → import → run macro → read sheet → fail/pass
- Permission bypass 1 lần config, xong quên
- Bắt đầu ship feature mới sau 2-3 ngày

**Cons**:
- Windows only (không chạy được trên Linux VPS — nhưng ERP chạy máy Nelson thôi, không sao)
- pywin32 chạy chậm nếu gọi 100+ lần/giây (không phải use case của Nelson)
- Visual ribbon vẫn phải mắt Nelson check — nhưng structure validate được qua XML parse

---

### Option B — Migrate Google Sheets + Apps Script (FULL REBUILD)

Rewrite toàn bộ workflow sang Google Sheets.

| Dimension | Đánh giá |
|---|---|
| Thời gian hoàn thành | **2-3 TUẦN** (phoặt 10x Option A) |
| Cost dev | Cao — rewrite 71KB VBA → Apps Script (JS) |
| Risk break pricing | **Cao** — chuyển công thức + data layer + formula |
| Scalability (data) | Trung bình — phải upload Parquet lên BigQuery/Cloud SQL |
| Team familiarity | Trung bình — Nelson biết JS nhưng chưa biết Apps Script quirks |
| Maintenance | Trung bình — ít file nhưng nợ kỹ thuật cao trong giai đoạn đầu |
| Test loop speed | Chậm — Apps Script execution quotas + latency cloud |
| UI richness | **Giảm** — Apps Script chỉ có `createMenu()` text list, không có comboBox/editBox/group/icon ribbon |
| Nelson effort | Cao — phải learn Apps Script + debug migration |

**Pros**:
- Nếu sau này có team, realtime collab dễ
- Truy cập mobile/tablet
- Không cần Excel license (nhưng Nelson đã có rồi)

**Cons**:
- **KHÔNG có ribbon**: 50 callbacks → 10 menu items. UX giảm thấy rõ.
- Parquet 6.6M rows: Apps Script không đọc được trực tiếp → phải BigQuery. Latency tăng từ ms lên sec.
- Pricing formula risk: công thức đã locked + test nhiều tháng. Port sai một dấu = sai giá = sai revenue.
- Execution quota: Apps Script trigger 6 min hard limit. Refresh full parquet có thể vượt.
- Không có use case hiện tại cho lợi ích collab (Nelson 1 mình).
- Mất 2-3 tuần KHÔNG ship được feature nào khác.

---

### Option C — Hybrid (Excel source + Google Sheets view-only mirror)

Giữ Excel như Option A, cộng thêm export view-only sang Google Sheets cho read access.

| Dimension | Đánh giá |
|---|---|
| Thời gian hoàn thành | 3-4 ngày |
| Cost dev | Trung bình — Option A + gspread sync script |
| Risk | Thấp — Google Sheets chỉ read, không logic |
| Nelson effort | Trung bình — config Google service account |

**Pros**: Best of both — local performance + cloud read access
**Cons**: Phức tạp hơn A, không có lợi ích ngay (mentees chưa dùng). **Defer, làm sau nếu có nhu cầu.**

---

## 4. Trade-off Analysis

**Nhanh nhất** → Option A. Gấp 7-10 lần Option B. Không ngang ngửa.

**Risk thấp nhất** → Option A. Không đụng pricing formula.

**Lợi ích dài hạn** → Option B chỉ thắng nếu có team 3+ người cùng edit realtime. Hiện tại Nelson 1 mình → lợi ích này = 0.

**UX tốt nhất** → Option A. Ribbon rich, Apps Script menu nghèo.

**Tóm lại**: Option A thắng trên 4/4 dimensions quan trọng với Nelson. Option B chỉ thắng trên 1 dimension (mobile collab) mà Nelson không cần hiện tại.

**Google Sheets làm sau nếu cần**: có thể add Option C (hybrid sync) sau Option A mà không phải rewrite — chỉ thêm 1 file `export_to_gsheet.py`. Không lock-in.

---

## 5. Consequences

**Sau khi làm xong Option A, anh sẽ có**:
- ✅ `tools/erp-helpers/` với 4 Python script:
  - `bas_importer.py` — import .bas files vào ERP_Master_v14.xlsm qua pywin32 (thay copy-paste thủ công)
  - `macro_runner.py` — chạy bất kỳ macro nào qua pywin32, capture output sheet, return JSON
  - `ribbon_validator.py` — parse CustomUI14 trong .xlsm ZIP, verify tất cả callbacks có match với .bas modules
  - `test_loop.py` — combine 3 cái trên: edit → import → run → verify → report
- ✅ `.claude/settings.json` — permission allow list cho ERP paths, Claude không hỏi nữa
- ✅ Workflow tự động hoá: edit .bas/.py/.xml → Claude chạy test_loop → report → fix → lặp
- ✅ Không còn manual click Excel ribbon để test

**Cái sẽ khó hơn**:
- Gỡ Windows khỏi workflow (pywin32 Windows-only) — không sao vì máy Nelson Windows
- Muốn chạy test_loop trên VPS Linux (hiện tại không cần, ERP không chạy VPS)

**Cái cần revisit**:
- Sau 3 tháng dùng: nếu Nelson thấy cần mobile access hoặc có mentee cần edit ERP → consider Option C hybrid sync (không phải rewrite)

---

## 6. Action Items — Chạy được ngay

### 6.1 Ngay lập tức (~5 phút) — Permission bypass

Nelson chạy (hoặc cho phép Claude chạy) để cấu hình allow list:

```bash
# File: D:/NELSON/2. Areas/Engine_test/.claude/settings.local.json
# (dùng .local.json để không commit vào git)
```

Nội dung file — xem `permission-bypass-config.md` cùng thư mục này.

### 6.2 Phase 1 (~Day 1, 4-6h) — `bas_importer.py` + `macro_runner.py`

- [ ] Setup `tools/erp-helpers/` trong repo Engine_test (hoặc OneDrive tùy Nelson chọn)
- [ ] Install `pywin32` vào anaconda python env: `C:/Users/Nelson/anaconda3/python -m pip install pywin32`
- [ ] Write `bas_importer.py`:
  - Input: xlsm path + list .bas files
  - Action: open Excel invisible → `wb.VBProject.VBComponents.Import(path)` cho từng .bas → save → close
  - Return: JSON `{"imported": [...], "errors": [...]}`
- [ ] Write `macro_runner.py`:
  - Input: xlsm path + macro name + args (optional)
  - Action: open invisible → `wb.Application.Run(macro_name, *args)` → read specified output range → close
  - Return: JSON `{"macro": ..., "result": ..., "elapsed_ms": ...}`
- [ ] Unit test với 1 macro có sẵn (ví dụ `GenerateQuote`) — dry run trên backup .xlsm
- [ ] Commit: `feat(erp-helpers): bas_importer + macro_runner pywin32`

### 6.3 Phase 2 (~Day 2, 3-4h) — `ribbon_validator.py` + `test_loop.py`

- [ ] Write `ribbon_validator.py`:
  - Input: xlsm path
  - Action: open as ZIP → read `customUI/customUI14.xml` → parse với lxml → extract tất cả `onAction/onChange/getLabel` callbacks → grep .bas files → report missing
  - Return: JSON `{"callbacks_in_xml": N, "callbacks_in_bas": M, "missing": [...], "orphan": [...]}`
- [ ] Write `test_loop.py`:
  - Input: config JSON (xlsm path, .bas files, macros to test, expected outputs)
  - Action: bas_importer → ribbon_validator → macro_runner per macro → compare expected → report
  - Return: text report pass/fail per check
- [ ] Run `test_loop.py` trên ERP_Master_v14.xlsm (backup first)
- [ ] Commit: `feat(erp-helpers): ribbon_validator + test_loop`

### 6.4 Phase 3 (~Day 3, 2-3h) — Integration + docs

- [ ] Write `tools/erp-helpers/README.md` — quick start, 3 commands
- [ ] Add script entries vào anh convenience (bat file hoặc package.json):
  - `erp-test` → chạy test_loop.py
  - `erp-import-bas` → chạy bas_importer.py
- [ ] Update `erp-master` skill trong `.claude/skills/erp-master/SKILL.md` — add section "Test loop helpers"
- [ ] Nelson test end-to-end 1 bug fix thực: sửa .bas → Claude chạy test_loop → verify → ship
- [ ] Commit + merge: `docs(erp-helpers): README + skill update`

### 6.5 Gate — Kết thúc project

- [ ] Nelson confirm: "edit VBA → test → ship" không cần mở Excel thủ công
- [ ] Document lesson learned vào `plans/260411-2010-erp-automation-adr/lessons.md`
- [ ] Archive plan, mark ADR = **Accepted**

---

## 7. Tracking

| Milestone | ETA | Status |
|---|---|---|
| ADR approved | After Nelson review | ⏳ |
| Permission bypass configured | 5 min after approval | ⏳ |
| Phase 1 complete | Day 1 | ⏳ |
| Phase 2 complete | Day 2 | ⏳ |
| Phase 3 complete + Nelson accept | Day 3 | ⏳ |
| ADR → Accepted | Day 3 | ⏳ |

---

## 8. Related

- `plans/260411-2010-erp-automation-adr/permission-bypass-config.md` — settings.json snippet + explanation
- `plans/260411-2010-erp-automation-adr/helper-scripts-spec.md` — API design cho 4 helper
- `.claude/skills/erp-master/SKILL.md` — current ERP rules (unchanged)
- `D:/OneDrive/NelsonData/erp/` — files hiện tại (unchanged)
