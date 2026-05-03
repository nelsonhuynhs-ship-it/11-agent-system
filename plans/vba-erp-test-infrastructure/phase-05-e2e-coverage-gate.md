---
phase: 5
title: "E2E Coverage Gate"
status: completed
priority: P1
effort: "2h"
dependencies: [1, 2, 3, 4]
---

# Phase 5: E2E Coverage Gate

## Overview
Establish CI/CD-equivalent gates so that every new feature (Python or VBA) has regression test coverage before merge. Python E2E tests run in CI; VBA tests are developer-time gates.

## Requirements
- Functional: pre-commit hook + coverage rules for Python and VBA
- Non-functional: zero new tests required for existing features (just rules for new ones)

## Architecture

```
.pre-commit-config.yaml  →  pytest --collect-only gate
CONTRIBUTING.md           →  VBA + Python test rules
tests/integration/        →  Python E2E test location
```

**Two-track testing strategy:**

| Track | What it tests | Runs in CI? | When |
|-------|--------------|-------------|------|
| **Python E2E** | VBA + Python integration via COM | ✅ Yes | Every commit |
| **VBA Rubberduck** | VBA business logic in VBE | ❌ No | Developer-time |

## Python E2E Gate (CI-Enabled)

**Pre-commit hook** (`pre-commit-config.yaml`):
```yaml
- repo: local
  hooks:
    - id: pytest-collect-only
      name: pytest collection check
      entry: pytest tests/ --collect-only -q
      language: system
      pass_files: []
      files: ^tests/
```

**Coverage rule for new Python features:**
```
Every new ERP/jobs/*.py or ERP/intelligence/*.py module
MUST have a corresponding test in tests/integration/
with @pytest.mark.e2e marker.
```

## VBA Gate (Developer-Time)

**Rubberduck test requirement** (from Phase 4):
```
Every new VBA feature module bas<Feature>.bas
MUST have TestModule_<Feature>.bas with ≥3 test cases.
```

**Merge rule**: PR cannot merge unless Rubberduck test module exists for each new/modified VBA module.

## Integration Test Pattern

All Python E2E tests go in `tests/integration/` and follow this fixture pattern:

```python
@pytest.mark.e2e
def test_new_feature_works(erp_copy, excel_app):
    """New feature integration test."""
    wb = excel_app.Workbooks.Open(erp_copy)
    # Call VBA macro via COM
    wb.Application.Run("OnAction_NewFeature")
    # Verify sheet state
    ws = wb.Sheets("Active Jobs")
    assert ws.Range("A1").Value == expected
    wb.Close(SaveChanges=False)
```

## Related Code Files
- Modify: `.pre-commit-config.yaml` (add pytest-collect-only hook)
- Modify: `CONTRIBUTING.md` (add test requirements)
- Create: `docs/vba-rubberduck-guide.md` (Rubberduck setup + test rule)

## Implementation Steps

1. **Add pre-commit hook** — verify `pytest tests/ --collect-only -q` returns 0 (no collection errors)
2. **Mark existing integration tests** — add `@pytest.mark.e2e` to all tests in `tests/integration/`
3. **Add `tests/integration/test_feature_name.py`** stub for each future feature (template only)
4. **Write `CONTRIBUTING.md`** test section:
   - Python: `tests/integration/test_<feature>.py` required for new Python modules
   - VBA: `TestModule_<Feature>.bas` required for new VBA modules
   - CI gate: `pytest tests/ --collect-only -q` must pass
5. **Write `docs/vba-rubberduck-guide.md`** — 1-page guide: install Rubberduck → write first test → run Test Explorer

## Success Criteria
- [ ] `pytest tests/ --collect-only -q` runs without errors in pre-commit
- [ ] All `tests/integration/*.py` have `@pytest.mark.e2e`
- [ ] `CONTRIBUTING.md` documents both Python and VBA test requirements
- [ ] `docs/vba-rubberduck-guide.md` exists with Rubberduck setup instructions

## Risk Assessment
- **Risk**: pre-commit hook blocks developers if pytest not installed
- **Mitigation**: require pytest in setup.py / requirements-dev.txt; document in CONTRIBUTING.md
- **Risk**: Rubberduck tests still manual — developer forgets to write them
- **Mitigation**: PR reviewer checks for `TestModule_*.bas` existence; hard rule in CONTRIBUTING.md
