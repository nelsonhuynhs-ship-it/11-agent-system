# OpenCode + MiniMax M2.7: AI Coding Workflow Audit

**Date:** 2026-05-03
**Author:** Brainstorm Agent
**Scope:** OpenCode ecosystem audit for MiniMax M2.7 integration

---

## 1. Executive Summary

**OpenCode là gì:**
- Open-source AI coding agent, 154K GitHub stars, MIT license
- Client/server architecture — TUI là 1 trong nhiều clients
- Provider-agnostic: 75+ LLM providers (Claude, GPT, Gemini, local, v.v.)
- Privacy-first: KHÔNG store code/context trên cloud
- Company: Anomaly (anoma.ly), Shanghai

**Verdict:**
```
OpenCode + M2.7: KHẢ THI nhưng CHƯA ổn định
- ✅ Open source, provider-agnostic, multi-session
- ⚠️ 4.5K open issues, recent connection failures (May 3, 2026)
- ⚠️ MiniMax integration chưa tested
- ⚠️ Documentation gaps, beta desktop
```

**Recommendation:** Dùng thử nhưng KHÔNG replace Claude Code hoàn toàn. Hybrid workflow là lựa chọn tối ưu.

---

## 2. Deep Architecture Analysis

### 2.1 System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    OpenCode Engine                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  Build Agent │  │  Plan Agent │  │  General Agent  │  │
│  │  (full-edit)│  │ (read-only) │  │  (@general)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
│                         │                                 │
│              ┌──────────┴──────────┐                    │
│              │   AGENTS.md Layer   │  ← Context store    │
│              └──────────┬──────────┘                    │
│                         │                                 │
│  ┌──────────────────────┼───────────────────────────┐   │
│  │              Tool Executor                       │   │
│  │  • Read/Write files  • Bash commands            │   │
│  │  • Web search         • Git operations           │   │
│  │  • Glob/grep          • LSP integration         │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
          │                    │              │
    ┌─────┴─────┐       ┌─────┴─────┐  ┌────┴────┐
    │  TUI      │       │  Desktop  │  │  IDE    │
    │  (local)  │       │  (Beta)   │  │Plugins  │
    └───────────┘       └───────────┘  └─────────┘
```

**Key architectural decisions:**
- Agent logic tách biệt khỏi interface (client/server)
- Context stored in `AGENTS.md` (project root, gitignored)
- `/undo` và `/redo` cho revert changes
- Plan mode (Tab): read-only, denies edits by default

### 2.2 Agent Loop

```
User Input → [Plan Mode: read-only, ask before bash]
                 ↓
          [Build Mode: full access, auto-approve bash]
                 ↓
         LLM Provider (75+ options)
                 ↓
         Tool Execution → Result → Feedback Loop
```

### 2.3 Installation

```bash
# Primary
curl -fsSL https://opencode.ai/install | bash

# Alternatives
npm i -g opencode-ai
bun add -g opencode-ai
brew install anomalyco/tap/opencode
```

---

## 3. Feature Comparison Matrix

| Feature | OpenCode | Claude Code | Aider | Cline | OpenHands |
|---------|----------|-------------|-------|-------|-----------|
| **License** | MIT | Proprietary | MIT | Proprietary | Apache 2.0 |
| **Stars** | 154K | N/A | 27K | N/A | 50K |
| **Model Support** | 75+ any | Claude only | Any LLM | Any LLM | Any LLM |
| **Architecture** | Client/Server | CLI | CLI | CLI/Ext | Agent |
| **Shell Integration** | TUI built-in | Full | Full | Full | Full |
| **Edit Strategy** | In-place | In-place | In-place/diff | In-place | In-place |
| **Memory** | AGENTS.md | .claude/ | .aider* | Workspace | Persistent |
| **LSP Enabled** | ✅ Yes | ❌ No | ❌ No | ✅ Yes | ❌ No |
| **Multi-session** | ✅ Yes | ❌ No | ❌ No | ❌ No | Limited |
| **Share Links** | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No |
| **Enterprise** | ✅ SSO/Self-host | ❌ No | ❌ No | ❌ No | ✅ Yes |
| **Terminal-first** | ✅ TUI | ✅ CLI | ✅ CLI | ⚠️ Hybrid | ⚠️ Hybrid |

---

## 4. Strengths & Weaknesses

### 4.1 Strengths

| # | Strength | Impact | Evidence |
|---|----------|--------|----------|
| 1 | **100% Open Source** | Transparency, audit được | 154K stars, 850 contributors |
| 2 | **Provider-agnostic** | Không phụ thuộc 1 provider | 75+ providers |
| 3 | **Privacy-first** | Code không bao giờ rời máy local | Official claim, self-host option |
| 4 | **LSP-enabled** | Hiểu code chính xác hơn | Auto LSP loading |
| 5 | **Multi-session** | Nhiều agent chạy song song | Trên cùng project |
| 6 | **Share links** | Collaborative debugging | Remote session share |
| 7 | **Enterprise ready** | Self-host, SSO cho team | Anomaly cung cấp |
| 8 | **TUI native** | Terminal workflow mượt | Built-in shell |

### 4.2 Weaknesses

| # | Weakness | Severity | Evidence |
|---|----------|----------|----------|
| 1 | **Stability issues** | 🔴 HIGH | 4.5K open issues, connection failures May 3, 2026 |
| 2 | **Young/Beta** | 🟡 MED | Desktop app beta, rapid changes |
| 3 | **Docs gaps** | 🟡 MED | Many 404s, sparse architecture docs |
| 4 | **Shell limitations** | 🟡 MED | Fish shell login args not supported |
| 5 | **Tool calling unclear** | 🟡 MED | Not well documented |
| 6 | **Memory system** | 🟡 MED | AGENTS.md < .claude/ memory sophistication |
| 7 | **MiniMax untested** | 🟡 MED | Chỉ qua OpenAI-compatible API |
| 8 | **4.5K open issues** | 🔴 HIGH | Massive backlog = unresolved bugs |

---

## 5. MiniMax M2.7 Compatibility

### 5.1 Integration Path

```
MiniMax M2.7
    ↓ OpenAI-compatible API endpoint
OpenCode Provider Config
    ↓ (provider: openai or custom)
LLM Tool Calling
```

**Cách cấu hình (推测):**
```json
# ~/.config/opencode/providers.json
{
  "providers": {
    "minimax": {
      "name": "MiniMax M2.7",
      "api_type": "openai",
      "api_base": "https://api.minimax.chat/v1",
      "api_key": "sk-xxx",
      "model": "M2.7"
    }
  }
}
```

### 5.2 Assessment

| Criteria | Status | Notes |
|----------|--------|-------|
| API Compatibility | ✅ Likely | OpenAI-compatible endpoint |
| Tool Calling | ✅ Likely | Standard function calling |
| Context Length | ⚠️ Check | M2.7 204K ctx — config needed |
| Image Input | ✅ Likely | Vision support |
| Token Efficiency | ❓ Unknown | No benchmarks |

**Verdict:** Integration khả thi nhưng CẦN TEST thực tế.

---

## 6. Real-World Workflow Analysis

### 6.1 Terminal Workflow Comparison

| Task | Claude Code | OpenCode |
|------|-------------|----------|
| **Single file edit** | ✅ | ✅ |
| **Multi-file refactor** | ✅ | ✅ |
| **Git commit loop** | ✅ | ✅ |
| **Code review** | ✅ | ✅ (plan mode) |
| **Architecture planning** | ✅ | ✅ (plan mode) |
| **Long-running task** | ⚠️ Session limit | ✅ Multi-session |
| **Parallel agents** | ❌ | ✅ |
| **陌生的 codebase** | ✅ | ✅ (plan mode ideal) |

### 6.2 Frontend/ Dashboard Project

```
OpenCode advantages:
- LSP-enabled → better code understanding
- Multi-session → parallel component work
- Share links → stakeholder review

OpenCode disadvantages:
- No native Next.js/React specifics
- AGENTS.md context < Claude memory sophistication
- Documentation gaps for complex setups
```

**Verdict:** OpenCode usable for frontend nhưng KHÔNG superior.

### 6.3 Autonomous Agent Loop

```
Claude Code:  Opus brain → MM workers (existing)
OpenCode:     M2.7 direct (if integrated)

Long-running concerns:
- OpenCode: Better (multi-session)
- Claude Code: Better (proven stability)
```

---

## 7. Comparison: OpenCode vs Claude Code Shell

### 7.1 When to Use OpenCode

| Scenario | Recommendation | Why |
|----------|---------------|-----|
| Cần open-source | **OpenCode** | MIT, auditable |
| Privacy-sensitive | **OpenCode** | No cloud storage |
| Nhiều provider cùng lúc | **OpenCode** | 75+ providers |
| Parallel agent tasks | **OpenCode** | Multi-session built-in |
| Stakeholder demo/share | **OpenCode** | Share links |

### 7.2 When to Use Claude Code

| Scenario | Recommendation | Why |
|----------|---------------|-----|
| Production work | **Claude Code** | Stable, proven |
| Complex planning | **Claude Code** | Better memory system |
| Unknown codebase | **Claude Code** | Sophisticated context |
| Nelson's existing workflow | **Claude Code** | Already optimized |
| Security-critical | **Claude Code** | Review reports available |

### 7.3 Hybrid Workflow (Recommended)

```
┌──────────────────────────────────────────────────────┐
│           AI Engineering Workstation                   │
│                                                       │
│  Claude Code (Opus brain)                             │
│  ├── Complex planning, architecture                   │
│  ├── Code review, security audit                      │
│  ├── Nelson's existing workflow                       │
│  └── MEMORY system                                    │
│                                                       │
│  OpenCode (M2.7 worker)                               │
│  ├── Experimental features                            │
│  ├── Parallel agent tasks                             │
│  ├── Privacy-sensitive work                          │
│  └── Open-source auditing                            │
└──────────────────────────────────────────────────────┘
```

---

## 8. Recommended Setup

### 8A. Architecture: Dual-System

```
Terminal Session A                    Terminal Session B
┌─────────────────────┐              ┌─────────────────────┐
│  Claude Code        │              │  OpenCode           │
│  Opus brain         │              │  M2.7 worker        │
│  /mm delegate task  │              │  opencode           │
│                     │              │  --model minimax    │
│  • Planning         │              │                     │
│  • Code review      │              │  • Multi-file edit  │
│  • Complex reasoning│              │  • Parallel agents  │
│  • Memory aware     │              │  • Experimental     │
└─────────────────────┘              └─────────────────────┘
         ↓                                  ↓
    OneDrive/NelsonData/              OneDrive/NelsonData/
    erp/ (production)                experiments/
```

### 8B. Installation Commands

```bash
# Install OpenCode
curl -fsSL https://opencode.ai/install | bash

# Verify
opencode --version

# Configure MiniMax (推测)
opencode config set provider minimax
opencode config set api_key $MINIMAX_API_KEY
opencode config set model M2.7
```

### 8C. Config Structure

```json
// ~/.config/opencode/config.json
{
  "provider": "minimax",
  "model": "M2.7",
  "temperature": 0.7,
  "max_tokens": 8192,
  "context_window": 204800,
  "agents": {
    "build": {
      "auto_approve_bash": true,
      "allow_edit": true
    },
    "plan": {
      "auto_approve_bash": false,
      "allow_edit": false,
      "ask_before_run": true
    }
  },
  "shell": {
    "integration": "native",
    "timeout_seconds": 300
  }
}
```

---

## 9. Best Practices

### 9.1 OpenCode Workflow

```bash
# 1. Init project
cd ~/projects/experiment
opencode --init

# 2. Plan mode (read-only exploration)
opencode --agent plan
# → Use when: unfamiliar codebase, reviewing

# 3. Build mode (full editing)
opencode --agent build
# → Use when: implement features, refactor

# 4. Multi-session (parallel)
opencode --session api-design &
opencode --session frontend &
wait

# 5. Share session (collaboration)
opencode --share
# → Returns share link
```

### 9.2 Hybrid Workflow

```bash
# Claude Code: Plan with Opus
claude
→ /plan: Implement X feature
→ /mm: delegate to M2.7

# OpenCode: Execute with M2.7
opencode
→ Context: AGENTS.md from Claude
→ Implement parallel tasks
```

### 9.3 AGENTS.md Usage

```markdown
# AGENTS.md (auto-generated by opencode --init)

# Project Context
- Type: React dashboard
- Framework: Next.js 14 App Router
- Styling: Tailwind CSS

# Build Instructions
- Run: npm run dev
- Test: npm test
- Build: npm run build

# Context Rules
- Always run type-check before commit
- Use existing component patterns
```

---

## 10. Final Recommendation

### 10.1 Summary

| Criteria | Score (1-5) | Notes |
|----------|-------------|-------|
| Open-source | 5 | MIT, 154K stars |
| Stability | 2 | 4.5K issues, recent failures |
| Documentation | 2 | Gaps, 404s |
| MiniMax compat | 3 | Possible, untested |
| Terminal workflow | 4 | TUI native |
| Memory system | 3 | AGENTS.md adequate |
| Claude Code replacement | 2 | Not yet stable enough |

### 10.2 Binary Decision

```
Anh nên thử OpenCode + M2.7 không?

✅ YES, nếu:
   - Muốn thử nghiệm open-source alternative
   - Cần multi-session parallel agents
   - Privacy-sensitive work
   - Ưu tiên open-source over stability

❌ NO, nếu:
   - Cần production stability
   - Đang dùng Claude Code workflow ổn định
   - Cần proven tool với track record
```

### 10.3 Action Items

```bash
# 1. Thử nghiệm (30 phút)
curl -fsSL https://opencode.ai/install | bash
opencode --version

# 2. Test basic workflow
mkdir ~/experiments/opencode-test
cd ~/experiments/opencode-test
opencode --init
opencode --agent plan "Explain this codebase"

# 3. Test MiniMax integration
# (Cấu hình provider, test API call)

# 4. Benchmark so với Claude Code
# → Run same task both directions
```

### 10.4 30-Day Plan

```
Week 1: Install + basic exploration + MiniMax config
Week 2: Parallel task benchmark vs Claude Code
Week 3: Hybrid workflow test (Claude → OpenCode)
Week 4: Decision: integrate hay drop
```

---

## 11. Unresolved Questions

| Question | Status | How to Resolve |
|----------|--------|----------------|
| MiniMax M2.7 actual compatibility | ❓ | Test directly |
| Token efficiency vs Claude Code | ❓ | Benchmark needed |
| Stability real-world assessment | ❓ | 2-week trial |
| Self-host complexity | ❓ | Test deployment |
| Tool calling implementation | ❓ | Code audit |

---

## Sources

- [OpenCode Official Site](https://opencode.ai)
- [OpenCode GitHub Repository](https://github.com/anomalyco/opencode)
- [OpenCode Download Page](https://opencode.ai/download)
- [OpenCode Docs](https://opencode.ai/docs)
- [OpenCode Enterprise](https://opencode.ai/enterprise)
- [GitHub Issues - Stability May 2026](https://github.com/anomalyco/opencode/issues)
