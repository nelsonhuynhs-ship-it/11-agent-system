# Code Review Report — Email Dashboard v7

**Date**: 2026-04-24
**Reviewer**: code-reviewer agent (claudekit workflow Phase 1)
**Scope**: Toàn bộ stack đang vận hành trên port 8100 sau khi commit 5d3ca15 (prewarm) + 7e61093 (paren+UI bundled)
**Files Reviewed**: 19 files (backend Python + frontend HTML + YAML configs)

## Summary

Hệ thống Email Dashboard v7 đang ổn định về mặt chức năng (Pool 22,482 CNEE, 700/700 rotation hôm qua PASS), nhưng có **1 bug CAO** đã được xác nhận gãy pipeline an toàn (`REPLY_STATUS` không bao giờ được ghi vào master → CNEE reply vẫn bị blast), cộng với nhiều vấn đề TRUNG/THẤP về concurrency (Excel race), CORS quá lỏng kết hợp `force=true` bypass preview-token, cache trùng lặp giữa `web_server._get_cnee_df` và `rotation_helpers.load_master_df`, silent-catch khắp frontend nuốt lỗi UI.

**Thống kê issue:**
- 🔴 CAO: **3**
- 🟡 TRUNG: **9**
- 🟢 THẤP: **7**

**Tổng 19 vấn đề cần review.** Trong đó 1 vấn đề CAO ảnh hưởng trực tiếp đến lời hứa "không spam khách đã reply" — phải fix trước khi chạy rotation tiếp theo.

---

## Issues Found

### 🔴 CAO (High Priority)

#### [CAO-1] `REPLY_STATUS` không bao giờ được ghi → người đã reply vẫn bị bulk blast
- **File**: `email_engine/scanner/handlers.py`
- **Line**: 437–476 (hàm `handle_real_reply`)
- **Description**:
  Khi khách reply (intent "general/rfq/booking"), scanner chỉ ghi `LAST_REPLY_AT/INTENT/SENTIMENT` + điều kiện `TIER/ACTION`. **KHÔNG có dòng nào set `REPLY_STATUS="HUMAN_REPLY"`**, trong khi:
  - `email_engine/core/priority_filter.py:21` định nghĩa `PRIORITY_REPLY_STATUS = frozenset({"HUMAN_REPLY"})`
  - `_get_eligible_candidates()` (rotation_helpers.py:170) gọi `drop_priority(cdf)` để loại reply khỏi bulk pool
  - Kết quả: bộ lọc đọc column trống → **không loại ai** → CNEE vừa reply "general" vẫn được đưa vào rotation ngày mai.

  Thêm nữa, `email_engine/intel/tier_engine.py:116` trả `writeback_fields={"REPLY_STATUS": "REPLIED"}` nhưng:
  - Giá trị "REPLIED" cũng sai (filter kỳ vọng "HUMAN_REPLY")
  - Scanner adapter (handlers.py:67–88 bundled logic) chỉ extract `new_tier` + `new_action`, **bỏ luôn `writeback_fields` dict** → giá trị dù có cũng không bao giờ chạy tới writeback queue.

- **Current Code** (`handlers.py:454-476`):
```python
_update_master(
    email,
    {
        "LAST_REPLY_AT": datetime.now(timezone.utc).isoformat(),
        "LAST_REPLY_INTENT": intent,
        "LAST_REPLY_SENTIMENT": sentiment,
        **({"TIER": decision["tier"]} if decision.get("tier") else {}),
        **({"ACTION": decision["action"]} if decision.get("action") else {}),
    },
)
```

- **Suggested Fix**:
```python
_update_master(
    email,
    {
        "REPLY_STATUS": "HUMAN_REPLY",                      # khớp priority_filter
        "LAST_REPLY_AT": datetime.now(timezone.utc).isoformat(),
        "LAST_REPLY_INTENT": intent,
        "LAST_REPLY_SENTIMENT": sentiment,
        **({"TIER": decision["tier"]} if decision.get("tier") else {}),
        **({"ACTION": decision["action"]} if decision.get("action") else {}),
    },
)
```
Song song cần sửa `intel/tier_engine.py:116` đổi `"REPLY_STATUS": "REPLIED"` → `"HUMAN_REPLY"` cho nhất quán, HOẶC xóa hẳn khỏi writeback_fields vì scanner adapter không dùng.

- **Impact**: Cao — vi phạm nguyên tắc "không blast khách đã reply" mà Nelson kể là một trong hai north-star (slogan YÊN TÂM). Kiểm chứng nhanh: `SELECT COUNT(*) FROM cnee WHERE LAST_REPLY_AT IS NOT NULL AND (REPLY_STATUS IS NULL OR REPLY_STATUS='')` — nếu > 0 là bằng chứng đã bỏ sót.

---

#### [CAO-2] `/api/rotation/run-today` có `force=true` bypass + CORS `.*` → CSRF khả thi
- **File**: `email_engine/api/routes/rotation_router.py`
- **Line**: 339–368
- **Description**:
  Endpoint này enqueue full rotation 700 emails vào Outlook. Normally yêu cầu `preview_token` (issued 10 min). **Nhưng có `force=true` escape hatch** để scheduler/CLI gọi. Kết hợp với `web_server.py:199-205`:
  ```python
  app.add_middleware(CORSMiddleware, allow_origin_regex=".*", allow_methods=["*"])
  ```
  → mọi trang web Nelson mở (coworker chia wifi, tab malicious, email phishing mở link) đều có thể gọi `POST http://localhost:8100/api/rotation/run-today {"force":true}` → 700 email gửi đi.

  Lý do `allow_origin_regex=".*"` là vì dashboard mở qua `file://` (Origin header null). OK về chức năng, không OK về bảo mật khi endpoint không có bất cứ auth nào.

- **Current Code** (`rotation_router.py:355-360`):
```python
if not force:
    if not token or not _consume_preview_token(token):
        raise HTTPException(400, detail="Preview required. ...")
```

- **Suggested Fix** (2 lớp):
  1. **Ràng buộc origin:** accept `force=true` CHỈ khi request đến từ localhost/127.0.0.1 HOẶC có shared secret:
```python
from fastapi import Request
def _check_force_auth(request: Request):
    client = request.client.host if request.client else ""
    if client not in ("127.0.0.1", "localhost", "::1"):
        raise HTTPException(403, "force=true only from localhost")

@router.post("/run-today")
def run_today(request: Request, background_tasks: BackgroundTasks,
              req: Optional[RunTodayRequest] = None) -> dict[str, Any]:
    ...
    if force:
        _check_force_auth(request)
    elif not token or not _consume_preview_token(token):
        raise HTTPException(400, detail="Preview required. ...")
```
  2. **Siết CORS:** đổi `allow_origin_regex=".*"` → giới hạn explicit:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "file://", "http://localhost:8100", "http://127.0.0.1:8100"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
```
  `"null"` cần thiết vì file:// có Origin "null".

- **Impact**: Cao nhất về tấn công surface — một request cross-site có thể flood 700 email/ngày, làm Outlook blacklist/throttle. Rủi ro thực tế thấp (Nelson dùng máy cá nhân) nhưng unacceptable cho production.

---

#### [CAO-3] `contacts_router.patch_contact` đọc+ghi xlsx không qua `xlsx_read_lock` → race condition với writeback flusher
- **File**: `email_engine/api/routes/contacts_router.py`
- **Line**: 281–322, 114–127 (`_save_to_xlsx`)
- **Description**:
  - Luồng 1: `writeback.py` flush 5 phút/lần (hoặc burst khi buffer ≥ 50) → đọc xlsx → patch → atomic `os.replace`.
  - Luồng 2: `contacts_router.patch_contact` PATCH inline edit → đọc xlsx (`pd.read_excel`) → sửa row → ghi lại (`_save_to_xlsx` ghi 2 sheet).
  - **Cả 2 không dùng `xlsx_read_lock`** (filelock đã có sẵn trong `core/xlsx_lock.py`, đang dùng ở `_get_cnee_df` + `rotation_helpers.load_master_df`).
  - Nelson Panjiva Import + Nelson PATCH một cell đồng thời → race: writeback đọc version A, user đọc version A, user ghi version A+patch, writeback ghi version A+writeback → **mất patch của user hoặc mất writeback**.

- **Current Code** (`contacts_router.py:113-127`):
```python
def _save_to_xlsx(sheet: str, df: pd.DataFrame) -> None:
    other_sheet = "SHIPPER" if sheet.upper() == "CNEE" else "CNEE"
    try:
        df_other = pd.read_excel(UNIFIED_V6, sheet_name=other_sheet)
    except Exception:
        df_other = pd.DataFrame()
    with pd.ExcelWriter(UNIFIED_V6, engine="openpyxl") as writer:
        ...
```

- **Suggested Fix**: bao toàn hàm `_save_to_xlsx` + đọc xlsx trong `patch_contact/create_contact/delete_contact` bằng `xlsx_read_lock`:
```python
def _save_to_xlsx(sheet: str, df: pd.DataFrame) -> None:
    from email_engine.core.xlsx_lock import xlsx_read_lock
    other_sheet = "SHIPPER" if sheet.upper() == "CNEE" else "CNEE"
    with xlsx_read_lock(UNIFIED_V6):  # exclusive for writes — lock module hỗ trợ
        try:
            df_other = pd.read_excel(UNIFIED_V6, sheet_name=other_sheet)
        except Exception:
            df_other = pd.DataFrame()
        tmp = UNIFIED_V6.with_suffix(".xlsx.tmp")
        with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
            if sheet.upper() == "CNEE":
                df.to_excel(writer, sheet_name="CNEE", index=False)
                df_other.to_excel(writer, sheet_name="SHIPPER", index=False)
            else:
                df_other.to_excel(writer, sheet_name="CNEE", index=False)
                df.to_excel(writer, sheet_name="SHIPPER", index=False)
        import os
        os.replace(tmp, UNIFIED_V6)  # atomic
```
Ngoài ra `writeback.py:207` cũng nên lock (hiện chỉ dùng `_is_locked` best-effort → không phải exclusive giữa các process Python).

- **Impact**: Cao — nguy cơ mất dữ liệu (PATCH biến mất, hoặc corrupt xlsx). Không xảy ra thường xuyên (Nelson ít edit inline lúc writeback flush) nhưng là bug đúng nghĩa "race" — khi xảy ra thì khó debug.

---

### 🟡 TRUNG (Medium Priority)

#### [TRUNG-1] `tier_engine.writeback_fields` bị scanner adapter bỏ qua hoàn toàn
- **File**: `email_engine/intel/tier_engine.py:116` + scanner adapter (handlers.py block tích hợp dev-intel)
- **Description**: Dev-intel return value bao gồm `writeback_fields: dict` nhưng handlers.py chỉ đọc `new_tier` và `new_action`. Tất cả field khác (REPLY_STATUS, RISK_SCORE, INTENT_CONFIDENCE, v.v.) mất trắng.
- **Suggested Fix**: trong adapter, merge `writeback_fields` vào payload `_update_master` thay vì drop.
- **Note**: Cùng nguồn với CAO-1 nhưng scope rộng hơn (ảnh hưởng mọi field intel tạo ra, không chỉ REPLY_STATUS).

#### [TRUNG-2] Circular import: `rotation_engine` → `web_server.DEFAULT_DESTINATIONS`
- **File**: `email_engine/core/rotation_engine.py`
- **Line**: 264–268
- **Description**:
```python
try:
    from email_engine.web_server import DEFAULT_DESTINATIONS
except Exception:
    DEFAULT_DESTINATIONS = ["USLAX", "USSAV", "USNYC"]
```
Core → web_server là đảo ngược layer. Khi core được import trước web_server (unit test, CLI script) thì fallback 3-lane kích hoạt → plan quality giảm ngầm mà không log cảnh báo.
- **Suggested Fix**: move `DEFAULT_DESTINATIONS` vào `email_engine/core/config_loader.py` (đọc từ `default_routes.yaml`), cả web_server và rotation_engine import từ core. Pattern đã có sẵn ở `intelligence/builder.py:36 _load_routing_config()` — tái sử dụng.

#### [TRUNG-3] `_compute_cycle_info` chia cho 0 fragile (dấu cộng 0.001)
- **File**: `email_engine/core/rotation_helpers.py:215`
- **Description**:
```python
week_in_cycle = max(1, int(weeks_elapsed % (remaining / emails_per_week + 0.001)) + 1) if emails_per_week > 0 else 1
```
`remaining / emails_per_week + 0.001` là hack tránh ZeroDivisionError. Khi remaining=0 (chu kỳ xong), công thức cho giá trị vô nghĩa.
- **Suggested Fix**:
```python
if remaining <= 0 or emails_per_week <= 0:
    week_in_cycle = 1
else:
    weeks_per_cycle = max(remaining / emails_per_week, 1.0)
    week_in_cycle = max(1, int(weeks_elapsed % weeks_per_cycle) + 1)
```

#### [TRUNG-4] Dashboard silent-catch nuốt lỗi ở 9+ vị trí
- **File**: `plans/visuals/email-dashboard.html`
- **Line**: 1759, 1761, 2055, 2056, 3219, 3220, 3456, 4357, 5090 (loadSendTimeHint, history/stats, opens feed, email-events/alerts, KB summary, contacts badge, random fetch)
- **Description**: Pattern `.catch(() => {})` và `} catch(_) {}` ở rất nhiều widget. Khi API đổi shape / 500 → UI hiển thị empty state "Loading..." hoặc số 0 mà không toast error → Nelson không biết gì đang fail.
- **Suggested Fix**: centralize error handling:
```js
const silentCatch = (widget) => (err) => {
  console.warn(`[${widget}]`, err);
  try { toast(`${widget} unavailable`, 'warn', 3000); } catch {}
};
// usage: loadSendTimeHint().catch(silentCatch('send-time-hint'));
```
Tối thiểu log console — không để error vô hình.

#### [TRUNG-5] `contacts_router` hardcode path `D:/OneDrive/NelsonData/email` → không dùng `shared.paths`
- **File**: `email_engine/api/routes/contacts_router.py:23`
- **Description**:
```python
_ONEDRIVE = Path("D:/OneDrive/NelsonData/email")
```
Các module khác (rotation_helpers, writeback) dùng `shared.paths.EMAIL_DATA` để auto-detect PC Home (`C:/Users/ADMIN/`) vs Laptop VP (`D:/`). Router này không auto-detect → khi chạy trên PC Home fail.
- **Suggested Fix**:
```python
from shared.paths import EMAIL_DATA
_ONEDRIVE = Path(EMAIL_DATA)
```

#### [TRUNG-6] Hai cache CNEE song song (web_server + rotation_helpers) — drift nguy hiểm
- **File**: `email_engine/web_server.py:1477 (_CNEE_CACHE)` + `email_engine/core/rotation_helpers.py:76 (_MASTER_CACHE)`
- **Description**:
  - `web_server._get_cnee_df()` cache theo `(path, mtime)` — load từ v7/v6/v5/v1 fallback chain.
  - `rotation_helpers.load_master_df()` cache theo mtime — load từ v7/v6.
  Hai cache độc lập, có thể phục vụ 2 version DataFrame khác nhau nếu một bên chưa invalidate. Ví dụ: xlsx vừa mới ghi → rotation gọi build_daily_plan dùng `load_master_df`, dashboard gọi `/api/prospects` dùng `_get_cnee_df` → mtime đồng bộ nhưng race điều kiện vẫn có thể cho ra khác nhau nếu một bên cache kịp.
- **Suggested Fix**: hợp nhất thành `email_engine/core/cnee_cache.py` — 1 cache đơn dùng `xlsx_read_lock` + mtime, export cho cả web_server và rotation_helpers.

#### [TRUNG-7] `_JOBS` và `_PREVIEW_TOKENS` dict grow unbounded
- **File**: `email_engine/api/routes/sent_scan_router.py:32` + `rotation_router.py:465`
- **Description**:
  - `_JOBS` (sent_scan) giữ mọi job forever → sau 3 tháng mỗi 30 min scan → 4,320 key. Memory leak nhẹ.
  - `_PREVIEW_TOKENS` cleanup chỉ khi có ai gọi `_issue_preview_token` mới → nếu Nelson preview rồi confirm ngay → dict stale forever.
- **Suggested Fix**: thêm LRU cap (maxsize 100) hoặc purge tại `get_status` nếu > 200 entries.

#### [TRUNG-8] `xlsx_read_lock` fallback silent (web_server.py:1510-1521) — khi filelock miss, concurrent read vẫn xảy ra
- **File**: `email_engine/web_server.py:1509-1521`
- **Description**:
```python
try:
    from email_engine.core.xlsx_lock import xlsx_read_lock
    with xlsx_read_lock(cnee_src):
        df = pd.read_excel(cnee_src, ...)
except Exception:
    # Fallback without lock if filelock unavailable
    df = pd.read_excel(cnee_src, ...)
```
`except Exception` quá rộng — bao luôn FileNotFoundError, PermissionError, cả lỗi parse Excel. Khi bất kỳ lỗi gì xảy ra trong `with` block → fallback no-lock read → có thể đọc xlsx trong lúc Nelson đang save file (corrupt data).
- **Suggested Fix**: chỉ fallback khi ImportError:
```python
try:
    from email_engine.core.xlsx_lock import xlsx_read_lock
    has_lock = True
except ImportError:
    has_lock = False

if has_lock:
    with xlsx_read_lock(cnee_src):
        df = pd.read_excel(cnee_src, ...)
else:
    df = pd.read_excel(cnee_src, ...)
```

#### [TRUNG-9] `auto_rate_builder` sys.path.insert tại runtime (per request) trong `builder.py:794`
- **File**: `email_engine/intelligence/builder.py:792-796`
- **Description**:
```python
try:
    import sys
    if str(Path(__file__).resolve().parent.parent / "core") not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))
    from auto_rate_builder import build_rate_table_for_customer
```
Modifying `sys.path` tại mỗi lần build_email là code smell — chạy đúng nhưng fragile (thứ tự import phụ thuộc runtime state). Mỗi email gửi là 1 lần push path.
- **Suggested Fix**: import theo dotted package:
```python
from email_engine.core.auto_rate_builder import build_rate_table_for_customer
```
(module đã có trong package). Remove sys.path hack.

---

### 🟢 THẤP (Low Priority)

#### [THẤP-1] Variable naming drift: `UNIFIED_V6` trỏ đến `contact_unified_v7.xlsx`
- **File**: `email_engine/api/routes/contacts_router.py:27`
- **Description**: `UNIFIED_V6 = _V7 if _V7.exists() else _V6` — tên biến còn `V6` sau khi đã migrate. Gây confusion cho reviewer mới. Chuỗi "v6" xuất hiện trong 10+ log message / API prefix `/api/v6/contacts`.
- **Suggested Fix**: rename → `UNIFIED_MASTER`, endpoint prefix đổi `/api/contacts` (hoặc giữ alias v6 cho backward compat 1 sprint).

#### [THẤP-2] `smart_send_window` pytz fallback — pytz có trong requirements?
- **File**: `email_engine/core/smart_send_window.py:62-71`
- **Description**: Python 3.9+ luôn có zoneinfo, fallback pytz là dead code. Gỡ cho gọn.
- **Suggested Fix**: xóa try/except ImportError zoneinfo — chỉ dùng zoneinfo.

#### [THẤP-3] `contacts_router` dummy table khởi tạo bằng `WHERE FALSE`
- **File**: `contacts_router.py:60-61`
- **Description**:
```python
_con.execute("CREATE TABLE IF NOT EXISTS cnee AS SELECT 1 AS dummy WHERE FALSE")
```
Nếu xlsx tạm thời missing (OneDrive sync lag) → dummy table được tạo → mọi query sau đó dùng `SELECT COUNT(*) FROM cnee` = 0. Dashboard hiển thị "0 contacts" mà không raise → Nelson nghĩ data mất. Tốt hơn: raise 503 để UI toast "OneDrive chưa sync".

#### [THẤP-4] `subprocess.run(migrate_script, timeout=120)` thiếu `shell=False` explicit (đã False default nhưng nên thêm cho clarity)
- **File**: `contacts_router.py:405`, `sent_scan_router.py:62`
- **Description**: cmd list được pass directly nên không có shell injection — nhưng code review dễ hiểu lầm. Comment 1 dòng giải thích `# shell=False implicit — cmd is list` giúp reviewer tương lai.

#### [THẤP-5] `booking_pool_writer._is_duplicate` đọc 100 dòng cuối mỗi lần append
- **File**: `email_engine/core/booking_pool_writer.py:90-103`
- **Description**: Không scale — nếu JSONL đến 10k dòng vẫn OK, nhưng nếu lên 1M dòng mỗi ngày có O(n) read. Hiện chưa phải vấn đề vì booking event ít (~10/day). Ghi chú cho future.

#### [THẤP-6] `outlook_queue_worker` log tracking pixel URL mặc định `localhost:8100`
- **File**: `email_engine/outlook_queue_worker.py:62-65`
- **Description**: Pixel `<img src="http://localhost:8100/t/o/{id}.gif">` gửi ra email recipient. Recipient mở email trên Gmail/Outlook cloud → pixel KHÔNG reach localhost → **open tracking không hoạt động trong production**. Log hiện đã comment warning nhưng nên fail-loud khi `NELSON_TRACK_BASE_URL` không set.
- **Suggested Fix**:
```python
if TRACK_BASE_URL in ("http://localhost:8100", "http://127.0.0.1:8100"):
    log.warning("TRACK_BASE_URL is localhost — open tracking disabled for external recipients. Set NELSON_TRACK_BASE_URL=http://14.225.207.145:8100 for VPS.")
```

#### [THẤP-7] `template_selector._shape_template` expose `_raw` với underscore prefix nhưng vẫn return trong dict
- **File**: `email_engine/intelligence/template_selector.py:209`
- **Description**: `_raw: raw` rò rỉ internal structure. Caller không nên depend trên `_raw`. Remove hoặc đổi tên public.

---

## Recommendations

### Ưu tiên xử lý (theo rủi ro runtime)

1. **CAO-1 trước tiên**: fix REPLY_STATUS trong 1 edit (handlers.py thêm 1 dòng) — làm ngay, test: reply 1 email test → scan → grep `REPLY_STATUS` xuất hiện trong xlsx.
2. **CAO-3**: lock xlsx trong contacts_router + writeback trước khi Nelson dùng Panjiva Import ngày nào.
3. **CAO-2**: siết CORS + force-auth — làm trước khi dashboard mở public link nào.
4. **TRUNG-2 + TRUNG-6**: refactor gom DEFAULT_DESTINATIONS + CNEE cache về core — làm chung cùng sprint.

### Đề xuất kiến trúc
- **Tạo `email_engine/core/cnee_cache.py`** duy nhất — xóa 2 implementation song song (web_server + rotation_helpers). Centralize `xlsx_read_lock` + mtime invalidation + v7→v6→v5 fallback.
- **Tạo `email_engine/core/config_loader.py`** — load `default_routes.yaml`, `rotation_quota.json`, `email_rules.yaml` một chỗ với hot-reload mtime (pattern `template_selector._cache` là good example).
- **Centralize frontend error handling**: 1 hàm `silentCatch(widget_name)` thay mọi `.catch(() => {})` — dashboard 5,097 lines có 9 vị trí silent-catch rải rác.

### Test cần viết (chuyển sang phase test-writer)
- Unit test: `handle_real_reply("customer@x.com", "general")` → assert xlsx có `REPLY_STATUS="HUMAN_REPLY"`.
- Integration test: run `/api/rotation/run-today force=true` từ IP khác 127.0.0.1 → phải 403.
- Concurrent test: `patch_contact` + `writeback.flush()` gọi song song 100 lần → không corrupt xlsx, không mất update.

---

## Files Analyzed

Backend Python (14 files):
- `email_engine/web_server.py` (3,802 lines)
- `email_engine/outlook_queue_worker.py` (352 lines)
- `email_engine/scanner/handlers.py` (reviewed priority sections)
- `email_engine/core/rotation_engine.py` (365 lines)
- `email_engine/core/rotation_helpers.py` (233 lines)
- `email_engine/core/priority_filter.py`
- `email_engine/core/rule_engine.py` (277 lines)
- `email_engine/core/typo_shield.py` (131 lines)
- `email_engine/core/smart_send_window.py` (194 lines)
- `email_engine/core/booking_pool_writer.py` (263 lines)
- `email_engine/core/auto_rate_builder.py` (head 120 lines — full quét grep)
- `email_engine/core/cnee_schema_adapter.py` (61 lines)
- `email_engine/intelligence/builder.py` (895 lines)
- `email_engine/intelligence/template_selector.py` (245 lines)
- `email_engine/intel/writeback.py` (295 lines)
- `email_engine/intel/tier_engine.py` (priority sections)
- `email_engine/api/routes/rotation_router.py` (741 lines)
- `email_engine/api/routes/contacts_router.py` (566 lines)
- `email_engine/api/routes/sent_scan_router.py` (218 lines)

Frontend (1 file):
- `plans/visuals/email-dashboard.html` (5,097 lines — grep silent-catch)

Config:
- `email_engine/config/default_routes.yaml` (inferred from builder loader)
- `email_engine/templates/email_rules.yaml` (inferred from template_selector)

---

**Status:** DONE_WITH_CONCERNS
**Summary:** 1 bug CAO đã xác nhận ảnh hưởng safety pipeline (REPLY_STATUS không ghi → bulk blast người đã reply). 2 CAO khác về CORS + xlsx race. Tổng 19 issues — cần Nelson confirm trước khi master-executor apply fix.
**Concerns:** CAO-1 nên fix NGAY trong hotfix riêng trước khi chạy rotation ngày mai. CAO-2/CAO-3 làm trong sprint cleanup tiếp theo.
