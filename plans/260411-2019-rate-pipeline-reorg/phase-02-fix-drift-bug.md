# Phase 2 — Fix drift bug in rate_importer.py

**Priority:** HIGH (root cause fix) | **Status:** PENDING
**Effort:** 1-2 hours | **Files touched:** `Pricing_Engine/rate_importer.py`

## Context

Bug: `incoming/` accumulates files forever. Two independent causes.

### Cause A — Re-download without dedup check
`scan_pricing_emails()` (line ~87-367) scans Outlook every run and writes every attachment to `INCOMING_DIR / target_name`. It never checks if `processed/target_name` already exists. So every cron tick re-downloads old files.

### Cause B — Silent move failure
`rate_importer.py:648-655`:
```python
try:
    shutil.move(str(fpath), str(dest))
except PermissionError:
    log.warning("File locked, skipping move: %s (will retry next run)", fpath.name)
```
When pandas holds an ExcelFile reference, the move fails → file stays in incoming → next run dedups the data but leaves the old file. Comment says "will retry next run" but there's no retry mechanism.

## Fix strategy

### 2.1 Dedup check in scan_pricing_emails()
Add one line before writing attachment to incoming:

```python
# rate_importer.py ~line 365, inside attachment download loop
target_path = INCOMING_DIR / target_name

# NEW: skip if already in processed/
if (PROCESSED_DIR / target_name).exists():
    log.debug("Skip re-download (already processed): %s", target_name)
    continue

# (existing save logic)
```

### 2.2 Close ExcelFile handles before move
The PermissionError is because pandas `ExcelFile(...)` isn't closed explicitly. Refactor the read to use context manager:

```python
# Wherever files are opened for reading
with pd.ExcelFile(fpath) as xl:
    df = pd.read_excel(xl, sheet_name=0)
# xl is closed → file no longer locked → move works
```

Grep for `pd.ExcelFile` in `rate_importer.py` + `master_loader_v2.py` and wrap each in `with`.

### 2.3 Retry loop with gc for stubborn locks
If `with` isn't enough (sometimes Excel COM holds the file from another process), add bounded retry:

```python
import gc, time

def safe_move(src: Path, dst: Path, retries: int = 3) -> bool:
    for attempt in range(retries):
        try:
            gc.collect()  # release any lingering handles
            shutil.move(str(src), str(dst))
            return True
        except PermissionError:
            if attempt < retries - 1:
                time.sleep(1.5)
    return False
```

Replace the line-651 move with `if not safe_move(fpath, dest): log.error(...)`.

### 2.4 Add drain_drift() utility
One-shot cleanup callable from CLI — deletes incoming files that already exist in processed:

```python
def drain_drift() -> int:
    """Delete incoming/* that already exist in processed/. Returns count."""
    removed = 0
    for f in INCOMING_DIR.glob("*.xlsx"):
        if (PROCESSED_DIR / f.name).exists():
            f.unlink()
            removed += 1
            log.info("Drained drift: %s", f.name)
    return removed
```

Wire into `if __name__ == "__main__":` block with `--drain` flag. Nelson can run once after P1 manual cleanup OR skip manual cleanup entirely and just `python rate_importer.py --drain`.

### 2.5 Regression test
Add to `tests/unit/` (no Excel needed):

```python
# tests/unit/test_rate_importer_drift.py
def test_drain_drift_removes_duplicates(tmp_path, monkeypatch):
    # arrange: fake incoming/processed with overlapping names
    # act: call drain_drift
    # assert: incoming/X.xlsx gone, processed/X.xlsx intact
```

## Implementation order

1. Read `rate_importer.py` lines 80-150 (scan_pricing_emails header) + 350-400 (attachment loop) + 630-660 (move block)
2. Add dedup check (2.1) + `safe_move` helper (2.3) + context manager (2.2) + `drain_drift` (2.4)
3. Write unit test (2.5)
4. Run `python -m pytest tests/unit/test_rate_importer_drift.py -v` → PASS
5. Run `python Pricing_Engine/rate_importer.py --drain` → reports 0 removed (P1 already cleaned)
6. Run `python -m pytest tests/integration` → 11 pass / 3 skip regression check

## Success criteria
- [ ] `safe_move` retries 3x on PermissionError
- [ ] `scan_pricing_emails` skips files already in `processed/`
- [ ] `drain_drift` CLI works: `python rate_importer.py --drain`
- [ ] Unit test covers drain_drift
- [ ] Integration test still green

## Risk
- MEDIUM — touches production import flow
- Mitigation: test on copy of `incoming/` first, keep OneDrive version history enabled, git commit before + after

## Next
P3 collapses the mapping duplication.
