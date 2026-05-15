# Task: {{PHASE_NAME}} — {{WORKFLOW_NAME}} workflow

<!-- 
PLAN TEMPLATE for MiniMax M2.7 delegation (used by ck:workflow v2.0)
Fill in placeholders {{...}} then pass to mm-delegate-phase.sh
-->

## Context
- **Workflow**: {{WORKFLOW_NAME}}
- **Phase**: {{PHASE_NUMBER}} — {{PHASE_NAME}}
- **Invoked by**: ck:workflow v2.0
- **Working dir**: {{ABSOLUTE_WORKING_DIR}}
- **Date**: {{ISO_TIMESTAMP}}
- **Model**: MiniMax-M2.7 (via sidecar)

## Reports to read (priority order — absolute paths)
<!-- List only reports that exist. Priority: security > code > ux > perf > design -->

1. `{{PATH}}/security-audit-report.md` ← TUYỆT ĐỐI ƯU TIÊN nếu có
2. `{{PATH}}/code-review-report.md`
3. `{{PATH}}/ux-review-report.md`
4. `{{PATH}}/perf-analysis-report.md`
5. `{{PATH}}/design-inspiration.md` ← chỉ implement nếu Opus đã confirm

## Source plan (nếu được invoke từ /ck:plan output)
<!-- Bỏ nếu không có -->
- Plan file: `{{PLAN_MD_PATH}}`
- Phase files: `{{PHASE_FILES_LIST}}`

## Your task
{{TASK_DESCRIPTION}}

Invoke the `{{SKILL_NAME}}` skill to do this work. The skill is available in Claude Code's skill registry — use the `Skill` tool to invoke it with appropriate args.

## Success criteria (acceptance test)
<!-- Must be verifiable — each checkbox has a concrete command or observable result -->
- [ ] {{CRITERION_1}}
- [ ] {{CRITERION_2}}
- [ ] {{CRITERION_3}}
- [ ] No test regressions (if tests exist)
- [ ] git status shows only expected files modified

## Constraints
- **Match existing code style** — read 2-3 reference files before writing
- **Do NOT touch**: {{FORBIDDEN_PATHS}}
- **Respect** `CLAUDE.md` rules in working dir
- **Max changes**: {{MAX_FILES}} files
- **Priority order** (for master-executor): security > code > ux > perf > design
- **If uncertain**: skip that change, report it in the "skipped" section — do NOT guess

## ERP safety (chỉ áp dụng khi scope chạm ERP/)
Nếu bất kỳ file nào trong `ERP/`, `erp-v14-*.bas`, `CustomUI_v14.xml`:
→ **STOP** ngay. Không tự chỉnh. Report back để Opus handle (VBA có compile gotchas).

## How to verify
```bash
{{VERIFY_COMMAND}}
```
Expected: {{VERIFY_EXPECTED_OUTPUT}}

## Report back (MANDATORY)
Return a structured response:

```
## Files modified
- `abs/path/file1.py` — <brief change description>
- `abs/path/file2.py` — <brief change description>

## Fixes applied (by source report)
- From security-audit-report.md:
  - [CRITICAL] {{issue}} → {{fix}}
- From code-review-report.md:
  - [HIGH] {{issue}} → {{fix}}

## Skipped / deferred
- {{item}} — reason: {{why}}

## Verification
- Ran: `{{VERIFY_COMMAND}}`
- Result: {{result}}

## git diff --stat
<paste output>
```

---

## Notes cho MiniMax M2.7

1. Bạn (MiniMax) có FULL Claude Code tool access: Read, Write, Edit, Bash, Glob, Grep, Skill.
2. Bạn đang chạy trên sidecar — không có conversation history, chỉ có plan này.
3. Đọc reports TRƯỚC KHI viết code. Không tự đoán.
4. Nếu report conflict với current code state (stale) → skip, report back.
5. Không delete/rename files unless explicitly listed in changes.
6. Không chạy `git commit` / `git push` — đó là việc của Opus hoặc git-commit phase.
