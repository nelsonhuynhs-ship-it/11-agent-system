---
status: pending
created: 2026-04-24
updated: 2026-04-24
priority: HIGH
effort: ~10h
blockedBy: []
blocks: []
related_plans:
  - 260416-email-nelson-solo-platform  # soft overlap email templates
---

# Rate Table v2 — Redesign Plan

## Context
- **Design doc (LOCK-IN):** `plans/reports/rate-table-v2-design-20260424.md` ✅ approved
- **Visual preview:** `plans/visuals/rate-table-v2-preview.html` ✅ approved
- **Root cause evidence:** `plans/reports/hotfix-send-a-debug-20260424.md` (separate hotfix)

## Problem (TL;DR)
`_query_best_rates` groupby("Carrier") + "latest Exp first" filter → rejects HPL SCFI (cheapest, 7-day validity) in favor of HPL FAK (expensive but validity xa hơn).
**Business impact:** ~$60K/week opportunity gap trên 5 USEC lanes.

## Goals
1. **G1** Surface HPL SCFI when cheapest (with "SCFI 7d" tag)
2. **G2** Default email to 10 POD (expand from 3)
3. **G3** TOP 3 distinct carriers per POD (no duplicates)
4. **G4** USATL routed RIPI via EC (not IPI via WC)
5. **G5** Side-by-side HPH/HCM layout + inland POD styling

## Phases

| # | Phase | File | Status | Effort | Critical |
|---|-------|------|--------|--------|----------|
| 1 | Fix `_query_best_rates` groupby bug | [phase-01-fix-query-bug.md](phase-01-fix-query-bug.md) | ⏳ Pending | 2h | 🔴 BLOCKER |
| 2 | TOP 3 distinct carriers selection | [phase-02-top3-carriers.md](phase-02-top3-carriers.md) | ⏳ Pending | 2h | 🟡 High |
| 3 | Gateway routing RIPI/IPI | [phase-03-gateway-routing.md](phase-03-gateway-routing.md) | ⏳ Pending | 3h | 🟡 High |
| 4 | HTML template side-by-side + theme | [phase-04-html-template.md](phase-04-html-template.md) | ⏳ Pending | 2h | 🟢 Medium |
| 5 | Smoke tests + rollout | [phase-05-smoke-tests.md](phase-05-smoke-tests.md) | ⏳ Pending | 1h | 🟢 Medium |

**Total:** ~10h · sequential (each phase blocks next)

## Scope (Files Touched)

| File | LOC | Phases |
|------|-----|--------|
| `email_engine/core/auto_rate_builder.py` | ~120 | 1, 2, 3 |
| `email_engine/config/default_routes.yaml` | ~40 | 2 |
| `email_engine/intelligence/builder.py` | ~30 | 2 |
| `email_engine/templates/email_rules.yaml` | ~25 | 4 |
| `email_engine/web_server.py` | ~60 | 2, 5 |
| Email HTML template renderer | ~80 | 4 |

**Total:** ~355 LOC · 6 files · no schema change · no new deps

## Dependencies
- **Internal:** Sequential — Phase N+1 requires N complete
- **External:** None (parquet/YAML SOT already in place)
- **Soft overlap:** `260416-email-nelson-solo-platform` (not started; email template coordination if runs parallel)

## Success Criteria (Plan-level)
1. `HCM→USSAV` → BEST = HPL SCFI $2,988
2. `HPH→USATL` → BEST = HPL via CHS (RIPI)
3. 10 POD email renders < 50KB HTML
4. All 3 carriers distinct per row
5. Existing `pytest email_engine/tests/` passes (no regression)
6. 5 smoke test CNEE confirmed send OK

## Rollback Strategy
- Git revert — atomic per phase (each phase = 1 commit)
- No DB migration
- No schema change
- YAML changes reversible by file revert

## Resolved Decisions (from design doc §8)
1. USATL gateway priority: **carrier preference** (cheapest wins)
2. SCFI refresh: **daily**
3. POD with 0 carriers: **skip silently**
4. Container display: **20GP + 40HQ both**
5. USATL RIPI vs IPI tie: **RIPI wins** (faster transit)

## Next Steps
1. Start Phase 1 — fix groupby key
2. Verify HPL SCFI surfaces via DuckDB smoke query
3. Commit Phase 1 → proceed Phase 2

---
**Rollout mode:** `--auto` fast (design locked, no research needed)
**Commit strategy:** 1 commit per phase, conventional commits (`feat:` / `fix:`)
**Test gate:** `pytest email_engine/tests/` must pass before each commit
