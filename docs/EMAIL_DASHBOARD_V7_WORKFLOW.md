# Email Dashboard v7 — Canonical Workflow (SOT)

**Last updated:** 2026-04-24
**Status:** LIVE — port 8100, Laptop VP Nelson's machine
**Rule:** AI agents MUST read this file BEFORE editing any email_engine/ or dashboard code. Do NOT infer workflow from codebase (has legacy endpoints).

---

## 1. WORKFLOW CHÍNH — Smart Send (DUY NHẤT)

Tab **Quick Send** (◎) là tab mặc định. **Chỉ có 1 cách gửi email**: Smart Send 2-step.

```
┌──────────────────────────────────────────────────────────────┐
│ [1] Bấm ⚙ → Quota Modal                                     │
│     Kéo slider theo TIER:                                    │
│       • CUSTOMER / VIP / HOT / WARM / COLD                   │
│     Tổng = N emails hôm nay                                  │
│     Save                                                      │
│                                                               │
│     Endpoint: GET/PUT /api/rotation/quota                    │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ [2] Bấm "▶ Smart Send"                                       │
│     POST /api/rotation/preview-in-outlook?markup=20          │
│                                                               │
│     Backend:                                                  │
│       • Build plan (top N theo quota)                        │
│       • Render email VIP#1 qua build_email()                 │
│       • Open Outlook COM draft (logo + signature + rate)     │
│       • Cấp preview_token (TTL 10 phút)                      │
│       • Return { preview_token, plan_total, previewed_to }   │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ [3] Nelson visual-verify email draft trong Outlook:          │
│       ✓ Subject đúng                                          │
│       ✓ Rate table POL→POD đủ                                 │
│       ✓ Logo CID "pudonglogo" hiện đúng                       │
│       ✓ Signature pudongprime.vn                              │
│                                                               │
│     Button dashboard đổi: "✓ Confirm & Send All (N)"         │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ [4] Quay về dashboard → Bấm "Confirm & Send All"             │
│     POST /api/rotation/run-today                             │
│     Body: { user_markup: 20, preview_token: "xxx" }          │
│                                                               │
│     Backend:                                                  │
│       • Validate preview_token (single-use)                  │
│       • Enqueue N jobs vào SQLite email_queue                │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ [5] outlook_queue_worker.py (PID bg, 3 thread) pop_one:      │
│       • Rate limit 60/min/thread                             │
│       • Thread-local Outlook COM Dispatch                    │
│       • Inject tracking pixel /t/o/{id}.gif                  │
│       • Inject logo CID                                       │
│       • Send via nelson@pudongprime.vn                        │
│       • Mark SENT / FAILED                                    │
└──────────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────────┐
│ [6] intel/writeback.py debounce flush xlsx master:           │
│       • SEND_COUNT_EMAIL += 1                                │
│       • LAST_SENT_EMAIL = now                                │
│       • EMAIL_STATUS = "SENT"                                │
│     Flush mỗi 5 phút hoặc khi buffer ≥50 dirty CNEE          │
└──────────────────────────────────────────────────────────────┘
```

**Safety Net (chạy ngầm tự động):**
- Cooldown 14 ngày
- Hard limit 3 emails/CNEE ever
- Typo Shield (RapidFuzz 92+ BLOCK)
- Smart Send Window (Tue/Wed/Thu 9-11h local, skip US holidays)
- Blacklist 49 domain + 98 keyword
- Priority filter REPLY_STATUS="HUMAN_REPLY" (exclude bulk)

---

## 2. ENDPOINTS v7 CHÍNH THỨC DÙNG (19 endpoints)

**⚠️ Mọi endpoint KHÔNG có trong list này đều là ORPHAN/LEGACY — AI không được reference khi mô tả workflow.**

| # | Endpoint | Method | Tab dùng | Chức năng |
|---|----------|--------|----------|-----------|
| 1 | `/api/version` | GET | (footer) | Dashboard version badge |
| 2 | `/api/send-stats` | GET | Quick Send | Stats widget (sent today) |
| 3 | `/api/rotation/quota` | GET | Quick Send | Load quota config |
| 4 | `/api/rotation/quota` | PUT | Quick Send | Save quota (modal ⚙) |
| 5 | `/api/rotation/preview-in-outlook` | POST | Quick Send | **Smart Send step 1** |
| 6 | `/api/rotation/run-today` | POST | Quick Send | **Smart Send step 2** (Confirm & Send All) |
| 7 | `/api/rotation/today` | GET | Quick Send | Plan today |
| 8 | `/api/rotation/progress` | GET | Quick Send | Progress bar |
| 9 | `/api/rotation/history` | GET | Quick Send | Lịch sử 1 ngày |
| 10 | `/api/rotation/batch-status` | GET | Quick Send | Session Progress polling 2s |
| 11 | `/api/rotation/preview-sample` | GET | (cần verify) | Optional preview 3 samples |
| 12 | `/api/v6/contacts` | GET | Contacts | List 22,482 CNEE |
| 13 | `/api/v6/contacts` | POST | Contacts | Create new |
| 14 | `/api/v6/contacts/{email}` | DELETE | Contacts | Delete |
| 15 | `/api/v6/contacts/typo-suspects` | GET | Contacts | Typo detection |
| 16 | `/api/panjiva/upload` | POST | Contacts | Import Panjiva |
| 17 | `/api/sent-scan/run` | POST | Inbox | Scan Outlook inbox |
| 18 | `/api/sent-scan/status/{id}` | GET | Inbox | Scan job status |
| 19 | `/api/sent-scan/latest` + `/pending` | GET | Inbox | Replies + pending queue |

---

## 3. TABS v7 (7 tabs) — UI STRUCTURE

```
📂 Workflow
  ◎ Quick Send   ← default, Smart Send flow
  ☆ Priority     ← CNEE có REPLY_STATUS="HUMAN_REPLY"
  📬 Inbox        ← Reply + bounce + auto-block

📂 Data
  👥 Contacts     ← CRUD CNEE master (DuckDB table)
  💬 WhatsApp     ← Tracking (chưa gửi thật)

📂 Intelligence
  ⊟ Insights     ← Analytics + Open Tracker + Follow-up Queue + Alerts + AI Model
  ⚙ Settings     ← Version, health, kill switches
```

---

## 4. ORPHAN CODE — KHÔNG phải workflow v7 (cần clean up)

**46 endpoints trong `web_server.py` KHÔNG ai gọi — gây nhầm lẫn:**

### Deprecated — Có thể xóa
- `POST /api/send` — "fast bulk 1000" cũ, v7 dùng Smart Send thay thế
- `POST /api/email-rate/campaign/bulk-send` — campaign bulk cũ
- `GET /api/contacts` (non-v6) — filter bar cũ, thay bằng `/api/v6/contacts`
- `GET /api/campaigns` — filter campaign cũ
- `GET /api/prospects/priority` — v7 có `/api/rotation/today` thay thế
- `GET/POST /api/customer/exclude*` — v7 dùng EMAIL_STATUS/blacklist
- `GET /api/rate-preview`, `/api/arb-rates` — v7 build inline qua build_email
- `GET /api/history*`, `/api/verify-emails/*`, `/api/data-health` — tools cũ
- `GET /api/market-snapshot`, `/api/model-status`, `/api/predict`, `POST /api/train-model` — AI cũ
- `GET /api/sequence/due`, `POST /api/sequence/send` — sequence engine cũ
- `GET /api/replies/scan`, `/api/leads/*` — v7 dùng sent-scan
- `GET /api/email-rate/campaign/prospects`, `/stats`, `/follow-up-queue` — campaign legacy

### Needs verification (có thể tab Insights dùng)
- `GET /api/analytics/overview`, `/campaign-stats`, `/timeline`
- `GET /api/email-events/alerts*`
- `GET /api/opens/*` (5 endpoints — Open Tracker tab dùng?)
- `GET /api/intel/*`, `/api/intelligence/lanes`, `/api/patterns/*`
- `GET /api/email-rate/batch/*`, `/admin/*`, `/queue/kill*`

### Keep (infrastructure)
- `GET /t/o/{job_id}.gif` — tracking pixel (khi deploy VPS)
- `GET /api/scanner/*` — background scanner
- WhatsApp endpoints — placeholder tab

---

## 5. RULE CHO AI AGENTS

**Trước khi edit code email_engine/ hoặc dashboard:**
1. Đọc file NÀY (SOT workflow v7)
2. Grep `fetch(` trong `plans/visuals/email-dashboard.html` để xác nhận endpoint nào dashboard thực gọi
3. Nếu đụng endpoint KHÔNG trong list 19 ở section 2 → HỎI Nelson trước khi sửa (có thể orphan)
4. KHÔNG được nhắc workflow cũ ("fast bulk 1000", "3-sample preview render in browser", "filter bar") — đó là LEGACY đã deprecated
5. KHÔNG đoán workflow từ endpoint trong `web_server.py` — luôn confirm với HTML

**Khi thêm endpoint mới:**
1. Update section 2 của file này
2. Thêm 1 dòng comment trong endpoint: `# v7: used by {tab} for {purpose}`
3. Orphan endpoints phải mark `# DEPRECATED v7 — do not call` trước khi xóa

---

## 6. Files liên quan

| File | Role |
|------|------|
| `plans/visuals/email-dashboard.html` | Frontend canonical (5,097 lines, 19 fetch calls) |
| `email_engine/web_server.py` | Main API (3,802 lines, 65 endpoints, 46 orphan) |
| `email_engine/api/routes/rotation_router.py` | **Smart Send core** (preview-in-outlook, run-today, quota) |
| `email_engine/api/routes/contacts_router.py` | `/api/v6/contacts/*` (11 endpoints) |
| `email_engine/api/routes/sent_scan_router.py` | `/api/sent-scan/*` (5 endpoints) |
| `email_engine/outlook_queue_worker.py` | Worker 3-thread, COM Dispatch per-thread |
| `email_engine/intel/writeback.py` | Debounced xlsx flush |
| `email_engine/intelligence/builder.py` | `build_email()` — SOT cho email rendering |
| `email_engine/intelligence/template_selector.py` | YAML hot-reload template match |
| `email_engine/config/default_routes.yaml` | Destination config |
| `email_engine/templates/email_rules.yaml` | Template rules |
| `D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx` | Master CNEE (22,854 × 62 cols + SHIPPER) |

---

## 7. Changelog

- **2026-04-24** — File tạo (canonical SOT). Trước đó AI agents đoán workflow từ codebase, dẫn đến hiểu sai lặp lại.
