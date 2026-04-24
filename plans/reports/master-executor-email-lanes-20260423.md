# Master-Executor Report — Email Dashboard Lane/POD Fix

**Date**: 2026-04-23
**Agent**: master-executor
**Reports processed**: `plans/reports/code-review-email-lanes-20260423.md`
**Scope**: Email dashboard lane/POD selection — 10-lane cross-sell default (Nelson Option A)

---

## Tóm tắt

- ✅ **Đã thực hiện**: 11 issues (4 CAO + 5 TRUNG + 2 THẤP)
- ⏭️ **Bỏ qua**: 2 (YAML dead-config cleanup — defer; stale tests — pre-existing)
- ⚠️ **Cần review**: 1 (OneDrive YAML SOT đã update — Nelson cần verify local OneDrive sync sau khi restart)

**Nelson's 4 confirmed decisions** (tất cả Option A) đều đã thực thi:
- A. 10 lanes: `[USLAX, USOAK, USTIW, USSAV, USNYC, USMIA, USHOU, USCHI, USDAL, CAVAN]`
- B. CAVAN included (smoke test PASS — 5 rates, ONE $2204, YML $2556)
- C. Template `default_cross_sell` thêm ở TOP `email_rules.yaml`
- D. `max_destinations_per_email: 10` enforced trong builder

---

## Phase Execution

### Phase 1 — Sync Sources ✅

**Files changed:**
- `email_engine/config/default_routes.yaml` — `fast_bulk_default` (9→10 lanes), `max_destinations_per_email` (5→10)
- `D:/OneDrive/NelsonData/email/config/default_routes.yaml` — **SOT THỰC SỰ**, đã sync cùng giá trị
- `email_engine/intelligence/builder.py` (dòng 28-55) — thêm `_load_routing_config()` load từ OneDrive SOT với local fallback; `_DEFAULT_DESTINATIONS` + `_MAX_DESTINATIONS` module-level
- `email_engine/intelligence/builder.py` (dòng ~750) — xoá hardcoded 9-lane, dùng `list(_DEFAULT_DESTINATIONS)`, truncate nếu `> _MAX_DESTINATIONS`
- `email_engine/web_server.py` (dòng 1916-1937) — `_FALLBACK_DESTINATIONS` giảm từ 9 → 3 lanes safe `["USLAX", "USSAV", "USNYC"]`

**Verify command:**
```bash
python -c "from email_engine.web_server import DEFAULT_DESTINATIONS; print(DEFAULT_DESTINATIONS)"
# Output: ['USLAX', 'USOAK', 'USTIW', 'USSAV', 'USNYC', 'USMIA', 'USHOU', 'USCHI', 'USDAL', 'CAVAN']
```
Builder + web_server cùng load 10 lanes từ OneDrive SOT — **SYNCED**.

### Phase 2 — Unify Path A + Path B ✅

**Files changed:**
- `email_engine/web_server.py` (~dòng 310-344) — enhance `_normalize_dest_text` với `log.debug` + `log.info` khi token không parse được
- `email_engine/web_server.py` — thêm helper `_resolve_destinations(row_dest, requested_dest, requested_dests, defaults) -> tuple[str, list[str], list[str]]` trả về `(primary_pod, full_pod_list, known_pods)`
- `email_engine/web_server.py` (Path A `/api/prospects` ~dòng 1570) — dùng helper thay inline logic
- `email_engine/web_server.py` (Path B `/api/bulk/build` ~dòng 2158) — dùng helper
- `email_engine/web_server.py` (`/api/rate-preview` ~dòng 607) — fallback `DEFAULT_DESTINATIONS` khi destinations rỗng

**Bug fixed:**
- Path A không merge defaults cho CNEE 1-POD → khách chỉ thấy 1 lane thay vì 10 cross-sell
- `/api/rate-preview` silent fail khi destinations rỗng

### Phase 3 — Template `default_cross_sell` + Scoring Tie-break ✅

**Pre-phase smoke test CAVAN:**
```
CAVAN rates found: 5
  - ONE: $2204
  - YML: $2556
→ Safe to include
```

**Files changed:**
- `email_engine/templates/email_rules.yaml` — thêm `default_cross_sell` ở ĐẦU list (trước `west_coast`)
- `email_engine/intelligence/template_selector.py` (dòng 114-156, 172-182) — sửa `_score_template()` trả về tuple `(score, match_count, neg_tmpl_size, reason)`; `match()` dùng tuple comparison để tie-break

**Vấn đề phát hiện lúc verify:**
Template `default_cross_sell` đặt ở top + chia sẻ port với regional templates → thắng TẤT CẢ tie với `west_coast`, `east_coast`, `canada`, `inland`.

**Fix applied (Option A từ code review):**
```python
match_count = sum(1 for d in dests_u if d in tmpl_dests)
tmpl_size = len([d for d in tmpl_dests if d != "ANY"])
# Tie-break: (score, match_count ↑, -tmpl_size ↑ = smaller template wins)
```

**Verify — 6/6 PASS:**
```
[PASS] [10 lanes]          -> default_cross_sell (expected default_cross_sell)
[PASS] West Coast 4-lane   -> west_coast         (expected west_coast)
[PASS] East Coast 3-lane   -> east_coast         (expected east_coast)
[PASS] Canada 3-lane       -> canada             (expected canada)
[PASS] Inland 2-lane       -> inland             (expected inland)
[PASS] Empty destinations  -> default            (expected default)
```

### Phase 4 — Enforce max_destinations ✅

Truncation block đã nhập vào `builder.build_email()` sau khi normalize destinations (gộp vào Phase 1 để tránh double-edit):
```python
if len(destinations) > _MAX_DESTINATIONS:
    log.info("[builder] truncating destinations %d→%d", len(destinations), _MAX_DESTINATIONS)
    destinations = destinations[:_MAX_DESTINATIONS]
```

**YAML cleanup (dead config):** KHÔNG thực hiện — giữ `by_campaign`, `by_country`, `regions` để không phá backward compat. Nelson có thể defer xoá cho session riêng.

---

## Test Results

### Pytest

```
89 passed, 2 deselected (pre-existing failures), 1094 warnings in 11.85s
```

**2 tests fail pre-existing (không liên quan changes):**
| Test | Lý do | Bằng chứng |
|------|-------|-----------|
| `test_build_email_integration_urgent` | Expect `"Acme Corp"` trong `html_body` nhưng template không render company | Fail cả trên `git stash` (trước changes) |
| `test_prod_yaml_loads` | Expect template id `west_coast_urgent` — YAML prod chỉ có `west_coast` | Fail cả trên `git stash` (trước changes) |

Cả 2 tests đã stale so với YAML production — không phải do session này.

### Integration test (custom)

```
builder._DEFAULT_DESTINATIONS = [10 lanes]  ✓
builder._MAX_DESTINATIONS = 10              ✓
web_server.DEFAULT_DESTINATIONS = [10 lanes] ✓
Both loaders SYNCED ✓
Template scoring: 6/6 test cases PASS ✓
```

---

## Files Changed (Summary)

| File | Changes | Purpose |
|------|---------|---------|
| `email_engine/config/default_routes.yaml` | 2 dòng | Local SOT — 10 lanes + cap 10 |
| `D:/OneDrive/NelsonData/email/config/default_routes.yaml` | 2 dòng | **OneDrive SOT thật** — đã sync |
| `email_engine/intelligence/builder.py` | ~30 dòng | `_load_routing_config()`, truncate, remove hardcoded list |
| `email_engine/web_server.py` | ~80 dòng | `_resolve_destinations()` helper, Path A/B unified, preview fallback, log enhancements, fallback 3-lane |
| `email_engine/templates/email_rules.yaml` | +16 dòng | New `default_cross_sell` template |
| `email_engine/intelligence/template_selector.py` | ~20 dòng | Scoring tuple + tie-break by match_count + tmpl_size |

---

## Issues bỏ qua

| Issue | Lý do | Gợi ý |
|-------|-------|-------|
| YAML dead-config (`by_campaign`, `by_country`, `regions`) | Risk phá backward compat — không rõ ai đang đọc | Session riêng + tech-debt-tracker log |
| `test_build_email_integration_urgent` failing | Pre-existing — template không render company name | Test owner cần fix signature hoặc template |
| `test_prod_yaml_loads` expect `west_coast_urgent` | YAML prod đã bỏ `_urgent` suffix từ trước session | Update test expected id — hoặc xoá assertion |

---

## Acceptance Criteria — ALL PASSED ✅

1. ✅ YAML là SOT duy nhất — `builder.py` + `web_server.py` đều load từ OneDrive path trước
2. ✅ `/api/prospects` → `destinations_all` có 10 lanes (known first) via `_resolve_destinations()`
3. ✅ `build_email()` với empty destinations → fallback 10 lanes từ YAML
4. ✅ Template match cho 10 lanes → `default_cross_sell` wins
5. ✅ Regional templates (west/east/canada/inland) vẫn win cho đúng subset
6. ✅ Builder truncate nếu `> 10` destinations
7. ✅ Existing tests pass (89/89 non-stale)

---

## Concerns & Next Steps

**⚠ OneDrive sync**: Em đã sửa cả local + OneDrive YAML. Nelson nên verify OneDrive sync đến các máy khác (Laptop VP, PC Home) sau khi sync xong.

**📋 Bước tiếp theo gợi ý (chưa thực hiện):**
- 🧪 `test-writer` — sinh test cho `_resolve_destinations()` + tie-break logic
- 📋 `tech-debt-tracker` — log 2 stale tests + YAML dead-config
- 💾 `git-commit` — sinh commit message chuẩn Conventional Commits

**KHÔNG tự commit** theo rule Nelson.

---

**Status**: DONE_WITH_CONCERNS
**Summary**: 11/11 issues fixed, 6/6 template matches PASS, 89/89 non-stale tests PASS. 2 concerns: OneDrive YAML cần verify sync cross-machine; 2 pre-existing tests fail không liên quan.
**Output file**: `plans/reports/master-executor-email-lanes-20260423.md`
