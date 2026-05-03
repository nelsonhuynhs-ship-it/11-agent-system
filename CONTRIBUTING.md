# Contributing to Nelson Freight ERP

## Development Setup

```bash
# Python dependencies
pip install -r requirements.txt

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Verify test infrastructure
pytest tests/ --collect-only -q
```

## Test Requirements

### Python Tests

**Rule: Every new Python module in `ERP/jobs/` or `ERP/intelligence/` MUST have a corresponding test.**

| Module type | Test location | Required marker |
|------------|--------------|-----------------|
| Unit test | `tests/unit/test_<feature>.py` | `@pytest.mark.unit` |
| Integration test | `tests/integration/test_<feature>.py` | `@pytest.mark.e2e` |
| API test | `tests/test_<router>.py` | default |

**Running tests:**
```bash
# All tests
pytest tests/ -v

# Only fast tests
pytest tests/ -m "not slow" -v

# Specific file
pytest tests/test_rate_router.py -v
```

**pytest collection check (pre-commit):**
```bash
pytest tests/ --collect-only -q
# Must show "X tests collected" with 0 errors
```

### VBA Tests (Rubberduck)

**Rule: Every new VBA feature module `bas<Feature>.bas` MUST have a companion `TestModule_<Feature>.bas` with ≥3 test cases.**

Rubberduck is a free Excel add-in for unit testing VBA.
- Website: https://rubberduck-vba.com/
- Install: Download → run installer → enable in Excel VBE

**Writing a VBA test:**
```vba
' TestModule_MyFeature.bas
Private Sub Test_MyFeature_HappyPath()
    Dim result As Long: result = fnMyFeature("valid_input")
    Assert.areEqual 100&, result
End Sub

Private Sub Test_MyFeature_EmptyInput()
    Dim result As Long: result = fnMyFeature("")
    Assert.areEqual 0&, result
End Sub
```

**Running VBA tests:**
1. Open `ERP_Master_v14.xlsm` in Excel
2. VBE → Rubberduck menu → Test Explorer → Run All
3. All tests pass → safe to commit VBA changes

### Adding a New Feature

1. **Python feature:**
   - Write the module in `ERP/jobs/` or `ERP/intelligence/`
   - Write tests in `tests/integration/test_<feature>.py`
   - Run `pytest tests/` — all pass before commit

2. **VBA feature:**
   - Create `ERP/vba-v14-mirror/bas<Feature>.bas`
   - Create `ERP/vba-v14-mirror/TestModule_<Feature>.bas`
   - Open in Excel → Rubberduck → Run All → all pass before commit

## Architecture Principles

- **YAGNI**: Don't build features you don't need yet
- **KISS**: Simple code is better than clever code
- **DRY**: Extract repeated logic into shared helpers

## Module Structure

```
ERP/jobs/           ← Python job scripts (FastID, ReeferPlug, etc.)
ERP/intelligence/    ← Python intelligence scripts (PriceWatch, etc.)
ERP/quotes/         ← Python quote generation
ERP/vba-v14-mirror/ ← VBA source mirror (source of truth: OneDrive)
tests/              ← Python tests
tests/unit/         ← Unit tests
tests/integration/  ← Integration + E2E tests
scripts/com-e2e/     ← Standalone COM scripts (not pytest)
```
