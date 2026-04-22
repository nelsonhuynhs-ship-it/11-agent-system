---
title: "Ribbon Pricing Tab — Toggle Buttons for Source/Note Filters"
description: "Replace Note combo box with fast toggle buttons for Source (SCFI/FAK/FIX) + Note (SOC) filtering. Faster daily pricing check workflow."
status: pending-approval
priority: P2
effort: 2h
branch: main
tags: [erp-v14, ribbon, ux, pricing, toggle-filter]
created: 2026-04-22
owner: Nelson
---

# Ribbon Pricing Tab — Toggle Buttons

## 🎯 Problem

Hiện tại workflow Nelson check giá mỗi ngày:
1. Chọn Carrier + POL + POD + Place trong combo box
2. Muốn filter theo Source (FAK/FIX/SCFI) hoặc Note (SOC/COC) → phải **click dropdown filter của cột Source bên dưới header** → chọn value → OK
3. Lặp lại 5-10 lần/ngày cho các query khác nhau

**Pain:** combo box Note trong ribbon chỉ dùng cho 1 case hẹp (chọn SOC) mà chiếm ~18 ký tự width. Filter Source phải thao tác filter cell — 4-5 click per filter.

## 💡 Nelson Policy

- **Default search:** hiển thị CẢ COC + SOC + all Source types (không filter gì)
- **Click 1 nút:** chuyển sang view filtered ngay
- **Layout ribbon:** phải gọn gàng, nhanh gọn kiểu nút `Best Price` hiện có

## 📋 Filter Modes Nelson Cần

| Mode | Kết quả |
|------|---------|
| **All** (default) | Hiện tất cả (COC+SOC, FAK+FIX+SCFI) |
| **SCFI only** | Chỉ SCFI rates |
| **FAK only** | Chỉ FAK (COC + SOC) |
| **FIX COC only** | FIX Special Rate COC |
| **FIX SOC only** | FIX Special Rate SOC |
| **SOC only** (cross-source) | Tất cả SOC bất kể loại rate |

## 🏗 Layout Proposals (2 options)

### Option A — Single Toggle Row (KISS ⭐)

```
┌──────────────────────── grpSearch ─────────────────────────────────┐
│ [Carrier▼] [POL▼] [POD▼] [Place▼] [Exp▼]                          │
│ [All ●] [SCFI ○] [FAK ○] [FIX COC ○] [FIX SOC ○] [SOC ○]           │
│ [Best Price] [Clear] [Freshness]                                    │
└────────────────────────────────────────────────────────────────────┘
```

6 toggle buttons (radio-style — chỉ 1 active tại 1 thời điểm). Default: "All".

**Pros:** Đơn giản, 1 row buttons. Click = state change instant.
**Cons:** 6 buttons trong 1 row hơi dài. "All" có thể redundant (không click = all).

### Option B — 2 Dimensions Separate (Flexible)

```
┌────────────────────────── grpSearch ────────────────────────────────────┐
│ [Carrier▼] [POL▼] [POD▼] [Place▼] [Exp▼]                               │
│ Source: [SCFI ○] [FAK ○] [FIX ○]    Container: [All ●] [SOC ○]         │
│ [Best Price] [Clear] [Freshness]                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Source row:** 3 toggle radio (if none pressed = All)
- **Container row:** COC/SOC (default All = COC+SOC, press SOC = SOC only)

Combinations:
- FAK + SOC = FAK SOC only
- FIX + SOC = FIX SOC only
- FAK alone = FAK COC+SOC
- SOC alone = SOC across all Source

**Pros:** 2 dimensions độc lập, flexible hơn, fewer buttons per dimension.
**Cons:** 2 row buttons, logic kết hợp cần giải thích 1 lần.

---

## 🎨 Recommendation — Em Nghiêng Option B

**Lý do:**
- **Pattern rõ ràng:** Source (rate type) vs Container type (COC/SOC) là 2 dimension thực sự khác nhau về bản chất
- **Combinations cover được:** 3 × 2 = 6 modes + "all" = cover đủ use case
- **Mở rộng dễ:** sau này nếu cần thêm type (e.g. NAC) → thêm button trong Source row
- **Semantic đúng:** SCFI luôn COC → khi Source=SCFI, SOC button auto-disabled

## 📐 Implementation Outline (~2h)

| Phase | Tasks | Effort |
|-------|-------|--------|
| 1 | Remove `cmbNote` from CustomUI + 4 callbacks. Add toggle button controls to `grpSearch` | 30m |
| 2 | VBA state module vars (m_SourceFilter, m_SocFilter) + toggle handlers | 45m |
| 3 | Wire toggle state into `ApplyQuickSearch` — filter Source col 9 + Note col 8 | 30m |
| 4 | Test 6 filter modes + E2E | 15m |

## 📂 Files Touched

- `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` — remove cmbNote, add 5 toggleButtons
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` — state vars + OnAction handlers + getPressed callbacks
- `D:/OneDrive/NelsonData/erp/erp-v14-quick-wins.bas` — ApplyQuickSearch extend với Source/Note toggle state
- `tests/test_erp_e2e.py` — verify new ribbon IDs

## ❓ Questions for Nelson (chốt trước khi code)

1. **Chọn Option A hay B?** (A=6 radio flat, B=2 dimension separate)
2. **"All" button explicit** hay **không press = All** (cleaner UX, no All button)?
3. Button size: **small compact** (fits 5-6 per row) hay **normal** (3-4 per row)?
4. Khi Source=SCFI → SOC button **auto-disable** hay **allow nhưng cho empty result**?
5. Filter có **persist giữa các sheet** (Pricing Dry ↔ Reefer) hay **reset khi switch sheet**?

## ✋ Chờ Nelson Duyệt Layout

Em sẽ gửi HTML preview để anh xem visually. Anh chốt option + 5 câu hỏi → em spawn agents ship.

## 🚫 Out of Scope

- Không đụng combo Carrier/POL/POD/Place/Exp (giữ nguyên)
- Không đổi Best Price / Clear / Freshness buttons
- Không đụng grpRateMix / grpSelectedRow / grpMargin / grpSellRate / grpQuoteAction
- Không thêm NAC/BULLET filter (YAGNI — chỉ khi Nelson request)
