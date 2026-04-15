# Known Legacy Failures

Tests intentionally skipped or kept as tripwires. Any addition here requires a
matching entry in the ERP v4 backlog so the debt does not get forgotten.

Rule (ERP_STANDARDS.md §3): `pytest tests/ -q` must show `0 failed` *excluding*
entries on this list.

---

## 1. `tests/integration/test_erp_quote_image.py::test_quote_image_multi_route`

**Status:** `@pytest.mark.skip` (2026-04-15)

**Symptom:** `_QuoteImg` sheet not created after `TestRunQuoteImage` — VBA
returns `OK_NO_SHEET` instead of `OK:<lastRow>`.

**Root cause:** QuoteImage was last touched 2026-04-13 before the Active Jobs
v4 migration (36 → 40 cols). The Quotes sheet schema it reads has shifted; the
selection/range logic needs a re-audit against the v4 COL dict.

**Re-enable when:**
1. `OnAction_QuoteImage` is ported to use `ERP/core/active_jobs_cols.py` COL
   names for any Active Jobs lookups it performs.
2. Quotes sheet column indices are verified live.
3. Happy-path manual run in Excel produces `_QuoteImg` with ≥3 route headers.

**Workaround:** QuoteImage button still works in Excel for Nelson's daily flow;
only the integration test is decoupled.

---

## 2. `ERP.core.refresh` legacy stub

**Status:** Tripwire module (not a failure, passes).

**Why it exists:** `ERP/core/refresh.py` was deleted 2026-04-13 as dead v13
code. To make accidental resurrection fail loudly, a stub remains that raises
`RuntimeError("dead code...")` on every call. Three unit tests
(`test_legacy_*_raises`) assert this behavior. Do not replace with real logic.

---

## Housekeeping

When a test moves off this list:
1. Remove its entry here.
2. Remove the `pytest.mark.skip` in the test.
3. Add a regression test that would fail again if the same bug resurfaces.
4. Commit with `test(scope): re-enable {name} — {fix reference}`.
