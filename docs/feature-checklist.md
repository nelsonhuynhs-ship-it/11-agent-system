# Feature Checklist — answer before writing code

Every new feature or non-trivial fix must pass this checklist. The cost of
answering 15 questions upfront is hours saved in debugging downstream.

Load with: `.claude/skills/erp-governance/SKILL.md` auto-triggers this when
user requests "add feature", "new button", "thêm tính năng", etc.

---

## A. Scope (1-5)

**1. What is the ONE sentence that describes this feature?**
> Example: "Auto-flag quotes where customer hasn't replied within 3 days."

**2. Which ERP layer is affected?**
- [ ] Ribbon XML (CustomUI_v14.xml)
- [ ] VBA handler (erp-v14-*.bas)
- [ ] Python helper (ERP/*.py)
- [ ] Data schema (Active Jobs cols, sheets)
- [ ] External data (parquet, Outlook, email_log.csv)

**3. What files will I create? What files will I modify?**
List explicitly. If modifying schema, trigger **Schema Change Protocol** (ERP_STANDARDS.md §4.4).

**4. Is this READ-only or WRITE to ERP_Master_v14.xlsm?**
- READ-only → no need to close Excel, fast UX
- WRITE → must close workbook → run Python → reopen → `save_preserving_ribbon`

**5. What's the minimal viable slice?**
Avoid scope creep. Cut to smallest useful unit first.

---

## B. Data dependencies (6-9)

**6. What input data does this feature need?**
- [ ] Active Jobs rows (cols needed: ...)
- [ ] Quotes sheet
- [ ] Pricing Dry / Reefer
- [ ] Outlook emails
- [ ] External file (path: ...)

**7. Is that data currently present in Nelson's workbook?**
- [ ] Yes → reference real cells
- [ ] No → seed test data via `ERP/core/seed_test_jobs.py` first, OR mock in test

**8. What output does this feature produce?**
- [ ] New sheet (name: ...)
- [ ] New cell values (which cols)
- [ ] New file on disk (path: ...)
- [ ] Just a MsgBox report

**9. Where does the output go? Who consumes it next?**
Draw the downstream flow. If no one consumes, probably dead code.

---

## C. Standards compliance (10-13)

**10. Which existing gotchas apply? (Read `docs/vba-gotchas.md` now)**
List applicable gotchas #1-10. Common ones for new VBA handlers:
- #1 Chr → ChrW for Unicode
- #2 Line continuation `& _` + `_X` trap
- #4 VBE Break on All Errors
- #6 `wb.save()` strips customUI

**11. Am I using source-of-truth imports? (ERP_STANDARDS.md §1.1)**
- [ ] Python: `from active_jobs_cols import COL`
- [ ] VBA: `AJ_*` constants from `MarkQuoteWin` layout
- [ ] No hardcoded col integers anywhere

**12. What's my error handling strategy?**
- [ ] VBA handler: `On Error GoTo ErrHandler` with MsgBox
- [ ] Python: try/except around file I/O, graceful exit code

**13. Does this button need a confirm dialog?**
If it closes Excel / takes >5s / writes to xlsm → YES. Show "Continue?" dialog.

---

## D. Testing strategy (14-15)

**14. What 3 tests prove it works?**
- [ ] Happy path (normal input → expected output)
- [ ] Edge case (empty data, max boundary, wrong type)
- [ ] Error path (missing input, bad format → graceful failure)

Write these as pytest in `tests/test_{feature}.py`.

**15. How do I run the regression check?**
```bash
scripts\verify-erp.bat    # must exit 0
pytest tests/test_{feature}.py -v
```

Both must pass before commit.

---

## Before writing any code

Answer ALL 15 questions in writing. If any answer is "I don't know" or "later"
→ stop. Research first.

If the answer document is under 10 lines → probably not thinking deeply enough.
If over 100 lines → maybe over-scoped, cut smaller.

---

## Anti-patterns to avoid

- ❌ "Let me just add a quick button..." (no plan, skips #5-#13)
- ❌ "I'll write tests later" (tests first or never)
- ❌ "This change shouldn't affect anything else" (audit before asserting)
- ❌ "Works on my machine" (run verify-erp.bat)
- ❌ "The old code did X so I'll just copy" (old code may have gotchas — check #10)

---

## Template (copy-paste for new feature doc)

Create `plans/{date}-{feature}/spec.md`:

```markdown
# Feature: ...

## Q1. One-sentence
...

## Q2. Layers
- [x] VBA
- [x] Python

## Q3. Files
- Modify: ...
- Create: ...

## Q4. READ or WRITE
WRITE (close + reopen Excel)

## Q5. Minimal slice
...

## Q6-9. Data
- Input: ...
- Output: ...

## Q10. Gotchas
- #1 Chr→ChrW because I use ●
- #6 save_preserving_ribbon

## Q11. Source of truth
- `from active_jobs_cols import COL`

## Q12. Error handling
- VBA: `On Error GoTo EH`
- Python: try/except

## Q13. Confirm dialog?
Yes — writes to xlsm

## Q14. Tests
1. Happy: mark WIN → tracking col has "1/7 BKG"
2. Edge: no data → "0 jobs tracked"
3. Error: corrupt file → graceful error MsgBox

## Q15. Regression
`pytest tests/test_new_feature.py -v`
`scripts\verify-erp.bat`
```
