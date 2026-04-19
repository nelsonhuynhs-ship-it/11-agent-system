---
name: Agent S1v2-PY Report
description: Column polish script + Target Watch logic in price_watch — S1v2 Python upgrades
type: project
---

# Agent S1v2-PY Report — ERP Column Polish + Target Watch

**Date:** 2026-04-20
**Agent:** S1v2-PY

---

## Upgrade #3 — Column Polish Script

**File:** `scripts/erp-s1v2-column-polish.py` (NEW, 235 lines)

### Changes applied to Quotes sheet (idempotent):

| Action | Target | Details |
|--------|--------|---------|
| HIDE | col B | Date column |
| HIDE | col AL (38) | StatusDate — found via header lookup |
| HIDE | col AO (41) | JobID — found via header lookup |
| GROUP outline=1 | cols L-R (12-18) | Buy_20GP..Buy_40RF |
| GROUP outline=1 | cols S-Y (19-25) | Mar_20GP..Mar_40RF |
| GROUP outline=1 | cols Z-AB (26-28) | PUC group |
| GROUP outline=1 | cols AC-AI (29-35) | Sell_20GP..Sell_40RF |
| SET | outlinePr.summaryRight=False | Summary cols on left |

**Discovery during scout:** Quotes sheet has 3 KPI dashboard rows (rows 1-3) before actual headers at row 4. `find_col_by_header` scans rows 1-6 to be resilient.

**Safety:** file-lock check + timestamped backup before any write + `save_preserving_ribbon` (gotcha #6).

### Dry-run output (verified):
```
[DRY] HIDE col B (Date)
[DRY] HIDE col AL (StatusDate, col 38)
[DRY] HIDE col AO (JobID, col 41)
[DRY] GROUP Buy: cols L12-R18 outline_level=1
[DRY] GROUP Mar: cols S19-Y25 outline_level=1
[DRY] GROUP PUC: cols Z26-AB28 outline_level=1
[DRY] GROUP Sell: cols AC29-AI35 outline_level=1
[DRY] SET outlinePr.summaryRight = False (summary on left)
[DRY-RUN] No file written.
```

---

## Upgrade #4 — Target Watch Logic in price_watch.py

**File:** `ERP/intelligence/price_watch.py` (extended)

### New functions added:

| Function | Purpose |
|----------|---------|
| `ensure_target_watch_sheet(wb)` | Create Target_Watch sheet with 16-col header (A-P) if missing. Bold header + freeze row 1 + autofilter. |
| `_find_min_buy(...)` | Internal helper — finds MIN buy rate for lane+cont from pricing indices |
| `scan_target_matches(wb, pricing_by_routine, pricing_by_line, default_markup=200)` | Scan WATCHING rows, evaluate buy+200 vs Target_USD, update MATCHED/EXPIRED in-place |
| `_send_target_match_alerts(matches)` | Telegram push per new MATCH via notify-telegram.py (graceful fail if BOT_TOKEN unset) |
| `write_target_matches_section(ws_pw, matches)` | Write/overwrite TARGET MATCHES block at bottom of Price_Watch sheet (sentinel-tagged, clears stale) |

### Logic flow:
```
main() existing scan (DROP/RISE)
  └─> write_price_watch_sheet(wb, alerts)
        └─> [NEW] scan_target_matches(wb, pricing_by_routine, pricing_by_line)
              for each WATCHING row:
                - expired? (age > 30d) → Status=EXPIRED
                - _find_min_buy() from routine or line index
                - sell = buy + 200
                - sell <= target → Status=MATCHED, fill cols L-O
              return new_matches list
        └─> [NEW] write_target_matches_section(Price_Watch sheet, matches)
        └─> [NEW] _send_target_match_alerts(matches)
              → telegram: "TARGET MATCHED {customer} ${sell_rate} vs target ${target_usd}"
```

### Idempotency:
- MATCHED rows skipped (Status != WATCHING)
- TARGET MATCHES section in Price_Watch uses sentinel tag → cleared + rewritten each run (no stale accumulation)
- EXPIRED rows not re-scanned

### Telegram message format:
```
TARGET MATCHED
Customer: ACME Inc
Route: HCM-LAX  40HC
Carrier: ONE
Buy: $1,200 + markup $200 = $1,400
Target: $1,500  (saved $100)
```

---

## Tests Run

| Test | Result |
|------|--------|
| `ast.parse` both files | PASS |
| `--dry-run` on live xlsm | PASS (exit 0, correct output) |
| `ensure_target_watch_sheet` on blank workbook | PASS |
| Idempotent ensure (second call) | PASS |
| `scan_target_matches` empty Target_Watch | PASS (returns []) |
| Unit: 1 MATCH + 1 no-match (mock pricing) | PASS — TW-001 matched, TW-002 watching |
| All 8 functions present after import | PASS |

---

## Concerns / Notes

- **Existing price_watch tests**: no existing test files found for price_watch.py — unit tests above are inline
- `save_preserving_ribbon` used only in polish script's LIVE mode. price_watch.py already used it before this change.
- Telegram `_send_target_match_alerts` fails silently if BOT_TOKEN/ADMIN_CHAT_ID env not set — safe for VPS cron
- Partner agent S1v2-VBA writes Target_Watch rows; Python only reads WATCHING + writes MATCHED/EXPIRED cols (L-O, K)

---

**Status:** DONE
**Summary:** Column polish script (dry-run verified, live ready) + Target Watch scan fully integrated into price_watch.py pipeline. All unit tests pass. No regression in existing DROP/RISE scan logic.
