---
name: ERP v14 Workflow Upgrade
slug: 260411-2121-erp-workflow-upgrade
status: DRAFT — pending Nelson approval
created: 2026-04-11 21:45 Asia/Saigon
owner: Nelson
blocks: []
blockedBy: []
related:
  - plans/reports/brainstorm-260411-2121-erp-workflow-upgrade-synthesis.md
  - plans/reports/audit-a-ribbon-ux.md (in this plan dir)
  - plans/reports/audit-b-parquet-query.md (in this plan dir)
  - plans/reports/audit-c-user-journey.md (in this plan dir — discard most, see synthesis)
  - docs/erp-automation-test-stack.md
---

# ERP v14 Workflow Upgrade

**Based on:** 3 parallel deep audits + synthesis brainstorm (see `related` above)
**Principle:** YAGNI / KISS / DRY — fix what's broken for Nelson's daily workflow, skip nice-to-haves
**Stealth mode:** PRESERVED throughout — no WebApp, no visible change for coworkers

## Goal

Upgrade Nelson's daily ERP workflow to eliminate friction in the hot path:
**search → load row → quote → mark win/loss → build image → create job**

Fix three categories of issues:
1. **UX friction** — stale ribbon on tab switch, non-cascading search, 32 MsgBox prompts
2. **Data correctness** — 45'HQ pivot bug, margin-per-carrier-only bug, legacy refresh.py
3. **Architecture drift** — two VBA trees, two refresh scripts, unused duckdb

## Success criteria (measurable)

- [ ] Switching `Pricing Dry` ↔ `Pricing Reefer` auto-refreshes ribbon state (0 extra clicks)
- [ ] Typing Carrier in search combo narrows POL/POD/Place dropdowns (cascading filter)
- [ ] Happy-path quote-to-job click count ≤ 10 (down from 16 per Audit C)
- [ ] Zero MsgBox blocking the happy path (errors only, info → status bar)
- [ ] `pytest tests/integration` shows `14 passed, 0 skipped` (up from 11/3 after MsgBox unblock)
- [ ] Margin persists per (carrier, lane) tuple — not clobbered across routes
- [ ] `refresh-v14.py` normalizes 45'HQ pre-pivot (zero orphan container rows)
- [ ] Legacy `ERP/core/refresh.py` + `ERP/vba/*.bas` marked deprecated via README stub
- [ ] All changes backwards-compatible with existing `ERP_Master_v14.xlsm` data

## Phase overview

| Phase | Tier | Scope | Effort | Blocks | Status |
|-------|------|-------|--------|--------|--------|
| **P1** | 1 | Sheet activate event + cascade search + row-1 reset | 2-3h | — | PENDING |
| **P2** | 1 | MsgBox refactor + g_TestMode flag (UNBLOCKS test stack) | 2-3h | P3 regression | PENDING |
| **P3** | 1 | Quote flow quick wins: Image bug, Customer validation, Margin default | 2h | — | PENDING |
| **P4** | 2 | Parquet 45'HQ normalize + legacy refresh.py kill | 1-2h | — | PENDING |
| **P5** | 2 | Margin per (carrier, lane) schema migration | 2-3h | — | PENDING |
| **P6** | 3 | Architecture docs + deprecation README stubs | 30 min | — | PENDING |

**Total estimate: 10-14 hours** across 2-3 sessions.

## Dependency chain

```
P2 (MsgBox + g_TestMode flag)
    ↓ UNBLOCKS
Task A P2 (3 ERP quote flow tests currently skipped with reason="MsgBox")
    ↓ ENABLES
P3, P4, P5 with regression safety net
```

Execute P2 **FIRST** in each session — unblocks test coverage for everything else.

## Phase files

- [Phase 1 — Sheet Activate Event + Cascade Search](phase-01-ribbon-tab-state.md)
- [Phase 2 — MsgBox Refactor + g_TestMode Flag](phase-02-msgbox-refactor.md) ⭐ BLOCKER
- [Phase 3 — Quote Flow Quick Wins](phase-03-quote-flow-quickwins.md)
- [Phase 4 — Parquet 45'HQ + Legacy Refresh Cleanup](phase-04-parquet-normalization.md)
- [Phase 5 — Margin Per-Lane Schema](phase-05-markup-per-lane.md)
- [Phase 6 — Architecture Docs + Deprecation README](phase-06-architecture-docs.md)

## Non-goals (YAGNI — explicitly deferred)

- ❌ Full API-first migration (Phase 2 in old memory) — needs separate sprint
- ❌ WebApp / Bot integration for quote flow — violates stealth mode
- ❌ Loss reason taxonomy / structured picklist — free text is fine
- ❌ Customer history quick view on ribbon — nice-to-have
- ❌ DuckDB migration for refresh-v14.py — YAGNI until refresh time >1min
- ❌ QuoteGroupID redesign — works fine per memory
- ❌ Rebuild ERP v15 from scratch — v14 is close to good, just polish

## Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| VBA changes break live ERP_Master_v14.xlsm | HIGH | ERP test stack (11 passed) is regression guard. Run before each commit. |
| MsgBox refactor breaks production error paths | MED | g_TestMode flag only suppresses in test mode; production paths untouched |
| 45'HQ pivot fix changes Pricing Dry row count | MED | Before/after row-diff test. Backup parquet first. |
| Margin schema migration loses existing markups | HIGH | Backup Markup_Store sheet pre-migration; dry-run script first |
| Legacy refresh.py still called by unknown code | MED | Grep + log deprecation warning before deletion |

## Integration with existing plans

**Tonight's ERP test stack (Task A — DONE):**
- P2 of THIS plan (MsgBox refactor) unblocks the 3 skipped tests
- After P2: `tests/integration/test_erp_quote_flow.py` → 3 passing instead of 3 skipped

**Rate pipeline reorg plan (`260411-2019-rate-pipeline-reorg`):**
- Orthogonal — touches `rate_importer.py`, this plan touches `refresh-v14.py` + VBA
- No conflict. Can run in parallel with this plan.

## Verification per phase

Each phase MUST end with:
1. Compile check (Python syntax OR VBA import)
2. `scripts\run-erp-tests.bat` → regression
3. Before/after screenshot (for UX phases)
4. Status update in this plan.md checkbox

## Unresolved questions (for Nelson)

1. **Audit C re-do?** — want fresh v14-accurate user journey audit, or trust my manual verification of the 4 big false claims?
2. **Margin granularity** — per-carrier only (current), per-(carrier, lane_region) (WC/EC/GULF), or per-(carrier, pol, pod) (full tuple)? Recommend lane_region as middle ground.
3. **g_TestMode scope** — wrap all 32 MsgBox, or only the happy-path critical ones (GenerateQuote, MarkWin, MarkLost, RefreshRates)?
4. **Legacy file handling** — delete `ERP/vba/` + `ERP/core/refresh.py` entirely, or leave with deprecation README?
5. **Phase execution cadence** — one marathon session (10-14h) or split into 2-3 sessions?
6. **Priority** — should P4 (data correctness) jump ahead of P1-P3 (UX) since data bugs silent-fail vs UX bugs are just annoying?
