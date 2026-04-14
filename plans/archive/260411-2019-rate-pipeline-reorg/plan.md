# Rate Import Pipeline — Reorganization Plan

**Date:** 2026-04-11 | **Status:** DRAFT — pending Nelson approval
**Branch:** claude/dazzling-engelbart
**Source audit:** `plans/reports/audit-260411-rate-import-pipeline.md`

## Goal

Clean + centralize the rate import pipeline so file drift stops, mapping has a single source of truth, and task scheduler jobs are documented. **YAGNI / KISS / DRY.**

## Root causes identified

1. **Incoming/processed drift** — 3 FAK files live in BOTH `incoming/` and `processed/`
   - Cause 1: `scan_pricing_emails()` re-downloads emails every scan, always saves to `incoming/`, never checks `processed/` for duplicates (`rate_importer.py:367`)
   - Cause 2: When `shutil.move` hits `PermissionError` (pandas ExcelFile lock), code just warns → file stays in incoming forever (`rate_importer.py:651-655`)
2. **Mapping duplication** — `Pricing_Engine/Mapping/CARRIER_RATE_MAPPING.json` identical to `OneDrive/pricing/mapping/CARRIER_RATE_MAPPING.json` (verified: diff clean). No single owner — future edits will diverge.
3. **Dead files** — `email_engine/_backup/backup_20260320/Port_Code_Mapping_Final.xlsx` unused
4. **PUC logic split** — hardcoded carrier list in `rate_importer.py` vs `pipeline_rules.json` vs `master_loader_v2.py`
5. **Task scheduler opacity** — no doc listing which .bat runs when (tools/goclaw/bat has 4 wrappers, memory has partial info)

## Phase overview

| Phase | Goal | Effort | Files touched |
|-------|------|--------|---------------|
| **P1** | Quick cleanup — delete dead files, drain drift | 30 min | Delete-only, no code |
| **P2** | Fix incoming→processed drift bug | 1-2 hours | `rate_importer.py` |
| **P3** | Consolidate mapping to single OneDrive source | 1 hour | `shared/paths.py`, `rate_importer.py`, delete repo dupe |
| **P4** | Document task scheduler + folder contract | 30 min | `docs/rate-pipeline-contract.md`, memory update |

**Total:** ~3-4 hours. Can run in one session after approval.

## Phase files

- [Phase 1 — Cleanup dead files + drain drift](phase-01-cleanup-dead-files.md)
- [Phase 2 — Fix drift bug in rate_importer](phase-02-fix-drift-bug.md)
- [Phase 3 — Mapping single source of truth](phase-03-mapping-single-source.md)
- [Phase 4 — Document scheduler + folder contract](phase-04-scheduler-contract.md)

## Non-goals (YAGNI)

- ❌ PUC logic consolidation — too risky without test coverage, defer to post-P2-test-extraction
- ❌ Knowledge folder pruning — 372 JSONs work fine, no complaints
- ❌ Slim parquet deletion — unclear if it's still referenced, leave for later audit
- ❌ nmi_config.json cleanup — only 1 reference (`rate_monitor.py`), not blocking
- ❌ Refactor `master_loader_v2.py` — out of scope, stable

## Success criteria

- [ ] `incoming/` contains only files NOT yet imported (zero overlap with `processed/`)
- [ ] `CARRIER_RATE_MAPPING.json` exists in exactly ONE place (OneDrive/pricing/mapping/)
- [ ] Repo `Pricing_Engine/Mapping/` folder gone (or reduced to stub README pointing to OneDrive)
- [ ] `docs/rate-pipeline-contract.md` lists all cron jobs + folder responsibilities
- [ ] `scripts/run-erp-tests.bat` still passes (no regression)

## Dependencies

- Task A (ERP automation test stack) — DONE tonight, provides regression guardrail for P2/P3 changes
- OneDrive must be synced before running any phase
- Excel closed when running P1 delete + P2 test runs
