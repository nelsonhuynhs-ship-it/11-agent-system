# Market Report 4C System — Architecture Brainstorm

**Date:** 2026-04-11 | **Author:** Claude (brainstorm mode) | **Decision owner:** Nelson
**Cadence:** Weekly — Monday W(N+1) 9am publish "W(N) summary + W(N+1) forecast"

## 1. Current state (from 5 sample reports)

### Observed format variants (INCONSISTENT)
| Report | Structure | Quality signal |
|---|---|---|
| W11→W12 | Costing / Capacity / Challenge&Chance / Dự đoán 1 number | Text-heavy, no source |
| W12→W13 | Same 4 blocks, more detail in Challenge | 7-10 surcharge updates listed manually |
| W13→W14 | Same, forecast = 2 numbers (WC/EC) | No confidence, no scenarios |
| W14 (tổng kết) | "Coasting" typo, text narrative | No structured data |
| W14→W15 | Best so far — has carrier-level prices + 3 catalysts tagged Panjiva/JOC | Still free-text, no machine schema |

### Problems
1. **Inconsistent headers** (Coasting vs COSTING vs Costing) → can't machine-parse
2. **Free-text everywhere** → no score, no tag, no trigger linkage
3. **Forecast = 1 number** → no low/base/high, no confidence, no "why"
4. **No backtest** — last week's prediction never checked against actual
5. **Capacity is fully manual prose** → can't trend/score
6. **Catalysts scattered in Challenge section** without source attribution or impact magnitude
7. **Not linked to parquet** → Costing section hand-copied from rate_importer output

## 2. Proposed 4C machine-readable schema

### 2.1 Costing (AUTO from parquet)
```python
@dataclass
class CostingItem:
    lane: Literal["WC", "EC", "GULF"]
    carrier: str
    rate_type: Literal["FIX", "FAK", "SCFI", "SPOT", "BULLET", "NAC"]
    container: str            # "40HC", "20DC"
    price: float
    valid_from: date
    valid_to: date
    is_pudong_best: bool      # best rate Pudong holds
    spread_vs_lane_avg: float # $ gap vs weekly market avg
    source_parquet_row: int
```

### 2.2 Capacity (MANUAL input → score)
```python
@dataclass
class CapacitySignal:
    week: str                 # "2026-W15"
    carrier: str
    lane: Literal["WC", "EC", "GULF", "ALL"]
    dimension: Literal["space", "equipment", "booking_policy"]
    status: Literal["OPEN", "TIGHT", "FULL", "ROLLING"]
    score: int                # 1=critical-tight → 5=abundant
    notes: str
    entered_by: str           # "CS_team" / "Nelson" / mentee name
    entered_at: datetime
```

**Input method:** `OneDrive/pricing/market-reports/inputs/capacity-W15.xlsx` — 1 sheet, columns match schema, team fills during week.

### 2.3 Catalyst (CRAWL → Gemini extract → tagged)
```python
@dataclass
class Catalyst:
    source: Literal["Panjiva", "JOC", "Xeneta", "CarrierNotice", "GoogleAlert", "Manual"]
    category: Literal["surcharge", "capacity", "geopolitical", "fuel", "labor", "policy", "weather"]
    headline: str
    body: str                     # 2-3 sentence summary (Gemini-extracted)
    impact_direction: Literal["UP", "DOWN", "FLAT", "VOLATILE"]
    impact_magnitude: Literal["LOW", "MED", "HIGH", "CRITICAL"]
    affected_lanes: list[str]     # ["WC"] / ["WC","EC"] / ["ALL"]
    affected_carriers: list[str]  # ["MSK"] or [] for market-wide
    effective_date: Optional[date]
    confidence: float             # 0.0-1.0 from Gemini self-score
    url: Optional[str]
    raw_text: str                 # for audit
    ingested_at: datetime
```

### 2.4 Forecast Scenario
```python
@dataclass
class ForecastScenario:
    lane: Literal["WC", "EC", "GULF"]
    week: str                     # target week "2026-W16"
    container: str                # "40HC"
    base_case: float              # most likely price
    low_case: float               # bearish
    high_case: float              # bullish
    confidence: float             # 0.0-1.0
    trigger_catalyst_ids: list[str]  # why this scenario
    rationale: str                # 1-2 sentences
    model_version: str            # "holt-winters-v2" / "lightgbm-v1"
```

## 3. Pipeline architecture

```
┌─ DAILY (Mon-Fri 8am) ────────────────────────────────────┐
│  costing-extractor.py     ← parquet (last 7 days)         │
│  capacity-loader.py       ← inputs/capacity-W{N}.xlsx     │
│  catalyst-crawler.py      ← Panjiva/JOC/Google Alert RSS  │
│     ↓ each writes to:                                      │
│  weekly/W{N}/{costing,capacity,catalysts}.parquet          │
└────────────────────────────────────────────────────────────┘

┌─ WEEKLY (Monday 9am) ─────────────────────────────────────┐
│  1. aggregate-week.py     ← merge 3 streams into W{N} view │
│  2. scenario-engine.py    ← existing run_forecast.py +     │
│                             catalyst impact blending       │
│  3. backtest-logger.py    ← compare W{N-1} forecast vs     │
│                             W{N-1} actual → append log     │
│  4. report-generator.py   ← python-docx render template    │
│     ↓                                                      │
│  weekly/W{N}/report-W{N}-predict-W{N+1}.docx               │
└────────────────────────────────────────────────────────────┘
```

## 4. Storage layout

```
OneDrive/NelsonData/pricing/market-reports/
├── weekly/
│   ├── 2026-W15/
│   │   ├── W15-costing.parquet
│   │   ├── W15-capacity.parquet
│   │   ├── W15-catalysts.parquet
│   │   ├── W15-forecast.parquet
│   │   └── report-W15-predict-W16.docx  ← final artifact
│   └── ...
├── inputs/
│   └── capacity-W15.xlsx                ← team fills weekly
├── templates/
│   └── weekly-report-template.docx      ← 4C format, placeholder-based
├── catalyst-sources.yaml                ← RSS URLs, Gemini prompt config
├── backtest-log.csv                     ← historical forecast vs actual
└── state/
    └── crawler-state.json               ← last-seen item hashes
```

## 5. Report template (DOCX output)

Match Nelson's existing W14→W15 format — best of the 5 samples:

```
BÁO CÁO THỊ TRƯỜNG TUẦN {W} & DỰ ĐOÁN TUẦN {W+1}
Generated: {date} | Model: {version}

I. COSTING  (source: parquet W{W})
   WC:     [top 3 carriers, 40HC, valid date, spread vs avg]
   EC:     [top 3]
   GULF:   [top 3]

II. CAPACITY  (source: team input, {entry_count} entries)
   Overall score: {avg_score}/5
   [table: carrier | lane | status | score | notes]

III. CHALLENGE & CHANCE  ({catalyst_count} catalysts ranked by impact)
   [HIGH impact catalysts first]
   • [HEADLINE]  — source: {src}, eff: {date}
     {body}
     → Impact: {direction} {magnitude} on {lanes}
   • ...

IV. FORECAST TUẦN {W+1}
   WC 40HC: base ${base} (range ${low}-${high}) confidence {pct}%
            Triggers: {top 3 catalyst headlines}
            Rationale: {1-2 sentences}
   EC 40HC: ...
   GULF 40HC: ...

V. BACKTEST TUẦN {W}  (previous week accuracy)
   WC: forecast ${fcst} vs actual ${act} → error {pct}%
   EC: ...
   GULF: ...
   Week accuracy score: {avg_error}% ({rating})
```

## 6. Scope options — Nelson pick

| Option | Scope | Effort | Trade-off |
|---|---|---|---|
| **A. Super-MVP** | Costing auto + Capacity xlsx + DOCX gen. NO crawler, NO backtest. | ~3h | Fast win, still manual catalyst |
| **B. MVP** ⭐ | A + Backtest logger + 1 catalyst source (Panjiva RSS via Gemini) | ~6-8h | Covers 80% value, shippable this week |
| **C. Full 4C** | MVP + JOC/Xeneta paid APIs + Google Alert + ML catalyst scoring | ~15-20h | Sprint-size, needs API budget |

**Em recommend B (MVP).** Lý do:
- Costing + backtest là cái anh đã có infra sẵn (parquet + forecast)
- Capacity xlsx = 10 phút setup, anh/team fill tay
- 1 catalyst source (Panjiva RSS) đủ prove concept → scale sau
- Paid APIs (Xeneta/JOC/Panjiva pro) tốn tiền, để C phase sau

## 7. Integration với các plan hiện tại

- **Reuse:** existing `Pricing_Engine/forecast/` 6-agent stack → scenario-engine is just a new orchestrator
- **Reuse:** `shared/paths.py` for OneDrive paths (P3 of rate-pipeline-reorg adds MAPPING_DIR, em add MARKET_REPORTS_DIR same time)
- **Depend on:** P2 of rate-pipeline-reorg (clean incoming/processed drift) — costing-extractor needs clean parquet
- **Depend on:** P5 ML auto-retrain (from earlier Q) — scenario-engine blends fresher model with catalysts

→ Nên làm **sau** P1-P4 rate-pipeline-reorg để không xung đột

## 8. Catalyst crawler — deep dive (biggest unknown)

### Sources evaluated
| Source | Access | Cost | Quality |
|---|---|---|---|
| Panjiva | Needs paid API | $$$ | Gold standard for shipping data |
| JOC.com | Public articles + paid | $$ | Surcharge news, carrier moves |
| Xeneta | API only, paid | $$$ | Rate benchmarks |
| Google Alerts RSS | Free | Free | Noisy but free, needs filter |
| Carrier notice inbox | Harry forwards | Free | Already have, just need OCR/extract |

### MVP strategy (cheapest)
1. **Carrier notices** — Harry's emails go to `pricing@pudongprime.vn`. Rate importer already saves JSONs to `knowledge/`. Add Gemini extraction pass: raw text → Catalyst struct.
2. **Google Alerts** — Set up 5 alerts: "shipping surcharge", "container freight rate", "Maersk EBS", "Trans-Pacific capacity", "GRI April". RSS feeds → parse → Gemini filter noise.
3. **Later:** JOC paid feed, Panjiva API

### Gemini extraction prompt (sketch)
```
Given this news snippet, extract:
- category (one of: surcharge, capacity, geopolitical, fuel, labor, policy, weather)
- impact_direction (UP/DOWN/FLAT/VOLATILE)
- impact_magnitude (LOW/MED/HIGH/CRITICAL)
- affected_lanes (WC/EC/GULF/ALL)
- affected_carriers (list or empty)
- effective_date (YYYY-MM-DD or null)
- confidence (0.0-1.0)
Return strict JSON.
```

Use `ai-multimodal` skill with Gemini — em có skill sẵn rồi.

## 9. Unresolved questions

1. **Panjiva/JOC budget** — MVP dùng free sources, sau có budget mở paid không?
2. **Capacity input cadence** — team fill xlsx khi nào? Daily? Tuần 1 lần? Hook Telegram Bot reminder?
3. **Report language** — hoàn toàn tiếng Việt như sample, hay bilingual?
4. **Distribution** — generated DOCX: email cho ai? Upload OneDrive? Telegram channel?
5. **Forecast granularity** — per carrier or per lane aggregate? Sample chỉ có lane-level (WC/EC/GULF).
6. **Carrier notices flow** — integrate với rate_importer ngay hay tách separate crawler?
7. **Historical backfill** — generate retroactive W11-W15 reports để có baseline không?
8. **"4C" naming** — em dùng Costing/Capacity/Catalyst/Change trong code. Confirm naming đúng không?
