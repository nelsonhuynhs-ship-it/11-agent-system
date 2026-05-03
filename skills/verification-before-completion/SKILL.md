---
name: verification-before-completion
description: Use when about to claim work is complete, fixed, or passing — requires running verification commands and confirming output before making any success claims. Evidence before assertions, always.
---

# Verification Before Completion

> **Source:** obra/superpowers (skills.sh)
> **Applied to:** Nelson system — Bot deploys, ERP refreshes, WebApp changes

## Overview
Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Bot runs OK | `python bot_v5.py` starts without error | "I checked the imports" |
| ERP refresh works | `python ERP/core/refresh.py` completes | "The script looks correct" |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!")
- About to commit/push without verification
- Relying on partial verification
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ runtime test |
| "I checked the imports" | Imports ≠ functionality |

## Nelson-Specific Verification

### Bot Changes
```bash
# Syntax check
python -c "import bot_v5; print('OK')"

# Full startup test (30s timeout)
timeout 30 python bot_v5.py

# Module import check
python -c "from query_engine import FreightQueryEngine; print('OK')"
python -c "from quote_formatter import format_quotation; print('OK')"
```

### ERP Changes
```bash
# Refresh script
python ERP/core/refresh.py

# Verify output
python -c "import openpyxl; wb=openpyxl.load_workbook('ERP_Master.xlsm'); print(f'Rows: {wb.active.max_row}')"
```

### WebApp Changes
```bash
# Build check
npm run build

# Dev server starts
npm run dev
```

## Key Patterns

**Tests:**
```
✅ [Run test command] [See: 34/34 pass] "All tests pass"
❌ "Should pass now" / "Looks correct"
```

**Build:**
```
✅ [Run build] [See: exit 0] "Build passes"
❌ "Linter passed" (linter doesn't check runtime)
```

## The Bottom Line

**No shortcuts for verification.**

Run the command. Read the output. THEN claim the result.

This is non-negotiable.
