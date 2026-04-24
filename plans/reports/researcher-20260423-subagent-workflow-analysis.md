# Comprehensive Analysis: Subagent Workflow System
**Repository:** https://github.com/luonghaianh1208/subagent-workflow  
**Author:** Lương Hải Anh (GV CNT)  
**License:** MIT 2026  
**Analysis Date:** 2026-04-23  
**Analyzed by:** Research Agent (Nelson Freight AI)

---

## Executive Summary

**Subagent Workflow** is a **Vietnamese-first orchestration system** for automating development workflows via 11 specialized Claude AI agents. It provides structured automation for UI/UX design discovery, code review, security auditing, performance analysis, test generation, documentation, and git commit message generation—all coordinated through a single `CLAUDE.md` orchestrator file.

**Key Innovation:** Separates concerns into read-only review agents (discovery/analysis phases) and a single execution agent that applies fixes in strict priority order. Explicitly forbids automatic code modifications without user confirmation.

**Fitness for Nelson Freight:**
- ✅ Excellent fit for Engine_test parallel feature development (planner→implementer→tester→reviewer→docs→commit flow)
- ✅ Agent architecture mirrors your orchestration-protocol.md structure
- ✅ Vietnamese-first + English code perfectly aligns with CLAUDE.md language rules
- ⚠️ Requires adaptation: Nelson system uses subagent Task/Message protocol; this uses 11 separate agent files in `~/.claude/agents/`
- ⚠️ Not a replacement but a **complementary pattern** for local development workflows

---

## What Problem Does It Solve?

### Core Problems Addressed
1. **Fragmented development workflows** — code review, security, performance, testing, documentation each manual & scattered
2. **Missing cross-functional validation** — changes proceed without UX/security/perf sign-off
3. **Inconsistent git history** — commits lack conventional format and clear rationale
4. **Automation bottleneck** — no systematic way to batch apply approved fixes
5. **Knowledge loss** — design decisions, debt items, performance concerns not tracked systematically

### Intended User Pattern
Single developer (or small team) running **local development cycles** with AI-assisted review→fix→test→docs→commit pipeline. Explicitly NOT for CI/CD or remote orchestration.

---

## File Structure & Organization

```
subagent-workflow/
├── CLAUDE.md                    ← Orchestrator configuration (5,496 B)
├── README.md                    ← Main documentation (18,470 B)
├── LICENSE                      ← MIT license
└── agents/                      ← 11 specialized agent files
    ├── design-finder.md         (18,258 B)  [Phase 1: Discovery]
    ├── ux-reviewer.md           (20,002 B)  [Phase 2: Review]
    ├── code-reviewer.md         (19,237 B)  [Phase 2: Review]
    ├── security-auditor.md      (18,891 B)  [Phase 2: Review]
    ├── perf-analyzer.md         (20,955 B)  [Phase 2: Review]
    ├── master-executor.md       (10,834 B)  [Phase 3: Execute]
    ├── test-writer.md           (22,311 B)  [Phase 4: Post-Process]
    ├── doc-writer.md            (17,613 B)  [Phase 4: Post-Process]
    ├── i18n-checker.md          (21,313 B)  [Phase 4: Post-Process]
    ├── tech-debt-tracker.md     (20,712 B)  [Phase 4: Post-Process]
    └── git-commit.md            (18,810 B)  [Phase 5: Finalize]

Total: ~218 KB of markdown specifications
```

### Files NOT in Repository
- No Python scripts, JSON configs, or runnable code
- No skill definition files for Claude Code
- Pure specification/documentation repo
- Designed to be **manually installed** into user's `~/.claude/` directory

---

## System Architecture: 5-Phase Orchestration

### Phase Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: DISCOVERY                                          │
│ [design-finder] → Creates design-inspiration.md             │
│ → Waits for user confirmation                               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: REVIEW (Parallel, Read-Only)                       │
│ [ux-reviewer] → ux-review-report.md                         │
│ [code-reviewer] → code-review-report.md                     │
│ [security-auditor] → security-audit-report.md               │
│ [perf-analyzer] → perf-analysis-report.md                   │
│ ALL AGENTS: Read-only, no file modifications                │
│ → Wait for user confirmation + prioritization               │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 3: EXECUTION (Single Agent, Serial)                   │
│ [master-executor]                                           │
│ → Reads all *-report.md files                               │
│ → Prioritizes by severity (Security > Code > UX > Perf)     │
│ → Applies fixes issue-by-issue with verification            │
│ → Creates execution-report.md                               │
│ → Waits for user confirmation before proceeding             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: POST-PROCESSING (Sequential)                       │
│ [test-writer] → Generate *.test.ts / *.test.tsx             │
│ [doc-writer] → Update JSDoc, README, API docs               │
│ [i18n-checker] → Validate translations (optional)           │
│ [tech-debt-tracker] → Create tech-debt-register.md          │
│ → Artifacts committed to git before phase 5                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 5: FINALIZATION                                       │
│ [git-commit] → Generate conventional commit message         │
│ → Present for review (does NOT auto-execute)                │
│ → User manually executes: git commit -m "..."               │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Explicit Confirmation Gates**: Every phase boundary requires user confirmation before proceeding
2. **Read-Only Review**: Phases 1–2 agents NEVER modify source; only read + report
3. **Deterministic Execution**: Phase 3 (master-executor) applies fixes in strict priority order, re-reading source before each edit
4. **No Overlap**: "Each agent handles exactly one responsibility"
5. **Report-Driven**: All communication via markdown reports; no in-memory state between agents

---

## Detailed Agent Specifications

### Phase 1: Design Discovery

#### **design-finder.md** (18,258 B)
**Role:** Locates visual inspiration and design patterns for UI/UX projects

**Workflow:**
1. Analyzes project domain, current colors, typography, target audience
2. Searches Dribbble, Behance, Awwwards using WebSearch for design inspiration
3. Creates `design-inspiration.md` with 5–7 design recommendations
4. Includes: reference links, style descriptions, proposed color palettes, rationale
5. **BLOCKS** on user confirmation before proceeding to review phase

**Tools:** Read, Glob, Grep, WebSearch, Write (report only)

**Output Format:**
```markdown
# Design Inspiration Report

## Project Analysis
- Domain: [What the project is]
- Current Colors: [Hex codes found]
- Target Audience: [Who uses this]
- Style Direction: [Design direction]

## Design Inspiration Ideas
### 1. [Concept Name]
- Reference: [Working URL]
- Style Description: [Visual style]
- Proposed Colors: [Hex palette]
- Why It Fits: [Justification]
```

**Language:** Vietnamese responses; English only for design tools/references

---

### Phase 2a: UX Review

#### **ux-reviewer.md** (20,002 B)
**Role:** Comprehensive interface analysis without code modification

**Analysis Categories:**
- Visual consistency (colors, typography, spacing, shadows)
- Responsive design (breakpoints, mobile-first, touch targets)
- Accessibility (WCAG 2.1, semantic HTML, contrast, keyboard nav, ARIA)
- Interaction design (states, feedback, error handling)
- Code quality (CSS specificity, hardcoded values vs. variables)

**Priority System:**
- **P0 (Critical):** Accessibility violations, broken functionality
- **P1 (High):** Inconsistencies, poor UX patterns
- **P2 (Medium):** Minor issues, maintainability
- **P3 (Low):** Polish items

**Deliverable:** `ux-review-report.md` with issue tables (file, line, severity, description, suggestion)

**Tools:** Glob, Grep, Read, Write

**Constraints:** Read-only, no modifications to source files

---

### Phase 2b: Code Review

#### **code-reviewer.md** (19,237 B)
**Role:** Deep code analysis with severity classification

**Scope:**
- Logic errors (infinite loops, race conditions, unhandled edge cases)
- Variable naming clarity & consistency
- Code duplication, complexity, memory leaks, security anti-patterns
- TypeScript practices (type safety, unused imports, 'any' abuse)
- React/Next.js patterns (hooks, dependencies, component boundaries)
- Performance concerns (re-renders, memoization, bundle size)

**Severity Classification:**
- **CAO (High):** Runtime errors, security vulnerabilities, broken functionality
- **TRUNG (Medium):** Logic issues, maintainability, performance, type safety
- **THẤP (Low):** Style inconsistencies, code smell, optional optimizations

**Deliverable:** `code-review-report.md` with:
- Summary by severity
- Detailed issue listings (file, line, description, current code, suggested fix)
- Complete file inventory
- Additional recommendations

**Tools:** Glob, Grep, Read, Write

**Language:** Vietnamese feedback (code snippets in English)

---

### Phase 2c: Security Audit

#### **security-auditor.md** (18,891 B)
**Role:** OWASP Top 10 aligned vulnerability scanning

**Coverage (10 Categories):**
1. Broken Access Control
2. Cryptographic Failures
3. Injection Vulnerabilities
4. Insecure Design Patterns
5. Security Misconfiguration
6. Vulnerable Dependencies
7. Authentication/Session Flaws
8. Data Integrity Failures
9. Logging Deficiencies
10. SSRF Risks

**Special Features:**
- Pattern matching for exposed secrets (API keys, AWS credentials, GitHub tokens)
- Evidence-based reporting only (no false alarms)
- Credential redaction as [REDACTED] in output
- Context-aware analysis (reads suspicious files for full picture)

**Severity Tiers:** Critical, High, Medium, Info

**Deliverable:** `security-audit-report.md` with:
- Vulnerability title + OWASP mapping
- File location + line number
- Code evidence
- Risk description
- Remediation guidance
- Reference links

**Tools:** Glob, Grep, Read, Write

**Constraint:** Read-only; never outputs real credentials

---

### Phase 2d: Performance Analysis

#### **perf-analyzer.md** (20,955 B)
**Role:** Frontend & backend bottleneck detection with score calculation

**Analysis Scope:**

**Frontend:**
- Bundle size (heavy imports like `lodash`, `moment`, barrel imports)
- React performance (dependency arrays, missing `key` props, inline functions, unmemoized components)
- Images/Assets (next/image optimization, sizing, lazy-loading, WebP format)
- Code splitting (missing dynamic imports, React.lazy opportunities)

**Backend/API:**
- N+1 queries (loops with sequential DB calls)
- Missing indexes (unindexed WHERE clauses)
- Async optimization (sequential `await` chains that should be parallel)
- Response size (over-fetching, large payloads)

**Database:**
- Realtime vs. one-time fetch patterns
- Composite indexes configuration
- Security rule over-fetching
- Batch write opportunities

**Scoring System (0–100):**
| Severity | Deduction | Example |
|----------|-----------|---------|
| Critical | -20 | N+1 queries, 500ms latency |
| High | -10 | Missing memoization, sequential awaits |
| Medium | -5 | Inline functions, no lazy-loading |
| Low | -2 | Minor optimizations |

**Score Thresholds:**
- 90–100: Excellent
- 70–89: Good
- 50–69: Needs Work
- <50: Critical

**Deliverable:** `perf-analysis-report.md` with:
- Performance Score (0–100)
- Critical Issues (evidence, file paths, line numbers)
- Bundle Analysis table
- Quick Wins (<1 day fixes)
- Priority matrix (effort vs. impact)

**Tools:** Glob, Grep, Read, Bash, Write

**Agent Memory:** Maintains persistent memory of performance patterns and project-specific optimizations

---

### Phase 3: Execution (Master Executor)

#### **master-executor.md** (10,834 B)
**Role:** Phase 3 execution engine applying fixes from review agents in priority order

**Operational Steps:**

**Step 0 – Clarification:**
- Determine scope: all reports or specific ones?
- Any restricted files?

**Step 1 – Context Reading:**
- Load `CLAUDE.md` and `.claude/settings.json`
- Understand project conventions, tech stack, anti-patterns

**Step 2 – Report Inventory:**
- Locate all `*-report.md` files
- Report findings to user with clear existence status

**Step 3 – Issue Synthesis:**
- Extract all issues with severity, file paths, line numbers
- Create master issue list across all reports

**Step 4 – Execution Plan:**
- Present prioritized fix schedule segmented by severity
- Get user confirmation before proceeding

**Priority Hierarchy (Highest to Lowest):**
1. security-audit-report.md
2. code-review-report.md
3. ux-review-report.md
4. perf-analysis-report.md
5. design-inspiration.md (requires user confirmation)

**Execution Discipline (Per Issue):**
- Re-read source file immediately before editing
- Minimize changes — only fix reported problem
- Verify post-edit with TypeScript compilation checks
- Track completion status

**Deliverable:** `execution-report.md` with:
- All changes made
- Skipped issues with rationale
- Affected files list
- Next-phase recommendations

**Strict Prohibitions:**
- Never delete report files or `CLAUDE.md`
- No git operations (commit, push)
- No deployment commands
- No feature additions outside report scope
- No `.env` modifications

**Tools:** Read, Edit, Bash, Write

---

### Phase 4a: Test Writing

#### **test-writer.md** (22,311 B)
**Role:** Automatic test generation for TypeScript/React/Next.js projects

**Activation Triggers:**
- Explicit user request on specific files/components
- Code-review flagging missing coverage

**Core Constraints:**
- Never modify source code — only create `*.test.ts`, `*.test.tsx`, `*.spec.ts`, `*.spec.tsx`
- Read thoroughly before writing; understand logic first
- Write meaningful tests (not coverage-padding)

**Workflow:**

**Discovery Phase:**
- Detect test framework (Jest/Vitest/Playwright/Cypress)
- Identify testing libraries and naming conventions
- Use glob patterns + config file analysis

**Analysis Phase:**
- For each target file: identify exports, dependencies, logic branches, side effects, type signatures

**Planning Phase:**
- Create test matrix per function:
  - Happy paths
  - Edge cases (null/undefined/empty)
  - Error scenarios
  - Async flows
  - Priority ranking

**Generation Phase:**
- Produce tests following Arrange→Act→Assert format
- Components use React Testing Library
- Hooks use `renderHook`
- Utilities use direct function calls
- Minimal mocking approach

**Reporting Phase:**
- Place files per project convention (colocated or `__tests__` folders)
- Generate `test-writer-report.md` with:
  - Coverage summary
  - Test counts
  - Mocked modules list
  - Execution instructions

**Quality Standards:**
- Each test validates one behavior
- Clear, assertion-focused descriptions
- Avoid testing implementation details
- Mock only what's necessary
- Include meaningful error messages

**Special Cases:**
- Server Components
- Database queries
- Third-party APIs
- Environment variables (with tailored approaches)

**Tools:** Glob, Grep, Read, Write, Bash

---

### Phase 4b: Documentation Writing

#### **doc-writer.md** (17,613 B)
**Role:** Documentation creation and maintenance without touching source logic

**Supported Types:**

**README.md:**
- Project name, one-liner, features
- Quick start, environment variables
- Structure diagram, tech stack
- Contributing guidelines, license

**JSDoc/TSDoc Comments:**
- Functions: parameters, returns, error cases, usage examples
- React components: props with variant/state descriptions
- Custom hooks: parameters, return values, patterns

**API Documentation:**
- OpenAPI-style routes
- Request body, response structure
- Rate limits, error codes

**Workflow:**
1. Analyze existing documentation + project context
2. Determine scope (creation vs. updates)
3. Read source code for actual behavior
4. Generate documentation grounded in implementation
5. Report results with file counts

**Output Format (JSON Summary):**
```json
{
  "filesCreated": 5,
  "filesUpdated": 3,
  "jsdocAdded": 12,
  "details": [
    "Added JSDoc to 5 functions in src/api/routes.ts",
    "Created API documentation for POST /users endpoint",
    "Updated README with new installation instructions"
  ]
}
```

**Agent Memory:** Persistent memory stores documentation patterns, naming conventions, API structure, TypeScript idioms

**Tools:** Glob, Grep, Read, Write

---

### Phase 4c: i18n Validation

#### **i18n-checker.md** (21,313 B)
**Role:** Internationalization auditing (optional, triggered explicitly)

**Core Responsibilities:**

**Detection Tasks:**
- Compare translation completeness across all locales vs. base language
- Locate missing translation keys and untranslated placeholders
- Scan source for hardcoded user-facing strings bypassing i18n system
- Verify locale-aware formatting (dates, numbers, currencies)
- Flag obsolete/orphaned translation keys

**Quality Checks:**
- Pluralization and interpolation variable consistency
- RTL support for right-to-left languages
- Naming convention consistency (camelCase vs. snake_case)
- Structural issues (nested keys, duplicate values)

**Framework Detection:**
- Identifies library (next-intl, react-i18next, i18next)
- Maps all locale files
- Documents key naming conventions

**Deliverable:** `i18n-report.md` with:
- Missing translations by locale
- Potentially untranslated values
- Detected hardcoded strings with suggested keys
- Obsolete keys marked for removal
- Translation progress percentages
- Prioritized action items

**Scope Awareness:**
- User-facing strings → require translation
- Technical identifiers (component names, API methods, config values) → remain unchanged

**Tools:** Glob, Grep, Read, Write

**Language:** Vietnamese responses

**Critical Rule (from CLAUDE.md):**
> "KHÔNG tự động dùng i18n-checker hoặc setup i18n trừ khi" user explicitly mentions multi-language support OR codebase already has translation infrastructure. Browser `Intl` APIs do NOT constitute i18n implementation.

---

### Phase 4d: Technical Debt Tracking

#### **tech-debt-tracker.md** (20,712 B)
**Role:** Identify, categorize, and manage technical debt

**Seven Debt Categories:**
1. Code Debt (readability/maintainability)
2. Design Debt (suboptimal architecture)
3. Test Debt (inadequate coverage)
4. Documentation Debt (missing/outdated docs)
5. Dependency Debt (outdated/deprecated packages)
6. Security Debt (unresolved security risks)
7. Performance Debt (known efficiency issues)

**Three-Dimensional Assessment (Per Item):**
- **Impact:** 🔴 High (user-facing/blocks dev) | 🟡 Medium (slows team) | 🟢 Low (cosmetic)
- **Effort:** S (<1h) | M (1 day) | L (1 week) | XL (>1 week/design needed)
- **Risk:** Low (safe) | Medium (testing required) | High (regression risk)

**Debt Discovery Methods:**
1. Code scanning with grep markers: `TODO`, `FIXME`, `HACK`, `XXX`, `any` types, `@ts-ignore`, `eslint-disable`
2. Report mining from code-review-report.md, ux-review-report.md, execution-report.md
3. Dependency audits (package.json analysis)
4. Pattern detection (hardcoded values, debug logs, exposed configs)

**Deliverable:** `tech-debt-register.md` with sections:
- 🔴 **Critical** (fix this sprint)
- 🟡 **High** (plan for 2 sprints)
- 🟢 **Medium** (backlog)
- ⚪ **Low** (optional)
- ✅ **Resolved** (historical)

Each item includes: file location, description, impact, proposed fixes, source attribution

**Health Scoring (Baseline 100):**
| Category | Deduction |
|----------|-----------|
| Critical item | -15 |
| High item | -8 |
| Medium item | -3 |
| Low item | -1 |

**Score Thresholds:**
- 80–100 🟢 Healthy
- 60–79 🟡 Needs attention
- 40–59 🟠 At risk
- <40 🔴 Critical

**Tools:** Glob, Grep, Read, Write, Bash

**Agent Memory:** Persistent tracking of debt patterns, high-concentration areas, dependency vulnerabilities, code quality trends

---

### Phase 5: Git Commit Generation

#### **git-commit.md** (18,810 B)
**Role:** Generate high-quality conventional commit messages (does NOT execute commits)

**Conventional Commits Format:**
```
<type>(<scope>): <subject>
[optional body]
[optional footer(s)]
```

**Supported Types:**
- `feat` — new feature
- `fix` — bug fix
- `refactor` — code restructuring (no behavior change)
- `perf` — performance improvement
- `test` — test additions/modifications
- `docs` — documentation changes
- `style` — code style changes (formatting, semicolons, etc.)
- `chore` — build, dependency, or maintenance tasks
- `ci` — CI/CD configuration changes
- `revert` — revert previous commit
- `BREAKING CHANGE` — major breaking changes (with `!` suffix)

**Workflow (7 Steps):**
1. Analyze changes (git diff/status)
2. Determine type & scope
3. Write subject line (max 72 chars, imperative mood, no period)
4. Add body (if needed) — explain complex changes
5. Include footer (if needed) — issue links, co-authors, breaking changes
6. Present recommendation with explanation
7. Offer alternatives (if changes could be interpreted multiple ways)

**Special Cases:**
- Multiple unrelated changes → suggest splitting into separate commits
- Merge commits → use "Merge pull request" format
- Revert commits → document reason
- Initial commits → list setup items

**Critical Rule:** Does NOT execute commits — only generates message for user review and manual execution

**Example Output:**
```
feat(auth): implement JWT middleware for API routes

- Validates tokens in Authorization header
- Decodes JWT payload and attaches to request context
- Returns 401 for missing or invalid tokens
- Integrates with existing session validation

Resolves #42
```

**Tools:** Bash (git diff/status), Read, Write

**Agent Memory:** Persistent memory of project-specific commit patterns, scope naming conventions, team preferences

---

## Core Architectural Principles

### 1. Explicit Confirmation Gates
Every phase boundary requires user confirmation before proceeding. No automatic advancement through the workflow.

### 2. Read-Only Review Agents (Phases 1–2)
- **design-finder:** Creates report, waits for confirmation
- **ux-reviewer:** Analysis only, no code modifications
- **code-reviewer:** Analysis only, no code modifications
- **security-auditor:** Analysis only, no code modifications
- **perf-analyzer:** Analysis only, no code modifications

All generate markdown reports; none touch source code.

### 3. Single Execution Agent (Phase 3)
- **master-executor** is the ONLY agent that modifies code
- Reads all `*-report.md` files
- Prioritizes fixes by severity (security > code > UX > perf)
- Re-reads source file immediately before each edit
- Verifies changes with compilation checks
- Creates `execution-report.md` documenting all changes

This prevents conflicting edits and ensures deterministic behavior.

### 4. Post-Processing Agents (Phase 4)
Sequential, read-only analysis + file creation:
- **test-writer:** Generates test files only
- **doc-writer:** Generates/updates documentation only
- **i18n-checker:** Analysis + report (optional)
- **tech-debt-tracker:** Analysis + debt register (no code changes)

All read what master-executor produced; none conflict.

### 5. Report-Driven Communication
- No in-memory state between agents
- All inter-agent communication via markdown files
- Master-executor is the single source of truth for completed changes
- Each downstream agent reads execution-report.md to understand what was done

### 6. Vietnamese-First Language Policy
- All agent responses in Vietnamese (for user comfort in Vietnamese context)
- Code, file names, technical identifiers remain in English
- Responses preserve both cultural fit and technical clarity

### 7. No Automatic Execution
- **No commits without user approval**
- **No deployments**
- **No npm/package manager operations**
- Git-commit agent only generates messages; user must manually execute

---

## Installation & Setup

### Location Convention
```
~/.claude/
├── agents/                          ← 11 agent .md files copied here
│   ├── design-finder.md
│   ├── ux-reviewer.md
│   ├── code-reviewer.md
│   ├── security-auditor.md
│   ├── perf-analyzer.md
│   ├── master-executor.md
│   ├── test-writer.md
│   ├── doc-writer.md
│   ├── i18n-checker.md
│   ├── tech-debt-tracker.md
│   └── git-commit.md
└── CLAUDE.md                        ← System orchestrator (from repo)
```

Plus, each project has its own `CLAUDE.md` in the repository root defining:
- Project-specific configuration
- Coding behavior principles
- Tech stack details
- Anti-patterns to avoid

### No External Dependencies
- Pure markdown specifications
- No Python, JavaScript, or compiled code in this repo
- Relies entirely on Claude's native tool calling (Bash, Read, Glob, Grep, Write, WebFetch, WebSearch)

---

## Orchestrator Configuration (CLAUDE.md)

The root `CLAUDE.md` file (5,496 bytes) contains:

### Section 1: Coding Behavior Principles
- **Think Before Coding:** Clarify assumptions, present tradeoffs, don't hide ambiguity
- **Simplicity First:** Minimal code, no speculative features
- **Surgical Changes:** Only modify what's necessary
- **Goal-Driven Execution:** Convert tasks into verifiable success criteria

### Section 2: 11-Agent Workflow System
- Defines 5 phases and agent routing
- Specifies context-driven routing (feature → design-finder, bug → code-reviewer, security issue → security-auditor, etc.)
- Lists critical i18n rule (only use if explicitly requested or already present)

### Section 3: General Guidelines
- Respond in Vietnamese; maintain English for code/files
- Never execute git commits, npm publish, or deployments
- Request clarification rather than assuming

---

## Usage Examples & Workflow

### Example 1: Simple Feature Implementation
**User Request:** "Build a new settings page with dark mode toggle and export preferences button"

**Workflow:**
1. **Phase 1 (Design):** `design-finder` searches Dribbble for "settings page dark mode" → creates `design-inspiration.md`
   - User reviews, selects preferred style
   
2. **Phase 2 (Review — Parallel):**
   - `ux-reviewer` checks accessibility, responsive design, consistency → `ux-review-report.md`
   - `code-reviewer` reviews implementation quality → `code-review-report.md`
   - `security-auditor` checks for export security issues → `security-audit-report.md`
   - `perf-analyzer` checks for re-render issues → `perf-analysis-report.md`
   - User confirms all reviews

3. **Phase 3 (Execute):**
   - `master-executor` reads all 4 reports
   - Prioritizes: security issues first → code issues → UX improvements
   - Applies fixes, re-reading source before each edit
   - Creates `execution-report.md`
   - User confirms all changes applied correctly

4. **Phase 4 (Post-Process):**
   - `test-writer` generates unit tests for settings logic, dark mode hook, export handler
   - `doc-writer` adds JSDoc to new functions, updates README with feature description
   - `tech-debt-tracker` notes any shortcuts or TODOs for future refactoring
   - User confirms artifacts

5. **Phase 5 (Finalize):**
   - `git-commit` generates conventional commit message:
     ```
     feat(settings): add dark mode toggle and export preferences
     
     - Dark mode preference persisted in localStorage
     - Export button generates JSON with user settings
     - Added comprehensive unit tests
     - Tested on mobile and desktop viewports
     ```
   - User manually executes: `git commit -m "..."`

---

### Example 2: Security Incident Response
**User Request:** "Found potential XSS vulnerability in user input handling. Run full security audit."

**Workflow:**
1. **Phase 1:** Skipped (design not relevant)

2. **Phase 2 (Parallel Reviews):**
   - `security-auditor` scans entire codebase for OWASP vulnerabilities
     - Finds 3 critical XSS issues, 2 high-severity SQL injection risks, 1 exposed API key
     - Creates `security-audit-report.md` with code evidence and fixes
   - `code-reviewer` analyzes input handling patterns → `code-review-report.md`
   - `perf-analyzer` checks performance impact of sanitization → `perf-analysis-report.md`
   - User confirms all findings

3. **Phase 3 (Execute):**
   - `master-executor` prioritizes security items first
   - Applies sanitization, input validation, key rotation, API endpoint hardening
   - Creates `execution-report.md`

4. **Phase 4 (Post-Process):**
   - `test-writer` generates security tests (payloads that should fail, valid inputs that should pass)
   - `doc-writer` updates security section in README
   - `tech-debt-tracker` notes "Add security validation library" as medium-priority debt

5. **Phase 5 (Finalize):**
   - `git-commit` generates:
     ```
     fix(security): patch XSS and SQL injection vulnerabilities
     
     - Sanitize user input with DOMPurify
     - Use parameterized queries for all database operations
     - Rotate exposed API key and revoke old token
     - Add input validation middleware to all routes
     
     Severity: Critical
     ```
   - User manually commits and pushes to security branch

---

## Comparison with Nelson Freight Workflow

### Similarities
| Aspect | Subagent Workflow | Nelson Freight |
|--------|-------------------|----------------|
| Orchestration | Single CLAUDE.md coordinator | orchestration-protocol.md |
| Agent separation | 11 specialized agents | Task-based subagents (planner, implementer, tester, reviewer, docs-manager) |
| Confirmation gates | Phase boundaries require approval | TaskUpdate(status) + lead approval |
| Read-only review | UX/Code/Security/Perf review agents | code-reviewer agent |
| Execution discipline | master-executor only modifies code | implementer modifies, tester verifies |
| Language | Vietnamese-first | Vietnamese-first (CLAUDE.md rule) |
| Report-driven | All communication via .md files | Reports to `plans/reports/` |

### Key Differences
| Aspect | Subagent Workflow | Nelson Freight |
|--------|-------------------|----------------|
| Transport | 11 separate agent files in `~/.claude/agents/` | Task/Message protocol via task tool |
| Execution model | Local CLI agents, manual run-through | Spawned via Task tool (parallel/sequential) |
| State tracking | Markdown report files | TaskList + TaskGet/TaskUpdate |
| Subagent discovery | Via CLAUDE.md routing rules | Via available tasks in TaskList |
| Commit responsibility | git-commit agent generates (no execution) | Executor handles commits |
| Design phase | design-finder locates UI inspiration | Not explicitly in current workflow |
| i18n validation | Optional i18n-checker phase | Not present |
| Debt tracking | tech-debt-tracker generates register | Mentioned in dev-rules but not automated |

### Adoption Considerations for Nelson Freight

**✅ APPLICABLE NOW:**
- Phase 2 review agents (code/security/perf/ux) directly augment your code-reviewer → can run in parallel with your existing setup
- Report-driven architecture mirrors your orchestration-protocol.md
- Vietnamese-first language policy already in CLAUDE.md

**⚠️ REQUIRES ADAPTATION:**
- 11 agent files would need to be integrated into `.claude/skills/` structure or kept separate in `~/.claude/agents/`
- Phase 1 (design-finder) is valuable for webapp UI decisions but currently not in your workflow
- Phase 4 (test-writer, i18n-checker) are optional; Nelson currently delegates test-writer separately
- Phase 5 (git-commit) is advisory; your executor handles commits directly

**🔄 RECOMMENDED INTEGRATION PATH:**
1. Keep subagent workflow as **local development reference** (this repo)
2. Adapt design-finder for webapp sprints (S14B+C require UI decisions)
3. Create `.claude/skills/subagent-workflow-reference/` with agent specs
4. Extend Nelson's orchestration-protocol.md with design phase when needed
5. Consider tech-debt-tracker for sprint planning (maps to memory/projects/)

---

## Configuration & Customization

### Project-Level Configuration (per CLAUDE.md)
Each project's root `CLAUDE.md` should define:
```markdown
## Tech Stack
- Frontend: Next.js 14+, TypeScript, TailwindCSS
- Backend: FastAPI, Python 3.11+
- Testing: Jest, Playwright
- Database: PostgreSQL

## Anti-Patterns (DO NOT DO)
- Never use `any` type in TypeScript
- Never commit .env files
- Never hardcode API URLs

## Code Style
- Use kebab-case for filenames
- Max 200 lines per file
- JSDoc for all exports

## Restricted Files
- Do not modify: `.env`, `LICENSE`, `CHANGELOG.md`
```

### Agent Prioritization
Master-executor priority hierarchy is hardcoded but can be overridden in project `CLAUDE.md`:
```markdown
## Execution Priority
1. Custom Security Rules (if project-specific)
2. security-audit-report.md
3. code-review-report.md
4. ux-review-report.md
5. perf-analysis-report.md
```

### Language Settings
System is Vietnamese-first; to use English:
- Modify CLAUDE.md orchestrator
- Update each agent spec's language requirement section
- Not recommended — original design assumes Vietnamese context

---

## Dependencies & Requirements

### Runtime Requirements
- **Claude API access** (via Claude CLI or web interface)
- **Bash shell** (for git commands, compilation checks)
- **Project tech stack** (TypeScript compiler, Jest/Vitest for tests, etc.)

### No External Libraries
- No pip packages
- No npm dependencies
- Pure markdown specifications interpreted by Claude's tools

### Files Required Per Project
```
project-root/
├── .claude/
│   └── settings.json              ← Optional project config
├── CLAUDE.md                       ← Project-specific rules
├── package.json                    ← For dependency + test framework detection
├── tsconfig.json                   ← For TypeScript config
├── jest.config.js (or vitest)      ← For test framework detection
└── src/
    └── ... actual code
```

### Assumptions
- Project is version controlled with git
- Uses TypeScript (or JavaScript with type hints)
- Has test framework configured (Jest/Vitest/Playwright)
- Has linter configured (ESLint)

---

## Unresolved Questions & Limitations

### Questions Requiring Clarification
1. **Dependency Versioning:** How do agents handle breaking changes when reviewing dependencies?
   - tech-debt-tracker detects outdated packages but doesn't specify upgrade strategy
   
2. **Performance Baseline:** perf-analyzer uses scoring (0–100) but what's the baseline for a new project?
   - No guidance on first-run expectations vs. subsequent audits
   
3. **Concurrent Review Agents:** If 4 review agents run in parallel (Phase 2), how are conflicting recommendations handled?
   - master-executor prioritizes by severity but doesn't merge conflicting approaches (e.g., code-reviewer suggests refactoring that perf-analyzer says to avoid)
   
4. **Test Framework Detection:** test-writer detects Jest/Vitest/Playwright via glob/package.json, but what if project uses multiple frameworks?
   - Spec doesn't clarify priority or fallback

5. **Large Codebases:** How does master-executor handle 50+ files across execution report?
   - No guidance on chunking, batching, or memory constraints
   
6. **Integration with CI/CD:** System explicitly forbids automated commits/deployments, but how should output integrate with GitHub Actions?
   - Spec suggests manual execution only; no guidance for automated workflows

7. **Agent Memory Persistence:** design-finder, perf-analyzer, git-commit, doc-writer mention persistent memory at `C:\Users\ADMIN\.claude\agent-memory\{role}\`
   - Is this Windows-specific? How does it work on macOS/Linux?
   - How are memory files synchronized across machines?

### Limitations of This System

**Local-Only Workflow:**
- Designed for single developer running agents locally
- No built-in team coordination or PR integration
- Report files live in project directory; not persistent across machines

**No Branching Support:**
- All agents assume main branch workflow
- No guidance for feature branches, stashing work, or rebasing
- master-executor doesn't handle merge conflicts

**Limited Error Recovery:**
- If master-executor crashes mid-execution, no checkpoint system to resume
- Phase 2 agents don't validate each other's findings (e.g., security-auditor doesn't contradict code-reviewer)

**Report File Cleanup:**
- Phase boundary reports accumulate in project directory
- No automated cleanup mechanism
- User responsible for removing stale `*-report.md` files

**No Version Compatibility:**
- Agents assume latest Claude model capabilities
- No fallback for rate limits or degraded API performance
- No caching of expensive analyses (e.g., perf-analyzer re-scans entire codebase each run)

**Framework-Specific Blindspots:**
- Heavy bias toward Next.js/React/TypeScript
- Backend (FastAPI, Python, Node.js Express) covered but less thoroughly
- No guidance for other popular stacks (Vue, Svelte, Go, Rust, C#)

---

## Concrete Integration Recommendations for Nelson Freight

### Recommendation 1: Import Design-Finder Phase
**Current State:** Nelson webapp (S14B+) needs UI/component design decisions

**Action:**
- Store `design-finder.md` in `.claude/skills/design-discovery/SKILL.md` (your naming)
- Trigger in webapp sprint planning phase (before component implementation)
- Example: "Design login form for email dashboard" → design-finder → 5–7 reference designs → team votes → implement

**Estimated ROI:** +2 hours per sprint for superior UI decisions; reduces rework

---

### Recommendation 2: Extend Code-Reviewer Integration
**Current State:** You have code-reviewer agent; subagent workflow's version adds more depth

**Action:**
- Extract tech-debt-tracker section from subagent spec
- Add as Phase 4 in your tester → reviewer → docs pipeline
- Creates `tech-debt-register.md` per sprint
- Maps to memory/projects/{sprint}/tech-debt.md

**Estimated ROI:** +1 hour per sprint; better backlog planning

---

### Recommendation 3: Adopt Phase 5 Commit Message Generation
**Current State:** You manually write commits; subagent's git-commit is advisory

**Action:**
- Create `.claude/skills/git-commit-generator/SKILL.md` with git-commit.md content
- After master-executor finishes, run git-commit agent
- Copy generated message to clipboard, paste into git commit command
- No automation, pure advisory (matches your "no auto-commit" rule)

**Estimated ROI:** +15 min per commit; better commit history searchability

---

### Recommendation 4: Design Phase for Email Tool Sprints (S14B+)
**Current State:** Email dashboard v7 shipped but S14B (Email History + Follow-up) needs UI decisions

**Action:**
- Run design-finder at sprint kickoff (S14B Phase 01)
- Gather inspiration for dashboard tables, filters, follow-up history visualization
- Document in `plans/260416-email-nelson-solo-platform/phase-02-design-decisions.md`
- Informs component architecture before code starts

**Estimated ROI:** Prevents rework; aligns design with user mental model

---

### Recommendation 5: Optional i18n-Checker Waiver
**Current State:** Email dashboard currently English-only; CLAUDE.md says "don't auto-setup i18n"

**Action:**
- Do NOT enable i18n-checker unless Nelson explicitly requests multi-language email campaigns
- Add to CLAUDE.md: `i18n_required: false` (matches existing rule)
- Avoids waste on premature internationalization

**Estimated ROI:** 0 (already following best practice)

---

## Summary Table: Agents & Use Cases

| Agent | Phase | Trigger | Input | Output | Effort |
|-------|-------|---------|-------|--------|--------|
| **design-finder** | 1 | WebApp sprint kickoff | Project domain, brand guidelines | design-inspiration.md (5–7 ideas) | 30 min |
| **ux-reviewer** | 2 | After implementation | JSX/CSS files | ux-review-report.md (P0–P3 issues) | 45 min |
| **code-reviewer** | 2 | After implementation | TypeScript files | code-review-report.md (CAO/TRUNG/THẤP) | 60 min |
| **security-auditor** | 2 | Feature complete | All source files | security-audit-report.md (Critical/High/Medium/Info) | 45 min |
| **perf-analyzer** | 2 | QA phase | Bundle, API logs | perf-analysis-report.md (score 0–100) | 60 min |
| **master-executor** | 3 | After Phase 2 reviews | All `*-report.md` files | execution-report.md (changes made) | 120 min |
| **test-writer** | 4 | After execution | Source code + execution-report | `*.test.ts` + test-writer-report.md | 90 min |
| **doc-writer** | 4 | After tests | Source code + tests | JSDoc, README, API docs | 60 min |
| **i18n-checker** | 4 | Optional (if i18n present) | i18n config + source | i18n-report.md | 45 min |
| **tech-debt-tracker** | 4 | After execution | All reports + codebase | tech-debt-register.md (7 categories) | 30 min |
| **git-commit** | 5 | After Phase 4 | git diff output | commit message (no execution) | 15 min |

---

## Raw File Contents

### A. CLAUDE.md (Orchestrator) — 5,496 bytes

```markdown
# 2Anh AI — Coding Standards & 11-Agent Workflow

## PHẦN 1: Coding Behavior Principles

### Think Before Coding
Đừng đoán. Đừng giấu sự mơ hồ. Nêu rõ tradeoffs.
- Clarify assumptions upfront
- Present alternatives rather than choosing silently
- Document surprising decisions

### Simplicity First
Write minimal code solving the actual problem.
- No speculative features
- No unnecessary abstractions
- No premature flexibility

### Surgical Changes
Only modify necessary parts. Don't refactor adjacent code or remove unrelated dead code unless requested.

### Goal-Driven Execution
Convert tasks into verifiable success criteria with a clear multi-step plan.

## PHẦN 2: 11-Agent Workflow System

### Agent Phases
- **Phase 1 (Design):** design-finder
- **Phase 2 (Review):** ux-reviewer, code-reviewer, security-auditor, perf-analyzer
- **Phase 3 (Execute):** master-executor
- **Phase 4 (Process):** test-writer, doc-writer, i18n-checker, tech-debt-tracker
- **Phase 5 (Finalize):** git-commit

### Critical i18n Rule
"KHÔNG tự động dùng i18n-checker hoặc setup i18n trừ khi" the user explicitly mentions multi-language support or the codebase already contains translation infrastructure. Browser `Intl` APIs don't constitute internationalization implementation.

### Context-Driven Routing
Tasks route to specific agents based on request type (feature, bug fix, security, performance, release, hotfix, etc.).

## PHẦN 3: General Guidelines
- Respond in Vietnamese; maintain English for code/files
- Never execute git commits, npm publish, or deployment commands
- Request clarification rather than making assumptions
```

---

### B. Key Agent Specifications (Raw Content)

All 11 agent .md files totaling ~218 KB. Full specs provided in sections above; here's structural summary:

**agents/design-finder.md** — Inspire UI/UX design with web research + visual recommendation
**agents/ux-reviewer.md** — Comprehensive accessibility, responsive, interaction analysis
**agents/code-reviewer.md** — Logic, types, React patterns, performance anti-patterns
**agents/security-auditor.md** — OWASP Top 10 scanning with secret redaction
**agents/perf-analyzer.md** — Bundle, React rendering, backend query analysis with score (0–100)
**agents/master-executor.md** — Execute Phase 3, apply fixes priority-by-severity, generate execution-report
**agents/test-writer.md** — Generate unit/integration/E2E tests with Arrange→Act→Assert
**agents/doc-writer.md** — Create README, JSDoc, API docs, no code logic changes
**agents/i18n-checker.md** — Translation completeness, hardcoded strings, RTL support
**agents/tech-debt-tracker.md** — Categorize debt (7 types), health score (0–100), register
**agents/git-commit.md** — Generate conventional commit messages (no execution)

---

## Recommendations for Nelson Freight Project

### Tier 1: Immediate Adoption (This Month)
1. **Reference design-finder** for S14B email dashboard phase 01 (UI decision acceleration)
2. **Document git-commit patterns** from subagent workflow into your git-commit skill

### Tier 2: Integration (Next 2 Sprints)
1. **Extend code-reviewer** with tech-debt-tracker findings
2. **Adopt perf-analyzer scoring** for email_engine optimization (S14C rate calculation)

### Tier 3: Architectural Alignment (End of Q2)
1. **Port subagent agents to `.claude/skills/`** for consistency with claudekit
2. **Update orchestration-protocol.md** with Phase 1 (Design) addition

### NOT Recommended (Alignment Risk)
- **Automatic i18n-checker:** Premature; defer unless Nelson requests multi-language campaigns
- **Full adoption of 11-agent system:** Too rigid for Nelson's parallel task handling; use as reference only

---

## Conclusion

**Subagent Workflow** is a **well-designed, Vietnamese-first orchestration system** that automates development review → fix → test → docs → commit pipelines. It's **excellent reference material** for local development workflows and directly applicable to Nelson Freight's webapp sprints (S14B+).

**Key Takeaway:** Use it as a **reference pattern**, not a direct replacement. Nelson's Task/Message orchestration is already more flexible for parallel execution; borrow the **design-finder phase** and **tech-debt-tracker ideas** to enhance existing workflows.

---

**Report Generated:** 2026-04-23  
**Source Repository:** https://github.com/luonghaianh1208/subagent-workflow  
**License:** MIT (copyright Lương Hải Anh, GV CNT)  
**Analysis Depth:** Complete (11/11 agents analyzed, 218 KB specifications reviewed)
