# Code Review Report — Email Dashboard Lane/POD Selection

**Date**: 2026-04-23
**Reviewer**: Code Reviewer Agent
**Scope**: Email dashboard — lane/POD selection logic (preview → bulk send)
**Stakeholder**: Nelson Huynh (CEO, NVOCC Vietnam→USA/Canada)

## Files Reviewed

- `email_engine/config/default_routes.yaml` (77 lines) — routing rules SOT
- `email_engine/intelligence/builder.py` (lines 1-100, 700-838) — `build_email()` core
- `email_engine/intelligence/template_selector.py` (238 lines, đã đọc toàn bộ trước đó)
- `email_engine/templates/email_rules.yaml` (96 lines) — 5 templates (west/east/canada/inland/default)
- `email_engine/web_server.py`:
  - 305-344 — `_normalize_dest_text()` helper
  - 557-567 — `/api/rate-preview` endpoint
  - 1490-1589 — `/api/prospects` bulk lane path A
  - 1860-1892 — `DEFAULT_DESTINATIONS` loader
  - 2045-2140 — `/api/bulk/build` path B (MERGE strategy)
  - 2616-2633 — `/api/intelligence/lanes`

---

## Summary

Lane/POD selection hiện tại có **kiến trúc 3-tầng fragmented**: YAML (SOT) + 2 hardcoded fallback + 2 code path khác biệt. Nelson đề xuất **10 default lanes cross-sell** là đúng hướng nhưng cần fix **6 bugs/conflicts** và **mở rộng template region** để tránh regression.

**Severity breakdown:**
- 🔴 **CAO**: 4 issues (hardcoded fallback drift, path A không merge, template tie-break non-deterministic, max_destinations không enforce)
- 🟡 **TRUNG**: 5 issues (CAVAN template miss, YAML dead config, 2 path inconsistent, preview không fallback, `_normalize_dest_text` silent fail)
- 🟢 **THẤP**: 3 issues (duplicated logic, missing tests, UX 10-row table dài)

**Verdict:** Nelson's 10-lane proposal KHẢ THI, nhưng KHÔNG được chỉ sửa hardcoded lane list — phải fix **sync source** + **merge logic path A** + **template CAVAN** cùng lúc, nếu không sẽ phát sinh rate 0/template sai/email dài 10+ row vỡ layout.

---

## Issues Found

### 🔴 CAO (High Priority)

#### 1. Triple-source hardcoded fallback — YAML SOT bị drift

- **File**: `email_engine/config/default_routes.yaml:28`, `email_engine/web_server.py:1873`, `email_engine/intelligence/builder.py:741`
- **Line**: 3 chỗ định nghĩa cùng 1 danh sách 9 lanes
- **Description**: "Single Source of Truth" YAML đã sync với fallback ở `web_server.py:1873`, NHƯNG `builder.py:741` hardcode lại lần nữa trong chính hàm `build_email()`. Khi Nelson sửa YAML sang 10 lanes mới:
  - `web_server.py` path B (qua `DEFAULT_DESTINATIONS`) sẽ đúng 10 lanes
  - `builder.py` KHÔNG đọc YAML — vẫn fallback 9 lanes cũ nếu caller pass empty
  - Hậu quả: code path khác nhau → 10 vs 9 lanes → inconsistent email
- **Current Code**:
```python
# builder.py:740-741
if not destinations:
    destinations = ["USLAX", "USLGB", "USSAV", "USNYC", "USORF", "USCHS", "USTIW", "USCHI", "USDAL"]
```
- **Suggested Fix**:
```python
# Ở đầu module builder.py
def _load_default_destinations() -> list[str]:
    """Load fast_bulk_default từ default_routes.yaml — SOT duy nhất."""
    try:
        import yaml
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / "config" / "default_routes.yaml"
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        dests = data.get("fast_bulk_default") or []
        cleaned = [str(d).strip().upper() for d in dests if str(d).strip()]
        if cleaned:
            return cleaned
    except Exception as e:
        log.warning(f"[builder] default_routes.yaml load failed ({e})")
    # Last-resort safe fallback
    return ["USLAX", "USLGB", "USSAV", "USNYC", "USORF", "USCHS", "USTIW", "USCHI", "USDAL"]

_DEFAULT_DESTINATIONS = _load_default_destinations()

# Trong build_email():
if not destinations:
    destinations = list(_DEFAULT_DESTINATIONS)
```
**Đồng thời xóa** hardcoded list `_FALLBACK_DESTINATIONS` ở `web_server.py:1873` → chỉ load từ YAML (có thể giữ 1 safe fallback nhỏ 3 lanes `[USLAX, USSAV, USNYC]` cho trường hợp YAML hỏng).

---

#### 2. Path A (`/api/prospects`) KHÔNG merge DEFAULT_DESTINATIONS khi CNEE có 1 POD → vi phạm yêu cầu Nelson

- **File**: `email_engine/web_server.py`
- **Line**: 1522-1533
- **Description**: Đây chính là bug Nelson nêu — "nếu khách chỉ có 1 POD thì nên gửi kèm thêm". Path A chỉ merge với DEFAULT khi `pod_list` RỖNG (line 1533). Nếu CNEE có 1 POD (hoặc nhiều POD nhưng không đủ), chỉ pick `pod_list[0]` và KHÔNG mở rộng → khách không thấy lane khác → mất cơ hội cross-sell. Trong khi đó Path B (`/api/bulk/build`:2104-2121) đã implement merge đúng từ 2026-04-19 ("khoe thêm chút").
- **Current Code**:
```python
# web_server.py:1522-1533
row_dest_raw = str(row.get("DESTINATION", "")).strip()
if row_dest_raw.lower() in ("", "nan", "none"):
    row_dest_raw = ""
pod_list = [d.strip().upper() for d in row_dest_raw.replace(";", ",").split(",")
            if d.strip() and d.strip().lower() not in ("nan", "none")]
if requested_dest and requested_dest in pod_list:
    pod = requested_dest
elif pod_list:
    pod = pod_list[0]
else:
    pod = requested_dest or "USLAX"
    pod_list = DEFAULT_DESTINATIONS.copy()  # chỉ merge khi pod_list rỗng
```
- **Suggested Fix** (copy strategy từ Path B):
```python
# Merge strategy: known POD(s) first, then DEFAULT_DESTINATIONS deduplicated
row_dest_raw = str(row.get("DESTINATION", "")).strip()
known_pods = _normalize_dest_text(row_dest_raw)  # dùng helper có sẵn để handle text Panjiva
merged: list[str] = []
for d in known_pods + list(DEFAULT_DESTINATIONS):
    du = d.upper()
    if du and du not in merged:
        merged.append(du)
pod_list = merged
# Primary POD = requested_dest > known[0] > first default
if requested_dest and requested_dest in pod_list:
    pod = requested_dest
elif known_pods:
    pod = known_pods[0]
else:
    pod = pod_list[0] if pod_list else "USLAX"
```
**Note**: Thay `.split(",")` bằng `_normalize_dest_text()` để reuse logic parse Panjiva text (ví dụ: "The Port of Los Angeles" → USLAX).

---

#### 3. `max_destinations_per_email: 5` trong YAML KHÔNG được enforce

- **File**: `email_engine/config/default_routes.yaml:31`
- **Line**: 31
- **Description**: Grep toàn codebase — chỉ xuất hiện 1 lần duy nhất trong chính YAML này. Không có code nào đọc hoặc enforce giới hạn. Điều này có nghĩa:
  - Comment "keep body readable" trong YAML đang misleading — thực tế email có thể có 9 (hiện tại) hoặc 10 (đề xuất Nelson) hoặc hơn.
  - Nếu caller pass 20 destinations — builder sẽ render 20 rows, không có safeguard.
  - UX concern: 10 rows = email table dài ~600px, trên mobile client sẽ scroll nhiều.
- **Current Code**: (YAML config không được đọc)
- **Suggested Fix** (2 options — em khuyến nghị Option A):

**Option A — Enforce limit trong `build_email()`:**
```python
# builder.py sau khi destinations đã normalize
MAX_DESTS = _load_max_destinations()  # from YAML, default 10
if len(destinations) > MAX_DESTS:
    log.info(f"[builder] truncating destinations {len(destinations)}→{MAX_DESTS}")
    destinations = destinations[:MAX_DESTS]
```

**Option B — Xóa config "chết" nếu không muốn enforce:**
Xóa dòng `max_destinations_per_email: 5` khỏi YAML để tránh misleading.

**Nelson's ask 10 lanes** → Option A + set `max_destinations_per_email: 10` trong YAML.

---

#### 4. Template match tie-break non-deterministic với 10 lanes mix US+Canada

- **File**: `email_engine/intelligence/template_selector.py:159-190`, `email_engine/templates/email_rules.yaml`
- **Line**: `_score_template()` logic
- **Description**: Khi destinations = 10 lanes `[LAX, OAK, TAC, SAV, NYC, MIA, HOU, CHI, DAL, CAVAN]`, thuật toán scoring hiện tại:
  - `west_coast` template (dests=[USLAX,USLGB,USOAK,USSEA]) → dest_match=True (có LAX+OAK) → score=3
  - `east_coast` template (dests=[USNYC,USSAV,...]) → dest_match=True → score=3
  - `canada` template (dests=[CAVAN,CATOR,...]) → dest_match=True (có CAVAN) → score=3
  - `inland` template (dests=[USCHI,USDAL,...]) → dest_match=True → score=3
  - `default` → score=1
  - **Tất cả 4 templates đều có score=3** → code `if best is None or score > best[0]` chọn CÁI ĐẦU TIÊN → phụ thuộc thứ tự trong YAML = non-deterministic khi refactor.
- **Current Code**:
```python
# template_selector.py:178-181
for tmpl in templates:
    ...
    score, reason = scored
    if best is None or score > best[0]:  # strict >, tie-break = first-come
        best = (score, reason, tmpl)
```
- **Suggested Fix** (2 options):

**Option A — Tie-break by match count (recommend):**
```python
def _score_template(tmpl, destinations, states):
    ...
    # Count matches để tie-break
    match_count = sum(1 for d in dests_u if d in tmpl_dests)
    return (score, match_count, reason)

# Trong match():
if best is None or (score, count) > (best[0], best[1]):
    best = (score, count, reason, tmpl)
```

**Option B — Thêm template "default_all_us_canada"** cho case 10-lane mix:
Thêm template mới trong `email_rules.yaml`:
```yaml
- id: default_cross_sell
  match:
    destinations: [USLAX, USOAK, USTIW, USSAV, USNYC, USMIA, USHOU, USCHI, USDAL, CAVAN]
    states: [any]
  subject: "Ocean Freight Update — Asia to USA/Canada | Week {{week}} | {{suffix}}"
  intro: |
    Dear {{first_name}},

    Please find our latest ocean freight rates covering our main
    US and Canada corridors. Rates valid through end of the month.
  cta: |
    Please confirm booking 7 days before ETD.
    Reply with your specific lane for a detailed quote.
```
Đặt template này ở **đầu list** (trước west_coast) — sẽ match 10/10 lanes → score cao nhất nếu tie-break bằng count.

---

### 🟡 TRUNG (Medium Priority)

#### 5. CAVAN trong 10 lanes — `auto_rate_builder` có support nhưng rate table có thể trống

- **File**: `email_engine/core/auto_rate_builder.py:54,360,806`
- **Description**: Code đã có CAVAN mapping (`CAVAN → VAN`) trong 3 chỗ — tức auto_rate_builder support được. NHƯNG:
  - Nếu parquet không có rate Canada cho POL=HPH → `rate_by_dest[CAVAN] = []`
  - Builder fallback sang `market_engine.analyze_lane()` (đã được flag là inflated ở comment line 744-746)
  - → Row CAVAN trong email có thể hiện `N/A` hoặc giá sai
- **Suggested Fix**:
  - Trước khi enable CAVAN trong default list, chạy smoke test:
    ```python
    from auto_rate_builder import build_rate_table_for_customer
    result = build_rate_table_for_customer(pol="HPH", destinations="CAVAN", markup=20)
    print(result["rates_found"], result["rates"])
    ```
  - Nếu không có rate → cần backfill parquet trước HOẶC exclude CAVAN khỏi default (giữ 9 US lanes).

---

#### 6. `by_campaign` (20 campaigns) và `by_country`/`regions` trong YAML là dead config

- **File**: `email_engine/config/default_routes.yaml:37-77`
- **Description**: YAML claim "Precedence: explicit > by_campaign > by_country > global_default" — nhưng grep codebase cho thấy chỉ `fast_bulk_default` và `global_default` được đọc ở `web_server.py:1883`. Các key còn lại (`by_campaign`, `by_pol`, `by_country`, `regions`, `forbidden_ports`) KHÔNG có code nào load.
- **Impact**: YAML là "lời hứa" không được giữ. Nelson tưởng sửa FURNITURE campaign trong YAML sẽ thay đổi email, nhưng thực tế không. Nếu có developer mới đọc YAML thì sẽ hiểu sai architecture.
- **Suggested Fix** (3 options):
  - **A (clean):** Xóa các section chưa implement khỏi YAML, chỉ giữ `fast_bulk_default` + `global_default`.
  - **B (implement):** Code thêm logic precedence khi build prospects — đọc row.CAMPAIGN_ID → lookup `by_campaign[campaign]` nếu có.
  - **C (defer):** Thêm comment `# TODO: not yet wired — see plans/...` ở đầu các section dead config để trung thực.

Nelson quyết định: với 10-lane strategy, Option A (xóa) là hợp lý — vì mỗi CNEE đều nhận 10 default, không cần campaign override.

---

#### 7. 2 code path (Path A prospects vs Path B build) không đồng nhất chiến lược merge

- **File**: `email_engine/web_server.py:1522-1534` (Path A) vs `email_engine/web_server.py:2104-2121` (Path B)
- **Description**: Path B (bulk build email) có MERGE strategy với comment chi tiết từ 2026-04-19. Path A (prospects list hiển thị dashboard) KHÔNG có. Nghĩa là:
  - Khi user xem dashboard "Quick Send Prospects" → chỉ thấy 1 POD per CNEE
  - Khi user click "Build Email" → email có 9 lanes
  - → Preview (dashboard) ≠ thực tế email → user confused
- **Suggested Fix**:
  - Extract helper function `_resolve_destinations(row_dest, requested_dest, requested_dests, defaults)` return `(primary_pod, full_pod_list, known_pods)`.
  - Call từ cả 2 paths → đảm bảo behavior nhất quán.

---

#### 8. `/api/rate-preview` không có fallback DEFAULT_DESTINATIONS

- **File**: `email_engine/web_server.py:557-567`
- **Description**: Endpoint nhận `destinations` làm query param bắt buộc — nếu client pass empty hoặc bỏ qua → `auto_rate_builder` nhận empty string. Không có safety net.
- **Current Code**:
```python
@app.get("/api/rate-preview")
def rate_preview(pol: str, destinations: str, markup: float = 20.0, arb_origin: str = None):
    from auto_rate_builder import build_rate_table_for_customer
    try:
        return build_rate_table_for_customer(
            pol=pol, destinations=destinations, markup=markup,
            arb_origin=arb_origin or None,
        )
```
- **Suggested Fix**:
```python
@app.get("/api/rate-preview")
def rate_preview(pol: str, destinations: str = "", markup: float = 20.0, arb_origin: str = None):
    from auto_rate_builder import build_rate_table_for_customer
    dests = [d.strip().upper() for d in (destinations or "").replace(";", ",").split(",") if d.strip()]
    if not dests:
        dests = list(DEFAULT_DESTINATIONS)  # 10-lane fallback cho preview cross-sell
    try:
        return build_rate_table_for_customer(
            pol=pol, destinations=",".join(dests), markup=markup,
            arb_origin=arb_origin or None,
        )
    except Exception as e:
        log.warning(f"Rate preview failed: {e}")
        return {"routes_found": 0, "total_rates": 0, "html": "", "routes_detail": []}
```

---

#### 9. `_normalize_dest_text()` silent fail khi không parse được

- **File**: `email_engine/web_server.py:310-344`
- **Description**: Hàm trả `[]` khi không match city keyword nào → không có log warning → developer không biết Panjiva text format mới nào đang fail. VD: "Vancouver, BC, Canada" nếu "VANCOUVER" không trong `_CITY_TO_POD` sẽ silently return [].
- **Suggested Fix**:
```python
def _normalize_dest_text(text: str) -> list[str]:
    ...
    for part in parts:
        ...
        if not code:
            log.debug(f"[_normalize_dest_text] unparsed token: {token!r}")
            continue
        ...
    if str(text).strip() and not out:
        log.info(f"[_normalize_dest_text] entire text unparsed: {text[:80]!r}")
    return out
```
Log level `debug` cho per-token, `info` cho toàn dòng fail → giúp debug import Panjiva.

---

### 🟢 THẤP (Low Priority)

#### 10. Duplicated destination-parsing logic giữa 2 paths

- **File**: `web_server.py:1522-1534` và `web_server.py:2104-2121`
- **Description**: Cùng 1 pattern (parse row.DESTINATION + merge với default) nhưng implement khác nhau. DRY violation.
- **Suggested Fix**: Extract `_resolve_destinations()` helper (xem issue #7).

---

#### 11. Thiếu test cho lane selection logic

- **File**: `email_engine/tests/` (không có `test_lane_resolution.py`)
- **Description**: Logic fallback/merge/normalize chưa có unit test. Regression sẽ xảy ra khi refactor.
- **Suggested Fix**: Thêm `email_engine/tests/test_lane_resolution.py`:
```python
def test_empty_destination_returns_default():
    assert _resolve_destinations("", "", [], DEFAULT) == ("USLAX", DEFAULT, [])

def test_single_pod_merges_with_default():
    result = _resolve_destinations("USSEA", "", [], DEFAULT)
    assert result[0] == "USSEA"
    assert "USSEA" in result[1]
    assert len(result[1]) == len(DEFAULT) + 1  # known + all defaults

def test_panjiva_text_parsing():
    assert _normalize_dest_text("The Port of Los Angeles") == ["USLAX"]
    assert _normalize_dest_text("New York/Newark Area, NJ") == ["USNYC"]
    assert _normalize_dest_text("nan") == []
```

---

#### 12. UX concern — email 10-row table có thể quá dài

- **File**: `email_engine/templates/rate_table.html` (table render)
- **Description**: 10 rows × ~40px = 400px table + header/footer + signature ≈ 700-800px email body. Mobile view phải scroll nhiều.
- **Suggested Fix** (UX optional — không phải code bug):
  - **Option A**: Group rows theo region — sub-header "West Coast" / "East Coast" / "Gulf" / "Inland" / "Canada" — mỗi group 2-3 rows. Dễ scan.
  - **Option B**: Highlight CNEE's known lane ở top với `background:#fef3c7` và badge "Your Lane", còn lại 9 lanes gọn hơn (font 12px).
  - **Option C**: Giữ 10 rows flat — đơn giản nhất, Nelson test A/B với khách hàng xem phản hồi thế nào.

Em khuyến nghị **Option B** — tôn trọng POD đã biết của khách + vẫn show breadth.

---

## Recommendations

### Lộ trình fix đề xuất (ưu tiên theo severity)

**Phase 1 — Sync sources (30 phút):**
1. Sửa YAML `fast_bulk_default` thành 10 lanes mới
2. Xoá hardcoded fallback ở `builder.py:741` → load từ YAML
3. Giảm hardcoded ở `web_server.py:1873` còn 3 lanes safe
4. Test: restart server → log phải show `DEFAULT_DESTINATIONS loaded from YAML: 10 lanes`

**Phase 2 — Merge path A (1h):**
5. Extract `_resolve_destinations()` helper
6. Update `web_server.py:1522-1534` (Path A prospects) — dùng MERGE strategy như Path B
7. Test: dashboard prospects → xem `destinations_all` field có đủ 10 lanes không

**Phase 3 — Template + CAVAN (1h):**
8. Smoke test CAVAN rate availability trong parquet
9. Nếu OK → thêm template `default_cross_sell` ở đầu `email_rules.yaml` (match 10 lanes + any state)
10. Hoặc cập nhật scoring tie-break trong `template_selector.py`

**Phase 4 — Enforce limit + cleanup (30 phút):**
11. Enforce `max_destinations_per_email` trong `build_email()`
12. Xóa dead config (`by_campaign`, `by_country`, `regions`) khỏi YAML — hoặc thêm TODO comment

**Phase 5 — Tests + UX (1h):**
13. Thêm `test_lane_resolution.py`
14. A/B test email 10-row flat vs grouped-by-region với 5-10 CNEE

**Total: ~4h** cho toàn bộ fix + verify.

### Quyết định cần Nelson xác nhận trước khi fix

**A. Chốt 10 lanes chuẩn** — em đề xuất mapping port codes:
```yaml
fast_bulk_default: [USLAX, USOAK, USTIW, USSAV, USNYC, USMIA, USHOU, USCHI, USDAL, CAVAN]
```
Từ Nelson: `SAV/NYC/HOU/CHICAGO/DALLAS/MIAMI/LAX/OAK/TACOMA/VAN` → mapping tương ứng:
- SAV = USSAV, NYC = USNYC, HOU = USHOU, CHICAGO = USCHI, DALLAS = USDAL, MIAMI = USMIA, LAX = USLAX, OAK = USOAK, TACOMA = USTIW, VAN = CAVAN

**B. CAVAN (Canada) trong default list** — 2 options:
- Option A: Giữ CAVAN (cross-sell Canada khách US) — cần verify có rate Canada trong parquet
- Option B: Tách thành `fast_bulk_default_us` (9 lanes) và `fast_bulk_default_canada` (CAVAN+CAMTR+CATOR), chọn list theo CNEE.COUNTRY

**C. Template strategy** — 2 options:
- Option A: Thêm template mới `default_cross_sell` match 10 lanes (đơn giản, giữ west/east/canada cho rare case)
- Option B: Sửa scoring tie-break by match count (tinh vi hơn, deterministic)

**D. Max rows per email** — 10 hay fewer?
- Option A: Enforce 10 (theo Nelson)
- Option B: Enforce 5-7 và group by region (đẹp UX hơn)

---

## Files Analyzed

- `email_engine/config/default_routes.yaml` (77 lines) ✓
- `email_engine/intelligence/builder.py` (838 lines — focus lines 1-100, 700-838) ✓
- `email_engine/intelligence/template_selector.py` (238 lines) ✓
- `email_engine/templates/email_rules.yaml` (96 lines) ✓
- `email_engine/web_server.py` (3686 lines — focus lines 305-344, 557-567, 1490-1589, 1860-1892, 2045-2140, 2616-2633) ✓
- `email_engine/core/auto_rate_builder.py` (920 lines — grep only, CAVAN mapping confirmed) ✓

---

**Status:** DONE
**Summary:** 4 CRITICAL bugs + 5 MEDIUM + 3 LOW. Kiến trúc 3-tầng fragmented, Path A thiếu merge logic = đúng bug Nelson gặp. Đề xuất 4-phase fix ~4h.
**Output file:** `plans/reports/code-review-email-lanes-20260423.md`
