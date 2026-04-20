# NEXT SESSION PROMPT — 2026-04-21 resume

**Paste này đầu session mới:**
> *"FreightBrian resume — đọc `memory/MEMORY.md` + `memory/project-session-wrap-20260420.md` + `plans/260416-email-nelson-solo-platform/NEXT_SESSION_PROMPT.md`. Task hôm nay: [mô tả]"*

Last updated: **2026-04-20** (cuối session 28 commits — ERP Quote polish, Customer Memory, carrier_rules unified, TRACKING 7-stage, Job_ID hidden, Month combo)

---

## 📊 Session 2026-04-20 kết quả (28 commits pushed to main)

### ✅ Đã ship

**Email Dashboard v5 — 5 sub-agent parallel:**
- A1 Foundation + Customer Memory (vault/cnee/ + scanner job #6 reply_processing)
- A2 Send-time state rules (parser + 4 preset)
- A3 Smart Compose LLM (💭 Draft button)
- A4 Pattern Learning AI (4 endpoints Insights tab)
- A5 Panjiva Clean Pipeline (6-step ETL + upload UI)
- MiniMax-M2 wired (dotenv + fallback paths)

**ERP v14 — Quote Sprint S1 + S1-v2 + polish:**
- KPI rows + Conditional Format + AutoFilter (Quote sheet)
- Insert-at-top (row 5 thay append)
- Re-neg / Target Watch / Container picker / WIN prompts / Last quoted / Reload VBA buttons
- Exp dropdown 4 preset + ApplyQuickSearch UsedRange fix
- Column polish (hide Date/StatusDate/JobID, outline group Buy/Mar/PUC/Sell)
- Shipments.xlsx → Active Jobs (5) + Archive (46 rows với Bkg)
- CRM build from merge (70 new + NAFOODS preserved)
- carrier_rules/ unified 13 JSON per-carrier on OneDrive
- text_normalize.py extract (DRY shared module)
- FIX → Special Rate rename (Pricing Dry 784 rows)
- TRACKING 7-stage auto-derive (HBL/SI/CY/ETD signals) + hover tooltip
- Job_ID columns hidden (primary key = Bkg_No)
- Month combo dropdown với job count per month (thay Prev/Next/Reset)

**Memory system cleanup:**
- 43 → 20 entries (xoá 54% stale)
- Updated task-scheduler (6 sub-jobs)
- NEW project-erp-v14-state-20260419.md
- NEW project-session-wrap-20260420.md

---

## ⚠ Known concerns / defer

1. **PUC pipeline fix deferred (Option C)** — audit 18 combos shows per-carrier TOF inconsistent · universal fix risky · wait Nelson decide approach (Option A strip config or B PSS_PUC_Lookup sheet)
2. **Note normalize partial** — regex rules wired but patterns don't cover typo variations (Yantain/Yantian) · distinct count still 56 vs target ~10
3. **Month combo refresh** — after new Shipments import, combo count cached · workaround: switch tab
4. **MiniMax API key leaked in chat** — Nelson should rotate on MiniMax dashboard

---

## 🎯 Likely next tasks

### HIGH priority — Nelson đã mention
- **Đổ data tháng cũ vào Active Jobs** — migrate Nov/Dec/Jan/Feb/Mar 2026 jobs từ Shipments.xlsx vào Active Jobs (hiện Active Jobs chỉ có Apr 2026 + 3 quote WIN). Month combo sẽ thấy đủ data sau khi đổ.

### MEDIUM — làm khi rảnh
- **PUC pipeline revisit** — decide Option A/B
- **Note normalize regex upgrade** — handle typo variants
- **Customer Memory vault populate** — đợi reply thực qua scanner verify

### LOW / optional
- **Panjiva weekly cron enable** — Monday 06:00 auto
- **Shipment Brain wire production**
- **Next.js WebApp dashboard phase-06**
- **VPS Deploy S13** — SSH issue unchanged

---

## 🔧 Infrastructure state

| Component | Status |
|-----------|--------|
| `NelsonUnifiedScanner` Task Scheduler | 6 jobs every 30 min 08:00-17:30 (reply_processing wired) |
| MiniMax API | Key in `email_engine/.env` (gitignored) · model M2 |
| Parquet | 4694 rows Pricing Dry · last refresh 2026-04-20 |
| ERP xlsm | 18 sheets · 2 tabs ribbon · 6 VBA modules · TRACKING auto + tooltip |
| carrier_rules | 13 JSON on OneDrive `pricing/carrier_rules/` |
| Email Dashboard v5 | 5 tab Live · port 8100 · pythonw hidden |

---

## 🚫 Rules reminder (never violate)

- `save_preserving_ribbon` when touching xlsm (gotcha #6)
- VBA edits: canonical `D:/OneDrive/NelsonData/erp/*.bas` + mirror `ERP/vba-v14-mirror/`
- `reimport-erp-vba-modules.py` after .bas edits + live compile check via `CommandBars.FindControl(Id=578)`
- Module vars at TOP (gotcha #11)
- No leading underscore (gotcha #12)
- ChrW for Unicode (gotcha #1)
- Close Excel before Python script write (file-lock check)
- Data NEVER in Git (parquet, xlsx, customer data) — OneDrive sync only

---

## 📦 Files created / modified (summary per session)

**New scripts:**
- `scripts/migrate-carrier-rules.py`
- `scripts/puc-audit.py`
- `scripts/erp-quote-polish.py`
- `scripts/erp-s1v2-column-polish.py`
- `scripts/erp-import-shipments.py`
- `scripts/erp-build-crm.py`
- `scripts/erp-fix-tracking-migrated.py`
- `scripts/erp-hide-jobid-cols.py`
- `scripts/erp-archive-add-month.py`
- `scripts/reimport-erp-vba.bat` (WMI wrapper)
- `scripts/migrate_cnee_add_status_state.py`

**New modules:**
- `Pricing_Engine/carrier_rules/__init__.py` (loader)
- `Pricing_Engine/normalization/text_normalize.py` (DRY)
- `email_engine/core/cnee_memory.py`
- `email_engine/core/llm_extract_reply.py`
- `email_engine/core/smart_compose.py`
- `email_engine/core/state_parser.py`
- `email_engine/intelligence/pattern_learner.py`

**New configs on OneDrive:**
- `D:/OneDrive/NelsonData/pricing/carrier_rules/` (13 JSON)
- `D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx` (schema +EMAIL_STATUS +STATE)
