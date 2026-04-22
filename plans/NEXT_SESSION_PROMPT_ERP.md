# NEXT SESSION PROMPT — ERP v14 continuation

**Paste nguyên chunk này vào đầu session mới để AI tiếp tục đúng track ERP:**

---

> FreightBrian ERP resume — đọc các file memory và plan sau trước khi làm gì:
>
> **Memory (BẮT BUỘC đọc trước):**
> - `memory/MEMORY.md` — index
> - `memory/project-erp-state-20260421.md` — live state ERP sau session 21/04 (shipped + pending + architecture)
> - `memory/project-email-dashboard-state-20260421.md` — sister state email dashboard
> - `memory/feedback-erp-refresh-all-url-bug.md` — incident pattern (URL bug xảy ra 3 lần rồi)
>
> **Plans cần review:**
> - `plans/260421-erp-tracking-auto-sync/plan.md` — **PRIORITY #1** — Plan C v2 (13h, pending approval)
> - `plans/260421-erp-tracking-auto-sync/visuals/plan-review.html` — HTML review Nelson đã xem
> - `plans/260421-0000-rate-mix-calculator/plan.md` — pending (3h, BLOCKED ribbon concurrency)
> - `plans/260421-0000-invoicelog-auto-scan/plan.md` — pending (4h, reuse CNEE architecture)
>
> **Task hôm nay:** [mô tả cụ thể]

---

## 🎯 State snapshot (tóm tắt để AI hiểu context nhanh)

### Đã ship session 21/04
1. ✅ **Refresh All URL bug fix** — VBA detect URL → redirect canonical local. Log tách `refresh_click_log.txt`. Incident #3 đã fix dứt điểm.
2. ✅ **CUSTOMER col fix** — Active Jobs hiện NAME (PANDA HCM) thay CODE (CS001296). MarkQuoteWin lookup CRM col 2.
3. ✅ **Cleanup ~141 MB** — email, pricing, erp folders sạch.
4. ✅ **Deep audit report** — 3 Critical + 5 High + 5 Medium tech debt mapped.

### Pending decision (Nelson cần chốt)
- **Plan C Phase 1 gate:** Tại sao shipment_brain scanner state.json empty + log 0 bytes? Phải investigate 2h trước khi commit full 13h.
- **Rate Mix 4 open questions:** tier markup flat $275 vs prompt, 40HC-only vs all containers, ambiguous peer auto-pick vs UI, custeam ratio memo storage
- **InvoiceLog 5 open questions:** accounting allowlist SMTPs, payment mail source, partial payment status, reminder dedup 7d, DATE_ISSUED timing

### Locked rules (never violate)
1. Canonical xlsm path: `D:\OneDrive\NelsonData\erp\ERP_Master_v14.xlsm` — use const `CANONICAL_ERP_PATH`
2. Open ERP từ Desktop shortcut, KHÔNG từ Teams/OneDrive Web (FullName → URL bug)
3. Close Excel BEFORE reimport VBA
4. Sync .bas 2 chỗ: canonical `D:/OneDrive/...erp/` + mirror `ERP/vba-v14-mirror/`
5. CUSTOMER col = NAME (not CODE)
6. No LLM on shipment data — regex only
7. Bkg unique per sales — no cross-sales filter needed
8. Data NEVER in Git (xlsm, parquet, cnee_master gitignored)

### Volumes
- Active Jobs: 12 rows (current Apr 2026)
- Archive: 48 rows
- Pricing Dry: 4,694 rows
- CRM: 72 rows
- VBA: 5,790 LOC

---

## 🚀 Recommended next actions (theo priority)

### Option A — Start Plan C Phase 1 (2h, HIGH VALUE)
Debug tại sao `shipment_brain.py` scanner state.json empty + log 0 bytes. Manual run + catch exception + check MAPI perms + test 5 sample emails. Deliverable: state.json populated ≥10 shipments.

**Command start:**
```bash
cd "D:/NELSON/2. Areas/Engine_test"
python -m email_engine.core.shipment_brain
tail -f email_engine/core/shipment_brain.log
```

Nếu scanner OK → tiếp Phase 2-8 (11h remaining).
Nếu scanner broken sâu → scope +3-5h infrastructure fix trước.

### Option B — Ship Rate Mix Calculator (3h)
4 open questions cần Nelson chốt trước (dropdown tier, container scope, peer pick, ratio storage). Sau approve → spawn backend-engineer agent code VBA ribbon group.

**File:** `plans/260421-0000-rate-mix-calculator/plan.md`

### Option C — Ship InvoiceLog Auto-Scan (4h)
5 open questions cần Nelson chốt (accounting allowlist, payment source, partial status, reminder dedup, date issued timing). Reuse 90% CNEE Milestone architecture → spawn agent.

**File:** `plans/260421-0000-invoicelog-auto-scan/plan.md`

### Option D — Tech debt sprint (3h)
7 quick wins per audit report:
1. Delete `erp-v14-preset-dryreefer.bas` (127 LOC orphan)
2. Delete 7 DEPRECATED Month subs
3. Extract PUC alias map (duplicated 2 places)
4. Fix `MsgBoxOrSilent` wrong module target
5. Delete 8 dead callback handlers
6. Move `QUOTE_DIR` to Const
7. Merge `FindScript` / `FindScriptRR`

### Option E — Continue Email Dashboard Sprint 2 (5h)
Separate roadmap — O365 quota tracker + throttle + suppression auto-management.
**File:** `plans/260421-email-dashboard-deliverability-roadmap/sprint-2-reputation-building.md`

---

## 💬 Quick guide cho AI mới

**Khi Nelson invoke session mới:**

1. Read ERP state + Plan C file
2. Check if Excel ERP đang mở (PowerShell `Get-Process EXCEL`)
3. Verify web server port 8100 status (nếu cần test email dashboard)
4. Check recent git log 10 commits để biết ship gì mới
5. Ask Nelson: "Tiếp tục Plan C Phase 1, hay muốn làm plan khác?"

**Patterns đã learnt:**
- Nelson prefer **plan-first, code-after** cho scope lớn (>5h)
- Nelson prefer **HTML workflow review** cho plans (via `/ck:preview --html --plan-review`)
- Nelson muốn **Vietnamese thuần** explanation, ít jargon
- Nelson prefer **YAGNI** — cắt scope nếu over-engineer
- Nelson không có DNS access, không admin IT, không SMTP admin — mọi thing qua Outlook COM
- Nelson mang 1 laptop duy nhất (không PC Home vs Laptop VP)

**Anti-patterns em đã gặp:**
- Over-worry security (Bkg cross-sales — Nelson said không conflict)
- Over-engineer LLM (MiniMax không cần cho ERP extraction)
- Assume complex = professional (Nelson prefer simpler)
- Build scanner from scratch khi đã có shipment_brain.py (reuse!)

---

## 🎨 HTML plan convention (từ session 21/04)

Mỗi plan mới em tạo → generate HTML review có:
- Workflow diagram Mermaid
- Current vs Target side-by-side
- Phase cards với effort badge
- Files touched table
- Risk matrix
- Success criteria
- Theme toggle light/dark (mandatory)

**Command:** `/ck:preview --html --plan-review <plan-path>`
**Output:** `{plan-dir}/visuals/plan-review.html`
**Palette rotation:** mỗi plan dùng palette khác (deep blue+gold / terracotta+sage / teal+slate / rose+cranberry / amber+emerald)

---

**Session 21/04 signature:**
- Commits session: 6 (refresh fix, customer fix, backup rotation, audit report, plan files, blacklist update)
- Plans shipped: 4 (CNEE Milestone v2, Dashboard Bounce Fix v2, Bounce Learning v3, Refresh All Fix)
- Plans created: 4 (Deliverability Roadmap, Rate Mix, InvoiceLog, Tracking Auto-Sync)
- Cleanup: ~141 MB freed
- Incidents logged: 1 (URL bug 3-time recurrence)
