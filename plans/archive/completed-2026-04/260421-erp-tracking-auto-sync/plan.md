---
name: ERP Tracking Auto-Sync — Email → Sheet Pipeline (Plan C)
created: 2026-04-21
status: superseded-by-260421-erp-full-tracking-system
note: Plan C (13h scope) absorbed into broader Full Tracking System plan which shipped with booking pool + 7-stage + SI 48h alert. Scanner silent-fail root cause resolved (shared.paths integration).
effort: ~11-13h
owner: Nelson
priority: HIGH
related: [260418-shipment-brain]
---

# ERP Tracking Auto-Sync — Full Email-to-Sheet Pipeline

## 🎯 Goal

Anh **không cần gõ tay** HBL/ETD/ATA vào Active Jobs. Scanner đọc email OPS Pudong → extract events → tự populate cells → TRACKING dots tự update.

**User flow sau khi ship:**
```
OPS gửi email "SI BKG 93217723 // HBL PLAX26040016 issued"
    ↓
Scanner 30p phát hiện → extract HBL_NO + Bkg_No
    ↓
Match row 12 Active Jobs (Bkg=93217723) → populate HBL col
    ↓
derive_tracking_stage() → SI_CUT 3/10 ● ● ● ○ ○ ○ ○ ○ ○ ○
    ↓
Nelson mở ERP → thấy TRACKING đã chuyển sang stage 3 tự động
```

## 📐 Current state (audit 2026-04-21)

| Component | Status |
|-----------|--------|
| `shipment_brain.py` scanner code | ✅ Exist, detect 11 stages (BOOKING → PAYMENT) |
| Config `shipment_brain: enabled=true` | ✅ |
| `shipment_state.json` | ❌ EMPTY (last touch 13/04, 0 shipments) |
| `shipment_brain.log` | ❌ 0 bytes (never ran?) |
| Bridge → Active Jobs TRACKING | ❌ **MISSING** |
| Email field extraction (HBL/ETD/ATA) | 🟡 Partial (only stage label, no dates/numbers) |

## 🏗 Architecture

```
┌─ Email OPS Pudong (@pudongprime.vn) ──────────────────────┐
│  Subject: "SI // BKG 93217723 // HBL PLAX26040016..."     │
│  Body: "...HBL issued, ETA HOUSTON 28/04..."              │
└────────────────────────┬──────────────────────────────────┘
                         ↓
┌─ shipment_brain scanner (existing, fix + extend) ─────────┐
│  1. Walk Inbox + CNEE subfolders (every 30 min)           │
│  2. Match mail to known customer (customer_rules.json)    │
│  3. Detect stages (SI_SUBMITTED, LOADED, ATD...)          │
│  4. 🆕 Extract fields: HBL, vessel, ETD, ETA, ATA         │
│  5. Append to shipment_state.json                         │
│  6. 🆕 Append to sync_queue.jsonl (NEW)                   │
└────────────────────────┬──────────────────────────────────┘
                         ↓
┌─ 🆕 sync_queue.jsonl (sidecar, append-only) ──────────────┐
│  {"bkg":"93217723","field":"HBL_NO","value":"PLAX...",    │
│   "source_mail_id":"...", "confidence":0.95,             │
│   "timestamp":"2026-04-21T14:30:00"}                     │
└────────────────────────┬──────────────────────────────────┘
                         ↓
┌─ 🆕 VBA button "Sync Tracking" (Operations ribbon) ───────┐
│  OR auto-trigger on Workbook_Open                         │
│                                                            │
│  Read sync_queue.jsonl → for each entry:                  │
│    - Find Active Jobs row by Bkg_No                       │
│    - Check if cell empty OR older timestamp               │
│    - If yes: populate cell (HBL/ETD/ATA)                  │
│    - Run derive_tracking_stage() for row                  │
│    - Update AJ_TRACKING dots + stage label                │
│    - Update hover comment với event log                   │
│  After sync: clear processed entries from jsonl           │
└───────────────────────────────────────────────────────────┘
```

## 🗂 Phases

### Phase 1 — Debug & fix shipment_brain scanner (2h)
**Problem:** Scanner config enabled nhưng state.json empty, log 0 bytes.

Investigate:
- [ ] Run `python -m email_engine.core.shipment_brain` manual → catch exception
- [ ] Verify import chain from outlook_scanner.py → shipment_brain
- [ ] Check MAPI folder walk — có lỗi permission không
- [ ] Test với 5 sample emails có Bkg_No

Deliverable: shipment_state.json populated ít nhất 10 shipments sau manual run.

### Phase 2 — Extract structured fields (3h)
**Current:** chỉ detect stage label (SI_SUBMITTED, ATD), không extract data.

**Add:**
- [ ] `extract_hbl(body)` regex — patterns: `HBL[#:\s]+([A-Z0-9]{8,20})`, `B/L#([A-Z0-9]+)`
- [ ] `extract_vessel(body)` — patterns: `vessel\s+(?:name\s*:\s*)?([A-Z ]+\d+[EW]?)`
- [ ] `extract_dates(body)` — ETD/ETA/ATA with dd/mm/yyyy or MMM DD
- [ ] Confidence score (regex hit = 0.9, LLM fallback = 0.7)
- [ ] MiniMax fallback for complex mails (low confidence)

Output: per-mail `{bkg, stage, fields: {hbl, vessel, etd, eta, ata}, confidence}`.

### Phase 3 — Sync queue sidecar (2h)
**New file:** `email_engine/data/tracking_sync_queue.jsonl`

Scanner appends each extracted event:
```json
{"bkg":"93217723","field":"HBL_NO","value":"PLAX26040016",
 "source_mail_id":"...","confidence":0.95,
 "timestamp":"2026-04-21T14:30:00","synced":false}
```

- [ ] Write pipeline in `shipment_brain.py` after extract
- [ ] Dedup: same bkg+field+value within 1h → skip
- [ ] Conflict markers (scanner sees old HBL vs Nelson's newer entry)

### Phase 4 — VBA sync button + logic (2h)
**New:** ribbon Operations tab → "🔄 Sync Tracking" button

VBA reads queue → apply to Active Jobs:
- [ ] `Btn_SyncTracking_OnAction` handler
- [ ] For each queue entry:
  - Find row by Bkg_No in col H
  - If target cell empty → populate
  - If target cell has value but older timestamp → populate (respect Nelson's newer manual edits)
  - If conflict (Nelson edited newer) → log, skip
- [ ] Call derive_tracking_stage logic (Python subprocess OR VBA implementation)
- [ ] Update AJ_TRACKING dots + AJ_STATUS text
- [ ] Clear processed entries from jsonl

Optional: auto-trigger on Workbook_Open (like CNEE milestone button).

### Phase 5 — Tracking re-derive + comment (1.5h)
**After sync:**
- [ ] Call `derive_tracking_stage()` for each modified row
- [ ] Update `ApplyTrackingDots(row, stage, animated=False)`
- [ ] Update row's hover comment with event log:
  ```
  ✓ BKG — 2026-04-13 (email confirm)
  ✓ Confirmed — 2026-04-15
  ✓ SI Cut — 2026-04-21 (HBL PLAX26040016 issued)
  ○ Gate-in (pending)
  ○ ATD, ETA, Delivered
  ```

### Phase 6 — Test + backfill (1.5h)
- [ ] Forward 5 real OPS mails → verify auto-populate
- [ ] Backfill existing Active Jobs rows (93217723 + 5 others)
- [ ] Conflict test: Nelson edit + scanner update same row → verify no overwrite
- [ ] 1-day soak

### Phase 7 — Documentation + kill switch (1h)
- [ ] Update SYSTEM_STANDARDS.md với new pipeline
- [ ] Kill switch file `TRACKING_SYNC_DISABLED` → scanner skip
- [ ] Nelson manual override: "Locked" flag per row (future)

**Total: ~13h** (within 10-15h estimate)

## 📂 Files touched

| File | Type | Purpose |
|------|------|---------|
| `email_engine/core/shipment_brain.py` | MODIFY | Add field extraction + sync queue write |
| `email_engine/core/tracking_extractor.py` | NEW | Regex + LLM fallback cho HBL/vessel/dates |
| `email_engine/data/tracking_sync_queue.jsonl` | NEW (runtime) | Sidecar queue |
| `scripts/derive_tracking_standalone.py` | NEW | Python entry called from VBA |
| `D:/OneDrive/NelsonData/erp/erp-v14-jobs-automation.bas` | MODIFY | Add Btn_SyncTracking_OnAction |
| `D:/OneDrive/NelsonData/erp/CustomUI_v14.xml` | MODIFY | Add ribbon button |
| `docs/SYSTEM_STANDARDS.md` | UPDATE | Document new pipeline |

## ⚠ Risks

| Risk | Mitigation |
|------|-----------|
| Email format varies wildly | Regex first, MiniMax LLM fallback |
| Scanner silent fail again | Telegram alert on zero extraction per run |
| Race with Nelson editing xlsm | Sidecar jsonl + VBA button (không write xlsm từ Python) |
| Overwrite Nelson's manual correction | Timestamp comparison + "locked" flag |
| Wrong Bkg match (collision) | Recency filter ETD > today − 90d |
| MiniMax cost explosion | Cap: 100 LLM calls/day, telemetry |

## 🎯 Success criteria

- [ ] shipment_state.json populates từ real emails
- [ ] HBL auto-appears in Active Jobs HBL_NO col within 30 min of OPS email
- [ ] TRACKING dots auto-update from 1 → 3 → 5 → 7 theo stage
- [ ] Hover comment shows event log với timestamps
- [ ] Nelson's manual edits NOT overwritten
- [ ] 1-week soak: 80%+ jobs có tracking update mà không cần Nelson gõ HBL

## 🚫 Out of scope

- Payment/invoice tracking (separate InvoiceLog plan)
- Email-to-quote generation (existing Rate Mix plan)
- External carrier API polling (ONE/ZIM/MSC direct)
- Mobile push notifications

## 🧩 Integration với plans hiện có

- **260418-shipment-brain** (parent plan) — này là implementation của plan đó
- **260420-1700-auto-cnee-milestone-notify** — similar pattern (sidecar + VBA button)
- **260421-0000-invoicelog-auto-scan** — reuse architecture

## 🚦 Decision point

Before coding: verify scanner shipment_brain **có chạy được** trong Phase 1 (2h investigation). Nếu scanner hoàn toàn broken → scope có thể tăng 3-5h cho infrastructure fix.
