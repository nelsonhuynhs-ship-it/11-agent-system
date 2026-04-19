# Target_Watch sheet schema — S1 v2 contract

Shared contract between S1v2-VBA (writes) + S1v2-PY (reads + writes matches).

## Sheet name

`Target_Watch` in `ERP_Master_v14.xlsm`. Create if missing (Python `ensure_target_watch_sheet()`).

## Header (row 1, frozen, bold)

| Col | Name | Type | Writer | Notes |
|-----|------|------|--------|-------|
| A | Target_ID | text | VBA | `TW-YYYYMMDD-NNN` auto-gen |
| B | Created | datetime | VBA | Now() when Nelson adds target |
| C | QuoteID | text | VBA | Link to Quote row (e.g. `14APR-734`) |
| D | Customer | text | VBA | From Quote row |
| E | POL | text | VBA | e.g. HCM |
| F | POD | text | VBA | e.g. LAX/LGB |
| G | Carrier | text | VBA | From Quote row (may be blank → all carriers) |
| H | ContType | text | VBA | `20GP` / `40GP` / `40HC` / `ANY` |
| I | Target_USD | number | VBA | Customer's deal target |
| J | CurrentQuote_USD | number | VBA | What Nelson originally quoted (Sell_*) |
| K | Status | text | both | `WATCHING` / `MATCHED` / `EXPIRED` / `RESOLVED` |
| L | LastCheck | datetime | Python | Last time price_watch.py scanned this row |
| M | Matched_Rate | number | Python | Current buy+default_markup when Status→MATCHED |
| N | Matched_Carrier | text | Python | Which carrier hit target first |
| O | Matched_Date | datetime | Python | When alert fired |
| P | Remark | text | VBA | Free-text note |

## Status transitions

- `WATCHING` (initial) → `MATCHED` when `buy + DEFAULT_MARKUP <= Target_USD` found in Pricing Dry/Reefer
- `WATCHING` → `EXPIRED` when Created > 30 days ago
- `MATCHED` → `RESOLVED` when Nelson manually marks done (via ribbon button) OR quote status becomes WIN/LOST

## VBA contract

Function `WriteTargetWatchRow(qid, cust, pol, pod, carr, cont, target, currQuote, remark)` in `ERPv14Ribbon`.

## Python contract

Function `scan_target_matches(db_path)` in `ERP/intelligence/price_watch.py`:
- Read Target_Watch sheet rows WHERE Status=WATCHING
- For each row: check Pricing Dry/Reefer for carrier matching POL+POD+ContType
- If `MIN(buy) + 200 <= Target_USD` → update Status=MATCHED, fill L-O
- Also create summary in Price_Watch sheet under section `🎯 TARGET MATCHES`
- Send Telegram alert for each new MATCH

## DEFAULT_MARKUP

Hard-coded `200` USD initially. Future: read from `Markup_Store` per (carrier, lane).

## Idempotency

- VBA: before insert, check if `QuoteID + ContType + Target_USD` combo already exists → skip dup
- Python: `MATCHED` rows not re-scanned. `WATCHING` rescanned every Price_Watch run.
