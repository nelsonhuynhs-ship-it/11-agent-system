# MiniMax Token Plan Cheatsheet

**Last updated:** 2026-04-25
**Source:** Official docs + research session

## 🎯 Counting Mechanism (CRITICAL)

| Aspect | Reality |
|---|---|
| Unit | **Requests** (số lần gọi API), NOT individual tokens |
| 5h quota | Base unit |
| Weekly quota | 10× 5h quota |
| 1 phase delegation = | **1 request** (regardless of duration) |

→ 70 phút runtime ≠ 70 phút worth of tokens. Nó = ~10 requests nếu 10 phases.

**Grandfather rule:**
- Subscribe before **2026-03-22 23:59:59 UTC** → No weekly quota (unlimited)
- Subscribe from **2026-03-23 onwards** → Subject to weekly quota

## 🔑 Key Types

| Type | Prefix | Endpoint | Billing |
|---|---|---|---|
| Token Plan (Nelson dùng) | `sk-cp-` | `https://api.minimax.io/anthropic` | Subscription |
| Open Platform | `sk-api-` | `https://api.minimax.io/v1` | Pay-per-token |

⚠ Error 1008 = sai loại key cho endpoint.

## 🚀 Sidecar Pattern (mm-claude.sh)

Already configured at `~/.claude/bin/mm-claude.sh`:

```bash
ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
ANTHROPIC_AUTH_TOKEN="$MINIMAX_API_KEY"
ANTHROPIC_MODEL="MiniMax-M2.7"
API_TIMEOUT_MS=3000000   # 50 min for long phases
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
```

Usage:
```bash
mm-claude.sh "<prompt>"
mm-claude.sh --file plan.md
cat plan.md | mm-claude.sh --stdin
```

## 📡 Verify Quota (no Claude session needed)

```bash
source ~/.claude/.env.minimax
curl -s -X POST "https://www.minimax.io/v1/token_plan/remains" \
  -H "Authorization: Bearer $MINIMAX_API_KEY" | jq
```

Output: total / used / remaining (request count).

## ⚡ MCP Setup — Add MiniMax web_search + understand_image vào Claude Code

```bash
claude mcp add -s user MiniMax \
  --env MINIMAX_API_KEY=$MINIMAX_API_KEY \
  --env MINIMAX_API_HOST=https://api.minimax.io \
  -- uvx minimax-coding-plan-mcp -y
```

Sau install: `/mcp` trong Claude Code → 2 tools mới.

**Tools provided:**
- `web_search` — search powered by MiniMax
- `understand_image` — image analysis (JPEG/PNG/GIF/WebP, max 20MB)

## 🧠 Best Practices (M2.7 Prompting)

### Multi-Window Pattern
- Window 1: Framework setup (tests.py, scripts, init.sh)
- Window 2+: Iteration through tasks
- Cross-session via tracking files

### Token Budget per Task
- Keep input+output ≤ 200k tokens
- Long task → break into multiple windows
- System prompt: minimize size

### Prompt Engineering
- ✅ Specific format expectations ("enterprise-grade data viz with rich analytics" > "create viz")
- ✅ Explain WHY (not just bare restrictions)
- ✅ Concrete +/- examples
- ❌ Vague open-ended requests
- ❌ Submit 5 goals in 1 prompt

### Recommended System Prompt for Long Tasks
```
Make full use of the complete output context to handle this—keep total
input and output tokens within 200k. Use the context window length to
complete thoroughly and avoid exhausting tokens.
```

## 🤖 Mini-Agent (Alternative Framework)

**NOT replacing Claude Code.** Standalone framework by MiniMax.

```bash
uv tool install git+https://github.com/MiniMax-AI/Mini-Agent.git
```

Config: `~/.mini-agent/config/config.yaml`
```yaml
api_key: "YOUR_API_KEY_HERE"
api_base: "https://api.minimax.io"
model: "MiniMax-M2.7"
max_steps: 100
workspace_dir: "./workspace"
```

**Capabilities:**
- File ops + shell
- Web search via MCP
- PDF/document generation
- 15 built-in professional skills
- Persistent session memory

**Use cases:** document processing, PDF gen, web research, long reasoning tasks.

## 🚨 Workflow Routing Rules (Nelson's setup)

Memory `reference_workflow_mm_routing.md`:
- ck:workflow auto-routes 4 exec phases to M2.7
- 6 judgment phases to Opus
- **ERP work auto-overrides to all-opus** (don't delegate VBA/Excel COM to M2.7)

Suitable for M2.7:
- ✅ Python scripts (standalone)
- ✅ HTML mockups
- ✅ Frontend code
- ✅ Document/markdown generation
- ❌ VBA / Excel COM (use Opus)
- ❌ Critical pricing logic (use Opus)
- ❌ Judgment/architecture phases (use Opus)

## 🔄 Counting Strategies

To verify usage:
1. Dashboard: https://platform.minimax.io/user-center/payment/token-plan
2. API: `POST /v1/token_plan/remains`
3. Local log: `~/.claude/mm-wf-runs.log` (workflow runs only, không count direct mm-claude.sh)

To track local invocations, optional add to `mm-claude.sh`:
```bash
echo "$(date -Iseconds) | mm-request | $1" >> ~/.claude/mm-request-counter.log
```

## 📚 References

- [Token Plan Setup](https://platform.minimax.io/docs/token-plan/claude-code)
- [Token Plan FAQ](https://platform.minimax.io/docs/token-plan/faq)
- [Best Practices](https://platform.minimax.io/docs/token-plan/best-practices)
- [Mini-Agent](https://platform.minimax.io/docs/token-plan/mini-agent)
- [MCP Guide](https://platform.minimax.io/docs/token-plan/mcp-guide)
- [Subscribe](https://platform.minimax.io/subscribe/token-plan)
- [Dashboard](https://platform.minimax.io/user-center/payment/token-plan)
