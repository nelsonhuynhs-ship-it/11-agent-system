---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior — requires root cause investigation before proposing fixes. Covers 4-phase debugging and the 3-fix architectural escalation rule.
---

# Systematic Debugging

> **Source:** obra/superpowers (skills.sh)
> **Applied to:** Nelson system — Bot, ERP, Data Pipeline, WebApp

## Overview
Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

## The Iron Law
```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use
Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Bot command errors
- ERP VBA errors
- Data pipeline issues

**Use ESPECIALLY when:**
- Under time pressure
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work

## The Four Phases

### Phase 1: Root Cause Investigation
**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Don't skip past errors or warnings
   - Read stack traces completely
   - Note line numbers, file paths, error codes

2. **Reproduce Consistently**
   - Can you trigger it reliably?
   - If not reproducible → gather more data, don't guess

3. **Check Recent Changes**
   - What changed that could cause this?
   - Recent code edits, new dependencies, config changes

4. **Gather Evidence**
   ```
   For EACH component boundary:
     - Log what data enters component
     - Log what data exits component
     - Verify environment/config propagation

   Run once to gather evidence showing WHERE it breaks
   THEN analyze evidence to identify failing component
   ```

5. **Trace Data Flow**
   - Where does bad value originate?
   - What called this with bad value?
   - Keep tracing up until you find the source
   - Fix at source, not at symptom

### Phase 2: Pattern Analysis
1. Find working examples in same codebase
2. Compare broken vs working — list every difference
3. Understand dependencies and assumptions

### Phase 3: Hypothesis and Testing
1. **Form Single Hypothesis** — "I think X is the root cause because Y"
2. **Test Minimally** — SMALLEST possible change, one variable at a time
3. **Verify Before Continuing** — Did it work? If not, new hypothesis. DON'T stack fixes.

### Phase 4: Implementation
1. **Create Failing Test Case** — simplest possible reproduction
2. **Implement Single Fix** — ONE change addressing root cause
3. **Verify Fix** — test passes, no regressions
4. **If Fix Doesn't Work:**
   - If < 3 attempts: Return to Phase 1
   - **If ≥ 3 attempts: STOP — question architecture**
   - Discuss with Sếp before attempting more fixes

---

## Red Flags - STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "I don't fully understand but this might work"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**

**ALL of these mean: STOP. Return to Phase 1.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too |
| "Emergency, no time for process" | Systematic debugging is FASTER than thrashing |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed or new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |

## Real-World Impact
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

## Related Skills
- **test-driven-development** — For creating failing test case (Phase 4)
- **verification-before-completion** — Verify fix before claiming success
- **auto-test-loop** — Automated fix-verify-retry cycle
