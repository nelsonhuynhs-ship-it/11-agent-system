---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code — requires writing a failing test first, watching it fail, then writing minimal code to pass, and verifying the cycle.
---

# Test-Driven Development (TDD)

> **Source:** obra/superpowers (skills.sh)
> **Applied to:** Nelson system — Bot modules, ERP scripts, WebApp

## Overview
Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

## When to Use
**Always:**
- New features
- Bug fixes
- Refactoring
- Behavior changes

## The Iron Law
```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

## Red-Green-Refactor

### RED - Write Failing Test
Write one minimal test showing what should happen.

**Requirements:**
- One behavior
- Clear name
- Real code (no mocks unless unavoidable)

### Verify RED - Watch It Fail
**MANDATORY. Never skip.**

```bash
python -m pytest path/to/test.py  # or: python test_script.py
```

Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

### GREEN - Minimal Code
Write simplest code to pass the test. Don't add features, refactor other code, or "improve" beyond the test.

### Verify GREEN - Watch It Pass
**MANDATORY.**

```bash
python -m pytest path/to/test.py
```

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix code, not test.

### REFACTOR - Clean Up
After green only:
- Remove duplication
- Improve names
- Extract helpers

Keep tests green. Don't add behavior.

### Repeat
Next failing test for next feature.

---

## Good Tests

| Quality | Good | Bad |
|---------|------|-----|
| **Minimal** | One thing. "and" in name? Split it. | `test_validates_email_and_domain_and_whitespace` |
| **Clear** | Name describes behavior | `test_1` |
| **Shows intent** | Demonstrates desired API | Obscures what code should do |

## Why Order Matters
Tests written after code pass immediately. Passing immediately proves nothing.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "TDD will slow me down" | TDD faster than debugging. |

## Example: Bug Fix (Nelson Bot)

**Bug:** Empty POL accepted in query

**RED**
```python
def test_rejects_empty_pol():
    from query_engine import FreightQueryEngine
    engine = FreightQueryEngine("test.parquet")
    result = engine.query_rates(pol="", place="Denver")
    assert result is None or len(result) == 0
```

**Verify RED** → FAIL: empty POL returns all rows

**GREEN**
```python
def query_rates(self, pol, place, ...):
    if not pol or not pol.strip():
        return []
    # ... existing logic
```

**Verify GREEN** → PASS

---

## Verification Checklist
Before marking work complete:
- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)

## Debugging Integration
Bug found? Write failing test reproducing it. Follow TDD cycle.

**Never fix bugs without a test.**

## Final Rule
```
Production code → test exists and failed first
Otherwise → not TDD
```
