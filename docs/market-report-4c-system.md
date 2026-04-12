# Market Report 4C System

Weekly market report generator for Nelson Freight — Vietnam→US/Canada freight forwarding.
Produces a Vietnamese DOCX with four streams:

| Stream | Source | Mode |
|---|---|---|
| **C**osting   | `Cleaned_Master_History.parquet` | Auto (DuckDB query) |
| **C**apacity  | `inputs/capacity-W{N}.xlsx`       | Manual (CS team fill) |
| **C**atalyst  | `inputs/catalysts-W{N}.yaml` (MVP fallback) | Manual / future Gemini crawl |
| **C**hange (forecast) | Derived from costing (baseline ±15%) | Auto |

Module path: `Pricing_Engine/market_report/`

## Quick start

```bash
# Generate report for current ISO week
python -m Pricing_Engine.market_report.cli --week current

# Generate for a specific week
python -m Pricing_Engine.market_report.cli --week 2026-W14

# Explicit prev/next override
python -m Pricing_Engine.market_report.cli --prev 2026-W14 --next 2026-W15 -v
```

Output location:
```
D:/OneDrive/NelsonData/pricing/market-reports/weekly/2026-W14/
  report-2026-W14-predict-2026-W15.docx
```

## Storage layout

```
OneDrive/NelsonData/pricing/market-reports/
├── weekly/
│   └── 2026-W15/
│       ├── 2026-W15-forecast.parquet   ← used by next-week backtest
│       └── report-2026-W15-predict-2026-W16.docx
├── inputs/
│   ├── capacity-template.xlsx          ← copy this to start a new week
│   ├── capacity-2026-W15.xlsx          ← team-filled
│   └── catalysts-2026-W15.yaml         ← manual seeds (fallback)
├── templates/
├── state/
│   └── crawler-state.json
├── catalyst-sources.yaml
└── backtest-log.csv                    ← appended every run
```

## Capacity input workflow

1. Copy `inputs/capacity-template.xlsx` → `inputs/capacity-2026-W{N}.xlsx`
2. CS team fills one row per carrier/lane/dimension observation during the week
3. Columns (all required):
   - `week` — `2026-W15`
   - `carrier` — `ONE`, `HPL`, `WHL`, `ZIM`, `MSK`, `CMA`, `YML`, etc.
   - `lane` — `WC`, `EC`, `GULF`, `ALL`
   - `dimension` — `space`, `equipment`, or `booking_policy`
   - `status` — `OPEN`, `TIGHT`, `FULL`, `ROLLING`
   - `score` — `1` (critical-tight) to `5` (abundant)
   - `notes` — free text
   - `entered_by` — `CS_team` / `Nelson` / mentee name
   - `entered_at` — ISO datetime

4. Run the CLI — loader silently ignores malformed rows and logs warnings.

Invalid rows are skipped (not fatal). Missing file = empty section in report.

## Catalyst crawler config

MVP uses a manual yaml seed file at `inputs/catalysts-{week}.yaml`. Example:

```yaml
- source: CarrierNotice
  category: surcharge
  headline: "HPL EFS $320/40HC from 23-Mar"
  body: "Hapag-Lloyd announces emergency fuel surcharge on TP non-FMC lanes."
  impact_direction: UP
  impact_magnitude: MED
  affected_lanes: [WC, EC]
  affected_carriers: [HPL]
  effective_date: 2026-03-23
  confidence: 0.9
  url: null
- source: JOC
  category: policy
  headline: "FMC rejects Maersk EBS waiver"
  body: "FMC declined Maersk's request for expedited EBS approval; 30-day notice required."
  impact_direction: DOWN
  impact_magnitude: LOW
  affected_lanes: [ALL]
  affected_carriers: [MSK]
  effective_date: null
  confidence: 0.85
```

Valid enums:
- `source`: `Panjiva` `JOC` `Xeneta` `CarrierNotice` `GoogleAlert` `Manual`
- `category`: `surcharge` `capacity` `geopolitical` `fuel` `labor` `policy` `weather`
- `impact_direction`: `UP` `DOWN` `FLAT` `VOLATILE`
- `impact_magnitude`: `LOW` `MED` `HIGH` `CRITICAL`

Catalysts are ranked by magnitude (`CRITICAL` → `LOW`) then confidence before rendering.

### Future: Gemini extraction

Phase 2 will extract catalysts automatically from:
1. `knowledge/` JSON email archive (carrier notices forwarded to `pricing@pudongprime.vn`)
2. Google Alerts RSS feeds
3. JOC / Panjiva paid APIs (budget permitting)

Wiring: `catalyst_crawler.py` will call the `ai-multimodal` skill with a JSON extraction prompt per news item. See brainstorm spec §8 for details.

## Backtest

Each run automatically compares the **previous** week's stored forecast parquet against actual lane averages computed from the main parquet, appending to `backtest-log.csv`:

```
logged_at, prev_week, lane, container, forecast_base, actual_avg,
error_abs, error_pct, model_version
```

Section V of the report renders the most recent 3 rows. If no forecast parquet exists for the prior week (first run, or no prior forecast), the section falls back to the last 3 rows of the log or displays a skip message.

## Adding manual catalysts

Fastest path to override auto-extracted catalysts:

1. Edit `inputs/catalysts-2026-W{N}.yaml`
2. Re-run `python -m Pricing_Engine.market_report.cli --week 2026-W{N}`

The loader merges manual + auto sources when both exist (auto path is currently stub).

## Architecture

```
cli.py
  └── report_generator.generate_weekly_report()
        ├── costing_extractor.extract_costing()       → DuckDB → parquet
        ├── capacity_loader.load_capacity()           → openpyxl → xlsx
        ├── catalyst_crawler.crawl_catalysts()        → yaml seed
        ├── _build_baseline_scenarios()               → simple ±15% band
        ├── backtest_logger.log_backtest()            → CSV append
        └── template.weekly_report_template.build_report()  → python-docx
```

Scenario engine is a placeholder. Wire `Pricing_Engine/forecast/` 6-agent stack here when ready (brainstorm §7).

## Testing

```bash
# Unit tests (schemas only, no data dependencies)
pytest tests/unit/test_market_report_schemas.py -v

# Integration smoke (generates DOCX to tmp, validates sections)
pytest tests/integration/test_market_report_generator.py -v
```

## Known gaps (MVP scope)

- Catalyst crawler: yaml-seeded only. Gemini extraction deferred.
- Forecast engine: baseline ±15% band. Real ML/stats model not wired.
- Distribution: DOCX saved to OneDrive only. No email/Telegram push yet.
- Historical backfill: no retroactive report generator for W11–W14.

See `plans/reports/brainstorm-260411-2043-market-report-4c-system.md` for the full architecture brainstorm and Option B scope.
