---
title: "ERP Contract # + Group Rate Pipeline Fix"
description: "Carry Contract number + Group Rate from parquet → Pricing Dry/Reefer → Active Jobs COST tooltip + booking email. ONE group code resolver (12 priority rules) for Dry + Reefer."
status: completed
shipped: 2026-04-21
commit: 291349b
priority: P1
effort: 4h
branch: main
tags: [erp-v14, vba, parquet, pricing, one-carrier, booking-email]
created: 2026-04-21
owner: Nelson
---

# Plan — ERP Contract # + Group Rate Fix

## 🎯 Goal

Fix data mất khi load parquet → Pricing Dry/Reefer → Active Jobs. Cost tooltip + booking email phải ghi ĐÚNG:
- **Contract #** (service contract thật, vd `25-4402`, `ONEYSGN-R12345`)
- **Group Rate** (text, vd `FAK PNW SOC`, `GROUP A GCFL`)
- **Group Code số** (chỉ ONE, vd `990146`, `990132` — BẮT BUỘC để book ONE SOC + Reefer)

Áp dụng cho **Dry + Reefer** (ONE rule priority 3-4 là REEFER).

## 📋 Nelson Decisions (Locked)

| # | Decision |
|---|----------|
| 1 | Apply ONE group rules tại **parquet load time** (không runtime VBA) |
| 2 | Chỉ **ONE** cần numeric group code. 13 carriers khác dùng text `Group Rate` |
| 3 | Contract **không bao giờ rỗng** — không cần fallback "[TBD]" |
| 4 | **Pricing Reefer cần** apply ONE group code. **Default = `1` (FROZEN)** vì Nelson nhận chủ yếu hàng âm độ, ít FRESH/CHILLED |
| 5 | Job cũ giữ nguyên — chỉ job mới sau deploy có tooltip đúng |

## 🗂 Current State

### Parquet (source of truth) — ✅ ĐÃ CÓ
```
schema: POL, POD, Place, Carrier, Commodity, Contract, Eff, Exp, Note, 
        Group Rate, Charge_Name, Container_Type, Amount, Source_File, 
        Rate_Type, Group_Code, Charge_Meta
```
- `Contract` populated (78 unique numbers across 14 carriers)
- `Group Rate` populated (FAK BAL, FAK EC, FAK PSW SOC, GROUP A GCFL, etc.)
- `Group_Code` **EMPTY** — never populated by master_loader

### Pricing Dry/Reefer (destination) — ❌ THIẾU
```
POL | POD | Place | Carrier | Commodity | Eff | Exp | Note | Source | 20GP | 40GP | 40HQ | 45HQ | 40NOR
```
- Không có Contract, Group Rate, Group Code

### VBA OnAction_MarkQuoteWin — ❌ SAI
- Truyền `source` (FAK/FIX) làm `contract` param cho ApplyBookingMailto
- Cost tooltip: `"S/C: COC | ONE FAK"` — hoàn toàn nhầm

### ApplyBookingMailto — 🟡 Parameter sẵn sàng, data sai
- Line 1316: `"- Contract number: " & contract` — nhận `source` sai
- Không có Group Rate / Group Code fields

---

## 🏗 Architecture (final)

```
┌─ Rate sheet xlsx (incoming/) ─────────────────────────┐
│  Contract: 25-4402, Group Rate: FAK PNW SOC           │
└───────────────────┬───────────────────────────────────┘
                    ↓
┌─ master_loader_v2.py (MODIFY) ────────────────────────┐
│  1. Extract Contract (ĐÃ CÓ)                           │
│  2. Extract Group Rate text (ĐÃ CÓ)                    │
│  3. NEW: apply ONE group code rules for ONE rows       │
│     → Group_Code populated ONLY for Carrier=ONE         │
└───────────────────┬───────────────────────────────────┘
                    ↓
┌─ Cleaned_Master_History.parquet ──────────────────────┐
│  Contract=25-4402 | Group Rate=FAK PSW SOC |           │
│  Group_Code=990146 (chỉ ONE)                           │
└───────────────────┬───────────────────────────────────┘
                    ↓
┌─ refresh-v14.py (MODIFY) ─────────────────────────────┐
│  Write Pricing Dry + Reefer với 3 cột hidden THÊM:     │
│  - Col 15: Contract (hidden)                           │
│  - Col 16: Group Rate (hidden)                         │
│  - Col 17: Group Code (hidden, chỉ fill cho ONE)       │
└───────────────────┬───────────────────────────────────┘
                    ↓
┌─ Nelson click WIN trên Pricing Dry row ───────────────┐
│  OnAction_MarkQuoteWin reads hidden cols               │
└───────────────────┬───────────────────────────────────┘
                    ↓
┌─ Active Jobs row — Cost col tooltip (UPDATE) ─────────┐
│  Rate Type: FAK (SOC)                                 │
│  Contract: ONEYSGN-25-4402                             │
│  Group: FAK PSW SOC                                    │
│  Group Code: 990146 (TPE1 - FAK & GARMENT)  ← chỉ ONE  │
│  ---                                                   │
│  COST: O/F $1,800 + ORC $50 + ...                      │
│  FREIGHT TOTAL/BOX: $1,975                             │
│  TOTAL (2x): $3,950                                    │
└───────────────────┬───────────────────────────────────┘
                    ↓
┌─ ApplyBookingMailto email body (UPDATE) ──────────────┐
│  - Carrier: ONE SOC                                    │
│  - Contract number: ONEYSGN-25-4402                    │
│  - NAC/Group: FAK PSW SOC                              │
│  - Group Code: 990146     ← chỉ ONE                    │
│  - POL/POD/ETD/...                                     │
└───────────────────────────────────────────────────────┘
```

---

## 🗂 Phases

### **Phase 1: ONE Group Code Resolver** (1.5h) — Foundational

**New file:** `Pricing_Engine/one_group_resolver.py`

Implement 12 priority rules từ `carrier_rules/ONE.json`:
```python
def resolve_one_group_code(
    contract_type: str,      # "FAK" | "FIX"
    commodity: str,          # "GARMENT" | "REEFER FROZEN" | ...
    note: str,               # "SOC DIRECT" | "" | ...
    pod: str,                # "USLAX" | "CATOR" | ...
) -> tuple[str, str]:        # (code, label) e.g. ("990146", "TPE1 - FAK & GARMENT")
```

Logic:
- POD region detect: `pod.startswith("CA") and not pod.startswith("CAI")` → CANADA else USA
- Priority scan 1→12, first match returns
- Ambiguous codes (`"990131|990132"` for Canada consol) → default to first; Nelson can override

**Tests** (inline unit tests):
- ONE FIX GARMENT → 990117
- ONE FAK REEFER (default, unknown temp) → **1 (FROZEN — Nelson default)**
- ONE FAK REEFER FROZEN / SEAFOOD / FROZEN FISH → 1
- ONE FAK REEFER CHILLED / FRESH → 2
- ONE FAK GARMENT SOC USA → 990117 (TPE10)
- ONE FAK GARMENT USA (no SOC) → 990146 (TPE1)
- ONE FAK any CANADA → 990131 (default single, consol = 990132)

**Default rule:** Nếu commodity contains "REEFER" nhưng không rõ FROZEN hay CHILLED → return **`1` (FROZEN)**. Log "defaulted-to-frozen" cho Nelson audit nếu cần.

**Deliverable:** CLI tool + importable module.

---

### **Phase 2: Parquet Load Integration** (1h)

**Modify:** `scripts/master_loader_v2.py`

- After existing Contract + Group Rate extraction (line 534)
- Add ONE group code population step:
  ```python
  if row['Carrier'] == 'ONE':
      code, label = resolve_one_group_code(
          row['Rate_Type'], row['Commodity'], row['Note'], row['POD']
      )
      row['Group_Code'] = code
      # Store label too? Or rebuild at VBA time? → store in Group_Code col for speed
  ```
- Run full reimport of `incoming/` to backfill

**Verify:** Query parquet → count ONE rows với non-empty Group_Code > 0.

---

### **Phase 3: Refresh Pipeline Carry Cols** (45m)

**Modify:** `ERP/vba-v14-mirror/refresh-v14.py`

Pricing Dry sheet write logic:
- Current cols 1-14: POL, POD, Place, Carrier, Commodity, Eff, Exp, Note, Source, 20GP, 40GP, 40HQ, 45HQ, 40NOR
- Add col 15: **Contract** (hidden)
- Add col 16: **Group Rate** (hidden)
- Add col 17: **Group Code** (hidden, chỉ ONE có value)

Pricing Reefer: cùng 3 cột hidden tương tự.

`ws.column_dimensions['O'].hidden = True` + P + Q for Dry sheet.

**Test:** refresh → verify cells có data, hidden attribute true.

---

### **Phase 4: VBA Cost Tooltip + Mailto Update** (1h)

**Modify:** `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas`

#### 4.1 Read hidden cols trong `OnAction_MarkQuoteWin`
```vbnet
Dim contractNo As String, groupRate As String, groupCode As String
contractNo = wsPricing.Cells(sourceRow, 15).Value  ' Contract
groupRate = wsPricing.Cells(sourceRow, 16).Value   ' Group Rate
groupCode = wsPricing.Cells(sourceRow, 17).Value   ' Group Code (ONE only)
```

#### 4.2 Update `scLine` + `sCostBreakdown`
```vbnet
Dim socSuffix As String: socSuffix = IIf(isSOC, " (SOC)", "")
scLine = "Rate Type: " & contractLabel & socSuffix & Chr(10) & _
         "Contract: " & contractNo & Chr(10) & _
         "Group: " & groupRate
If carrier = "ONE" And groupCode <> "" Then
    scLine = scLine & Chr(10) & "Group Code: " & groupCode
End If
```

#### 4.3 Update `ApplyBookingMailto` call + signature
Thêm 2 param mới: `groupRate As String, groupCode As String`

Email body:
```vbnet
body = body & "- Contract number: " & contractNo & vbCrLf
body = body & "- NAC/Group: " & groupRate & vbCrLf
If carrier = "ONE" And groupCode <> "" Then
    body = body & "- Group Code: " & groupCode & vbCrLf
End If
```

**Test:** click WIN trên 3 row: ONE FAK SOC, HPL SCFI, CMA FAK → verify tooltip + email.

---

## 📂 Files Touched

| File | Action |
|------|--------|
| `Pricing_Engine/one_group_resolver.py` | **NEW** — 12 priority rules |
| `scripts/master_loader_v2.py` | **MODIFY** — apply ONE resolver |
| `Cleaned_Master_History.parquet` | **REBUILD** — Group_Code populated for ONE |
| `ERP/vba-v14-mirror/refresh-v14.py` | **MODIFY** — write 3 hidden cols |
| `D:/OneDrive/NelsonData/erp/erp-v14-ribbon-callbacks.bas` | **MODIFY** — MarkQuoteWin + tooltip + mailto |
| `ERP/vba-v14-mirror/erp-v14-ribbon-callbacks.bas` | **MIRROR** |
| `tests/test_one_group_resolver.py` | **NEW** — 12+ test cases |

---

## ⚠️ Risks + Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| ONE rule ambiguity (`"990131\|990132"` Canada consol) | Medium | Default first code; log to resolver audit file; Nelson override if needed |
| Reefer commodity không match keyword (e.g. "SEAFOOD" thay "REEFER") | Low | Default = `1` FROZEN (Nelson rule). Alias map: SEAFOOD, FROZEN FISH, FISH → FROZEN. CHILLED/FRESH word required để ra code 2 |
| Parquet rebuild fail | High | Backup parquet trước; rollback script |
| Hidden cols break Quote button layout | Low | Column index offset check — existing code uses `AJ_BUY=17` constant; Pricing Dry là sheet khác, không affect |
| VBA mirror out-of-sync | Medium | Reimport script tự copy `OneDrive → mirror` post-edit |
| ONE group rules change in future | Low | Rules in JSON, resolver auto-rebuilds on parquet refresh |

---

## ✅ Success Criteria

- [ ] `python one_group_resolver.py test` → 12+ cases pass
- [ ] Parquet query: `SELECT COUNT(*) FROM parquet WHERE Carrier='ONE' AND Group_Code IS NOT NULL` > 0
- [ ] Pricing Dry sheet: cols 15-17 hidden, data present (verify 5 random ONE rows)
- [ ] Pricing Reefer sheet: cols 15-17 hidden, ONE REEFER rows có Group_Code `1` (default frozen) hoặc `2` (chỉ khi rate sheet có chữ CHILLED/FRESH)
- [ ] Click WIN trên 3 test rows (ONE SOC / HPL / CMA) → Cost tooltip đúng format
- [ ] Send BKG mailto body có Contract + Group + Group Code (nếu ONE)
- [ ] Active Jobs 12 rows cũ giữ nguyên (không re-build tooltip)

---

## 🧪 Test Plan

### Pre-deploy
1. Backup parquet + xlsm
2. Run `one_group_resolver.py --self-test`
3. Test parquet rebuild on 100-row sample

### Post-deploy
1. Refresh All → verify Pricing Dry có 3 cols mới (hidden)
2. Click WIN on:
   - **Row ONE FAK SOC GARMENT USA** → expect Group Code 990117 (TPE10)
   - **Row ONE FAK REEFER (no FROZEN/CHILLED word)** → expect Group Code **1** (default frozen)
   - **Row ONE FAK REEFER CHILLED** → expect Group Code 2
   - **Row HPL SCFI** → Group Code trống, Group Rate vẫn có
   - **Row CMA FAK** → tương tự HPL
3. Open Send BKG mail trên Active Jobs → verify body
4. 1 ngày soak — Nelson dùng thật → báo em nếu có sai

---

## 🔄 Rollback Plan

1. `git revert` commits → files restore
2. `master_loader_v2.py` revert → parquet rebuild = Group_Code empty (backward compat)
3. VBA mirror copy lại file .bas từ git → reimport modules
4. Pricing Dry 3 cols hidden: vô hại nếu giữ, có thể xóa manual nếu cần

---

## 🚫 Out of Scope (YAGNI)

- Group code cho 13 carriers khác (chỉ ONE)
- Pricing Reefer full visible cols (chỉ hidden đủ dùng)
- UI picker cho ambiguous group code (default first)
- Historical parquet backfill cho data cũ hơn 1 năm
- Auto-detect filename contract # (đã có trong parquet từ master_loader)
