# Golden Principles — Nelson Pipeline

**Auto-generated:** 2026-04-29
**Source:** `~/.claude/agent-failures.db` — promoted when recurrence ≥ 3

---

## Philosophy

> "Golden principles are opinionated, mechanical rules that keep codebase legible for future agent runs."
> — OpenAI Codex pattern (verified 1M LOC)

These rules are **NOT** style preferences. They are failure-derived mechanical guarantees:
- If a failure appears 3+ times across sessions → promote to rule
- Rules are enforced via `verify-pipeline.bat` pre-spawn hook
- Human review section below for edge cases

---

## Auto-Promoted Rules (recurrence ≥ 3)

### G1 — Always check None before parquet access
- **Recurrence:** 5
- **Why:** Empty parquet returns DataFrame[0,0], but `.parquet` AttributeError if None
- **Fix pattern:** `if df is None or df.empty: return default`

### G2 — Carrier rate column names case-sensitive
- **Recurrence:** 4
- **Why:** Mix of `Carrier` vs `carrier` across files causes silent failure
- **Fix pattern:** `df.columns = df.columns.str.lower()` after load

### G3 — Email campaign name must match cnee_master.xlsx exactly
- **Recurrence:** 3
- **Why:** Case mismatch silently skips prospects
- **Fix pattern:** `campaign.upper()` before lookup

---

## Human-Reviewed Rules (static)

### H1 — All public functions have docstring + type hint
- Enforced by: R3 in verify-pipeline.bat
- Rationale: Self-documenting code reduces misinterpretation by agent runs

### H2 — No f-string SQL (parameterized only)
- Enforced by: R9 in verify-pipeline.bat
- Rationale: SQL injection risk, even in internal tools

### H3 — Paths via shared/paths.py only
- Enforced by: R1 in verify-pipeline.bat
- Rationale: Hardcoded D:/ or C:/ breaks portability, OneDrive path resolution

### H4 — Use logger, not print()
- Enforced by: R2 in verify-pipeline.bat
- Rationale: print() goes nowhere in production, logger writes to file

### H5 — No bare except:
- Enforced by: R5 in verify-pipeline.bat
- Rationale: Swallows errors silently, makes debugging impossible

### H6 — TODO must reference ticket (TODO: NF-XXX)
- Enforced by: R8 in verify-pipeline.bat
- Rationale: Orphaned TODOs indicate uncompleted work that should not ship

### H7 — Line length ≤ 120 chars
- Enforced by: R7 in verify-pipeline.bat
- Rationale: readability, terminal compatibility

---

## Whitelist Mechanism

Files or lines can opt-out of a rule with `# noqa: R<N>`:

```python
# noqa: R3 — third-party API, cannot add type hint
def complex_external_call(param):
    return external_lib.process(param)
```

Whitelist is **intentional violation** — must be reviewed annually.

---

## Update Process

1. Failure logged via `log-failure.py` script
2. When recurrence ≥ 3, `promote-to-rules.py` appends new G-rule
3. Next pre-spawn lint picks up updated golden-principles.md
4. Human review section: monthly review of G-rules for accuracy

---

## Verification

```bash
# Run lint on entire Engine_test
bash Engine_test/scripts/verify-pipeline.bat "D:/NELSON/2. Areas/Engine_test"

# Check specific file
bash Engine_test/scripts/verify-pipeline.bat "D:/NELSON/2. Areas/Engine_test/api/routers"

# Verify rule count
grep -c "^### G[0-9]" golden-principles.md
```