# Plan: Redesign Forecast + Costing Architecture

## Context

Hệ thống forecast hiện tại có nhiều vấn đề:
1. **Costing sai** — trộn FAK/FIX/SCFI, hiện giá expired, hiện 3 carriers/region nhưng chỉ cần 1 best
2. **Forecast disconnected** — 2 hệ thống forecast riêng biệt (ETS agents vs baseline report), không kết nối
3. **Band quá hẹp** — 44.7% accuracy vì hardcode -6%/+10%, không dựa vào volatility thực
4. **Không có human-in-the-loop** — Nelson không validate/adjust được, model không học từ expert input
5. **SCFI bị hiểu sai** — SCFI chỉ là giá HPL short-term, không phải market indicator

### Nelson's requirements:
- Costing: **1 best carrier per region** — giá tốt nhất + valid xa nhất
- FIX vs FAK: **hiện cả hai**, ghi rõ loại — hiện tại FIX đang có lợi thế
- Forecast: **Hybrid AI + Nelson validate** — AI predict range, Nelson adjust, system learns
- Report cho **cả sales team (đơn giản) + Nelson review (chi tiết)**

### Thực tế thị trường (từ Nelson):
- EC: HPL SCFI đang lead ~$2,900/40HC, ONE/CMA FIX $3,000-3,200
- WC: WHL/ONE FAK $3,500-3,700
- FIX đang rẻ hơn FAK ở thời điểm hiện tại

---

## Architecture Changes

### 1. Costing Extractor — Fix filtering + display

**File:** `Pricing_Engine/market_report/costing_extractor.py`

Changes:
- Filter: `Exp >= report_monday + 7 days` (không hiện giá sắp hết)
- Scoring: `score = -price + (days_until_exp * weight)` — giá thấp VÀ valid lâu được ưu tiên
- Output: **1 best per region** (thay vì 3), nhưng show cả rate type
- Thêm field `days_remaining` vào `CostingItem`
- Hiện: `HPL FIX $2,609/40HQ (valid 01-30 Apr, 17 days left) [-$1,087 vs avg]`

### 2. Costing Rate Type Comparison — Thêm section mới

**File:** `Pricing_Engine/market_report/costing_extractor.py` (new function)

Thêm `extract_rate_type_comparison()`:
- Per region: hiện best FAK rate vs best FIX rate vs best SCFI rate
- Highlight loại nào đang có lợi thế
- VD: "EC: FIX $3,200 (ONE) vs FAK $3,700 (CMA) → FIX đang rẻ hơn 14%"

### 3. Forecast Pipeline — Wire Agent2 into Report

**File:** `Pricing_Engine/market_report/report_generator.py`

Changes:
- Replace `_build_baseline_scenarios()` placeholder với real Agent2 predictions
- Read `forecast_memory.json` → extract target week → aggregate per region
- Band: thay hardcode -6%/+10% bằng **volatility-based band** (2x weekly stdev)

**File:** `pricing/forecast/agent2_model_engine.py`

Changes:
- Band calculation: `low = forecast - 2*weekly_std`, `high = forecast + 2*weekly_std`
- Minimum band width: ±8% (floor)
- Maximum band width: ±25% (cap)
- Remove dead `BAND_MARGIN_PCT` from config

### 4. Human-in-the-Loop — Nelson Adjustment Layer

**New file:** `Pricing_Engine/market_report/nelson_adjust.py`

Architecture:
```
Agent2 predicts W16: WC $4,128 [UP]
    ↓
nelson_adjust.yaml (Nelson's manual overrides):
    WC:
      direction: UP        # agree with AI
      adjustment_pct: -5   # "market feels softer than AI thinks"
      note: "GRI chưa kick in, buyer đang hold"
    EC:
      override_base: 3200  # Nelson sets explicit price
      note: "FIX rate đang lead, FAK sẽ follow xuống"
    ↓
Final prediction = AI base * (1 + adjustment_pct/100)
    ↓
Backtest tracks BOTH: AI-only accuracy vs Nelson-adjusted accuracy
```

**File:** `pricing/forecast/agent3_backtest_judge.py`

Changes:
- Track 2 accuracy streams: `ai_raw` vs `nelson_adjusted`
- Over time, weight shifts toward whoever is more accurate
- Nelson sees: "AI predicted $4,128, you adjusted to $3,922, actual was $3,850 → your adjustment was better"

### 5. Report Structure — 2-layer output

**File:** `scripts/build-weekly-report.js` (generalized from build-w15-report.js)

```
I.   COSTING (1 best per region, rate type comparison table)
II.  CHALLENGE & CHANGE (from Nelson's docx — manual input)
III. FORECAST (AI prediction + Nelson adjustment + confidence)
IV.  SALES BRIEF (2-3 bullet: giá bao nhiêu, nên book ngay hay chờ)
V.   TECHNICAL APPENDIX (full carrier breakdown, accuracy metrics, model version)
```

---

## Implementation Steps

### Step 1: Fix Costing Extractor
- `costing_extractor.py`: filter Exp >= monday+7, score by price+validity, return 1 per region
- Add `extract_rate_type_comparison()` function
- Test: verify output matches Nelson's market reality (EC HPL SCFI ~$2,900)

### Step 2: Fix Forecast Band
- `agent2_model_engine.py`: replace hardcoded band with volatility-based
- `config.py`: remove dead BAND_MARGIN_PCT, add BAND_MIN_PCT=0.08, BAND_MAX_PCT=0.25
- Test: re-run backtest, expect band accuracy > 60% (from 44.7%)

### Step 3: Wire Agent2 → Report
- `report_generator.py`: read forecast_memory.json instead of baseline placeholder
- Aggregate by region (WC/EC/GULF) from carrier-level predictions
- Test: report shows real ETS predictions, not min(costing)±15%

### Step 4: Nelson Adjustment Layer
- Create `nelson_adjust.yaml` template
- Create `nelson_adjust.py`: load yaml, apply to predictions, track both streams
- Update `agent3_backtest_judge.py`: dual accuracy tracking
- Test: Nelson fills yaml for W16, verify adjusted output

### Step 5: Rebuild Report Generator
- Generalize `build-weekly-report.js` to accept week parameter
- Add rate type comparison table
- Add Sales Brief section (auto-generated from costing + forecast)
- Add Technical Appendix

---

## Verification

1. Run: `python -m Pricing_Engine.market_report.cli --prev 2026-W15 --next 2026-W16`
2. Check costing: should show 1 best per region with valid dates >= 7 days
3. Check forecast: should show volatility-based bands (wider than current 16pt)
4. Check rate comparison: FAK vs FIX per region
5. Run backtest: `python run_forecast.py --backtest` — band accuracy should improve
6. Nelson fills `nelson_adjust.yaml` → re-generate → verify adjusted predictions appear

---

## Key Files

| File | Change |
|------|--------|
| `Pricing_Engine/market_report/costing_extractor.py` | Fix filter, 1 per region, rate comparison |
| `Pricing_Engine/market_report/report_generator.py` | Wire real forecast, new structure |
| `pricing/forecast/agent2_model_engine.py` | Volatility-based band |
| `pricing/forecast/config.py` | Clean dead params |
| `pricing/forecast/agent3_backtest_judge.py` | Dual accuracy tracking |
| `Pricing_Engine/market_report/nelson_adjust.py` | NEW: human-in-the-loop |
| `scripts/build-weekly-report.js` | Generalize, add sections |
