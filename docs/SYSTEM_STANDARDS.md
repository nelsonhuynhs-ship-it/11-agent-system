# Nelson Freight — SYSTEM STANDARDS

**Last updated:** 2026-04-22 23:00
**Status:** 🔒 **SINGLE SOURCE OF TRUTH.** Tất cả chuẩn vận hành hệ thống ở đây. Mọi thay đổi code PHẢI check file này trước. Không tạo file chuẩn khác ở folder khác.

**Cách dùng:**
- Trước khi sửa code: đọc section liên quan
- Trước khi commit: chạy `python scripts/validate-system.py`
- Chuẩn mới Nelson chốt → thêm vào file NÀY (không tạo doc mới)

---

## Section 1 — Canonical File Paths

**Nguồn sự thật duy nhất cho MỌI path.** Code không được hard-code path khác.

| Resource | Path |
|----------|------|
| Parquet rate data | `D:/OneDrive/NelsonData/pricing/Cleaned_Master_History.parquet` |
| Mapping CSVs | `D:/OneDrive/NelsonData/pricing/mapping/V4_FINAL_CHECK_*.csv` |
| Carrier rate mapping JSON | `D:/OneDrive/NelsonData/pricing/mapping/CARRIER_RATE_MAPPING.json` |
| PUC SOC file | `D:/OneDrive/NelsonData/pricing/processed/PUC *.xlsx` (latest) |
| ERP Master xlsm | `D:/OneDrive/NelsonData/erp/ERP_Master_v14.xlsm` |
| ERP VBA exports (.bas canonical) | `D:/OneDrive/NelsonData/erp/*.bas` |
| ERP refresh script | `D:/OneDrive/NelsonData/erp/refresh-v14.py` |
| ERP VBA mirror (repo backup) | `ERP/vba-v14-mirror/` |
| Email dashboard HTML | `plans/visuals/email-dashboard-v6.html` |
| Email local server | `email_engine/web_server.py` |
| CNEE master data v6 | `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx` (2-sheet CNEE+SHIPPER) |
| CNEE master data v2 (fallback) | `D:/OneDrive/NelsonData/email/cnee_master_v2.xlsx` |
| Email log | `email_engine/logs/email_log.csv` |
| Rotation quota config | `email_engine/config/rotation_quota.json` |
| Daily rotation plans | `email_engine/data/daily_plans/YYYY-MM-DD.json` |
| Repo root (PC Home) | `D:/NELSON/2. Areas/Engine_test/` |

**RULE 1.1** — Code Python đọc path qua `shared/paths.py` (resolve OneDrive). Không hard-code string paths trừ fallback.

**RULE 1.2** — Code VBA đọc path qua `FindScript(relPath)` helper. Không hard-code.

---

## Section 2 — Charge Name Mapping (Parquet)

**Giá báo khách all-in LUÔN ở `Charge_Name = 'Total Ocean Freight'`.** Không dùng label nào khác.

| Rate Type | Excel column → Parquet Charge_Name |
|-----------|-------------------------------------|
| FAK | `ALL IN COST` → `Total Ocean Freight` |
| FAK | `BASIC O/F` → `BASIC O/F` (raw, không phải all-in) |
| SCFI (HPL) | `BASE O/F` → `Total Ocean Freight` (đã bao gồm DLF+ISPS+EMF+COMM) |
| SCFI (HPL) | `HLCU Offer` → `HLCU Basic Cost` (basic, không phải all-in) |
| FIX COC | `Base Ocean Freight` → `Total Ocean Freight` |
| FIX SOC HPL | `TOTAL O/F` → `Total Ocean Freight` |
| FIX SOC HPL | `BASIC O/F` → `BASIC O/F` (raw) |

**RULE 2.1** — Mapping ĐI QUA `Pricing_Engine/charge_normalizer.py` → đọc `CARRIER_RATE_MAPPING.json`. Không hard-code dict trong loader.

**RULE 2.2** — Forbidden charge names trong Parquet: `BASE O/F`, `HLCU Offer`. Có = loader chưa normalize → fail validator.

**Incident 2026-04-17:** HPL SCFI mapping ngược → under-quote $1,561/40HQ inland.

---

## Section 3 — Active Jobs Sheet Schema (row 7 headers)

**Cột CỐ ĐỊNH, thứ tự KHÔNG đổi.** Thêm chỉ ở cuối.

```
A=MONTH  B=FAST_ID  C=Job_ID  D=CUSTOMER  E=POL-POD  F=FINAL_DEST
G=CARRIER  H=Bkg_No  I=HBL_NO  J=CONT  K=QTY  L=SERVICE  M=ETD
N=STATUS  O=TRACKING  P=SELL  Q=COST  R=PROFIT  S=EMAIL
T=Routing  U=ETA  V=ATA  W=Contract_Type  X=Profit_Margin
Y=Customer_Type  Z=SI_Received  AA=CY_Cutoff  AB=Door_Delivery
AC=Door_Status  AD=Delay_Count  AE=Delay_Log  AF=Notes
AG=Created_Date  AH=Last_Updated  AI=Cost_Breakdown
AJ=TRACKING_STAGE  AK=RELEASE_EMAIL_SENT  AL=RELEASE_CONFIRMED
AM=PRICE_WATCH_STATUS  AN=PRICE_WATCH_DELTA

[ADDED 2026-04-20 — Milestone Notify cols, added at END]:
AO=ATD_DATE     (date DD/MM/YYYY — filled by VBA Sync Milestones button from milestone_state.jsonl)
AP=ETA_DATE     (date DD/MM/YYYY — Nelson fills manually or from ETA update mails)
AQ=NOTIFIED_ATD  (Y/N dropdown — Y after cnee_milestone drafted ATD email)
AR=NOTIFIED_ETA7 (Y/N dropdown — Y after cnee_milestone drafted ETA-7 email)
```

**RULE 3.4 (Milestone cols)** — ATD_DATE/ETA_DATE/NOTIFIED_* được scan bởi cnee_milestone.py via `email_engine/data/milestone_state.jsonl` sidecar (append-only). Scanner KHÔNG bao giờ write trực tiếp vào xlsm (race condition risk). VBA "Sync Milestones" button đọc sidecar + write vào 4 cols này khi Nelson click.

**RULE 3.1 — Col Q "COST" cell comment format (bắt buộc):**
```
S/C: {Carrier} {Contract#}
Service: {Rate_Type} {Group_Rate} {Note}

Cost Breakdown (USD):
  O/F          ${basic}
  ISPS         ${isps}
  ARB          ${arb}         (nếu POL cross-origin)
  PUC          ${puc}         (chỉ SOC)
  COMMISSION   ${comm}        (nếu carrier có)
  ─────────────
  TOTAL        ${cost}
```

Ví dụ đúng (HPL SCFI HCM→Saint Louis 40HQ):
```
S/C: HPL S25NEA203
Service: SCFI MR PUDSCF001 EC

Cost Breakdown (USD):
  O/F          2,939
  ISPS            25
  EMF             20
  DLF          1,500
  COMMISSION      16
  ─────────────
  TOTAL        4,500
```

**RULE 3.2** — Col W "Contract_Type" là SOC/COC (container ownership), KHÔNG PHẢI contract number. Contract number → append vào comment Col Q.

**RULE 3.3** — Lookup auto-populate Col Q breakdown: Python tra Parquet theo `(Carrier, POL, POD, Place, Container_Type, Rate_Type, Eff, Exp)` → build comment string.

### CRM Sheet Schema (row 1 headers, relevant cols for Milestone Notify)

| Col | Name | Notes |
|-----|------|-------|
| B | Customer_Name | Must match Active Jobs CUSTOMER exactly for lookup |
| H | Contact1_Email | Primary CNEE email (supports semicolon list) |
| K | Contact2_Email | Secondary CNEE email (fallback) |
| AP | AUTO_NOTIFY | **Y/N dropdown (added 2026-04-20)** — set Y to enable auto CNEE drafts |

**RULE 3.5 (CRM AUTO_NOTIFY)** — Chỉ tạo draft khi CRM.AUTO_NOTIFY = "Y" cho customer đó. Default = "N". Nelson opt-in manually per customer.

---

## Section 4 — Rate Type Cheat Sheet (Booking requirements)

Mỗi loại rate cần field gì để email booking request đúng cho carrier CS team:

| Rate Type | Required fields trong email booking |
|-----------|-------------------------------------|
| **FAK** | Contract# + Group Rate (FAK GCFL/PSW...) + Note (SOC/direct/via) |
| **FIX** | Contract# + Group Rate (BASKET NAC PSW/PNW/GCFL) + "FIXED RATE" |
| **SCFI** | Contract# (S25NEA203) + **MR Code** (PUDSCF001) + Scope (WC/EC/GULF) |

**RULE 4.1** — SCFI BẮT BUỘC có MR Code. Email không có MR Code = carrier có thể apply giá FAK default → lose margin.

**RULE 4.2** — Source field trong Parquet:
- Contract# → `Contract` column
- Group Rate → `Group Rate` column (có space)
- MR Code → `Group_Code` column (SCFI only: `PUDSCF001`)
- Note/Scope → `Note` column

---

## Section 5 — ERP Ribbon Launch Pattern (VBA → Python)

**RULE 5.1** — Ribbon callback launch external process PHẢI dùng **WMI Win32_Process.Create**. KHÔNG Shell/wsh.Run.

```vb
' CORRECT:
Dim bootCmd As String
bootCmd = "cmd /c """"" & batPath & """ """ & arg1 & """"""
Dim wmi As Object
Set wmi = GetObject("winmgmts:\\.\root\cimv2:Win32_Process")
wmi.Create bootCmd, Null, Null, procId
ThisWorkbook.Save
ThisWorkbook.Close SaveChanges:=False
```

**WHY:** Excel gom child process vào Job Object, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` kill children khi Excel exit. Shell/wsh.Run children bị kill. WMI tạo process bên ngoài job → sống sót.

**RULE 5.2** — Bootstrap bat phải poll xlsm file lock 30s TRƯỚC khi chạy Python (chờ Excel release lock).

**RULE 5.3** — Reopen Excel qua `start "" "<xlsm>"` (file association), không `excel.exe <xlsm>`.

**RULE 5.4** — Edit `.bas` tại `D:/OneDrive/NelsonData/erp/` (canonical) → re-import qua `python scripts/reimport-erp-vba-modules.py` → copy vào `ERP/vba-v14-mirror/` → commit.

**Incident 2026-04-17:** Refresh All/Rates ribbon dùng `Shell "cmd /c ..."` + `ThisWorkbook.Close` → VBA abort + children killed → Python không chạy bao giờ. Nelson bấm hàng chục lần fail. WMI = fix.

---

## Section 6 — Email Send Pipeline

**RULE 6.1** — Email send CHỈ qua `email_engine/web_server.py` (local PC) → Outlook COM desktop.

**FORBIDDEN paths (đã xoá 2026-04-17, không tạo lại):**
- ❌ `api/routers/email_rate_router.py`
- ❌ `api/routers/email_queue_router.py`
- ❌ `api/routers/auto_quote_router.py`
- ❌ `webapp/src/app/dashboard/rate-send/`
- ❌ `webapp/src/app/dashboard/email-campaign/`
- ❌ `webapp/src/app/dashboard/email-log/`
- ❌ `emailRateApi`, `campaignApi` trong `webapp/src/lib/api.ts`

**RULE 6.2** — SMTP không dùng. Office 365 SMTP credentials không có. **Outlook COM local only.**

**RULE 6.3** — `email_router.py` (không nhầm với `email_rate_router.py`) là Email Event Engine (scan inbox), KHÔNG phải send. Giữ nguyên.

---

## Section 6.5 — Email Anti-Spam Standards (v6 2026-04-22)

**Master data:** `D:/OneDrive/NelsonData/email/contact_unified_v6.xlsx` (2-sheet: CNEE + SHIPPER)

**5-col LOCK (không được edit) — Schema fixed:**
| Column | Type | Purpose |
|--------|------|---------|
| `EMAIL_STATUS` | Enum: ACTIVE/EXCLUDED/SUPPRESSED/HOLD/DEAD | Send eligibility |
| `SEND_COUNT` | Integer | Total sends since baseline |
| `LAST_SENT_DATE` | Date | Last successful send (ISO 8601) |
| `REPLY_STATUS` | Enum: NONE/OOO/LEFT/BOUNCED | Auto-reply classifier |
| `TIER` | Enum: CUSTOMER/VIP/PROSPECT | Priority level |

**RULE 6.5.1 — Cooldown enforcement (hard, no override):**
- Minimum 7 days between sends to same recipient
- Checked by `rotation_engine.py` before queue
- Violation = log WARN + skip email + increment deficiency counter

**RULE 6.5.2 — Hard send limit per window:**
- Max 3 sends per 30-day rolling window per recipient
- Enforced at:
  - `build_daily_plan()` exclusion filter (before pick)
  - `smart_send_window` queue validation (before Outlook)
- Violation = log ERROR + orphan email + manual review flag

**RULE 6.5.3 — Daily quota + rotation:**
- Target: 700 emails/weekday (Monday–Friday only)
- Config: `email_engine/config/rotation_quota.json` (by commodity)
- Default distribution:
  ```
  FLOORING       150    FURNITURE_INDOOR  150
  CANDLE         100    RUBBER            100
  PLASTIC        100    PLYWOOD            50
  FOOD_AMBIENT    30    OTHERS             20
  ```
- Redist logic: commodity not enough candidates → spill to next commodity (auto)
- **Skip on:** Saturday/Sunday + US/VN holidays (via `us_holidays.py`, `vn_holidays.py`)

**RULE 6.5.4 — Excluded list (3 files):**
| File | Purpose | Updated by |
|------|---------|-----------|
| `email_engine/data/excluded_customers.json` | Direct customers (Nelson manual HOLD) | Nelson manual |
| `email_engine/data/excluded_emails.json` | Hard bounces, spam complaints | Scanner auto-detect |
| `email_engine/data/competitor_blacklist.json` | VN team overlap (for SHIPPER sheet) | Panjiva clean script |

**Scan trigger:** After each Quick Send batch completes, `scan-sent-outlook.py` auto-runs (Task Scheduler):
- Read Outlook Sent folder (last 14 days)
- Extract auto-reply subject/body
- Classify: OOO / LEFT / BOUNCED
- Update `REPLY_STATUS` + `EMAIL_STATUS` in master file
- Commit to git log: `scan_sent_YYYY-MM-DD_HHMM.log`

**RULE 6.5.5 — Typo Shield (RapidFuzz fuzzy domain match):**
- Threshold 1: ≥92% confidence → auto-BLOCK (log ERROR, skip)
- Threshold 2: 85–91% confidence → HOLD (manual review flag, ask Nelson)
- Threshold 3: <85% confidence → OK (send)
- Domain list: `email_engine/core/typo_domains.py` (TOP_DOMAINS ~300 entries)
- Usage: called in `web_server.py` before Outlook queue, also in batch verifier

**RULE 6.5.6 — Bounce Harvest v2 (OOO/LEFT auto-detect):**
- OOO reply → parse return date → set `DEFER_UNTIL` (resume send after date)
- LEFT reply → extract replacement contact (position: PRICING/BOOKING/OPS) → queue for Nelson approval before master insert
- Detection: regex patterns in `email_engine/core/harvest_patterns.py`
- Storage: Replacement queue in `email_engine/data/replacement_candidates.json` (append-only)

**RULE 6.5.7 — Smart Send Window (timezone-aware scheduling):**
- Target: Tue/Wed/Thu 9–11h local time (contact's TIMEZONE col)
- Avoid: Mon before 10h, Fri after 15h, Sat/Sun, US federal holidays
- URGENT bypass: contact['URGENT'] == True → send immediately
- Module: `email_engine/core/smart_send_window.py::plan_send_time(contact_row)`

---

## Section 7 — Windows Task Scheduler

**Task được register under `\Nelson\` hoặc root:**

| Task Name | Trigger | Exec | Purpose |
|-----------|---------|------|---------|
| `NelsonUnifiedScanner` | Every 30 min | `outlook_scanner.py` | Scan Outlook inbox cho replies |
| `ForecastRetrainCheck` | ??? | `check-retrain.bat` ⚠ **broken path** | ML model retrain check |
| `NelsonCNEEMilestoneETA7` | Daily 08:00 | `python -m email_engine.core.cnee_milestone eta-reminder` | Check Active Jobs ETA 1-8 days out, compose CNEE arrival notice draft. Register via: `scripts/register-eta-reminder-task.ps1` |

**RULE 7.1** — Task registry đầy đủ phải ở file này. Task mới = thêm row.

**RULE 7.2** — Arg path KHÔNG được chứa khoảng trắng không quote. Quote toàn bộ path trong Arguments.

**Known broken (cần fix):**
- `ForecastRetrainCheck.Arguments = Areas\Engine_test\.claude\worktrees\dazzling-engelbart\scripts\check-retrain.bat` (path `D:\NELSON\2.` bị tách ở space) → task không chạy được

---

## Section 8 — Desktop Shortcuts (Nelson's workflow)

Shortcut ở `C:/Users/Nelson/OneDrive/Desktop/`:

| Shortcut | Target | Purpose |
|----------|--------|---------|
| `ERP Master v14.lnk` | `D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm` | Mở ERP Excel |
| `Nelson Email Dashboard.lnk` | `scripts\start-dashboard-v4.bat` → `email_engine/web_server.py` | Local email server |
| `Refresh Pricing NOW.lnk` | `scripts\refresh-pricing-now.bat` | Full refresh pipeline (import + parquet + xlsm) |
| `Scan Pricing (preview).lnk` | `scripts\refresh-pricing-scan-only.bat` | Preview rate file scan (no import) |
| `Verify ERP.lnk` | `scripts\verify-erp.bat` | Run ERP validation tests |
| `NELSON - D.lnk` | `D:\NELSON` | Folder shortcut |

**RULE 8.1** — Shortcut mới = thêm row vào bảng này + target phải là file trong repo (không ad-hoc).

**RULE 8.2** — Target path có khoảng trắng → shortcut phải handle (shortcut format cho phép, không cần quote).

---

## Section 9 — Temp / Plan Files Cleanup

**RULE 9.1** — Mọi file tạm debugging PHẢI có prefix `_tmp_` (e.g. `_tmp_debug_refresh.py`, `_tmp_test.html`). Cuối task = xoá.

**RULE 9.2** — Plans folder `plans/YYMMDD-*` được tạo BẮT BUỘC trước khi implement lớn. Xong task = archive vào `plans/archive/YYMMDD-*/`.

**RULE 9.3** — Test script sinh ra trong development (e.g. PowerShell test scripts) = xoá cuối task. Chỉ giữ lại nếu có giá trị reusable → move sang `scripts/` với tên chính thức.

**RULE 9.4** — `.agent/`, `claudekit-skills/`, `sessions/` folder (nếu có) = do tooling tạo, không commit.

**RULE 9.5 — ERP Backup Rotation**
- Script: `scripts/erp-backup-rotation.py`
- Target dir: `D:/OneDrive/NelsonData/erp/`
- Patterns handled: `ERP_Master_v14.backup_YYYYMMDD_HHMMSS.xlsm`, `ERP_Master_v14_BACKUP_YYYYMMDD_HHMM.xlsm`, `ERP_Master_v14_backup_YYYYMMDD_HHMMSS.xlsm`
- Default: keep newest 5, delete older. `migration_test.xlsm` deleted if >7 days old.
- NEVER deletes: `ERP_Master_v14.xlsm` (live) or `~$ERP_Master_v14.xlsm` (lock)
- Usage: `python scripts/erp-backup-rotation.py [--dry-run] [--keep N]`
- Schedule: Weekly via Windows Task Scheduler
  ```
  Program:   C:\Users\Nelson\anaconda3\python.exe
  Arguments: "D:\NELSON\2. Areas\Engine_test\scripts\erp-backup-rotation.py" --keep 5
  Trigger:   Weekly, Sunday 09:00
  ```

**Auto-detect:** `python scripts/validate-system.py` check section 9 → list file vi phạm.

---

## Section 10 — Git / Commit Discipline

**RULE 10.1** — Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`. 1 commit = 1 concern.

**RULE 10.2** — KHÔNG commit trước khi chạy `python scripts/validate-system.py` pass.

**RULE 10.3** — Push lên `main` sau khi commit — repo github.com/nelsonhuynhs-ship-it/FrieghtBrian.git.

**RULE 10.4** — Không commit files: `.env*`, `*.xlsx` trong root (data OneDrive riêng), `_tmp_*`, `*.pyc`, `__pycache__/`, `.next/`.

---

## Section 11 — Python Module Architecture

**Active modules (used):**
```
email_engine/                — local Outlook send + scanner + intelligence
  web_server.py              — :8100 local FastAPI, triggers Outlook COM
  core/auto_rate_builder.py  — Parquet → rate table HTML
  core/arb_pricing.py        — ARB cross-origin surcharge
  intelligence/builder.py    — smart email template builder
  outlook_scanner.py         — Outlook inbox scan (run by Task Scheduler)

Pricing_Engine/
  rate_importer.py           — Import Excel rate files → Parquet
  charge_normalizer.py       — Single source mapping (CARRIER_RATE_MAPPING.json)

scripts/
  master_loader_v2.py        — Full Parquet rebuild from Excel files
  refresh-all-bootstrap.bat  — ERP Refresh All launcher (WMI-detached)
  refresh-rates-bootstrap.bat — ERP Refresh Rates launcher
  refresh-all-chain.bat      — Actual chain (rate_importer + refresh-v14.py)
  reimport-erp-vba-modules.py — Push .bas changes into xlsm
  verify-erp.bat             — Desktop shortcut: run tests
  refresh-pricing-now.bat    — Desktop shortcut: full pricing refresh
  refresh-pricing-scan-only.bat — Desktop shortcut: scan preview
  check-retrain.bat          — Scheduled task: forecast retrain
  validate-system.py         — THIS FILE's validator

D:/OneDrive/NelsonData/erp/refresh-v14.py — Parquet → ERP xlsm writer
```

**Deprecated / dead (cần cleanup):**
- `ERP/core/build_erp_v13_ribbon.py` — v13 legacy, replaced by v14
- `ERP/core/refresh.py` — stub only, redirect (CLAUDE.md claimed removed)
- `.agent/` folder — old agent system unused
- `scripts/check_vba_compile.py`, `check_vba_live_compile.py`, `check_vba_modules.py`, `check_zip_structure.py`, `inject_workbook_open.py` — dev tools superseded by `reimport-erp-vba-modules.py`
- `scripts/reimport-erp-vba.py` (no `-modules`) — old version
- `scripts/backfill_intel_from_*.py`, `migrate-markup-store.py`, `build_uat_checklist.py`, `handoff-update.*` — one-shot scripts đã chạy xong
- `email_engine/outlook_send_agent.py`, `email_engine/ingest/send_with_rates.py`, `email_engine/run_outlook_agent.bat`, `email_engine/tests/test_integration.py` — gọi VPS API đã chết

---

## Section 11.5 — Email Intelligence (NEW 2026-04-22)

**Modules for rate & ARB intelligence:**

| Module | Purpose | Status |
|--------|---------|--------|
| `email_engine/core/rule_engine.py` | POL + ARB origin resolution per ORIGIN_COUNTRY | 🔨 TBD (next session) |
| `email_engine/data/arb_rates.yaml` | Rate tables per origin (shanghai, port_klang, lat_krabang, phnom_penh) | ✅ Exists |
| `email_engine/core/auto_rate_builder.py` | Generate rate table HTML per customer | ✅ Integrated (2026-04-22) |

**RULE 11.5.1 — ARB Mapping:**
- POL resolution uses `rule_engine.py` per ORIGIN_COUNTRY (VN/MY/TH/CN/KH)
- Malaysia (MY) fallback: `port_klang` when POL empty
- China (CN): direct carrier lanes (NOT via Vietnam)
- Details: See `docs/ARB_ORIGIN_MAPPING.md`

---

## Section 12 — Incident Log (drift history)

Mỗi lần chuẩn bị vi phạm / gây bug → ghi vào đây để AI/dev future học.

**2026-04-17 — HPL SCFI rate mapping inverted**
- Symptom: quote khách thấp hơn thực tế $1,561/40HQ inland routes
- Root cause: `BASE O/F` mapped to "BASIC O/F", `HLCU Offer` mapped to "Total Ocean Freight" (ngược)
- Fix: swap mapping + purge stale parquet + re-import + JSON source of truth
- Commit: `c2c9aa5`

**2026-04-17 — ERP Refresh ribbon không chạy Python**
- Symptom: Nelson bấm Refresh All 15:50, xlsm saved nhưng log/status stale 15:40
- Root cause: `ThisWorkbook.Close` terminate VBA + Shell children killed bởi Excel Job Object
- Fix: WMI Win32_Process.Create bootstrap pattern
- Commit: `e859164` + `7082997`

**2026-04-17 — Webapp email paths mù quáng**
- Symptom: code Rate Table v2 fix vào `api/routers/email_rate_router.py` thay vì `web_server.py`
- Root cause: 2 router cùng prefix `/api/email-rate/*`, source of truth không rõ
- Fix: xoá `api/routers/email_*.py` + webapp dashboard email pages
- Commit: `d32c6a0`

**2026-04-17 — Col Q cost comment format drift**
- Symptom: tooltip "S/C: COC | COSCO FAK" (SAI — thiếu contract#, thứ tự sai, dùng EIC/BAF)
- Root cause: spec Nelson chốt không được document → refactor sau drift
- Fix: RULE 3.1 ở section 3 + validator check
- Commit: (pending)

**2026-04-22 — Daily Rotation Engine queue integration (verified live)**
- **Symptom:** `queue_to_outlook_worker()` logged emails instead of queuing to Outlook
- **Root cause:** Function call to `queue_store.enqueue_batch()` was missing; import path incorrect (`auto_rate_builder` instead of `email_engine.core.auto_rate_builder`)
- **Fix:** Wired actual queue integration + corrected import + implemented lane-level grouping (24 unique lanes per batch instead of 700 rate builder calls)
- **Verification:** Batch ROT_1776868843 (700 emails) → 700/700 SENT, 0 FAILED
- **Commit:** (pending)
- **Files changed:** `email_engine/core/rotation_engine.py`, `email_engine/api/routes/rotation_router.py`

**2026-04-22 — ARB Origin Mapping research (China correction)**
- **Symptom:** AI documentation claimed China routes transit via Vietnam (HPH), would under-quote
- **Reality:** China ports (Shanghai, Ningbo) have direct carrier lanes with independent full pricing (ONE/CMA/HPL/YML)
- **Incident:** High-impact misunderstanding caught before implementation
- **Resolution:** Document corrected in `docs/ARB_ORIGIN_MAPPING.md`; implementation `rule_engine.py` deferred to next session
- **Parallel finding:** 7,232 Malaysia CNEE (32% of pool) currently mismapped to HCM → need `port_klang` fallback rule

**2026-04-21 — ERP Refresh All mở OneDrive Web thay vì refresh (lần thứ 3)**
- **Symptom:** Nelson bấm Refresh All → tự động mở file xlsm trên OneDrive Web trong browser, không chạy refresh pipeline. Local xlsm không được update. Đã xảy ra **3 lần** (17/04, 20/04, 21/04) — fix xong lần này tạm hết.
- **Pattern chập chờn:** Cùng 1 laptop. Đôi lúc work (nhà), đôi lúc fail (công ty hoặc sau restart). Không có log entry khi fail → black box.
- **Root cause:** `ThisWorkbook.FullName` trả về **URL** (`https://...`) khi Excel mở file từ:
  - Teams chat link click
  - Outlook attachment (cloud)
  - Office 365 Recent Files > Cloud version
  - AutoSave restore sau crash
  - OneDrive "Files On-Demand" chưa fully synced
  VBA spawn bootstrap.bat với URL → `start "" "https://..."` → Windows defaults → browser mở.
- **Secondary bug:** `refresh_all_log.txt` bị bootstrap.bat TRUNCATE mỗi run (line 37: `echo ... > "%LOGF%"`) → mọi CLICK log từ VBA trước đó bị xoá → không thể debug retroactive.
- **Fix (2026-04-21):**
  1. VBA `OnAction_RefreshAll`: detect URL via `InStr(LCase(path), "://") > 0` → redirect to `CANONICAL_ERP_PATH` + user confirm dialog (warn file Web vs Local)
  2. Bootstrap.bat: defense-in-depth URL guard at top — findstr http:// → fallback canonical or exit code 10
  3. New helper `LogRefreshClick` → append to SEPARATE file `refresh_click_log.txt` (not truncated)
  4. Click log status codes: `LOCAL_OK_SPAWNING`, `URL_REDIRECTED`, `URL_BLOCKED_NO_LOCAL`, `URL_USER_CANCELLED`, `WMI_FAIL_RC*`, `WMI_SPAWNED_PID*`, `ERROR_*`
- **Prevention going forward:** Luôn mở ERP xlsm từ Desktop shortcut "ERP Master v14" (target = local path). Nếu mở từ Teams/Outlook → VBA sẽ redirect + warn.
- **Commit:** (pending)
- **Plan doc:** `plans/260421-refresh-all-fix/plan.md`
- **Files changed:**
  - `D:/OneDrive/NelsonData/erp/erp-v14-jobs-automation.bas` (OnAction_RefreshAll + LogRefreshClick + constants)
  - `ERP/vba-v14-mirror/erp-v14-jobs-automation.bas` (mirror sync)
  - `scripts/refresh-all-bootstrap.bat` (URL guard)
  - Reimport via `scripts/reimport-erp-vba-modules.py`

---

## Known Outstanding Violations (cần fix session sau)

**1. 16 Operations ribbon buttons chưa refactor WMI (Section 5 validator FAIL)**
- Buttons: Price Watch, Tracking Sync, Release Alert, Enrich Email, Monthly Report V4, Transit Time, Weekly Report, YML Scan, FAST ID, Reefer Plug, Enrich $, Archive Job, Month Prev/Next/Reset
- Current: dùng `RunPythonHidden` helper với `wsh.Run("cmd /c ...", 0, True)` + `EnsureFileClosedThenReopen` → same bug như Refresh ribbon trước fix
- Scope fix: refactor `RunPythonHidden` → `RunPythonDetached` (WMI.Create) + generic `erp-python-bootstrap.bat`
- Effort: ~30 phút
- Priority: HIGH (các button này Nelson bấm không chạy)

**2. `ForecastRetrainCheck` scheduled task path broken** ✅ FIXED 2026-04-17
- Was: Arguments split at space (`D:\NELSON\2.` | `Areas\Engine_test\...`)
- Now: Execute = `D:\NELSON\2. Areas\Engine_test\scripts\check-retrain.bat` (Windows handles quoting)

**3. Col Q cost comment auto-populate chưa implement**
- Current: Nelson manual nhập / không có
- Spec: RULE 3.1 section 3
- Fix: VBA + Python hook khi thêm row Active Jobs → lookup Parquet + build comment string
- Effort: ~1 giờ

---

## Cleanup History

**2026-04-17 — Cleaned up 20 dead code items** ✅
- `ERP/core/build_erp_v13_ribbon.py` + `refresh.py` — v13 legacy
- `.agent/` folder (~50 files) — old GSD agent system (different from `.claude/` claudekit)
- `scripts/check_vba_*.py` (3 files) + `check_zip_structure.py` + `inject_workbook_open.py` — dev tools superseded by `reimport-erp-vba-modules.py`
- `scripts/reimport-erp-vba.py` (non-`-modules` old version)
- `scripts/backfill_intel_from_*.py` (2 one-shots) + `migrate-markup-store.py` + `build_uat_checklist.py`
- `scripts/handoff-update.sh` + `.ps1` — legacy handoff (replaced by memory/ auto-load)
- `scripts/cloud_sync.ps1` — legacy (OneDrive + rclone handles sync now)
- `email_engine/outlook_send_agent.py` + `ingest/send_with_rates.py` + `run_outlook_agent.bat` + `tests/test_integration.py` — VPS API dependencies (all 4 hit dead `14.225.207.145:8100`)

Next cleanup candidates (detected but not deleted — may still be referenced):
- `intelligence/rag_engine.py` — loads from deleted `.agent/skills/` folder. Orphan now.

---

## Validator

```bash
python scripts/validate-system.py
```

Checks:
- Section 1: canonical paths exist
- Section 2: Parquet không có forbidden charge names
- Section 3: Active Jobs header row 7 match expected
- Section 5: `.bas` không chứa `Shell "cmd` cho launch external
- Section 6: forbidden email paths không tồn tại (api/routers, webapp pages)
- Section 9: không có `_tmp_*` trong working tree
- Section 11: deprecated modules không bị import mới

Exit 0 = pass. Exit != 0 = list chuẩn vi phạm.

---

## Contract với AI / future devs

**Khi sửa code bất kỳ:**
1. Đọc section liên quan của file này
2. Implement theo RULE
3. Chạy validator → pass mới commit
4. Thêm incident log nếu phát hiện drift mới

**Khi Nelson chốt chuẩn mới:**
- Thêm vào file này (không tạo doc mới)
- Add check vào validator
- Update Incident Log

**KHÔNG:**
- Tạo folder `standards/`, `specs/`, `rules/` riêng
- Tạo JSON/YAML config mới cho chuẩn (trừ khi code cần đọc programmatically — như CARRIER_RATE_MAPPING.json)
- Hard-code chuẩn ở nhiều file (DRY)
- Commit khi validator fail
