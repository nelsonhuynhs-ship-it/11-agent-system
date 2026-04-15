# ERP v4 — Project Standards (RAG Governance)

**RAG** = **R**egression prevention · **A**cceptance criteria · **G**overnance

This doc is the **defensive perimeter**. Every new feature, fix, or refactor
MUST be checked against these standards before shipping. Claude agents auto-load
this file via `.claude/skills/erp-governance/SKILL.md`.

---

## 1. Architecture standards

### 1.1 Source-of-truth files (never hardcode, always import)

| Asset | Source | Rule |
|---|---|---|
| Active Jobs col layout | `ERP/core/active_jobs_cols.py` → `COL` dict | Every Python helper imports `COL`; no hardcoded integers. VBA constants mirror manually — update both. |
| VBA ribbon callbacks | `D:/OneDrive/NelsonData/erp/erp-v14-jobs-automation.bas` | Single canonical file. No duplicates (`Name1`, `Name2` must be auto-cleaned). |
| VBA core ribbon | `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` | Edit carefully — ribbon buttons depend on it. |
| Ribbon XML | `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` | Must be re-injected into xlsm after edits via `customui_utils.py`. |
| Workbook | `D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm` | Never edit directly without `save_preserving_ribbon`. |
| Booking email rules | `ERP/carrier_rules/booking_rules.json` (v2.0 schema) | email_builder.py reads this — don't drift. |
| Commission/insurance | `ERP/data/commissions_rules.yaml` | cost_addons.py reads this. |
| Reefer plug fees | `ERP/data/reefer_freetime.yaml` | reefer_plug.py reads this. |
| Parquet rates | `D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet` | 6.9M rows; always filter last 30 days (fallback 60→90d). Never load all. |

### 1.2 Layer boundaries

```
VBA (ribbon callbacks)  ──shells out──▶  Python helpers  ──reads/writes──▶  ERP_Master_v14.xlsm
                                               ↓
                                         openpyxl + ribbon_guard
```

- VBA handlers do **coordination only** (show dialog, close workbook, call Python, reopen, show result).
- Python helpers do **all data work** (parquet reads, xlsm writes, file I/O).
- Ribbon XML defines **UI only** — no logic.

### 1.3 Required wrappers

- **Every openpyxl `wb.save()` on ERP_Master_v14.xlsm** → use `ERP.core.ribbon_guard.save_preserving_ribbon(wb, path)`. Otherwise customUI14.xml gets stripped and ribbon disappears.
- **Every new button**: ribbon XML → VBA handler → shells to Python. Never put heavy logic in VBA.

---

## 2. Code standards

### 2.1 VBA (erp-v14-*.bas)

**Unicode:** `Chr(n)` only supports 0-255. Use `ChrW(n)` for Unicode characters (→, ●, ○, ✓, 📧). See `docs/vba-gotchas.md` #1.

**Line continuation:** Never put a `_`-prefixed identifier at the start of a continuation line — VBA will concat `_` from previous line into `__`. See gotchas #2.

**Error handling:** Every `Public Sub OnAction_*(control As IRibbonControl)` must begin with `On Error GoTo ErrHandler` or `On Error Resume Next`. Never let a ribbon button error bubble up.

**Module-level state:** `Public g_State As X` reset to default on workbook open. Always check `If Len(s) = 0 Then s = default` before use.

**Cross-module calls:** Use `Application.Run "ModuleName.SubName"` wrapped in `On Error Resume Next` for resilience.

### 2.2 Python helpers

**Imports:** Every helper must import from `ERP.core.active_jobs_cols`:

```python
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core"))
from active_jobs_cols import COL, HDR_ROW, DATA_START
from ribbon_guard import save_preserving_ribbon
```

**Save:** Never `wb.save(path)` directly on ERP_Master_v14.xlsm. Always:

```python
save_preserving_ribbon(wb, path)
```

**CLI interface:** Every helper must accept `--erp <path>` and exit 0 on success, non-zero on error. Print human-readable log to stdout.

**Hyperlinks:** Setting `cell.value = None` does NOT clear hyperlinks. Must also `cell.hyperlink = None`. See gotchas #7.

### 2.3 Tests

**Location:** `tests/` (unit), `tests/integration/` (E2E), `tests/unit/` (isolated unit).

**Fixture-based:** Use `erp_copy` or `seeded_erp` fixtures from `conftest.py`. Never modify live ERP_Master_v14.xlsm.

**COL references:** Import COL from `active_jobs_cols`. No hardcoded integers in test code.

**Seed by field name:** `{"CRM_ID": "X", "Status": "Booked"}` not `{1: "X", 16: "Booked"}`.

---

## 3. Testing standards (minimum bar)

Every new feature MUST ship with:

1. **At least 1 happy-path test** — normal inputs, expected output.
2. **At least 1 edge-case test** — empty input, max boundary, wrong type.
3. **At least 1 error-path test** — verify graceful failure, no crash.
4. **Regression test** if fixing a bug — ensures same bug doesn't return.

Before commit: `scripts\verify-erp.bat` MUST exit 0.

Before ship: `pytest tests/ -q` MUST show `0 failed` (excluding pre-existing legacy failures documented in `docs/known-legacy-failures.md`).

---

## 4. Deployment standards

### 4.1 VBA changes

1. Edit `erp-v14-*.bas` in `D:/OneDrive/NelsonData/erp/`
2. Run `python ERP/core/install_jobs_automation.py` → auto-cleanup duplicates + re-import modules
3. Run `scripts/verify-erp.bat` → verify compile + no regression
4. Test in Excel

### 4.2 Ribbon XML changes

1. Edit `CustomUI_v14.xml` in OneDrive
2. Validate XML: `python -c "import xml.etree.ElementTree as ET; ET.parse(r'D:/OneDrive/NelsonData/erp/CustomUI_v14.xml')"`
3. Re-inject: `python D:/OneDrive/NelsonData/erp/customui_utils.py <xlsm> <xml>`
4. Run `scripts/verify-erp.bat`

### 4.3 Python helper changes

1. Edit under `ERP/`
2. CLI smoke: `python ERP/{path}/helper.py --help` or `--dry-run`
3. `pytest tests/test_{helper}.py -v`
4. `scripts/verify-erp.bat`

### 4.4 Schema changes (Active Jobs COL layout)

**VERY DANGEROUS** — migration breaks every Python helper + test + VBA handler. Only do if absolutely necessary.

Required steps:
1. Update `ERP/core/active_jobs_cols.py` first (single source of truth)
2. Run `python ERP/core/migrate_active_jobs_v4.py` to reorder existing workbook data
3. Update `ERP/core/seed_test_jobs.py` (uses COL dict — should auto-adapt)
4. Audit every Python helper: `grep -r "ws.cell(r, [0-9]" ERP/` — must all be `COL["..."]`
5. Audit every test: same grep on `tests/`
6. Update VBA AJ_* constants in `erp-v14-ribbon-callbacks.bas` MarkQuoteWin + CancelJob
7. Run `pytest tests/ -q` → expect 0 failed
8. Run `scripts/verify-erp.bat` → expect PASS
9. Backup live xlsm with timestamp before re-migrating

---

## 5. Change standards

### 5.1 Conventional commits

```
type(scope): <short summary>

Root cause / reasoning...

Verified: <test command + result>
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`.

Scopes: `erp`, `ribbon`, `vba`, `pricing`, `scripts`, `tests`, `ops`.

### 5.2 Known gotchas to check before editing

Read `docs/vba-gotchas.md` — 10 traps that already cost us time. Each has symptom + BAD / GOOD code.

### 5.3 Pre-flight checklist (every feature)

See `docs/feature-checklist.md` — 15 questions to answer before writing code.

---

## 6. Observability standards

### 6.1 Logs

- Every button handler in VBA writes `{button}_log.txt` in OneDrive\erp\ when it shells to Python
- Python stdout/stderr captured
- If button fails, MsgBox shows last 20 lines of log

### 6.2 Backups

- Before schema migration: `cp ERP_Master_v14.xlsm ERP_Master_v14_BACKUP_YYYYMMDD_HHMM.xlsm`
- Parquet has auto-backup via `_backup/` folder in `OneDrive\NelsonData\pricing\`

### 6.3 Version labels

RateVersions sheet in xlsm shows current FAK/SCFI/FIX/PUC versions in ribbon top-right. Check here first when pricing looks wrong.

---

## 7. Regression prevention system

3 layers of defense:

1. **Pre-commit:** `scripts/verify-erp.bat` — compiles VBA, checks modules, runs core pytest
2. **Post-deploy:** manual smoke test in Excel (click each new button)
3. **Continuous:** `pytest tests/ -q` in CI (or weekly manual)

Any regression caught → add a test that fails until root cause fixed.

---

## 8. When things break

See `docs/buttons-guide.html` troubleshooting table:

| Symptom | Likely cause | Fix |
|---|---|---|
| "Cannot run macro 'OnAction_X'" | Module not imported / duplicate module | `python ERP/core/install_jobs_automation.py` |
| Ribbon missing Pricing/Operations tabs | customUI14.xml stripped | `python customui_utils.py <xlsm> <xml>` |
| Excel closes but doesn't reopen (button click) | Python script crashed | Read `{button}_log.txt` in OneDrive\erp\ |
| Cannot execute code in break mode | VBE stuck in debug | Click Reset ⏹ in VBE, or kill Excel + reopen |
| "Syntax error" in ApplyBookingMailto | Line continuation `& _` + `_X` | Rename or reshape per gotchas #2 |

---

## 9. Meta: how to add a new rule here

When you find a new way to break the system:
1. Fix the immediate issue
2. Add a row to `docs/vba-gotchas.md` or this file
3. Add a check to `scripts/verify-erp.bat`
4. Add a test that would have caught it
5. Commit with reference to the failure

This doc is **living** — every bug makes it stronger.

---

**Maintained by:** Claude Code (auto-updated via `.claude/skills/erp-governance/SKILL.md`)
**Last audited:** 2026-04-15
**Reviewers:** Nelson + every Claude session editing ERP
