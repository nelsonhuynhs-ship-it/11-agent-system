# ERP VBA — LEGACY v13 (DO NOT EDIT)

These `.bas` files are v13 code kept for git history only. **The live ERP uses v14**.

## Live v14 source of truth

```
D:/OneDrive/NelsonData/erp/
├── ERP_Master_v14.xlsm            ← main workbook (11 sheets)
├── erp-v14-quick-wins.bas         ← ERPv14Core module
├── erp-v14-ribbon-callbacks.bas   ← ERPv14Ribbon module
├── erp-v14-preset-dryreefer.bas   ← ERPv14Preset module
├── CostBreakdown.bas              ← CostBreakdown module (shared HDL rules)
├── CustomUI_v14.xml               ← ribbon definition (Pricing + Operations tabs)
├── refresh-v14.py                 ← parquet → xlsm refresh
└── customui_utils.py              ← CustomUI inject helper
```

## Why v14 lives on OneDrive, not repo

- **Stealth mode** — Nelson uses Excel at the office. Coworkers don't see a webapp.
  Keeping the `.bas` files on OneDrive means the Excel refresh/rebuild workflow
  never touches git.
- **Fast iteration** — VBA edits can be tested without a git commit cycle.
- **Backup** — OneDrive version history is the safety net.

## When working on v14

1. Edit the `.bas` files on OneDrive directly
2. Open `ERP_Master_v14.xlsm` in VBE → re-import modules
3. Save as `.xlsm`
4. Run `scripts\run-erp-tests.bat` for regression
5. Legacy files in this directory: IGNORE

## If you're an AI agent

**DO NOT read files from this directory when auditing v14 code.**
Read from `D:/OneDrive/NelsonData/erp/` instead.

See `docs/erp-v14-source-of-truth.md` for the full map, deprecation table,
and audit checklist.
