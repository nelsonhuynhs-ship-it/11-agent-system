# Phase 04 — Test & Verify

**Priority:** P2 · **Status:** pending · **Effort:** 30m · **Depends on:** phase 03

## Context Links

- Overview: [plan.md](plan.md) — test matrix (4 numeric scenarios)
- Phase 02: numerical guards + state machine
- Phase 03: quote writer

## Overview

Execute 3 manual test scenarios (per user requirement) + full regression sweep + rollback drill. Confirm MVP ready for production use.

## Key Insights

- Manual testing is acceptable for MVP per KISS principle — no pytest for VBA (out of harness)
- Must test on REAL Pricing Dry data, not synthetic rows, to catch lane-matching edge cases
- Save a snapshot of Quotes sheet BEFORE tests so rollback = delete 3-5 tagged rows
- Every scenario: note actual values in a test log (inline table below) — not just checkmarks

## Requirements

**Test dataset (live Pricing Dry):**
- Pick a real lane with BOTH FIX and FAK rows (Nelson chooses, e.g., `COSCO HPH→USLAX` if available)
- Record pre-test state: screenshot Quotes sheet top 10 rows + note exact FIX/FAK 40HC rates for the lane

## Test Scenarios

### Scenario A — Pure FIX (edge case)

| Step | Input | Expected |
|------|-------|----------|
| 1 | Click FIX row ($X) | Label: `Sell: $— (enter FIX× / FAK×)` |
| 2 | ebFixQty=3, ebFakQty=0 | Label: `Sell: $(X+150) (blend $X + $150)` · button enabled |
| 3 | Set Customer=TEST | Button enabled |
| 4 | Click MIX QUOTE | MsgBox confirms · Quotes row 5: Source="MIX (3F:0A)" Buy=X Mar=150 Sell=X+150 |

### Scenario B — Balanced 1:1

| Step | Input | Expected |
|------|-------|----------|
| 1 | Click FIX row ($X), peer FAK row = $Y | — |
| 2 | ebFixQty=1, ebFakQty=1 | Label: `Sell: $((X+Y)/2 + 200) (blend $((X+Y)/2) + $200)` |
| 3 | Click MIX QUOTE | Quotes row 5: Source="MIX (1F:1A)" Buy=(X+Y)/2 Mar=200 Sell=(X+Y)/2 + 200 |

### Scenario C — FAK-heavy 1:2 (spec example)

| Step | Input | Expected |
|------|-------|----------|
| 1 | Click FIX row $2000, peer FAK $2800 (manual test row if needed) | — |
| 2 | ebFixQty=1, ebFakQty=2 | Label: `Sell: $2,808 (blend $2,533 + $275)` |
| 3 | Click MIX QUOTE | Quotes row 5: Buy_40HC=2533 Mar_40HC=275 Sell_40HC=2808 Source="MIX (1F:2A)" Remark contains `fak%=67` |

### Scenario D — Missing peer (negative)

| Step | Input | Expected |
|------|-------|----------|
| 1 | Click a FIX row on lane with NO FAK row | Label: `⚠ No peer FIX/FAK on this lane` |
| 2 | Enter qty | Button stays disabled |
| 3 | Manually click button (via keyboard?) | MsgBox: "Rate Mix not ready: NO_PEER" |

### Scenario E — Wrong row type (negative)

| Step | Input | Expected |
|------|-------|----------|
| 1 | Click row with Source="FIXED" (not FIX/FAK) | Label: `⚠ Selected row not FIX/FAK` |
| 2 | Button disabled | — |

## Regression Sweep

| Control | Action | Expected |
|---------|--------|----------|
| Pricing tab → grpMargin (7 editBoxes) | Type value | Sell labels update |
| Pricing tab → btnQuote (normal) | Click with row+customer | Normal quote appears at row 5 (MIX quote now at row 6) |
| Pricing tab → btnQuoteBatch | Select 3 rows, click | 3 normal quotes appear at top, pushing prior down |
| Operations tab → btnSyncMilestones | Click | (blocking plan feature) still opens correctly |
| Operations tab → cmbMonth | Change month | Active Jobs + Archive filter correctly |

## Rollback Drill (dry run)

**Trigger condition:** if any test scenario fails with corruption (xlsm crash, ribbon broken, data loss).

1. Close xlsm WITHOUT saving
2. Restore `CustomUI_v14.xml` + `erp-v14-ribbon-callbacks.bas` from phase 01 backup folder
3. Run `reimport-erp-vba-modules.py`
4. Open xlsm → verify ribbon back to pre-mix state (no grpRateMix group)
5. Inspect Quotes sheet — delete any test rows tagged `Source LIKE "MIX%"` (row 5-9 likely)
6. Log incident in SYSTEM_STANDARDS incident section per project rule

## Implementation Steps

1. **Snapshot Quotes sheet:** screenshot or copy rows 4-20 to a scratch sheet for diff reference
2. **Execute scenarios A-E** in order, recording actual values in test log table below
3. **Execute regression sweep** — all 5 rows must pass
4. **Cleanup:** delete test-tagged Quotes rows (those with Customer="TEST" or Source LIKE "MIX%" created during test)
5. **Run validator:** `python scripts/validate-system.py` per SYSTEM_STANDARDS — must pass
6. **Git mirror sync:** `ERP/vba-v14-mirror/` receives updated `.bas` + `CustomUI_v14.xml` via reimport post-hook
7. **Commit:** conventional message `feat(erp-v14): add Rate Mix calculator (FIX+FAK blend with tier markup)` on main branch
8. **Update plan status:** change plan.md frontmatter `status: pending` → `status: completed`

## Test Log (fill during execution)

| Scenario | Date/Time | FIX rate | FAK rate | qty | Computed blend | Tier markup | Sell | Actual result | Pass? |
|----------|-----------|----------|----------|-----|----------------|-------------|------|---------------|-------|
| A | | | — | 3:0 | | 150 | | | |
| B | | | | 1:1 | | 200 | | | |
| C | | 2000 | 2800 | 1:2 | 2533 | 275 | 2808 | | |
| D | | — | — | — | — | — | — | warning label | |
| E | | — | — | — | — | — | — | warning label | |

## Todo List

- [ ] 1. Pre-test snapshot of Quotes sheet saved
- [ ] 2. Scenario A executed and logged
- [ ] 3. Scenario B executed and logged
- [ ] 4. Scenario C executed and logged (most important — spec example)
- [ ] 5. Scenario D warning verified
- [ ] 6. Scenario E warning verified
- [ ] 7. Regression sweep 5/5 pass
- [ ] 8. Test rows cleaned up
- [ ] 9. `validate-system.py` pass
- [ ] 10. Commit landed on main
- [ ] 11. plan.md status → completed
- [ ] 12. MEMORY.md updated with new project entry (optional: learn tier markup rule)

## Success Criteria

- 5/5 scenarios pass with exact numeric match on A/B/C
- 5/5 regression controls unchanged
- Zero xlsm corruption, zero ribbon load error
- validate-system.py pass
- Mirror `ERP/vba-v14-mirror/` in sync with canonical OneDrive files
- 1 real customer quote sent successfully using MIX QUOTE (within first week post-deploy)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Real Pricing Dry lacks lane with both FIX+FAK | Med | Med | Temporarily add synthetic FAK row for test, delete after |
| Scenario C exact values unavailable (no $2000/$2800 pair) | Med | Low | Substitute closest pair, recompute expected values in log |
| Cleanup forgets 1 test row | Low | Low | Status PENDING + Customer=TEST filter easy to grep |
| Git commit rejected by pre-commit hook | Low | Med | Follow rule 5.4 + hook output; don't bypass |
| Rollback drill itself breaks file | Low | Critical | Drill is dry-run — only execute if actual failure; backup dir immutable |

## Security Considerations

- Delete test rows — don't leave TEST customer in production Quotes
- No external API touched during tests

## Next Steps

- Soak period: 1 week of live use
- Week-1 retro: did Nelson actually use MIX QUOTE on ≥3 real quotes? If 0 uses → UX issue, revisit
- v2 candidates (if v1 successful):
  - Container grid (not just 40HC)
  - Auto-ratio suggestion from Custeam weekly memo parse
  - Reefer lane support
  - Historical mix-quote analytics tab
