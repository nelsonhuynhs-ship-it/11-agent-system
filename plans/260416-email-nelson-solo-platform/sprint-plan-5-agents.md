---
plan: Email Dashboard v5 — Customer Memory + 5-Tab Hub
date: 2026-04-19
status: IN PROGRESS
agents: 5
---

# Sprint Plan — 5 Agents Parallel

Chốt 2026-04-19 sau brainstorm. 5 sub-agents ship toàn bộ roadmap.

## Goal

Biến Email Dashboard v5 thành **HUB trung tâm** với **Customer Memory System** — mỗi khách có bộ nhớ riêng, AI học từ reply thật, gộp 7 tab → **5 tab workflow-first**.

## 5-Tab Target (từ 7 tab)

| Tab | Purpose | Agent chính |
|-----|---------|------------|
| 🎯 Priority | Landing — VIP+HOT+Overdue + per-customer rules + Memory modal | **A1** |
| 📢 Quick Send | Bulk gửi đại trà + gợi ý giờ theo state + strategy AI | **A2, A4** |
| 📬 Inbox | Unified feed: open + reply + bounce + nút Quét Bounce | **A1** |
| 📊 Insights | Analytics + Data Health + AI Model pattern | **A1, A4** |
| ⚙ Settings | HUB control: ARM/DISARM + Panjiva upload + Customer rules + Scheduled jobs | **A5** |

## 5 Sprint × 5 Agent

### A1 — Foundation + Customer Memory Phase 1 (fullstack)
**Sprint 0 + 1 gộp (coupling cao).** Scope rộng nhất, blocking cho A3/A4.
- Migrate `cnee_master_v2_final.xlsx`: add `EMAIL_STATUS`, `STATE`
- Wire `inbox_scanner` thành job #6 trong `outlook_scanner.py`
- Gộp 7 tab → 5 tab dashboard
- Tạo `vault/cnee/{email}/memory.md` system
- LLM extract structured reply → auto-enrich `customer_rules.json`
- Nút "🧹 Quét bounce ngay" + Data Health section

### A2 — Send-time State Rules (backend)
- Parse STATE từ DESTINATION field
- `send_time_rules.json` 50 states → giờ VN tối ưu
- Endpoint `/api/send-time/suggest`
- Quick Send tab hint + nút "Đặt lịch 21h"

### A3 — Smart Compose (ai-sdk-expert)
- `smart_compose.py` LLM đọc `vault/cnee/{email}/memory.md` + customer rules
- Endpoint `/api/draft/smart?cnee=X`
- Priority tab: nút Draft → smart compose modal
- Depend A1 memory interface — mock nếu chưa có

### A4 — Pattern Learning / AI Model (backend+ai)
- `pattern_learner.py` analyze email_log + opens + replies
- 3 endpoints: top-templates, hot-industries, heatmap
- Insights tab AI Model section
- Quick Send strategy hint

### A5 — Panjiva Clean Pipeline (backend)
- `scripts/panjiva_clean.py` — 6 bước ETL: blacklist → LLM classify → parse state → dedup → filter bounce → merge
- Endpoint `/api/panjiva/upload` multipart
- Settings tab upload UI
- Cron weekly thứ 2

## Dependency Graph

```
A1 (Foundation+Memory) ──┬──> A3 (Smart Compose depends vault)
                         ├──> A4 (Pattern depends reply data)
                         └──> A5 (Panjiva depends EMAIL_STATUS)
A2 (Send-time) ───────────> independent
```

## File Ownership — Strict

| Agent | OWN (edit) | READ only |
|-------|-----------|-----------|
| A1 | `outlook_scanner.py`, `scanner_rules.json`, `scanner/handlers.py`, `cnee_master_v2_final.xlsx`, NEW `core/cnee_memory.py`, NEW `core/llm_extract_reply.py`, `vault/cnee/`, dashboard tab merge + Inbox + Data Health sections, `web_server.py` section #A1 | others |
| A2 | NEW `core/state_parser.py`, NEW `data/send_time_rules.json`, dashboard Quick Send hint section, `web_server.py` section #A2 | A1 output |
| A3 | NEW `core/smart_compose.py`, Priority tab Draft handler extension, `web_server.py` section #A3 | A1 vault interface |
| A4 | NEW `intelligence/pattern_learner.py`, Insights AI Model section, `web_server.py` section #A4 | email_log, outlook_queue.db |
| A5 | NEW `scripts/panjiva_clean.py`, Settings Panjiva section, `web_server.py` section #A5 | blacklist, cnee_master |

**Shared files use FENCE markers** — mỗi agent append section với comment `# === A{N} BEGIN ===` / `# === A{N} END ===`.

## Reports Path

Each agent saves report to:
`plans/260416-email-nelson-solo-platform/reports/agent-{N}-report.md`

## Status Protocol

Each agent reports: `DONE` · `DONE_WITH_CONCERNS` · `BLOCKED` · `NEEDS_CONTEXT`

## Claudekit Skills Per Agent

| Agent | Primary skills |
|-------|---------------|
| A1 | cook, backend-development, frontend-development, ui-styling, databases, fix |
| A2 | cook, backend-development, databases |
| A3 | cook, vercel-ai-sdk, backend-development, ui-styling |
| A4 | cook, backend-development, databases, vercel-ai-sdk |
| A5 | cook, backend-development, databases, vercel-ai-sdk |
