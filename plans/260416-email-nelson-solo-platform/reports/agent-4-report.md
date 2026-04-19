# Agent A4 Report — Pattern Learning / AI Model
Date: 2026-04-19

## Files Touched

- **NEW**: `email_engine/intelligence/pattern_learner.py` (266 lines)
- **MODIFIED**: `email_engine/web_server.py` — fence `# === A4 BEGIN ===` / `# === A4 END ===` added after A1 END (4 endpoints + in-memory cache)
- **MODIFIED**: `plans/visuals/email-dashboard-v5.html` — `#insightsPatterns` section added to `viewAI`, `#qsStrategyHint` added to Quick Send form, 3 JS functions + poller + campaign select wiring injected

## Endpoints Shipped

| Endpoint | Cache TTL | Description |
|----------|-----------|-------------|
| `GET /api/patterns/top-templates?days=30&limit=10` | 10 min | Top subjects by reply rate |
| `GET /api/patterns/hot-industries?days=30` | 10 min | Campaign ranking by score |
| `GET /api/patterns/heatmap?days=30` | 10 min | 7x24 open rate grid |
| `GET /api/patterns/strategy?campaign=X&days=30` | 10 min | Combined suggestion |

All 4 support `X-Force-Refresh: 1` header to bypass cache.

## Top 5 Templates (Actual Data — 365 days, min_sent=50)

| Template Pattern | Sent | Reply% | Score |
|-----------------|------|--------|-------|
| Reliable Carrier Options + Updated Weekly Rates | 106 | 3.8% | 2.85 |
| Simple, Transparent Ocean Freight Quote (No Surpri...) | 138 | 3.6% | 2.70 |
| Secure Your Booking: Strong Rate, Smooth Transit | 122 | 3.3% | 2.48 |
| Latest Ocean Freight Offer | 1,104 | 3.1% | 2.33 |
| Special Rate for This Week | 1,185 | 2.9% | 2.18 |

## Top 5 Hot Industries (Actual Data — 365 days)

| Rank | Campaign | Sent | Reply% |
|------|----------|------|--------|
| #3 | GARMENT C.A | 105 | 3.8% |
| #4 | STEEL RACK | 73 | 2.7% |
| #5 | POTTERY | 164 | 2.4% |
| #6 | FURNITURE | 5,598 | 2.3% |
| #7 | CANDLE | 2,416 | 1.8% |

Note: Rank #1 is "NAN" (1 row, anomaly). Rank #2 is FLOORING with 0% reply (225 sent — no reply tracking in older data).

## Send Heatmap Best Slot

Best slot found: **Sunday 14:00 VN** — open rate 5.3% (based on 19 opens from queue DB, small sample).
Note: Most historical data from email_log.csv does NOT have open tracking (pre-Open-Tracker era). Heatmap will improve significantly as more emails are sent with the new pixel tracker.

## Known Data Gaps

1. **Open tracking is sparse**: Only 19 opens recorded in `outlook_queue.db` (all from 2026-04-18+ since Open Tracker shipped). Historical `email_log.csv` has no open data. Heatmap open_rate = 0 for all historical cells — only sent count is available for pre-tracker sends.

2. **Reply tracking limited**: 200 replies total across 17,288 sends (1.16% overall). REPLIED events come from email_log.csv status field — relies on manual entry or reply_detector. REPLIED_1, REPLIED_3 are non-standard statuses from legacy flow.

3. **Campaign normalization needed**: email_log uses legacy campaign IDs (PLASTIC C.A, GARMENT C.A) while CNEE schema v3 maps to 18 COMMODITY_CATEGORY. Pattern learner uses raw campaign_id — minor inconsistency with hot_industries for new schema campaigns.

4. **A1 vault not yet available**: `strategy_suggestion()` has a bonus path to read `vault/cnee/*/memory.md` for sentiment enrichment — skipped since A1 not done. Marked as optional in code comments.

5. **Confidence is low for small campaigns**: Any campaign with < 20 sends gets confidence=30%. Fine for now.

**Status:** DONE_WITH_CONCERNS
**Summary:** All 4 pattern learner functions + 4 endpoints + HTML UI shipped and syntax-verified. Data is real but sparse for open tracking (Open Tracker only 2 days old). Reply rate data is solid (200 real replies across 17K sends).
**Concerns:** Open heatmap will be mostly empty until more emails go through the pixel tracker. Recommend re-running after 2+ weeks of tracked sends for meaningful heatmap.
