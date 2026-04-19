# Next Session Prompt — Copy-paste vô đầu session mới

> Copy block dưới đây paste vô Claude session mới.
> Last updated: 2026-04-19 (cuối session "dashboard polish + customer sort + Open Tracker brainstorm")

---

## 📋 PROMPT (copy từ đây xuống)

```
FreightBrian session resume: tiếp tục build Email Dashboard v5 cho Nelson Freight (NVOCC VN→US/CA).

BẮT BUỘC ĐỌC TRƯỚC KHI LÀM GÌ:
1. Engine_test/CLAUDE.md — project rules, paths, architecture
2. memory/MEMORY.md — 20+ memory entries, context toàn bộ
3. memory/idea-open-tracker-tab.md — TASK TIẾP THEO, brainstorm done, cần plan+code

TASK ƯU TIÊN CAO NHẤT:
Build tab "Open Tracker ✉" trong dashboard v5 để Sếp xem AI mở email.
Decisions pending cần hỏi Sếp chốt TRƯỚC khi code:
- Layout: A (Feed) / B (Leaderboard) / C (Hybrid 3-panel, em recommend) / Sếp tự design
- Main action per row: Follow-up button / Preview email cũ / Mark VIP / All 3
- Default scope: 24h / 7d / 30d

HỆ THỐNG ĐÃ CÓ (KHÔNG build lại):
• Dashboard v5 LIVE — 6 tabs (Quick Send, Priority, Analytics, AI Model, Alerts, Queue) + Phase A/B/C polish shipped
• Customer Sort LIVE — Task Scheduler 30min, 59 customer rules, Inbox tự sort vô DIRECT/FWD/CNEE folders
• Schema v3.1 — cnee_master_v2_final.xlsx 22,230 rows × 26 cols (COMMODITY_CATEGORY, ORIGIN_COUNTRY, HS_CODE_PRIMARY, PIC smart-parsed)
• Blacklist — 49 domains + 98 keywords (Top 50 VN NVOCC + Nelson's private list) + whitelist pudongprime.vn
• Email templates — 20 subjects + 15 preheaders + 10 intros + 5 closings (random pick per send)
• Rate table v3 — max 3 carriers/POD, YOUR LANE highlight cho CNEE có DEST
• Open tracking pixel LIVE — /t/o/{id}.gif → DB opened_at + open_count (per-person chính xác)
• Hidden CMD + kill switch — pythonw launch, Desktop shortcuts STOP/Resume, dashboard ARM/DISARM buttons

DATA SOURCE CHO OPEN TRACKER (ready, no migration needed):
• outlook_queue.db → email_queue table → opened_at + open_count columns
• API có sẵn: GET /api/email-rate/analytics/opens?days=7
• API CẦN THÊM (SQL samples trong idea-open-tracker-tab.md):
  - GET /api/opens/feed?days=7&limit=50 — recent opens join cnee_master
  - GET /api/opens/hot?days=7&limit=20 — top open_count DESC
  - GET /api/opens/by-campaign?days=7 — group COMMODITY_CATEGORY → rate %

WORKFLOW START/RESTART DASHBOARD (sau mọi code change):
1. PowerShell: Stop-Process -Name pythonw -Force -ErrorAction SilentlyContinue
2. Double-click Desktop shortcut "Nelson Email Dashboard"
3. Browser mở → hard refresh Ctrl+Shift+R
4. Verify: HTTP 200 + dashboard góc trên phải hiện ● Live

NGUYÊN TẮC NELSON NORTH STAR:
• NHANH - CẠNH TRANH - YÊN TÂM (slogan)
• Solo workflow (không mentee trong email tool)
• KPI 2 tháng: $10K profit/month + 10 leads/month + 1-2 direct customer/month
• File data KHÔNG push GitHub (feedback-no-data-on-github.md)
• Luôn filter qua competitor_blacklist.json mỗi lần import mới

ROADMAP TASK SAU OPEN TRACKER:
1. ✅ Open Tracker tab (task này)
2. Shipment Brain Phase 02 — extractor live, plan có sẵn ở plans/260418-shipment-brain/phase-02
3. Reply Auto-Drafter MVP — highest ROI cho KPI 10 leads/tháng, ~1 ngày code
4. GoComet auto-quote Tier 2 — Vitacoco workflow saver, memory/project-gocomet-opportunity.md
5. Rate Anomaly Telegram push — 30 dòng DuckDB + notify-telegram.py

Bắt đầu: hỏi Sếp 3 decisions pending cho Open Tracker → plan phase file → implement.
```

---

## 🎯 Alternative prompts (nếu Sếp muốn làm task KHÁC)

### Nếu làm Shipment Brain Phase 02:
```
FreightBrian session resume: Ship Shipment Brain Phase 02 live.
Read: plans/260418-shipment-brain/phase-02-extractor-dual-write.md
Blocker cần giải: bridge Outlook COM ↔ filesystem (gap ghi memory project-shipment-brain-scaffold.md).
Scaffold xong ở commit 0bc8aae. Cần: MINIMAX_API_KEY verify + extract 10 email PANDA test accuracy.
```

### Nếu làm Reply Auto-Drafter:
```
FreightBrian session resume: Build Reply Auto-Drafter MVP.
Khi CNEE reply email → Claude/MiniMax đọc reply + rate context + CNEE profile → draft reply.
Nelson approve 1-click → enqueue gửi. Save 5-10ph/reply = 50-100ph/tháng. Direct serve KPI 10 leads.
Read: plans/260416-email-nelson-solo-platform/reports/evolution-plan-20260418.html Section 5.1
Data: scanner/handlers.py đã có REAL_REPLY classifier. Cần hook LLM draft + new API endpoint.
```

---

## 📊 Snapshot hệ thống — cuối session 2026-04-19

| Metric | Value |
|--------|-------|
| Commits today | 18 (`7995fa1` → `3be3771`) |
| Master CNEE | 22,230 × 26 cols |
| Inbox state | 582/851 (269 moved by Customer Sort LIVE) |
| Campaigns shown | 18 COMMODITY_CATEGORY (trước 48 lộn xộn) |
| Open rate | 7.7% real (1/13 test), expect 15-25% live |
| CMD windows on startup | **0** (pythonw hidden) |
| Desktop shortcuts | Nelson Email Dashboard · STOP Email · Resume Email |

## 🗂 File locations quick-ref

| File | Purpose |
|------|---------|
| `email_engine/web_server.py` | FastAPI backend port 8100 |
| `email_engine/intelligence/builder.py` | Email HTML builder |
| `email_engine/outlook_queue_worker.py` | 3-thread Outlook COM sender |
| `email_engine/start-dashboard-v4.bat` | Shortcut launcher (pythonw hidden) |
| `plans/visuals/email-dashboard-v5.html` | Dashboard UI |
| `email_engine/data/outlook_queue.db` | Queue + opens tracking |
| `D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx` | ⭐ Master 22K CNEE |
| `D:/OneDrive/NelsonData/email/customer_rules.json` | 59 khách rules |
| `D:/OneDrive/NelsonData/email/competitor_blacklist.json` | Blacklist 49 + 98 |

## 💡 Pending decisions log

Khi resume session, Sếp sẽ thấy đây là 5 câu hỏi đang chờ chốt:

1. **Open Tracker layout** — A / B / C / custom?
2. **Open Tracker action** — Follow-up / Preview / Mark VIP / All 3?
3. **Open Tracker scope** — 24h / 7d / 30d default?
4. **OTHERS 4,252 rows (19%)** — LLM classify từ COMPANY name? (deferred từ session trước)
5. **FURNITURE_OUTDOOR split** — Sếp gõ 20 keyword để tách kitchen cabinet vs outdoor chair?
