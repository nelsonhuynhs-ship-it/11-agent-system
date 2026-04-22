---
name: Rule Engine + Smart Send UI Consolidation
status: completed
priority: P1
created: 2026-04-22
completed: 2026-04-22 23:30
mode: fast
effort_hours: 5.5 (actual)
parent: 260422-2100-daily-rotation-engine
blockedBy: []
blocks: []
---

# Rule Engine + Smart Send UI Consolidation

## Mục tiêu

Chuyển 6 control từ Send configuration cũ (Campaign · POL · Destination · Markup · ARB · Subject) lên Smart Send widget → Nelson bấm 1 nút Start batch là xong, không cần scroll xuống manual.

Kèm: build `rule_engine.py` tự resolve ARB/POL per recipient dựa ORIGIN_COUNTRY (MY 7,232 contacts đang sai route).

## Vấn đề hiện tại

1. Quick Send có 2 layer UI độc lập:
   - Top: Smart rotation widget (Start batch) — hiển thị đẹp nhưng không expose config
   - Bottom: Send configuration (Campaign/POL/Dest/Markup/ARB/Subject) — cần fill manual
2. Nelson phải scroll xuống + fill manual → 95% case auto được
3. `rule_engine.py` chưa build → backend dùng POL=HPH default cho ALL, sai cho 7,232 Malaysia contacts
4. Markup: Nelson muốn 1 input chung cho batch (hiện hardcode 20)

## Deliverables

### Phase 1 — `rule_engine.py` (2h)

**File:** `email_engine/core/rule_engine.py`

```python
ARB_MAPPING = {
    "VN": {"pol_default": "HCM", "arb_key": None},
    "MY": {"pol_default": "PKG", "arb_key": "port_klang"},
    "TH": {"pol_default": "BKK", "arb_key": "lat_krabang"},
    "CN": {"pol_default": "SHA", "arb_key": "shanghai"},  # or "ningbo" based on actual POL
    "KH": {"pol_default": "HCM", "arb_key": "phnom_penh"},  # Cambodia: base HCM + ARB
}

def resolve_config(row: dict, user_markup: int = 20, campaign_override: str = None) -> dict:
    """Return per-email config dict for rotation_engine queue_to_outlook_worker."""
    country = (row.get("ORIGIN_COUNTRY") or "VN").upper().strip()
    rule = ARB_MAPPING.get(country, ARB_MAPPING["VN"])
    
    pol = (row.get("POL") or rule["pol_default"]).upper().strip()
    
    # Normalize CN variant: NGB uses ningbo key, others use shanghai
    arb_key = rule["arb_key"]
    if pol in ("NGB", "NINGBO") and arb_key == "shanghai":
        arb_key = "ningbo"
    
    # Destination fallback per country
    dest = (row.get("DESTINATION") or "").strip()
    if not dest or dest.lower() in ("nan", "none"):
        dest = "USLAX,USLGB"
    
    # Subject template (rotate 5 variants for anti-spam)
    subjects = [
        f"Ocean Freight Update — {pol} to {_region(dest)} | Week {_week()} | NELSON",
        f"Weekly Rate Update — {row.get('COMMODITY_CATEGORY', '')} | {pol} -> US",
        f"{pol} to US Freight Rates — Week {_week()}",
        f"Latest Container Rates from {pol}",
        f"Shipping Quote — {pol} to US | Valid end of month",
    ]
    import random
    subject = random.choice(subjects)
    
    return {
        "pol": pol,
        "destination": dest,
        "arb_origin": arb_key,
        "markup": user_markup,
        "subject": subject,
        "campaign": campaign_override or row.get("COMMODITY_CATEGORY", ""),
    }
```

Wire vào `rotation_engine.queue_to_outlook_worker()` thay hardcode HPH/markup=20.

### Phase 2 — Smart Send widget consolidation (3h)

**File:** `plans/visuals/email-dashboard-v6.html`

Chuyển 6 field lên **bên trong** rotation-widget:

```
┌─ 2026-04-23 · Vòng 1 · Tuần 2/5.3 ──────────────── ⚙ ┐
│                                                       │
│  🎯 SMART MODE (default)                             │
│  HÔM NAY: 0 / 700    ████░░░░░░ 0%   [▶ Start batch] │
│                                                       │
│  📝 Config (auto-resolved per email):                │
│  Markup USD: [20____]                                │
│  ARB: auto · Subject: random · POL: per contact      │
│  [👁 Preview 3 samples]                              │
│                                                       │
│  ▼ MANUAL OVERRIDE (advanced — collapsed)            │
│    Campaign [FLOORING▼] POL [HPH▼] ARB [port_klang▼] │
│    Subject [custom...] → override for THIS batch     │
└──────────────────────────────────────────────────────┘
```

Giữ Send configuration cũ (POL/Destination/Campaign/Subject) **collapsed** trong accordion "Manual Override" — 5% case dùng khi Nelson muốn override 1 batch.

### Phase 3 — Preview Modal (1h)

Click "👁 Preview 3 samples" → modal hiển thị:
- 3 email sample (FLOORING + FURNITURE + CANDLE)
- Mỗi email: subject · từ ai · rate table thật render · tính cả ARB + markup
- Click "Send all 700" confirm → queue_to_outlook_worker

## Files sẽ touch

| File | Action |
|---|---|
| `email_engine/core/rule_engine.py` | NEW |
| `email_engine/core/rotation_engine.py` | Update: call rule_engine.resolve_config |
| `email_engine/api/routes/rotation_router.py` | Add /api/rotation/preview-sample endpoint |
| `plans/visuals/email-dashboard-v6.html` | Restructure Quick Send layout |

## Testing

- `tests/test_rule_engine.py`: 10 scenarios (VN/MY/TH/CN/KH + edge cases)
- Manual: chọn Malaysia contact → verify POL=PKG + ARB=port_klang
- Manual: preview modal render đúng rate table cho 3 lane
- End-to-end: bấm Start batch → 700 email với correct POL per country

## Success criteria

- [ ] 7,232 Malaysia contacts route POL=PKG (thay vì HCM)
- [ ] Markup field nằm trong Smart widget (Nelson nhập 1 lần)
- [ ] Manual Override collapsed default (95% không cần mở)
- [ ] Preview modal hiển thị 3 sample emails thật
- [ ] Start batch sử dụng user_markup từ widget (không hardcode 20)
- [ ] Next-day rotation vẫn hoạt động Task Scheduler 8AM

## Dependencies

✅ Phase 1+2+4 Daily Rotation (shipped)
✅ 700 email ROT_1776868843 validated
✅ ARB_ORIGIN_MAPPING.md docs
✅ arb_rates.yaml config file exists

## Next steps after this plan

- BD/IN/PH/ID coverage research (chưa có trong arb_rates.yaml)
- Cache optimization `/api/rotation/progress` < 100ms (bug hiện tại)
- Phase 5A WhatsApp SANDBOX khi Nelson có Meta token

## 🚨 URGENT tech debt phát hiện 2026-04-22 23:30

### Bug: web_server.py dùng file master CŨ (v5)
- `web_server.py:41,49` hardcode `cnee_master_v2_final.xlsx` (22,230 rows)
- File v6 master `contact_unified_v6.xlsx` (22,842 rows) build xong nhưng chưa wire
- Hệ quả: rotation engine + web_server dùng 2 nguồn data khác nhau
- Fix trong phase này: update tất cả reference sang `contact_unified_v6.xlsx`

### Bug: File corrupt do concurrent write
- 22:20 file `cnee_master_v2_final.xlsx` corrupt zlib
- Giả thuyết: scan-sent update + rotation read → xung đột
- Fix: thêm `filelock` module, lock xlsx trước mọi write operation
- Restore: `cnee_master_v2_final.backup_20260422_2052.xlsx` (đã apply 23:30)

### Phase bổ sung — Master file consolidation

**Effort:** 1.5h

1. Update `web_server.py` tất cả reference → `contact_unified_v6.xlsx` (sheet CNEE)
2. Fallback chain: v6 → v5 (cnee_master_v2_final) → v1 (cnee_master.xlsx)
3. Add file lock với `filelock` library khi write master
4. Update `scan-sent-outlook.py --update-master` target sang v6
5. Test end-to-end: scan sent → update v6 → rotation pick mới

## Completion Notes (2026-04-22 23:30)

### Shipped
- ✅ Phase 1 — `email_engine/core/rule_engine.py` (218 LOC, 13/13 tests PASS)
  - ARB_MAPPING: VN/MY/TH/CN/KH implemented
  - CN NGB variant mapped to `ningbo` key
  - `resolve_config()` schema-adaptive (v5/v6)
- ✅ Phase 2+3 — UI + Preview Modal
  - `plans/visuals/email-dashboard-v6.html` (+120 LOC): Smart config inline, Manual Override collapsed
  - `/api/rotation/run-today` accept RunTodayRequest pydantic
  - Preview modal renders 3 samples with real rate table
- ✅ Phase 4 — Master wire + filelock (BONUS)
  - `email_engine/core/xlsx_lock.py` (NEW)
  - `email_engine/core/cnee_schema_adapter.py` (NEW)
  - `web_server.py _get_cnee_df` loads contact_unified_v6.xlsx sheet="CNEE"
  - Fallback chain: v6 → v5 → v1
  - **Verified:** 22,842 rows (v6) vs 22,230 (v5) — Malaysia 7,232 contacts now route POL=PKG + ARB=port_klang

### Test Results
- Unit: 29/29 PASS (rule_engine 13, smart_send 12, rotation 4)
- Integration: 5/5 PASS (send-stats, rotation/today, preview-sample, progress, contacts)
- Code review: 9.25/10 · 0 critical · 8 minor (tracked below)

### Technical Debt (8 minor, follow-up only)
1. SEC-1: Pydantic `user_markup` validation `ge=0 le=500`
2. LOCK-1: rename `xlsx_read_lock` → docstring clarity
3. LOCK-2: narrow exception catch dalam `_get_cnee_df`
4. FALLBACK-1: v6 file missing sheet "CNEE" graceful fallback
5. PERF-1: `/preview-sample` return 503 nếu plan not built (avoid sync build)
6. SEC-2: subject format injection (low risk)
7. ERR-1: scan-sent-outlook catch PermissionError (file locked by Excel)
8. TEST-1: docstring says "10 scenarios" but 13 present (cosmetic)

### Files Modified
- `email_engine/core/rule_engine.py` (NEW)
- `email_engine/core/xlsx_lock.py` (NEW)
- `email_engine/core/cnee_schema_adapter.py` (NEW)
- `email_engine/web_server.py` (_get_cnee_df updated)
- `api/routers/contacts_router.py` (DuckDB PRAGMA fix)
- `plans/visuals/email-dashboard-v6.html` (UI consolidated)

### Ready for commit
- ✅ All tests passing
- ✅ Code review complete
- ✅ Docs updated (see below)
- ⏳ Git commit pending (assign to git-manager)

---

## Đúng tinh thần Nelson

- KISS: Smart default hide complexity, Manual Override chỉ hiện khi cần
- Anti-spam: subject random 5 variants → Gmail/Outlook filter không mark pattern
- Predictable: anh biết 700 email/ngày gửi với markup anh nhập, route theo origin country
