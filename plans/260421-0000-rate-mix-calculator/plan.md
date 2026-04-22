---
title: "Rate Mix Calculator (FIX+FAK blend)"
description: "Manual-ratio FIX/FAK rate blender with tiered markup, 1-click QUOTE from Ribbon Pricing tab"
status: pending
priority: P2
effort: 2-3h
branch: main
tags: [erp-v14, vba, ribbon, pricing, rate-mix]
created: 2026-04-21
blockedBy: [260420-1700-auto-cnee-milestone-notify (Sync Milestones button — shares CustomUI_v14.xml + erp-v14-ribbon-callbacks.bas write lock)]
blocks: []
related: [260420-1700-auto-cnee-milestone-notify]
owner: Nelson
---

# Plan — Rate Mix Calculator

## Goal

Peak season pricing strategy: Custeam Pudong gives weekly FIX/FAK ratio per vessel. Nelson blends 2 buy costs at manual ratio, applies tiered markup, 1-click QUOTE with blended sell. MVP lives in existing Ribbon Pricing tab — no new sheet, no new module.

## Business Formula

```
blended_cost = (fix_qty × FIX_rate + fak_qty × FAK_rate) / (fix_qty + fak_qty)
fak_pct      = fak_qty / (fix_qty + fak_qty) × 100
markup       = TierLookup(fak_pct)   // see table below
sell         = blended_cost + markup
```

**Markup tier (per cont):**

| FAK% band | Markup USD |
|-----------|------------|
| 0–33 | 100 |
| 34–66 | 150 |
| 67–99 | 200 |
| 100 | 250 |

Example verified: 1 FIX $2,000 + 2 FAK $2,800 → blend $2,533 → FAK%=66.7% → tier `67-99` → $275 markup → sell **$2,808**.

## Scope (YAGNI)

**In:** Pricing Dry only (no Reefer RF), **4 container types: 20GP + 40HC + 45HC + 40NOR**. 1 POD/carrier pair at a time, 1 ratio applied to ALL applicable containers (auto-skip if peer row missing rate). Preview labels before QUOTE. **6 carriers** with both FIX+FAK contracts: CMA/HMM/HPL/ONE/YML/ZIM.

**Container coverage by carrier (verified from parquet 2026-04-22):**

| Carrier | 20GP | 40HC | 45HC | 40NOR |
|---------|------|------|------|-------|
| CMA | ✅ | ✅ | ✅ | ❌ |
| HMM | ✅ | ✅ | ✅ | ❌ |
| HPL | ✅ | ✅ | ❌ | ❌ |
| ONE | ✅ | ✅ | ✅ | ✅ (ONLY carrier) |
| YML | ✅ | ✅ | ✅ | ❌ |
| ZIM | ✅ | ✅ | ✅ | ❌ |

Cells without peer rate: auto-skip, label displays only blendable containers.

**Out:** Auto-ratio suggestion, Reefer 20RF/40RF FAK blend (no FIX peers exist), carrier-specific tier markup override, Quote_History reporting split, historical ratio tracking, Pudong API feed.

## Tier Markup Update (2026-04-22)

Nelson confirmed tighter margin bands for NHANH · CẠNH TRANH policy:
- Old: $150 / $200 / $275 / $350
- **New: $100 / $150 / $200 / $250** (tolerance smaller, more competitive)

## Container Handling Note

Existing `OnAction_GenerateQuote` (line 1288-1305 ribbon-callbacks.bas) auto-detects
containers from Pricing Dry row (20GP/40GP/40HC/45HC/40NOR/20RF/40RF) and presents
editable CSV popup. **No change needed** for 45HC/40NOR scenarios — Rate Mix
adds a SEPARATE path for FIX+FAK blend, not replacing the general quote flow.

## Architecture

```
Ribbon "Pricing" tab
    └── NEW group "grpRateMix"  (added AFTER grpSellRate, BEFORE grpQuoteAction)
        ├── editBox ebFixQty        (label "FIX ×", sizeString "00")
        ├── editBox ebFakQty        (label "FAK ×", sizeString "00")
        ├── labelControl lblMixSell (getLabel returns "Sell: $X,XXX (tier $YYY)")
        └── button btnMixQuote      (OnAction_MixQuote, large, imageMso "CreateTable")

VBA flow (extends erp-v14-ribbon-callbacks.bas):
    ebFixQty.OnChange / ebFakQty.OnChange
        → store m_FixQty / m_FakQty (module-level, top of file)
        → ComputeMix()
            • Validate: currently-selected Pricing Dry row is "Special Rate" OR "FAK" in Source col
            • Find PEER row (same Carrier+POL+POD+Place+COMMODITY) with OPPOSITE Source
            • Read 40HC rate from selected row + peer row
            • blended = weighted avg
            • tier markup = TierMarkup(fak_pct)
            • Store m_MixBlended40HC, m_MixMarkup, m_MixSell40HC
        → Invalidate lblMixSell → refresh label
    btnMixQuote.OnAction
        → Guard: m_Customer, m_Carrier, both rows found, both qty > 0
        → Call existing OnAction_GenerateQuote pathway BUT override:
            • Mar_40HC := m_MixMarkup       (bypass ebMar40HC)
            • Buy_40HC := m_MixBlended40HC  (weighted, not selected row's raw)
            • Sell_40HC := m_MixSell40HC
            • Remark col appended: "MIX fix=X fak=Y blend=$Z"
        → Status "PENDING" like normal quote
        → Single container (40HC) written, other cont cols left blank
```

## Phases

| # | File | Effort | Purpose |
|---|------|--------|---------|
| 01 | [phase-01-ribbon-group.md](phase-01-ribbon-group.md) | 45m | Add grpRateMix to CustomUI + 5 callbacks (get/onChange/getLabel) |
| 02 | [phase-02-blend-logic.md](phase-02-blend-logic.md) | 60m | VBA ComputeMix + TierMarkup + peer-row lookup |
| 03 | [phase-03-quote-integration.md](phase-03-quote-integration.md) | 45m | OnAction_MixQuote reusing Quotes sheet writer with override |
| 04 | [phase-04-test-verify.md](phase-04-test-verify.md) | 30m | 3 manual scenarios + rollback drill |

**Total: ~3h realistic.**

## Files Touched

**Modified (2 — SHARED WITH BLOCKING PLAN):**
- `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` — new `<group id="grpRateMix">` block inserted between grpSellRate (line 91) and grpQuoteAction (line 94)
- `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` — new module vars (top), ComputeMix sub, TierMarkup function, 5 ribbon callbacks, OnAction_MixQuote

**Unchanged:**
- Pricing Dry sheet (no schema change — existing `Source` col 9 already distinguishes)
- Quotes sheet (same header row, same Status pipeline)
- ERP/vba-v14-mirror/ (mirror auto-synced via reimport script)
- No new .bas module (respect KISS — goes into existing callbacks file)

## File Ownership & Blocker

**CRITICAL:** This plan requires write access to 2 files that another active plan also touches:

| File | This plan needs | Blocking plan (260420-1700 Sync Milestones) |
|------|-----------------|---------------------------------------------|
| CustomUI_v14.xml | Add grpRateMix in tabPricing | Added btnSyncMilestones in tabOperations grpTracking (DONE per file scan line 143) |
| erp-v14-ribbon-callbacks.bas | Add ~80 LOC block for mix logic | Added Btn_SyncMilestones_OnAction |

**Resolution:**
- Blocking plan status: `implemented-pending-soak` — already merged to CustomUI + .bas (verified via grep at plan time)
- → **Treat as SEQUENTIAL dep, NOT parallel.** Start this plan only after confirming blocking plan's bytes are committed to OneDrive canonical files (git log on mirror + file mtime check).
- If overlap detected (both modifying same line range), restructure: let blocking plan land first, rebase this plan's XML diff against post-merge CustomUI.

## Data Flow

```
Nelson selects row on Pricing Dry (e.g. COSCO POL=HPH POD=USLAX, Source="Special Rate", 40HC=$2000)
    ↓
Existing logic already populated m_Carrier, m_POL, m_POD, m_Place, m_Buy40HC, m_Source (line 710)
    ↓
Nelson types ebFixQty=1, ebFakQty=2 on ribbon
    ↓
OnChange fires → ComputeMix()
    ↓
Scan Pricing Dry for peer row:
  • same Carrier+POL+POD+Place+COMMODITY  (cols 4,1,2,3,5)
  • OPPOSITE Source value
  • Eff/Exp window overlap with selected row
    ↓
If found: blend 40HC rates, apply tier markup, update lblMixSell
If not found: label shows "⚠ No FAK peer for this lane" (ChrW for Unicode)
    ↓
Nelson clicks btnMixQuote
    ↓
OnAction_MixQuote → insert row at QUOTES_DATA_START=5 → fill:
  Customer, Carrier, POL, POD, Place, Via, Eff (min of 2 rows), Exp (min of 2 rows),
  Source = "MIX (1F:2A)",
  Buy_40HC = blended, Mar_40HC = tier markup, Sell_40HC = sell,
  all other cont cols = blank,
  Remark = "MIX fix=1 fak=2 blend=$2533 FIX_row=14 FAK_row=87",
  Status = "PENDING", StatusDate = Now
```

## Failure Modes & Mitigation

| # | Failure Mode | Severity | Mitigation |
|---|--------------|----------|------------|
| F1 | Peer row not found (lane only has FIX, no FAK yet) | High | Show ChrW warning on label, disable btnMixQuote via getEnabled callback |
| F2 | Peer row ambiguous (multiple FAK rows match same lane) | High | Use latest by Eff date; if tie, use row with 40HC > 0; last-resort first match + log row# in Remark |
| F3 | Nelson forgets which row was selected (stale m_SourceRow) | Medium | Reuse existing guard: `If m_Carrier = "" Then MsgBox "click row first"` (copy pattern from line 1260) |
| F4 | Both qty=0 or negative | Medium | Guard at ComputeMix entry: both must be >=1; clear blended vars, label shows "—" |
| F5 | Selected row is neither "Special Rate" nor "FAK" (e.g. "FIXED") | Medium | Case-insensitive check `UCase(m_Source) LIKE "*FAK*" Or "*SPECIAL*"`; else label "⚠ row not FIX/FAK" |
| F6 | 40HC rate = 0 on one of the rows | Low | Skip blend, show "⚠ no 40HC on peer row" |
| F7 | Ribbon callback crash breaks entire tab | Critical | Wrap all 6 callbacks in `On Error Resume Next` + `g_LastError` capture (existing pattern line 1651) |
| F8 | Quotes sheet schema drift (col order changes) | Medium | Use named header lookup (not hardcoded col numbers) — scan QUOTES_HEADER_ROW=4 once, cache positions |
| F9 | CustomUI reimport drops existing buttons | Critical | Use `customui_utils.py` pattern — patch ONE group, don't rewrite file; verify backup before+after |
| F10 | Unicode chars (⚠, ×) break VBA compile | Low | Use ChrW(9888) for ⚠, ChrW(215) for ×, per SYSTEM_STANDARDS RULE 5.x |

## Backwards Compatibility

- All existing Pricing tab buttons/edit boxes unchanged → Nelson's existing workflow intact
- Quotes sheet header unchanged → legacy quotes still read correctly
- Mix quotes marked `Source="MIX (XF:YA)"` — downstream reports can grep and exclude/include as desired
- No Active Jobs schema change, no CRM change
- Rollback = delete grpRateMix XML block + remove 6 Sub/Function blocks; no data migration needed

## Test Matrix (phase 04 detail)

| Scenario | FIX | FAK | Expected blend | Expected markup | Expected sell |
|----------|-----|-----|----------------|-----------------|---------------|
| Pure FIX | 3 | 0 | $2000 | $150 (0%) | $2150 |
| Balanced | 1 | 1 | $2400 | $200 (50%) | $2600 |
| FAK-heavy | 1 | 2 | $2533 | $275 (66.7%) | $2808 |
| Pure FAK | 0 | 3 | $2800 | $350 (100%) | $3150 |
| Missing peer | 1 | 1 | — | — | label warning, btn disabled |

## Success Criteria

- [ ] Ribbon loads without error after reimport (verify via `python scripts/check-vbe-settings.ps1` + manual open)
- [ ] All existing Pricing tab controls still functional (regression test: 1 normal QUOTE works)
- [ ] 4 numeric scenarios match table above within $1 rounding
- [ ] Missing-peer scenario shows warning, not crash
- [ ] `Source="MIX (1F:2A)"` visible in resulting Quotes row
- [ ] 1 live quote to real customer: Nelson sends + customer receives correct price
- [ ] No bloat on file size: .xlsm within +5KB of pre-change backup

## Rollback Plan

1. Keep backup of CustomUI_v14.xml and erp-v14-ribbon-callbacks.bas pre-change (dated copies in OneDrive `backups/`)
2. If broken after reimport: restore both files → re-run `reimport-erp-vba-modules.py` → verify ribbon reloads
3. Orphan mix-tagged quotes (if any) are harmless in Quotes sheet — no cleanup needed

## Open Questions

- [ ] Confirm tier 67–99%: use $275 flat or keep range $250-300 and prompt? **Assumption: flat $275 for MVP, prompt deferred to v2.**
- [ ] Should blend apply to 40GP + 20GP too, or ONLY 40HC for MVP? **Assumption: 40HC only (Nelson's 90% book).**
- [ ] When peer row found ambiguous, should we show picker? **Assumption: auto-pick latest Eff + log row# in Remark; picker deferred.**
- [ ] Where to store Custeam's weekly ratio guidance (for audit/recall)? **Deferred — not in MVP scope; Nelson enters ad-hoc.**
