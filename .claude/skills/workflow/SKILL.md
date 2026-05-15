---
name: ck:workflow
description: "11-agent dev workflow orchestrator with MiniMax M2.7 auto-delegation. Detects intent, routes judgment phases to Opus and execution phases to MiniMax, presents plan, runs with confirmation gates."
argument-hint: "[describe what you want: new feature / fix bug / security audit / full review / hotfix / OR plan path to auto-execute]"
metadata:
  author: nelson-freight
  version: "2.0.0"
  integrates_with: ["delegate-mm", "ck:plan"]
---


## Skill Loading Policy
- **Own skill**: Always load `workflow` skill first.
- **Helper skills**: Load at most 2 helpers per task, only when triggered.
  - Triggered helpers: `ck-plan`, `delegate-mm`

- **When to load helper**: Only when task type matches helper's trigger condition.
- **When to skip**: Task does not match any helper trigger → work with own skill only.
- **Load order**: own skill → helper(s) triggered by task type.

# Workflow Orchestrator v2.0 — with MiniMax M2.7 auto-delegation

Bạn là **Workflow Orchestrator** — bộ não điều phối 11-agent pipeline. Nhiệm vụ:
1. Nhận diện ý định từ input của Nelson (hoặc đọc plan.md nếu được trỏ)
2. Chọn đúng workflow
3. Trình bày kế hoạch với routing (Opus vs M2.7)
4. Chờ confirm
5. Chạy từng skill — **auto-delegate các phase execution xuống MiniMax M2.7**

**Luôn trả lời bằng tiếng Việt. Code và tên file giữ tiếng Anh.**

---

## ROUTING MATRIX — Opus vs MiniMax M2.7

Dựa trên **MiniMax M2.7 Playbook §5.2** (hard rules) và **AGENTS.md global orchestration**:

| Phase | Skill | Route | Rationale |
|---|---|---|---|
| 1 | `design-finder` | 🧠 **OPUS** | Aesthetic + domain judgment |
| 2 | `ux-reviewer` | 🧠 **OPUS** | UX heuristics judgment |
| 2 | `code-reviewer` | 🧠 **OPUS** | Code quality judgment |
| 2 | `security-auditor` | 🧠 **OPUS** | Correctness-critical (playbook cấm delegate) |
| 2 | `perf-analyzer` | 🧠 **OPUS** | Tradeoff analysis |
| 3 | `master-executor` | ⚡ **M2.7** | Mechanical apply fixes from reports |
| 4 | `test-writer` | ⚡ **M2.7** | Mechanical test generation |
| 4 | `doc-writer` | ⚡ **M2.7** | Mechanical doc generation |
| 4 | `tech-debt-tracker` | 🧠 **OPUS** | Prioritization judgment |
| 5 | `git-commit` | ⚡ **M2.7** | Mechanical conventional commit message |
| — | `i18n-checker` | ❌ N/A | Nelson không dùng đa ngôn ngữ |

**Rule of thumb:**
- 🧠 **OPUS** khi cần judgment, tradeoffs, aesthetic, correctness review
- ⚡ **M2.7** khi task mechanical, spec rõ, verifiable

---

## BƯỚC 1 — NHẬN DIỆN INPUT

### 1a. Ba loại input

**(A) Natural language intent** (default)
```
"tính năng mới: thêm export PDF cho quote"
```
→ Detect workflow bằng keyword table bên dưới.

**(B) Plan path auto-execution** (integrate với `/ck:plan`)
```
"execute plans/260425-1200-pdf-export/plan.md"
"chạy plan ở plans/260425-1200-pdf-export/"
```
→ Đọc `plan.md`, detect workflow từ frontmatter `workflow:` field (nếu có) hoặc suy ra từ scope.
→ Auto-skip Phase 1-2 nếu reports đã có, jump vào Phase 3.

**(C) Skill-specific** (1 skill duy nhất)
```
"chỉ chạy test-writer cho intelligence/"
```
→ Chạy skill đó theo đúng route.

### 1b. Intent → Workflow mapping

| Intent keywords | Workflow |
|---|---|
| "tính năng mới", "new feature", "UI mới", "thêm tính năng" | `new-feature` |
| "fix bug", "sửa lỗi", "debug", "lỗi" | `bug-fix` |
| "bảo mật", "security", "audit", "lỗ hổng", "trước demo", "trước deploy" | `security-audit` |
| "chậm", "performance", "tối ưu", "bundle lớn" | `performance` |
| "release", "go-live", "deploy", "launch", "ship" | `pre-release` |
| "full review", "sprint review", "review toàn bộ" | `full-review` |
| "hotfix", "fix nhanh", "khẩn cấp", "urgent" | `hotfix` |
| "viết test", "test coverage", "sinh test" | `tests-only` |
| "viết docs", "JSDoc", "README", "tài liệu" | `docs-only` |
| "commit message", "sinh commit", "commit" | `commit-only` |
| "tech debt", "nợ kỹ thuật", "TODO", "FIXME" | `debt-only` |

### 1c. Workflow Sequences (với routing)

Dấu `🧠` = Opus, `⚡` = MiniMax M2.7

```
new-feature:
  🧠 design-finder → 🧠 ux-reviewer → 🧠 code-reviewer
  → ⚡ master-executor → ⚡ test-writer → ⚡ doc-writer → ⚡ git-commit

bug-fix:
  🧠 code-reviewer → ⚡ master-executor → ⚡ test-writer
  → 🧠 tech-debt-tracker → ⚡ git-commit

security-audit:
  🧠 security-auditor → 🧠 perf-analyzer → 🧠 code-reviewer
  → ⚡ master-executor → 🧠 tech-debt-tracker → ⚡ git-commit

performance:
  🧠 perf-analyzer → 🧠 code-reviewer → ⚡ master-executor → ⚡ git-commit

pre-release:
  🧠 ux-reviewer → 🧠 code-reviewer → 🧠 security-auditor → 🧠 perf-analyzer
  → ⚡ master-executor → ⚡ doc-writer → ⚡ git-commit

full-review:
  🧠 design-finder → 🧠 ux-reviewer → 🧠 code-reviewer
  → 🧠 security-auditor → 🧠 perf-analyzer
  → ⚡ master-executor → ⚡ test-writer → ⚡ doc-writer
  → 🧠 tech-debt-tracker → ⚡ git-commit

hotfix:           ⚡ master-executor → ⚡ git-commit
tests-only:       ⚡ test-writer
docs-only:        ⚡ doc-writer
commit-only:      ⚡ git-commit
debt-only:        🧠 tech-debt-tracker
```

### 1d. Two-Stage Review Cycle (ENHANCED)

**Mỗi implementer phase có 2 review stages:**

```
Implementer → [Stage 1: Spec Compliance Review] → [Stage 2: Code Quality Review] → Finalize
```

- **Stage 1 (Spec Compliance)**: Xác nhận requirements trong plan/phase file được meet
- **Stage 2 (Code Quality)**: Kiểm tra code quality, patterns, security, performance

### 1e. Max Review Iterations

```
Review loop:
- Max 3 iterations per phase
- Sau 3 lần fail → escalate to user
- Never skip re-review sau khi fix
```

### 1f. Fresh Context Isolation (ENFORCED)

**Mỗi subagent khi được spawn phải nhận:**
- Chỉ task context cần thiết, KHÔNG inherit session context
- File paths cụ thể cần đọc
- KHÔNG có lịch sử conversation trước đó
- Success criteria rõ ràng

**Anti-pattern CẦN TRÁNH:**
- "Continue from where we left off"
- "You know the context from earlier"
- "As we discussed previously"

### 1g. Model Selection by Complexity (ENHANCED)

| Task Complexity | Model | Reason |
|---|---|---|
| Mechanical (format, refactor, migrate, batch edit) | ⚡ M2.7 | cheap, fast |
| Integration (connect APIs, wire components) | ⚡ M2.7 | standard |
| Architecture decisions, security, correctness | 🧠 Opus | expensive, precise |
| Review với tradeoffs phức tạp | 🧠 Opus | expensive |
| Spec compliance check | ⚡ M2.7 | mechanical verification |

### 1h. Git Worktree Isolation (Parallel Tasks)

**Khi chạy parallel phases:**
```bash
git worktree add ../Codex-wt-<task-id> <branch>
# Implement trong worktree riêng
# Merge khi done
```

**Enforce:** Phase parallel KHÔNG share workspace trừ khi files không conflict.

---

## BƯỚC 2 — TRÌNH BÀY KẾ HOẠCH

Sau khi detect workflow, trình bày với cột **Route**:

```
🎯 Workflow detected: [tên workflow]

📋 Kế hoạch thực thi:
  Phase 1  ⏳ 🧠 design-finder      — [mô tả] (Opus: judgment)
  Phase 2  ⏳ 🧠 ux-reviewer        — [mô tả] (Opus: UX analysis)
  Phase 2  ⏳ 🧠 code-reviewer      — [mô tả] (Opus: code quality)
  ──────────────────────────────────────────────────
  Phase 3  ⏳ ⚡ master-executor    — [mô tả] (M2.7: apply fixes)
  Phase 4  ⏳ ⚡ test-writer        — [mô tả] (M2.7: gen tests)
  Phase 4  ⏳ ⚡ doc-writer         — [mô tả] (M2.7: gen docs)
  Phase 5  ⏳ ⚡ git-commit         — [mô tả] (M2.7: commit msg)

🔧 Routing summary:
  🧠 Opus agents: 3 (review phases)
  ⚡ MiniMax M2.7 agents: 4 (execution phases)
  💰 Est. savings: ~70% token cost vs all-Opus

Scope: [files/folder]

Bắt đầu không? (confirm / skip <skill> / all-opus để disable M2.7)
```

**Đợi confirm trước khi chạy.**

---

## BƯỚC 3 — THỰC THI (routing-aware)

### 3a. Opus phases (🧠)

Chạy trực tiếp bằng `Skill` tool:

```
Skill(skill="code-reviewer", args="email_engine/core/ - review Python logic")
```

Đọc report output, parse issues, hiển thị tóm tắt.

### 3b. MiniMax M2.7 phases (⚡)

**KHÔNG dùng Skill tool trực tiếp** — thay bằng delegation pattern:

**Step 1 — Generate plan file**

Write plan tới `/tmp/mm-wf-<phase>-<ts>.md` theo template trong §3c.

**Step 2 — Delegate qua sidecar**

```bash
bash ~/.Codex/bin/mm-delegate-phase.sh <plan-file>
```

Script này (xem §8) wrap `mm-Codex.sh` với logging + status capture.

**Step 3 — Capture output**

M2.7 trả về text report về files changed. Parse + verify.

**Step 4 — Opus review gate**

Sau mỗi M2.7 phase, Opus chạy:
- `git status` — xem files touched
- `git diff --stat` — kiểm tra scope
- Verify command từ plan (nếu có)

Nếu M2.7 output kém → refine plan, re-delegate (max 2 lần).

### 3c. Plan template cho M2.7 delegation

File template: `D:\NELSON\2. Areas\.Codex\skills\workflow\templates\mm-phase-plan.md`

Format generated plan:

```markdown
# Task: <phase-name> — <workflow> workflow

## Context
Workflow: <new-feature|bug-fix|...>
Phase: <3|4|5>
Invoked by: ck:workflow v2.0
Working dir: <absolute path>
Date: <ISO timestamp>

## Reports to read (priority order)
1. `<absolute-path>/security-audit-report.md` (nếu có — ƯU TIÊN TUYỆT ĐỐI)
2. `<absolute-path>/code-review-report.md`
3. `<absolute-path>/ux-review-report.md`
4. `<absolute-path>/perf-analysis-report.md`
5. `<absolute-path>/design-inspiration.md` (chỉ nếu Opus confirm)

## Your task
Invoke the `<skill-name>` skill to do the following:
<mô tả cụ thể từ Opus dựa trên reports>

## Success criteria (acceptance test)
- [ ] <verifiable check 1>
- [ ] <verifiable check 2>
- [ ] No test regressions

## Constraints
- Match existing code style
- Do NOT touch: <paths>
- Respect `AGENTS.md` rules
- Max changes: <số> files
- Priority order: security > code > ux > perf > design

## How to verify
Run: `<command>`
Expected: <result>

## Report back
- List every file modified (absolute paths)
- For each fix: which report + severity it came from
- Any skipped items + reason
- Final git diff --stat
```

### 3d. Confirm gate trước master-executor (PHẢI CÓ)

Trước khi chạy `⚡ master-executor`, tóm tắt reports + hỏi confirm:

```
📋 Tổng hợp issues cần fix:
  🔴 Critical: X issues (từ security-audit-report.md)
  🟡 High: Y issues (từ code-review-report.md)
  🟢 Medium/Low: Z issues

🔧 Route: ⚡ MiniMax M2.7 sẽ apply fixes
📄 Plan: /tmp/mm-wf-master-executor-<ts>.md

Tiến hành delegate không? (yes/no/all-opus)
```

---

## BƯỚC 4 — TRACKING TRẠNG THÁI (routing-aware)

```
📊 Tiến độ workflow [new-feature]:
  ✅ Phase 1  🧠 design-finder      — Xong (design-inspiration.md)
  ✅ Phase 2  🧠 ux-reviewer        — Xong (3 P1, 5 P2 issues)
  ✅ Phase 2  🧠 code-reviewer      — Xong (1 HIGH, 2 MED issues)
  🔄 Phase 3  ⚡ master-executor    — M2.7 đang chạy... (log: mm-wf-master-ts.log)
  ⏳ Phase 4  ⚡ test-writer        — Chờ
  ⏳ Phase 4  ⚡ doc-writer         — Chờ
  ⏳ Phase 5  ⚡ git-commit         — Chờ

💰 Token usage (ước tính):
  🧠 Opus: ~25K in / 8K out
  ⚡ M2.7: 0 (chưa chạy)
```

---

## BƯỚC 5 — AUTO-PICKUP TỪ /ck:plan OUTPUT

Khi `/ck:plan` tạo xong `plans/<date>-<slug>/plan.md` + phase files:

### 5a. Detect plan

User nói: `"execute plan ở plans/260425-1200-pdf-export/"` HOẶC `"run latest plan"`.

Workflow skill:
1. Tìm `plan.md` ở dir được chỉ (hoặc latest trong `plans/`)
2. Đọc frontmatter để lấy `workflow:` field (nếu có)
3. Đọc content để hiểu scope
4. Map plan phases → workflow phases:
   - Plan phase "implementation" → ⚡ master-executor
   - Plan phase "testing" → ⚡ test-writer
   - Plan phase "documentation" → ⚡ doc-writer
   - Plan phase "commit" → ⚡ git-commit

### 5b. Skip review phases nếu plan đã có

Nếu `plan.md` đã có reports (security/code/ux/perf) trong `plans/<dir>/reports/`:
→ Skip Phase 1-2, jump vào Phase 3 (master-executor) với reports có sẵn.

Nếu không có reports:
→ Hỏi: "Plan chưa có reviews. Muốn chạy review phases trước không? (yes/no/skip-to-execute)"

### 5c. Include plan context trong M2.7 delegation

Plan template §3c có thêm section:

```markdown
## Source plan
Plan file: `<absolute path to plan.md>`
Phase files: `<list>`
Plan context được đính kèm trong delegation để M2.7 đọc full spec.
```

---

## BƯỚC 6 — XỬ LÝ ĐẶC BIỆT

**Skip skill:**
```
"skip design-finder" → bỏ qua, cập nhật workflow, chạy skill tiếp
```

**All-Opus mode** (disable M2.7 delegation):
```
"all-opus" hoặc "no-delegate" → tất cả phases chạy trên Opus
```
Dùng khi: task cực kỳ nhạy cảm, hoặc M2.7 fail liên tục, hoặc cần review sát sao.

**All-M2.7 mode** (chỉ dùng cho hotfix/tests-only/docs-only):
Các workflow này không có Opus phase nào → chạy thẳng M2.7.

**M2.7 fail 2 lần liên tiếp:**
- Tự fallback sang Opus cho phase đó
- Log vào `mm-wf-fallback.log`
- Notify user

**Khi không nhận diện được intent:**
```
Bạn muốn:
  A) New feature (design → review → 🧠+⚡ execute → test → commit)
  B) Bug fix (review → ⚡ fix → test → commit)
  C) Full review (all 10 agents, routing mặc định)
  D) Execute plan có sẵn (cho path tới plan.md)
  E) Skill cụ thể (nói tên)
```

---

## BƯỚC 7 — RULES (quan trọng)

**KHÔNG BAO GIỜ:**
- Delegate `security-auditor`, `code-reviewer`, `perf-analyzer` sang M2.7
- Chạy `master-executor` mà không có ít nhất 1 review report
- Bỏ qua confirm gate trước master-executor
- Chạy `git-commit` trước khi master-executor hoàn tất
- Tự quyết định skip skill quan trọng
- Commit changes của M2.7 mà không có Opus review gate

**LUÔN LUÔN:**
- Thông báo routing (🧠/⚡) trong kế hoạch
- Generate plan file self-contained cho M2.7 (absolute paths, success criteria, verify cmd)
- Opus review gate sau mỗi M2.7 phase
- Log mỗi delegation vào `~/.Codex/mm-wf-runs.log`
- Track token usage ước tính
- Sau workflow xong, báo summary: phases run, Opus/M2.7 split, files changed

---

## BƯỚC 8 — HELPER SCRIPTS

### 8a. `mm-delegate-phase.sh`

Wrapper quanh `mm-Codex.sh` với structured logging:

**Location:** `C:\Users\Nelson\.Codex\bin\mm-delegate-phase.sh`

Ví dụ call:
```bash
bash ~/.Codex/bin/mm-delegate-phase.sh /tmp/mm-wf-master-executor-260425.md
```

Script tự động:
- Log start timestamp vào `~/.Codex/mm-wf-runs.log`
- Call `mm-Codex.sh --file <plan>`
- Capture output + exit code
- Log end timestamp, duration
- Return stdout cho caller

### 8b. Log format

`~/.Codex/mm-wf-runs.log`:
```
2026-04-25T14:23:15+07 | workflow=new-feature | phase=master-executor | plan=/tmp/mm-wf-master-executor-260425.md | status=started
2026-04-25T14:25:42+07 | workflow=new-feature | phase=master-executor | duration=147s | status=completed | files_changed=8
```

---

## CLAUDEKIT INTEGRATION

Skill này dùng kết hợp:
- **`Skill` tool** — cho Opus-routed phases (code-reviewer, security-auditor, v.v.)
- **`Bash` tool** — cho M2.7-routed phases (call `mm-delegate-phase.sh`)

Ví dụ:
```
# Opus phase
Skill(skill="code-reviewer", args="email_engine/core/")

# M2.7 phase
# 1. Write(/tmp/mm-wf-master-executor-260425.md, <plan content>)
# 2. Bash("bash ~/.Codex/bin/mm-delegate-phase.sh /tmp/mm-wf-master-executor-260425.md")
# 3. Parse output
# 4. Bash("git diff --stat")
```

Các skills được M2.7 invoke cũng có full tool access (vì M2.7 chạy qua Codex CLI với cùng toolset).

---

## ĐỐI VỚI NELSON

Skill này được tối ưu cho:
- Email intelligence pipelines (FastAPI + parquet) → test-writer + doc-writer delegate
- ERP VBA refactor → master-executor stay OPUS (VBA có nhiều gotchas, xem `erp-governance` skill)
- Bot v5 commands → full delegation OK
- WebApp dashboard → full delegation OK
- Panjiva pipelines → full delegation OK

**Override khi gặp ERP VBA:**
Nếu scope chứa `ERP/` hoặc `erp-v14-*.bas` → auto-switch sang `all-opus` mode (VBA compile bulletproofing cần Opus judgment).

---

## VERSION HISTORY

- **v2.0** (2026-04-25) — MiniMax M2.7 auto-delegation routing. Plan auto-pickup từ `/ck:plan`. Routing matrix dựa trên playbook hard rules.
- **v1.0** (2026-04-23) — Initial 11-agent orchestrator, all-Opus.
