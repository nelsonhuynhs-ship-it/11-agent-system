# ERP v14 Workflow Upgrade — Synthesis Brainstorm

**Date:** 2026-04-11 21:40 | **Author:** Claude | **Decision owner:** Nelson
**Based on:** 3 parallel audits (A=ribbon UX, B=parquet query, C=user journey) + my own verification

## Audit verification status

**IMPORTANT:** Before trusting audit findings, I verified each against live v14 code on `D:/OneDrive/NelsonData/erp/`:

| Audit | File looked at | Status | Action |
|---|---|---|---|
| **A — Ribbon UX** | `erp-v14-*.bas` on OneDrive ✅ | **VERIFIED** | Trust findings |
| **B — Parquet query** | `ERP/core/refresh.py` (legacy v13) ⚠ | **PARTIAL** | Kill legacy, keep 1 `refresh-v14.py` finding |
| **C — User journey** | `ERP/vba/QuoteBuilder_ERP.bas` (v13 legacy) ❌ | **DISCARD MOST** | Re-audit from v14 needed |

### Specific Audit C claims DEBUNKED vs v14 code
| Claim | v14 reality | Evidence |
|---|---|---|
| "Quote status NOT updated to WIN" | FALSE — Status updates correctly | `erp-v14-ribbon-callbacks.bas:1038` → `wsQ.Cells(r, 36).Value = "WIN"` |
| "Quote status NOT updated to LOST" | FALSE — Status updates correctly | line 1280 → `wsQ.Cells(r, 36).Value = "LOST"` |
| "Quote Image feature removed" | FALSE — exists at `OnAction_QuoteImage` | line 1526 |
| "Loss reason overwrites Note" | PARTIALLY TRUE — need re-verify v14 | line 1277 — writes to reason column, not Note column |

### Specific Audit B claims VERIFIED vs refresh-v14.py
| Claim | Reality | Evidence |
|---|---|---|
| "Missing Eff filter → 197K stale rows" | FALSE for v14 | `refresh-v14.py:68` — `RefreshDate = Eff.where(notna, Exp)` + line 79 filter |
| "No 15d→30d→90d fallback" | FALSE for v14 | lines 77-85 explicit cascade |
| "45'HQ not normalized pre-pivot" | TRUE for v14 (post-pivot rename risky) | lines 105-106 |
| "DuckDB unused" | TRUE | `db/duckdb_engine.py` exists, `refresh-v14.py` uses pandas |

## VERIFIED pain points (final list)

### Priority 1 — UX friction (high impact, daily pain)
1. **P1-1: No sheet activate event** — switching `Pricing Dry` ↔ `Pricing Reefer` does NOT refresh ribbon state. Nelson must click a data cell after every tab switch to re-trigger `LoadRowToRibbon`. Stale Buy20GP values shown when Reefer active.
   - File: `erp-v14-ribbon-callbacks.bas:429` — `LoadRowToRibbon` only wired via `Worksheet_SelectionChange`, no `Workbook_SheetActivate`
   - Fix: 5 lines in `ThisWorkbook.vba` — `Workbook_SheetActivate` → call `LoadRowToRibbon(ActiveCell.Row)` if sheet is a pricing sheet

2. **P1-2: Search combo doesn't cascade** — type Carrier=ONE, then POL dropdown still shows all POLs (not just ONE's). Nelson has to mentally filter.
   - File: `erp-v14-ribbon-callbacks.bas:185-340` — each `OnChange_Search*` writes to row 1 independently
   - Fix: ~30 lines — cascade filter: after combo change, rebuild other combos' item lists from filtered visible rows

3. **P1-3: Search row 1 persists across sheets** — filter "ONE" on Dry sheet, click Reefer tab, filter text still in row 1 but applied to different column structure → silent data mismatch
   - File: `Workbook_SheetActivate` (missing)
   - Fix: bundle with P1-1 — on sheet activate, clear row 1 search OR re-apply to new sheet

4. **P1-4: 32 MsgBox prompts** — GenerateQuote alone has 4 (validate Customer empty → validate Carrier empty → write row → success). Every extra click breaks Nelson's flow.
   - File: `erp-v14-ribbon-callbacks.bas` — 32 `MsgBox` occurrences
   - Fix: categorize → keep errors (5-10), convert success/info to status bar (15-20), add `g_TestMode` flag for headless test path (blocks ERP test stack P2)

### Priority 2 — Data correctness (silent failures)
5. **P2-1: Margin keyed by carrier only** — ONE carrier on 2 different routes (WC vs EC) gets same saved margin. Nelson tweaks WC margin, EC margin silently updates.
   - File: `erp-v14-ribbon-callbacks.bas:484-528` — `LoadMarkupForCarrier` / `SaveMarkupForCarrier` only use carrier name as key
   - Fix: extend `Markup_Store` schema → (carrier, pol_region) or (carrier, pol, pod) tuple; migrate existing rows

6. **P2-2: 45'HQ post-pivot rename risky** — `refresh-v14.py:105-106` renames "45'HQ" column to "45HQ" AFTER pivot. If a route has BOTH in raw data, they become separate columns, rename creates duplicate column name → second one overwrites first. 105K rows affected.
   - File: `refresh-v14.py:63-80`
   - Fix: normalize `Container_Type` column to "45HQ" BEFORE pivot, 1-line add: `df['Container_Type'] = df['Container_Type'].replace({"45'HQ": "45HQ"})`

7. **P2-3: Legacy `ERP/core/refresh.py` still broken** — missing Eff filter → 197K stale rows. If any code path still calls this instead of `refresh-v14.py`, silent data corruption.
   - File: `ERP/core/refresh.py:168-170`
   - Fix: grep for callers; kill the file OR redirect to `refresh-v14.py`; add deprecation error
   - Audit B already wrote fix diff — use it directly

### Priority 3 — Architecture drift
8. **P3-1: Two VBA code trees** — legacy `ERP/vba/*.bas` (v13) in repo vs. live `erp-v14-*.bas` on OneDrive. Audit C was confused. Any new contributor will be confused.
   - Fix: either (a) delete `ERP/vba/` entirely, (b) move `erp-v14-*.bas` into repo as master, or (c) add README in `ERP/vba/` saying "legacy, see OneDrive for v14"
   - Recommend: (c) README only — v14 lives on OneDrive for stealth-mode reason, don't move

9. **P3-2: Two refresh scripts** — `refresh-v14.py` (OneDrive, authoritative, well-designed) vs. `ERP/core/refresh.py` (repo, legacy, broken).
   - Fix: Same as P3-1 — README in `ERP/core/` pointing at OneDrive

10. **P3-3: DuckDB engine unused** — `db/duckdb_engine.py` exists, correctly queries parquet, claims 28× speedup. Never called from refresh-v14.py.
    - Fix: measure first. `refresh-v14.py` takes ~2 min for 84K charges. If <1min acceptable, YAGNI (don't migrate). If user wants faster, rewrite `refresh-v14.py` STEP 1-3 using duckdb queries → pandas → write.

### Priority 4 — Quick wins (low effort, high DX)
11. **P4-1: Customer free-text input** — no dropdown, no validation. Typo = orphan quote.
    - File: `erp-v14-ribbon-callbacks.bas` — Customer ComboBox (exists) reads from CRM sheet — need to verify if validation applied
    - Fix: ~20 lines — on `OnChange_Customer`, look up name in CRM sheet, red-highlight if not found, offer "Add new CRM row?" prompt

12. **P4-2: Margin entry is 7 fields** — every new quote Nelson re-types all 7 container margins even if 80% of the time he uses default
    - Fix: default margin profile per carrier (already have `LoadMarkupForCarrier` — extend it to return a "last used" snapshot); add "Apply default" button

13. **P4-3: Quote Image multi-row bug** (memory says `dùng Selection.Columns(1).Cells`)
    - File: `erp-v14-ribbon-callbacks.bas:1526` `OnAction_QuoteImage`
    - Fix: 1 line — use `Selection.Columns(1).Cells` instead of `Selection.Cells`
    - Bonus: auto-delete `_QuoteImg` sheet on cleanup

14. **P4-4: PUC lookup substring match** — Audit C claimed fragile (first 5 chars). I haven't verified v14's `LookupPUC`. Need to re-read.
    - File: `erp-v14-ribbon-callbacks.bas:533` `LookupPUC`
    - Fix: exact match first, fuzzy fallback; log mismatches

## Upgrade layout — 3-tier architecture

Based on verified pain points, em đề xuất layout 3 tier:

```
┌─────────────────────────────────────────────────────────┐
│ TIER 1 — UX Polish (1-2 ngày)                           │
│ (Excel-only changes, no Python dependency)              │
├─────────────────────────────────────────────────────────┤
│ • Sheet activate event wiring                           │
│ • Cascade search combos                                 │
│ • MsgBox → StatusBar conversion + g_TestMode flag       │
│ • Quote Image multi-row fix                             │
│ • Customer dropdown validation                          │
│ • Margin default snapshot                               │
│                                                         │
│ Output: ERP_Master_v14.xlsm (live edit VBA modules)     │
└─────────────────────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────────────────────┐
│ TIER 2 — Data Correctness (1-2 ngày)                    │
│ (Python refresh layer, parquet query)                   │
├─────────────────────────────────────────────────────────┤
│ • refresh-v14.py: normalize 45'HQ pre-pivot             │
│ • Kill / deprecate legacy ERP/core/refresh.py           │
│ • Markup_Store schema: (carrier, pol_region) key        │
│ • Add SCFI 7-day grace period                           │
│ • (Optional) duckdb migration if perf bottleneck        │
│                                                         │
│ Output: refresh-v14.py updated + data migration script  │
└─────────────────────────────────────────────────────────┘
             ↓
┌─────────────────────────────────────────────────────────┐
│ TIER 3 — Architecture Docs (30 min)                     │
│ (No code, just README stubs)                            │
├─────────────────────────────────────────────────────────┤
│ • ERP/vba/README.md → points to OneDrive v14            │
│ • ERP/core/README.md → refresh-v14.py is authoritative  │
│ • docs/erp-v14-source-of-truth.md                       │
└─────────────────────────────────────────────────────────┘
```

## Out of scope (YAGNI — defer)

- ❌ Full API-first migration (Phase 2 from memory) — too big, needs separate sprint
- ❌ WebApp/Bot integration for quote flow — separate sprint
- ❌ CRM full integration (FMC tier, billing terms auto-populate) — nice-to-have
- ❌ Customer history lookup on ribbon — nice-to-have
- ❌ Loss reason taxonomy — UX polish only, not correctness
- ❌ QuoteGroupID redesign — works fine per memory, don't touch
- ❌ WebApp ERP equivalent — Nelson uses stealth mode at office

## Dependency chain

```
Tier 1 P1-4 (MsgBox refactor with g_TestMode flag)
         ↓ UNBLOCKS
Task A P2 (ERP test stack — 3 quote flow tests currently skipped)
         ↓ ENABLES
Tier 2 (Python refresh changes with regression safety net)
```

I.e., Tier 1's MsgBox refactor unblocks the 3 skipped tests from tonight's ERP test stack, which then provides regression coverage for Tier 2 Python changes.

## Estimated total

| Tier | Effort | Blocking for |
|---|---|---|
| Tier 1 (UX) | 6-10h | Tier 2 (via test unblock) |
| Tier 2 (Data) | 6-10h | — |
| Tier 3 (Docs) | 30 min | — |

**Total: 12-20h.** Phase over 2-3 sessions. Stealth mode preserved throughout.

## Verification approach

Each tier ends with regression:
- Tier 1: Run `scripts\run-erp-tests.bat` → expect 14/0 pass (was 11/3) because MsgBox unblock
- Tier 2: Re-run refresh + pytest `tests/integration` → diff Pricing Dry rows before/after 45'HQ fix
- Tier 3: grep `ERP/core/refresh.py` and `ERP/vba/` → assert READMEs present

## Unresolved questions

1. **Audit C needs re-do** for v14 — want em spawn fresh agent to audit actual v14 quote flow accurately, or skip since I've already manually verified the big claims?
2. **Margin per-route vs per-carrier** — confirm anh muốn granularity (POL, POL+POD, POL+POD+Place)?
3. **DuckDB migration** — measure refresh time first? If <1min, YAGNI; if 2+min, upgrade?
4. **g_TestMode flag** — anh OK để em thêm `Public g_TestMode As Boolean` vào ERPv14Ribbon.bas + wrap 32 MsgBox calls? (This is the KEY unblock for test stack)
5. **`ERP/vba/` + `ERP/core/`** — delete, keep-with-README, or leave alone?
6. **Tier ordering** — làm Tier 1 trước (vì unblock test stack), or parallel Tier 1 + Tier 2?
