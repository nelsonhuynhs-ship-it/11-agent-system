# Phase 1 — Cleanup dead files + drain drift

**Priority:** HIGH (quick win, zero risk) | **Status:** PENDING
**Effort:** 30 min | **Files touched:** delete-only

## Context

Audit report identified concrete scattered/dead files. This phase deletes them manually (or via short script) — no code changes, no business logic risk.

## Actions

### 1.1 Audit incoming/ vs processed/ overlap
```bash
# List files appearing in BOTH folders
comm -12 \
  <(ls "D:/OneDrive/NelsonData/pricing/incoming" | sort) \
  <(ls "D:/OneDrive/NelsonData/pricing/processed" | sort)
```
Expected duplicates (from 2026-04-11 verification):
- `FAK_20260408_Update rate to US CANADA_ 08 APR NO. 2.xlsx`
- `FAK_20260409_Update rate to US CANADA_ 09 APR NO. 1.xlsx`
- `FAK_20260410_Update rate to US CANADA_ 10 APR NO. 1.xlsx`

### 1.2 Decide keeper and drain drift
For each duplicate file: `processed/` is authoritative (successfully imported to parquet). Delete the `incoming/` copy — it's a re-download that never got cleaned up.

```powershell
# Run this PowerShell snippet (Nelson to execute manually — destructive)
$incoming = "D:\OneDrive\NelsonData\pricing\incoming"
$processed = "D:\OneDrive\NelsonData\pricing\processed"
Get-ChildItem $incoming | Where-Object {
    Test-Path (Join-Path $processed $_.Name)
} | Remove-Item -Verbose
```

### 1.3 Delete dead backup
```powershell
Remove-Item "D:\NELSON\2. Areas\Engine_test\.claude\worktrees\dazzling-engelbart\email_engine\_backup\backup_20260320\Port_Code_Mapping_Final.xlsx" -Verbose
```

Verify nothing else references it:
```bash
grep -r "Port_Code_Mapping_Final" --include="*.py" --include="*.json" .
```
(Expected: only in email_engine/_backup/ — safe to delete)

### 1.4 Verify SCFI file freshness
`incoming/` has `SCFI_20260410_HPL SCFI CONTRACT 41.xlsx`, `processed/` has `SCFI_20260403_HPL SCFI CONTRACT 40.xlsx`. Different numbers — N41 is newer, still pending import. **Do NOT delete.**

## Success criteria
- [ ] `incoming/` has zero files also present in `processed/`
- [ ] `email_engine/_backup/backup_20260320/Port_Code_Mapping_Final.xlsx` gone
- [ ] Remaining `incoming/` files are all pending real imports (N41 SCFI confirmed)
- [ ] pytest regression: `scripts/run-erp-tests.bat` still 11 pass / 3 skip

## Risk
- LOW — only delete files that have identical copies in processed/
- Rollback: restore from OneDrive version history (keeps 30 days)

## Next
P2 fixes the root cause so this drift never happens again.
