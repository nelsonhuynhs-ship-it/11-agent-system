# Research: Next-Phase Evolution — Nelson Email Dashboard
Date: 2026-04-18
Depth: Focused Investigation (8 tool calls)

---

## TOPIC 1: MindsDB for Raw Data Cleaning (Panjiva XLSX ingestion)

### What's new in 2025–2026
MindsDB pivoted hard toward "Agentic Web infrastructure" — not ETL/cleaning. Major 2025 moves:
- MCP (Model Context Protocol) support: MindsDB as universal adapter for Claude Desktop / agents
- Knowledge Base improvements (hybrid search, refresh), SOC2 compliance, Python 3.13 support
- GUI became full IDE; Docker extension simplified setup (no pidfile issues)
- Memory footprint: **no official min-RAM spec published**, community reports ~4–6 GB for stable Docker run

### Can MindsDB clean XLSX → clean CSV?
Yes, technically. MindsDB has a `files` handler (Excel, CSV, JSON → SQL table). You: upload XLSX → `SELECT * FROM files.panjiva` → run an LLM-powered `UPDATE` or `CREATE TABLE AS SELECT` with GPT/Claude to normalize fields. But:
- XLSX multi-sheet bug (#10092 on GitHub) was reported and still only uploads first sheet
- The cleaning logic is SQL + LLM prompt — no native NLP pipeline for "extract company name from noisy text"
- Pre-cleaning (Power Query or pyjanitor) before import is MindsDB's own recommended workflow
- This is **not MindsDB's designed use case** — it's an AI agent/query layer, not a cleaning ETL

### Honest verdict for Nelson's workflow
Nelson already has 28K clean CNEE + Splink/rapidfuzz stack. The Panjiva problem is **field extraction from noisy text** (e.g., "APPLE BEES FURNITURE LLC C/O JOHN" → clean company name), NOT dedup. For that task:

| Tool | Fit | Why |
|------|-----|-----|
| **pyjanitor** | Best | pip install, fluent pandas API, `clean_names()`, `expand_column()`, zero infra |
| **cleanlab** | OK for ML labels | Overkill for Nelson's simple XLSX; targets label noise not string noise |
| **Great Expectations** | CI/validation | Good for schema checks but not extraction/normalization |
| **MindsDB** | Overkill | 4–6 GB Docker, complex setup, designed for agents not ETL |

Lightweight 3-step Panjiva pipeline that beats MindsDB: `pandas.read_excel()` → `pyjanitor.clean_names()` + regex + `rapidfuzz.process.extractOne()` against CNEE master → output clean CSV. Total: ~50 lines, zero Docker.

**VERDICT: SKIP** — MindsDB brings 4–6 GB Docker overhead for a task pyjanitor + rapidfuzz solves in 50 lines. No ROI in 2-month window. Re-evaluate only if Nelson needs multi-source SQL agent across Panjiva + Parquet + CRM simultaneously.

**URLs:**
- [MindsDB 2025 Universal AI Data Hub](https://mindsdb.com/blog/mindsdb-in-2025-from-sql-to-the-universal-ai-data-hub)
- [MindsDB XLSX multi-sheet bug #10092](https://github.com/mindsdb/mindsdb/issues/10092)
- [pyjanitor GitHub](https://github.com/pyjanitor-devs/pyjanitor)

---

## TOPIC 2: Karpathy Second-Brain for System-Wide Memory

### State of the art 2025–2026
Karpathy dropped the gist (442a6bf) in early 2026. It went viral immediately. Community built 4+ OSS implementations within weeks:
- [lucasastorian/llmwiki](https://github.com/lucasastorian/llmwiki) — upload docs + Claude via MCP, writes wiki
- [Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki) — Claude Code / Codex / Cursor sessions → vault
- [skyllwt/OmegaWiki](https://github.com/skyllwt/OmegaWiki) — full-lifecycle research platform, wiki-centric
- rohitg00's "LLM Wiki v2" gist — extends with `agentmemory` patterns

Core pattern is stable and battle-tested in 3 months of community use. Three ops: **Ingest** (1 source → 10–15 wiki pages updated), **Query** (answers filed as new pages), **Lint** (weekly health check, fix contradictions). No vector DB needed for <500K words.

### For Nelson's use case: 28K customer email histories → per-CNEE living notes
This is a **perfect fit** for Karpathy pattern — but adapted for CRM not personal research. Proven architecture 2026:

```
Raw: email_log.csv + reply emails (EML/MSG)
     ↓ LLM extractor (Claude API or Ollama llama3.1:8b)
Wiki: /vault/cnee/{CNEE_ID}.md  ← "John's Candles - likes FOB, hates HPH, replies Tues"
     ↓ simple grep / DuckDB FTS
Retrieval: "show me all CNEE in CANDLE campaign who like fixed rates"
```

**Local LLM vs API:** For 28K CNEE, Ollama llama3.1:8b (8GB VRAM) handles batch extraction offline, ~2–3 min/100 emails. Claude API is 10x faster but costs ~$0.10/1K emails. Given privacy (PII in emails), **Ollama local is preferred** for initial extraction; Claude API for interactive query.

**Pre-built OSS to fork:** `lucasastorian/llmwiki` is closest — but built for research docs not email CRM. Would need: (1) email parser layer (mbox/MSG → text), (2) schema CNEE.md defining fields (company, tier, last_reply, preferences, notes), (3) batch ingest vs. real-time. Estimated fork effort: 2–3 days for MVP.

**Privacy/encryption 2026 standard for solo operator:**
- Vault on local disk or OneDrive with BitLocker (Windows) = sufficient for solo NVOCC
- If VPS: encrypt vault dir with `age` (simple, modern) or VeraCrypt volume
- No enterprise-grade solution needed; GDPR/CCPA risk is low for B2B freight forwarder

**VERDICT: DEFER to Phase 02** — architecture is proven and OSS exists. But Nelson's 2-month window is $10K profit, not knowledge infra. Build after Phase 01 bulk send is stable and generating replies. Foundation work: enable `process_reply.py v3.0` (already exists, not running) first — that gives you structured reply data to feed the vault.

**URLs:**
- [Karpathy LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [lucasastorian/llmwiki OSS implementation](https://github.com/lucasastorian/llmwiki)
- [Ollama + structured extraction (CocoIndex)](https://cocoindex.io/blogs/cocoindex-ollama-structured-extraction-from-pdf)

---

## TOPIC 3: High-Impact Bonus Additions (not in backlog)

1. **LLM Reply Auto-Drafter** — When scanner detects reply, Claude drafts context-aware response using CNEE tier + last rate sent. *Fit: HIGH — directly serves 10 leads/month KPI, ~1 day to wire into existing reply scanner.*

2. **Rate-Change Anomaly Push** — DuckDB query: if carrier rate drops >$50/40HQ vs 7-day avg, push Telegram alert. *Fit: HIGH — SENTINEL-lite, 30 lines, reuses existing Parquet + Telegram notifier.*

3. **Conversational CNEE Search** — Natural language query ("show FURNITURE importers in LA who went cold >60 days") → DuckDB SQL via Claude tool call. *Fit: MEDIUM — good UX upgrade for dashboard tab 6, but Nelson knows SQL already.*

4. **Panjiva Auto-Import Pipeline** — Scheduled script: watch OneDrive/Panjiva/ folder → pyjanitor clean → fuzzy match against CNEE master → append NEW rows with tier=NEW. *Fit: HIGH — closes the data freshness gap, no new infra, natural companion to Topic 1's pyjanitor verdict.*

5. **Weekly ROI Report (auto-gen)** — Every Monday: emails sent, open rate, replies, rate changes, estimated pipeline value. PDF or Telegram. *Fit: MEDIUM — good for Nelson to track $10K goal, but only valuable after click-tracking and reply scanner are stable.*

---

## Unresolved Questions

- MindsDB MCP integration: could MindsDB act as SQL gateway for Nelson's Parquet + CNEE master + Panjiva simultaneously (multi-source join)? Worth testing in Month 3 if Panjiva pipeline is live.
- Ollama on Windows VPS: does 14.225.207.145 have enough VRAM/RAM for llama3.1:8b? Unknown — need `nvidia-smi` check.
- `process_reply.py v3.0` status: exists in repo but "not running" per memory — what's blocking? This is the prerequisite for both Topic 2 vault and LLM auto-drafter.
- Karpathy pattern assumes Obsidian as reader — is Nelson willing to adopt Obsidian, or should vault be readable directly in the dashboard?

---

## Research Metadata
- Searches performed: 8
- Key sources: mindsdb.com, github.com/mindsdb, github.com/karpathy (gist), github.com/lucasastorian/llmwiki, cocoindex.io, pyjanitor-devs
- Research depth: Focused Investigation
