# CLAUDE.md — Nelson Freight AI System
Last updated: 2026-04-26 (Telegram Channels routing added)

## Language
**LUÔN trả lời bằng tiếng Việt** — mọi giải thích, phân tích, hướng dẫn đều dùng tiếng Việt. Code/command vẫn viết bằng tiếng Anh như bình thường.

---

## 🔴 TELEGRAM CHANNELS ROUTING — BẮT BUỘC TUÂN THỦ
> Áp dụng KHI session chạy với `--channels plugin:telegram@claude-plugins-official` (Sếp DM bot @nelson_freight_bot từ phone).

### Rule 1 — Reply NGẮN ≤5 dòng
Sếp đọc trên phone, đi ngoài. Format chuẩn:
```
✅ <Status> — <one-line summary>
   <key metric 1>, <key metric 2>
   📄 Full report: <Funnel HTML link>
   🔀 PR: <GitHub link nếu có>
```
- Status emoji: ✅ done · ⚠ partial · ❌ failed · 🔄 in-progress
- KHÔNG paste markdown table phức tạp (Telegram render xấu)
- KHÔNG paste code block >20 dòng — dump vào HTML thay

### Rule 2 — Output dài → BẮT BUỘC sinh cream HTML + reply link
Khi output > 5 dòng:
1. Invoke skill `cream-output` (có trong skill list)
2. Save vào `D:/OneDrive/NelsonData/reports/<today>/<slug>.html`
3. Auto-rebuild index
4. Reply Telegram chỉ summary + URL `https://laptop-no6f8ibp.tail82dc4e.ts.net/<today>/<slug>.html`

### Rule 3 — Slash command từ Telegram = INVOKE skill literal
Khi Sếp gõ `/skill <args>` từ Telegram (vd `/brainstorm cách add filter`):
- **TREAT AS NATIVE SLASH COMMAND** — KHÔNG reply text "đưa A/B option"
- Invoke skill matching tên (vd `/brainstorm` → invoke brainstorm skill, args = `cách add filter`)
- Mapping 11 commands đã đăng ký Telegram bot menu:

| Sếp gõ | Em invoke |
|---|---|
| `/brainstorm <topic>` | brainstorm skill |
| `/fix <issue>` | fix skill --auto |
| `/cook <feature>` | cook skill |
| `/research <topic>` | research skill |
| `/plan <feature>` | ck-plan skill |
| `/report <subject>` | cream-output skill |
| `/status` | nelson-system-audit skill |
| `/minimax <task>` | delegate-mm skill |
| `/review <branch>` | code-reviewer agent |
| `/deploy` | run cowork_deploy.ps1 |
| `/help` | list 11 commands above |

### Rule 4 — Natural language tiếng Việt → auto invoke skill
Nếu Sếp KHÔNG dùng slash, detect intent từ keywords:
- "brainstorm/thảo luận/ý tưởng" → brainstorm
- "fix/sửa/lỗi" → fix
- "build/code/làm tính năng/implement" → cook
- "research/tìm hiểu" → research
- "lên plan/kế hoạch" → ck-plan
- "audit/check hệ thống" → nelson-system-audit
- "giao M2.7/minimax/đỡ tốn token" → delegate-mm
- "deploy/ship" → cowork_deploy.ps1

### Rule 5 — `cmd:` prefix cho slash literal
Nếu Sếp gõ `cmd: /reload-plugins` hoặc `cmd: /telegram:access list`:
- Strip prefix `cmd:`
- Execute literal slash command (skip mapping)

### Rule 6 — PR-only safety, KHÔNG push main
Khi DM task code change:
1. Branch `claude/<slug>` từ main
2. Commit
3. `git push origin claude/<slug>`
4. `gh pr create --base main --head claude/<slug> --title "..." --body "..."`
5. Reply Sếp link PR (cho Sếp tap review GitHub mobile)
KHÔNG `git push origin main` trừ Sếp explicit "skip PR, push main".

### Rule 7 — Khi report dài kèm cream HTML
Đầu reply Telegram nên có `📄` icon + link Funnel. Nếu Sếp tap link không mở được → báo Sếp `_serve.bat` HTTP server có thể chết, restart bằng double-click `D:/OneDrive/NelsonData/reports/_serve.bat`.

---

## Me
**Nelson Huynh** — Owner, Nelson Freight (NVOCC). Vietnam→USA/Canada freight forwarding.
Email: nelsonhuynhs@gmail.com | Company: nelson@pudongprime.vn

## People
| Who | Role | Contact |
|-----|------|---------|
| **Nelson** | Owner/Boss — tôi | nelsonhuynhs@gmail.com |
| **Johnny** | Mentee | johnny@pudongprime.vn |
| **Jennie** | Mentee | jennie@pudongprime.vn |
| **Blue** | Mentee | blue@pudongprime.vn |
| **Lina** | Mentee | lina@pudongprime.vn |
| **Otis** | Mentee | otis@pudongprime.vn |
| **Jun** | Mentee | jun@pudongprime.vn |

→ Full profiles: memory/people/ | Customer details: memory/context/customers.md

## Terms & Acronyms
| Term | Meaning |
|------|---------|
| **NVOCC** | Non-Vessel Operating Common Carrier |
| **CNEE** | Consignee (người nhận hàng bên Mỹ/Canada) |
| **POL** | Port of Loading (HPH=Hải Phòng, HCM=Hồ Chí Minh) |
| **POD** | Port of Discharge (USLGB=Long Beach, USLAX=Los Angeles…) |
| **40HQ / 20GP** | Container types (40ft High Cube / 20ft General Purpose) |
| **markup** | Phí cộng thêm vào giá carrier (USD/cont) |
| **Campaign** | Nhóm CNEE theo ngành hàng (CANDLE, FURNITURE, FLOORING…) |
| **Parquet** | File dữ liệu giá (~6.6M rows) — Cleaned_Master_History.parquet |
| **DuckDB** | Query engine, 28x nhanh hơn Pandas |
| **Rate & Send** | Tool gửi email giá hàng loạt trên WebApp |
| **SEQ** | Email sequence — follow-up theo bước (Step 0→1→2…) |
| **Cooldown** | Thời gian chờ giữa 2 lần gửi email cho cùng 1 CNEE |
| **S14A/B/C/D** | Sprint 14A/B/C/D — các phase nâng cấp Email Tool |
| **SENTINEL** | Module giám sát anomaly trong N.E.L.S.O.N |
| **ORACLE** | Module dự báo giá trong N.E.L.S.O.N |
| **HPH** | Hải Phòng (port code) |
| **HCM** | Hồ Chí Minh (port code) |
| **VPS** | Server tại IP 14.225.207.145 |

→ Full glossary: memory/glossary.md

## Active Projects
| Project | Status | File |
|---------|--------|------|
| **Email Solo Platform** | 🔨 IN PROGRESS — See `plans/260416-email-nelson-solo-platform/` | `email_engine/web_server.py` |
| **VPS Deploy S13** | ⏳ BLOCKED (SSH issue) | deploy/auto_deploy.bat |
| **JWT Middleware** | ⏳ PENDING | api/ |

→ Full roadmap: `plans/260416-email-nelson-solo-platform/plan.md` | memory/projects/

## 🔒 SYSTEM STANDARDS — Single Source of Truth (2026-04-17)

**TẤT CẢ chuẩn vận hành hệ thống ở 1 file duy nhất: `docs/SYSTEM_STANDARDS.md`**

**Trước khi sửa BẤT KỲ code nào:**
1. Đọc section liên quan trong `docs/SYSTEM_STANDARDS.md`
2. Implement theo RULE
3. Chạy `python scripts/validate-system.py` — pass mới commit

**Chuẩn mới Nelson chốt → thêm vào file NÀY. Không tạo doc/folder mới.**

File chứa 12 section: canonical paths (Parquet @ OneDrive), charge name mapping (Total Ocean Freight = all-in), Active Jobs schema (col Q cost comment format), rate type cheat sheet (FAK/FIX/SCFI booking requirements), VBA launch pattern (WMI not Shell), email pipeline (web_server.py only), Task Scheduler inventory, desktop shortcuts, tmp cleanup, git discipline, Python module architecture, incident log.

## System Overview
Nelson Freight NVOCC — Vietnam→USA/Canada freight forwarding.
Repo: github.com/nelsonhuynhs-ship-it/FreightBrian.git

## Architecture
- FastAPI port 8100 (VPS) — 15 routers, DAL pattern via data_access.py
- Next.js port 3003 (VPS) — 9 pages + login, Cloudflare Tunnel HTTPS
- TelegramBot v5 — runs on VPS (NOT local)
- Parquet ~6.6M rows — ALWAYS filter last 30 days only (fallback 60d→90d nếu empty)
- DuckDB engine — 28.6x faster than Pandas

## ERP v14 Source of Truth

See `docs/erp-v14-source-of-truth.md` — AI agents and new contributors MUST
read this before auditing or modifying ERP v14. Live v14 lives on OneDrive
(`D:/OneDrive/NelsonData/erp/`), not in the repo. ERP/vba/ and ERP/core/refresh.py
were removed (2026-04-13) — they were legacy v13 dead code.

## VPS
IP: 14.225.207.145
Services: nelson-api (8100), nelson-webapp3003 (3003)
DO NOT TOUCH: ports 3000+3001 (TraSuaPOS Docker)
Deploy: git pull → cp files → npm build → systemctl restart

## Machine Roles
- PC Home: ALL Claude/Cowork development (WebApp + email_engine + API)
- Laptop VP: Chatbot runtime only (bot_v5, Telegram) — NO Claude Code
- Both: same GitHub repo

## GoClaw (PC Home)
⚠️ **MỌI file GoClaw đều ở ổ D — KHÔNG phải C:\Users\Nelson\AppData**
| Item | Path |
|------|------|
| DB | `D:/GoClaw/data/goclaw.db` |
| Workspace | `D:/GoClaw/workspace/` |
| Fox Spirit | `D:/GoClaw/workspace/little-fox/SOUL.md` |
| Bat tools | `C:/Users/Nelson/5398948978/` ← exception, intentionally on C |
| Port | 18790 (PC Home only) |
| Version | v1.2.2 (update từ v1.2.0) |
| Agents | Fox Spirit (lead), SALES-OPS, OPS-ENGINE, WATCHDOG |
| Cron | Daily Email Campaign — `0 16 * * 1-5` Asia/Ho_Chi_Minh |
Python: `C:/Users/Nelson/anaconda3/python` (NOT system python3)

## Vercel Skills (for Email Dashboard + AI features)
Load from `skills/` folder when building web UI or AI integrations:
| Skill | Use For |
|-------|---------|
| `vercel-ai-sdk` | AI agents, rate forecast, text generation, tool calling |
| `vercel-workflow` | Durable email sequences (send→wait→follow-up→cooldown) |
| `vercel-building-components` | Dashboard UI components, accessible widgets |
| `vercel-ai-elements` | AI chat interface, email history display |
| `vercel-react-best-practices` | Performance optimization for dashboard |
| `vercel-composition-patterns` | Component architecture patterns |
| `web-artifacts-builder` | Self-contained HTML artifacts (mockups, previews) |

## Repo Cleanup Log (2026-04-13)
- Removed: `tools/goclaw/` (35 dead CLI scripts)
- Removed: `ERP/vba/`, `ERP/core/refresh.py` (legacy v13, real files on OneDrive)
- Moved: `Pricing_Engine/scripts/master_loader_v2.py` → `scripts/`
- Archived: 2 completed plans → `plans/archive/`
- Cleaned: 16 stale branches (14 claude/*, 2 forge/*) local + remote
- Cleaned: email_engine/ duplicate data, dead schedulers, old planning docs

## SSH
HOME PC: C:\Users\ADMIN\.ssh\id_nelson_vps
Laptop VP: id_ed25519 (working as of 2026-03-24)
VPS SSH config: Host nelson-vps → 14.225.207.145

## Deploy (Cowork Auto-Deploy)
⚠ Cowork KHÔNG SSH trực tiếp được (network blocked) — dùng PowerShell script thay thế.

**Cách em deploy:**
```powershell
# Full deploy (API + WebApp):
powershell -ExecutionPolicy Bypass -File "C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test\deploy\cowork_deploy.ps1" -Message "S14A: mô tả thay đổi"

# Chỉ restart API (nhanh, sau khi sửa Python):
powershell -ExecutionPolicy Bypass -File "...\cowork_deploy.ps1" -ApiOnly -Message "fix: ..."

# Chỉ rebuild WebApp (sau khi sửa Next.js):
powershell -ExecutionPolicy Bypass -File "...\cowork_deploy.ps1" -WebOnly -Message "ui: ..."

# Test không deploy thật:
powershell -ExecutionPolicy Bypass -File "...\cowork_deploy.ps1" -DryRun
```

**VPS script (cài 1 lần):** `/home/nelson/deploy.sh` ← copy từ `deploy/vps_deploy_full.sh`
**Log deploy:** `deploy/deploy_log.txt`
**Flow:** Code edit → git commit+push → SSH VPS → git pull → restart services → health check

## Workspace Root (PC Home)
C:\Users\ADMIN\Documents\2. Areas\PricingSystem\Engine_test\
(Previously D:\NELSON\ — fully migrated to C: for Claude/Cowork compatibility)

## Key Files
| File | Purpose |
|------|---------|
| email_engine/data/cnee_master.xlsx | 5,316 CNEE prospects, 23 campaigns |
| email_engine/logs/email_log.csv | 585 rows — send history |
| email_engine/logs/followup_alerts.csv | Follow-up alerts từ scanner |
| email_engine/data/customer_rules.json | Nelson's direct customers + mentee rules |
| api/routers/email_rate_router.py | Rate & Send API (Sprint 13+14) |
| webapp/src/app/dashboard/rate-send/page.tsx | Rate & Send WebApp UI |
| db/duckdb_engine.py | DuckDB query engine |
| Pricing_Engine/data/Cleaned_Master_History.parquet | Rate data ~6.6M rows |
| deploy/auto_deploy.bat | VPS deploy script |
| memory/ | Memory system — glossary, people, projects |

## Rules (NEVER VIOLATE)
- ALL files under C:\Users\ADMIN\Documents\2. Areas\ — C:\tmp FORBIDDEN
- Backup before edit, never delete files
- Parquet: filter last 30 days (fallback 60d→90d auto nếu empty)
- API: use DuckDB via FreightDB, never raw Pandas read_parquet in new code
- Ports 3000/3001: never touch (TraSuaPOS)
- email_engine/ send = Office 365 SMTP (not Outlook COM)

## SMTP Config
SMTP_HOST=smtp.office365.com | SMTP_PORT=587
Files: email_engine/.env + api/.env

## Email Campaigns (cnee_master.xlsx)
| Campaign | Prospects | Notes |
|----------|-----------|-------|
| FLOORING | 1,057 | Largest |
| FURNITURE | 745 | |
| PLASTIC | 590 | |
| MALAYSIA | 562 | |
| CANDLE | 495 | Active campaign |
| + 18 more | ~867 | See memory/context/campaigns.md |

Total: 5,316 prospects | Sent: 4,198 | Not Sent: 1,118

## Auto-Load Skills (ALWAYS READ AT SESSION START)
> **Rule:** Mỗi session Cowork mới, em PHẢI: (1) đọc CLAUDE.md + memory files, (2) đọc skill phù hợp theo task type bên dưới — KHÔNG chờ anh nhắc.

### 🔁 Core Memory (load mỗi session — BẮT BUỘC)
```
Engine_test/CLAUDE.md                                        ← đang đọc ✅
Engine_test/memory/glossary.md                               ← terms & acronyms
Engine_test/memory/projects/sprint-14-email-tool.md          ← sprint status
Engine_test/memory/context/system-architecture.md            ← infra & deploy
```

### 🛠 Skill Map — Load theo task type (ĐỌC TRƯỚC KHI LÀM)

#### 🐍 Backend / API / Python
| Task | Skill path |
|------|-----------|
| FastAPI router, DuckDB query, email engine | `claudekit-skills/.claude/skills/backend-development/SKILL.md` |
| Debug lỗi Python / API / logic | `claudekit-skills/.claude/skills/debugging/SKILL.md` |
| Database schema, query optimization | `claudekit-skills/.claude/skills/databases/SKILL.md` |

#### 🌐 Frontend / WebApp
| Task | Skill path |
|------|-----------|
| Next.js page, App Router, RSC, data fetching | `claudekit-skills/.claude/skills/web-frameworks/SKILL.md` + `.claude/skills/next-best-practices/SKILL.md` |
| UI component, dashboard design, Tailwind | `claudekit-skills/.claude/skills/ui-styling/SKILL.md` + `.claude/skills/ui-ux-pro-max/SKILL.md` |
| Frontend React/TypeScript patterns | `claudekit-skills/.claude/skills/frontend-development/SKILL.md` |
| Test WebApp trên localhost (Playwright) | `claudekit-skills/.claude/skills/web-testing/SKILL.md` |

#### 🚀 Deploy / DevOps
| Task | Skill path |
|------|-----------|
| Deploy VPS, Docker, systemctl | `claudekit-skills/.claude/skills/devops/SKILL.md` |
| CI/CD, GitHub Actions | `claudekit-skills/.claude/skills/devops/SKILL.md` |
| *(Cowork deploy script)* | `deploy/cowork_deploy.ps1` — xem Deploy section |

#### 🧠 Planning / Architecture
| Task | Skill path |
|------|-----------|
| Brainstorm sprint, lên kế hoạch | `.claude/skills/brainstorm-upgrade/SKILL.md` |
| Context engineering, memory system | `claudekit-skills/.claude/skills/context-engineering/SKILL.md` |
| System design / ADR | `claudekit-skills/.claude/skills/backend-development/SKILL.md` |

#### 📄 Document / File
| Task | Skill path |
|------|-----------|
| Tạo file Word (.docx) | `.claude/skills/docx/SKILL.md` |
| Tạo file Excel (.xlsx) | `.claude/skills/xlsx/SKILL.md` |
| Tạo file PDF | `.claude/skills/pdf/SKILL.md` |
| Tạo slide PowerPoint (.pptx) | `.claude/skills/pptx/SKILL.md` |
| Tạo scheduled task / cron job | `.claude/skills/schedule/SKILL.md` |
| Tìm / cài thêm skill mới | `.claude/skills/find-skills/SKILL.md` |

### 📂 Base paths
```
Claudekit skills : Engine_test/.claude/skills/[skill-name]/SKILL.md    ← CORRECT (108 skills installed)
                   (legacy wrong path: Engine_test/claudekit-skills/.claude/skills/ — does NOT exist)
Cowork skills   : /sessions/.../mnt/.claude/skills/[skill-name]/SKILL.md
```

### ⚡ Quick-load command (anh paste 1 dòng này vào đầu mỗi session)
```
FreightBrian session: [mô tả task hôm nay — VD: "S14A fix fallback", "build email history page", "debug API lỗi 500"]
```
→ Em tự đọc CLAUDE.md + memory + load đúng skill theo task, không hỏi lại.

---

## Sprint Status (2026-04-01)
✅ S1–S4, N.E.L.S.O.N v2.0, Intelligence Pipeline, Auto-Rate, Knowledge Parquet
✅ S13 Rate & Send API + WebApp
✅ email_engine/ in Git
✅ S14 Campaign CNEE tab (bulk send 50)
🔨 S14A — Rate fallback + freshness (IN PROGRESS)
⏳ S14B — Email History + Follow-up Dashboard
⏳ S14C — Price Delta + Smart Compose
⏳ S14D — Bulk Send Intelligence + Cooldown
⏳ VPS Deploy S13 (SSH issue blocking)
⏳ JWT middleware, Mentee dashboard, Carrier Scorecard
