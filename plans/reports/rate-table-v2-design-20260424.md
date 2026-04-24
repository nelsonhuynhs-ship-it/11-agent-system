# Rate Table v2 — Design Doc (LOCK-IN SPEC)

**Date:** 2026-04-24
**Author:** Nelson Huynh + AI
**Status:** ✅ APPROVED 2026-04-24 — Nelson accepted all 5 defaults
**Scope:** `auto_rate_builder.py` query logic · `default_routes.yaml` POD list · email HTML template
**Visual preview:** `plans/visuals/rate-table-v2-preview.html` ✅ Nelson approved

---

## 1. Problem Statement

**Symptom:** HPL SCFI rates (cheapest carrier cho USEC từ HCM) chưa bao giờ surface trong rate table email, mặc dù giá tốt nhất và khách hàng USEC rất nhạy giá.

**Root cause** (đã verify qua SQL query trên parquet):
File `email_engine/core/auto_rate_builder.py` line 243-253:
```python
for carrier, grp in results_40.groupby("Carrier"):   # gom tất cả HPL (FAK+FIX+SCFI)
    grp["_exp_ts"] = pd.to_datetime(grp["Exp"], errors="coerce")
    max_exp = grp["_exp_ts"].max()
    latest = grp[grp["_exp_ts"] >= max_exp - pd.Timedelta(days=1)]  # HPL FAK Exp xa nhất
    best_row = latest.loc[latest["Amount"].idxmin()]
```
→ Filter "latest Exp first" ăn FAK (Exp May 14) thay vì SCFI (Exp May 3) dù FAK đắt hơn $571-741/cont.

**Data funnel verify:** 53,220 HPL SCFI rows → 9,336 expired (97.4%) → 252 valid rows → 0 row làm BEST vì bị group loại.

**Business impact:** Nelson mất lợi thế pricing trên 5 USEC lanes (NYC/SAV/MIA/ATL/CHI) mỗi tuần, estimated ~$600/cont × 100 cont/week miss = **$60K/week opportunity gap**.

---

## 2. Goals & Non-Goals

### Goals
1. **G1** — Surface HPL SCFI khi nó là giá rẻ nhất cho lane, kèm tag "SCFI 7d" để khách biết validity ngắn
2. **G2** — Default email gửi 10 POD (mở rộng từ 3 hiện tại)
3. **G3** — TOP 3 **distinct carriers** per POD (không cho 3 variants HPL trong 1 row)
4. **G4** — Atlanta mặc định RIPI (via EC gateway), không IPI (via WC) — rẻ hơn
5. **G5** — Layout email side-by-side HPH/HCM, inland port styling tách biệt main port

### Non-goals (explicit)
- ❌ Thêm carrier mới ngoài 11 carrier hiện có
- ❌ Thay đổi parquet schema
- ❌ Thay đổi column structure của email template (Nelson đã chốt giữ)
- ❌ Thêm POD mới ngoài 10 default
- ❌ Carrier scorecard / ranking system
- ❌ Rate negotiation UI
- ❌ Container type ngoài 20GP/40HQ

---

## 3. Design Decisions (LOCK-IN)

### D1 — 10 POD Default List

Config file: `email_engine/config/default_routes.yaml`

| # | POD | City | POL source | Route type | Badge | Gateway |
|---|-----|------|------------|-----------|-------|---------|
| 1 | USLAX | Los Angeles | HPH+HCM | Main port | — | direct |
| 2 | USSAV | Savannah | HPH+HCM | Main port | — | direct |
| 3 | USNYC | New York | HPH+HCM | Main port | — | direct |
| 4 | USHOU | Houston | HPH+HCM | Main port | — | direct |
| 5 | USMIA | Miami | HPH+HCM | Main port | — | direct |
| 6 | USTIW | Tacoma | HPH+HCM | Main port | — | direct |
| 7 | USATL | Atlanta | HPH+HCM | Inland | 🔵 RIPI | via CHS/NOR/SAV |
| 8 | USCHI | Chicago | HPH+HCM | Inland | 🟣 IPI | via LAX/OAK |
| 9 | USDAL | Dallas | HPH+HCM | Inland | 🟣 IPI | via LAX/OAK |
| 10 | USDEN | Denver | HPH+HCM | Inland | 🟣 IPI | via LAX/OAK |

YAML spec:
```yaml
fast_bulk_default:
  pod_list:
    - { code: USLAX, city: "Los Angeles", type: main }
    - { code: USSAV, city: "Savannah",    type: main }
    - { code: USNYC, city: "New York",    type: main }
    - { code: USHOU, city: "Houston",     type: main }
    - { code: USMIA, city: "Miami",       type: main }
    - { code: USTIW, city: "Tacoma",      type: main }
    - { code: USATL, city: "Atlanta",     type: inland, gateway: RIPI, via: [CHS, NOR, SAV] }
    - { code: USCHI, city: "Chicago",     type: inland, gateway: IPI,  via: [LAX, OAK] }
    - { code: USDAL, city: "Dallas",      type: inland, gateway: IPI,  via: [LAX, OAK] }
    - { code: USDEN, city: "Denver",      type: inland, gateway: IPI,  via: [LAX, OAK] }
  pol_list: [HPH, HCM]
  max_destinations_per_email: 10
```

### D2 — TOP 3 Distinct Carriers Selection Algorithm

**Input:** Danh sách valid rates cho 1 (POL, POD) combo
**Output:** Tối đa 3 rows, mỗi row 1 carrier khác nhau

**Algorithm:**
```python
def select_top3_distinct_carriers(rates: pd.DataFrame) -> pd.DataFrame:
    # Step 1: Filter valid Exp (not expired) — baseline
    valid = rates[pd.to_datetime(rates["Exp"]) >= today]

    # Step 2: Per (Carrier, Rate_Type) → keep cheapest 40HQ
    per_carrier_type = valid.loc[valid.groupby(["Carrier", "Rate_Type"])["Amount_40HQ"].idxmin()]

    # Step 3: Per Carrier → keep cheapest across rate types
    #   BUT if SCFI exists AND is cheapest → keep SCFI (anchor pricing)
    per_carrier = per_carrier_type.sort_values(
        ["Carrier", "Amount_40HQ"]
    ).groupby("Carrier").head(1)

    # Step 4: Sort carriers by price, take top 3
    top3 = per_carrier.sort_values("Amount_40HQ").head(3)

    return top3
```

**Tie-break rules:**
1. Cùng giá → carrier có Exp xa nhất thắng (trừ khi SCFI)
2. Nếu SCFI cùng giá với Special rate → **SCFI thắng** (anchor pricing, rẻ thật sự)
3. Nếu < 3 distinct carriers available → return bao nhiêu có (không pad fake data)

### D3 — Rate Type → Carrier Compatibility Matrix

| Rate Type | Valid Carriers | Notes |
|-----------|---------------|-------|
| SCFI | HPL **only** | Shanghai index, 7-day validity |
| Special rate | CMA, ONE, HMM, YML, ZIM, HPL | Fixed contract, 2-6 weeks validity |
| Special SOC | HPL (primary), YML | Shipper-Owned Container |
| FAK COC | CMA, ONE, HMM, YML, ZIM, HPL, WHL | Freight All Kinds + Carrier-Owned |
| FAK SOC | HPL, YML | Freight All Kinds + SOC |

Builder query phải respect matrix — nếu DB có row sai (ví dụ SCFI carrier = ONE) → log warning, skip.

### D4 — Gateway Routing for Inland POD

**USATL (Atlanta) — RIPI first:**
- Primary: Rail via **CHS** (Charleston) / **NOR** (Norfolk) / **SAV** (Savannah)
- Fallback: IPI via LAX if RIPI no rate available
- Meta display: `"via CHS"` or `"via NOR"` depending on carrier's gateway

**USCHI / USDAL / USDEN (Chicago/Dallas/Denver) — IPI first:**
- Primary: Rail via **LAX** / **OAK** (West Coast)
- Fallback: (none — these lanes default WC gateway)
- Meta display: no suffix (IPI is default, not noteworthy)

**Gateway resolution logic:**
```python
def resolve_inland_gateway(pod: str, carrier: str) -> tuple[str, str]:
    """Return (gateway_port, routing_label)"""
    if pod == "USATL":
        ec_rates = query(pod_in=["USCHS", "USNOR", "USSAV"], carrier=carrier)
        if ec_rates:
            return (best_ec.port, f"via {best_ec.port}")
        # fallback
        return ("USLAX", "via LAX")
    elif pod in ["USCHI", "USDAL", "USDEN"]:
        return ("USLAX", "")  # WC default, no meta
    return (pod, "")  # main port, no gateway
```

### D5 — Visual Spec (from approved preview)

**Layout:**
- Side-by-side: `<table>` outer với 2 `<td width="50%">`, HPH left, HCM right
- Mobile fallback: `@media (max-width: 600px)` → `display: block` stack vertical

**Color themes:**
- HPH = green (North VN) — bg `#d4f0dd`, text `#0a4d3c`, border `#8bc9a3`
- HCM = blue (South VN) — bg `#d9ebf8`, text `#0a3d5c`, border `#7fb3dd`

**Inland POD styling:**
- Cell bg `#eef5ff` + border-left `3px solid #0366d6`
- POD code color `#0366d6`
- City subtitle 9px `#4a6b8a` (Atlanta/Chicago/Dallas/Denver/Tacoma)

**Badges:**
- `BEST` — dark green `#0a4d3c`, white text
- `SCFI 7d` — orange `#e8a617`, white text (warns short validity)
- `RIPI` — blue `#0366d6`, white text
- `IPI` — purple `#6b46c1`, white text

**Typography:**
- Price: 11.5px, bold, color `#0a4d3c`
- Meta (rate type · expiry): 9.5px, color `#666`, line-height 1.3
- Column widths FIXED: POD 68px, 3 carrier cols equal = `(100% - 68px) / 3`

---

## 4. Implementation Scope (Files to Touch)

| File | Change | LOC est |
|------|--------|---------|
| `email_engine/core/auto_rate_builder.py` | Fix `_query_best_rates` groupby bug + add TOP 3 distinct logic + gateway resolver | ~120 |
| `email_engine/config/default_routes.yaml` | Expand `fast_bulk_default` từ 3 → 10 POD + gateway metadata | ~40 |
| `email_engine/intelligence/builder.py` | Load YAML as SOT + enforce `max_destinations_per_email` | ~30 |
| `email_engine/templates/email_rules.yaml` | Thêm template `default_cross_sell` match 10 POD | ~25 |
| `email_engine/web_server.py` | Update `/api/rate-preview` helper + fallback 10 POD | ~60 |
| Email HTML template renderer | Inland port styling + HPH/HCM color theme + side-by-side | ~80 |

**Total:** ~355 LOC touched · 6 files · no schema change · no new dependencies

---

## 5. Implementation Plan Preview (5 Phases)

Full plan sẽ được tạo trong Step 3 via `/ck:plan`. Preview:

1. **Phase 1** — Fix `_query_best_rates` groupby bug (2h)
   Change groupby key: `["Carrier", "Rate_Type"]` instead of `["Carrier"]`. Verify SCFI surfaces.

2. **Phase 2** — TOP 3 distinct carriers selection algo (2h)
   Implement `select_top3_distinct_carriers()` per D2 spec. Unit test tie-break rules.

3. **Phase 3** — Gateway routing for RIPI/IPI (3h)
   Implement `resolve_inland_gateway()` + integrate với builder. Smoke test USATL via CHS.

4. **Phase 4** — HTML template update (2h)
   Side-by-side layout + color theme + inland styling. Outlook desktop smoke test.

5. **Phase 5** — Smoke tests + rollout (1h)
   5 test CNEE (1 Quick, 1 Priority, 3 rotation) · verify HPL SCFI surfaces · verify ATL routed RIPI

**Total effort:** ~10h · sequential (Phase N+1 needs N)

---

## 6. Risks & Mitigations

| # | Risk | Severity | Mitigation |
|---|------|----------|-----------|
| R1 | SCFI 7-day validity → rate stale trong email gửi T-3 | 🔴 HIGH | Badge "SCFI 7d" + meta "to 3 May" · Auto-refresh rate daily via scheduler |
| R2 | CAVAN no rate in parquet | 🟡 MED | **N/A** — Nelson đã chốt 10 POD toàn US, không có CAVAN |
| R3 | Mobile Outlook break side-by-side 1100px | 🟢 LOW | Media query stack vertical < 600px (đã có trong preview) |
| R4 | RIPI cheaper but transit +5-10 days | 🟡 MED | Meta "via CHS" giúp khách biết; không phải surprise |
| R5 | TOP 3 distinct có thể < 3 carriers cho lane niche | 🟢 LOW | Return what's available, không pad fake |
| R6 | Gateway resolver cho USATL cần DB có USCHS/USNOR data | 🟡 MED | Verify data availability trong Phase 1 trước khi implement Phase 3 |
| R7 | HPH/HCM color theme với colorblind users | 🟢 LOW | Dot icon prefix + text label "HAIPHONG"/"HO CHI MINH" (redundant encoding) |

---

## 7. Success Criteria

**Functional:**
1. ✅ HCM→Savannah → BEST = HPL SCFI $2,988 (thay vì HPL FAK $3,559 hiện tại)
2. ✅ HPH→Atlanta → BEST = HPL RIPI via CHS (không phải IPI via LAX)
3. ✅ 10 POD email render < 50KB HTML
4. ✅ Side-by-side render OK Outlook 2016/2019/365 desktop + Outlook Web + Gmail
5. ✅ All 3 carriers distinct trong mỗi row (không duplicate)
6. ✅ Mobile < 600px stack vertical (no horizontal scroll)

**Verification commands:**
```bash
# Verify HPL SCFI surfaces:
python -c "from email_engine.core.auto_rate_builder import build_rate_table_for_customer; \
  r = build_rate_table_for_customer(pol='HCM', destinations='USSAV', markup=20); \
  print([row for row in r['rates'] if row['carrier'] == 'HPL'])"

# Verify 10 POD default:
python -c "from email_engine.web_server import DEFAULT_DESTINATIONS; print(len(DEFAULT_DESTINATIONS))"
# Expected: 10
```

**Regression check:**
- Existing Quick Send flow không broken (cnee_master v7 22,854 rows filter)
- Existing Smart Draft single-CNEE send không broken
- Rotation engine 700/700 pattern preserved

---

## 8. Resolved Decisions (Nelson accepted 2026-04-24)

| Q | Decision |
|---|----------|
| Q1 USATL gateway priority | **Carrier preference** — whoever gives cheapest rate |
| Q2 SCFI refresh frequency | **Daily** — SCFI publishes Fridays, keep table fresh |
| Q3 POD with 0 carrier match | **Skip silently** — keep email compact |
| Q4 Container display | **Both 20GP + 40HQ** — format `$X / $Y` unchanged |
| Q5 USATL tie-break RIPI vs IPI same price | **RIPI wins** — faster transit, Nelson preference |

---

## 9. Next Step

**Nelson review** design doc này (~5 phút) → reply:
- ✅ **OK** → em chạy `/ck:plan` full workflow cho implementation plan
- 🔄 **Cần sửa** → em edit section cụ thể rồi re-submit
- ❓ **Cần làm rõ** → trả lời 5 Open Questions ở Section 8

---

**References:**
- Visual preview: `plans/visuals/rate-table-v2-preview.html`
- Parquet path: `D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet` (via `shared.paths`)
- Config SOT: `D:/OneDrive/NelsonData/email/config/default_routes.yaml`
- Related hotfix (separate): `plans/reports/hotfix-send-a-debug-20260424.md`
