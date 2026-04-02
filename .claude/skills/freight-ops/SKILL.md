---
name: freight-ops
description: >
  Nghiệp vụ Logistics & Freight core của Nelson Freight System.
  TRIGGER khi: tra giá, báo giá, freetime, phân tích win/loss, tư vấn carrier,
  xem profile khách hàng, cảnh báo rủi ro vận chuyển, hoặc bất kỳ nghiệp vụ
  logistics nào liên quan đến hệ thống Nelson.
---

# Freight Operations Skill

> **Domain:** Logistics & Ocean Freight (Vietnam → USA)
> **Hệ thống:** Nelson Freight ERP + Bot v5 + Parquet 19,700 rates
> **KHÔNG sửa** `bot_v5.py` core — tạo module mới khi cần

---

## 🎯 Sub-Skills & Triggers

### 1. rate-lookup — Tra giá vận chuyển
**Triggers:** "báo giá", "check giá", "/quote", "giá HPH đi Denver"
**Data source:** Parquet `Cleaned_Master_History.parquet` qua `query_engine.py`
**Output template:** xem `references/templates.md` → Quick Quote Template

**Logic:**
1. Parse: POL → POD → Place + Carrier (optional) + Container type
2. Query Parquet qua `query_engine.py`
3. Apply Markup qua `markup_engine.py` (Base + PUC + CarrierMarkup)
4. Format qua `quote_formatter.py` → Top 3 carriers

### 2. quotation — Tạo và lưu báo giá
**Triggers:** "lưu quote", "/savequote", "tạo báo giá chính thức"
**Data flow:** Bot query → ERP GenerateQuote VBA → lưu sheet Quotes
**Rule:** KHÔNG sửa `GenerateQuote` VBA — locked function

### 3. win-loss-analysis — Phân tích thắng/thua
**Triggers:** "/analyze", "/wins", "/losses", "tại sao thua thầu", "win rate"
**Module:** `win_loss_analyzer.py` → Gemini 2.5 Flash
**Output:** Pattern analysis + Action plan cụ thể

### 4. carrier-advisory — Tư vấn hãng tàu
**Triggers:** "hãng nào tốt", "freetime CMA", "ONE có SOC không"
**Data source:** `carrier_tips.json` + `freetime_formatter.py`
**13 Carriers:** CMA, ONE, MSK, YML, ZIM, OOCL, WHL, HMM, PIL, TSL, ESL, MCK, APL

**Key facts (hot cache):**
- SOC carriers: ONE, YML, ZIM
- Best freetime: CMA 21d | ONE 14d | MSK 14d
- Tips chi tiết: `carrier_tips.json`

### 5. freetime-lookup — Tra freetime/detention
**Triggers:** "freetime", "demurrage", "detention", "bao nhiêu ngày miễn phí"
**Module:** `freetime_formatter.py` — intent detection riêng biệt
**Rule:** Nếu query chỉ về freetime → BYPASS pricing engine

### 6. customer-profile — Hồ sơ khách hàng
**Triggers:** "khách HML", "SIRI cần gì", "/crm CUSTOMER", "profile khách"
**Module:** `customer_profiles.py` (static) + `erp_reader.py` (live CRM)

**Customer quick-ref:**
| Code | Lanes | Hàng | Behavior |
|------|-------|------|----------|
| HML | Denver/El Paso/Kansas | Stone, Slabs | Volume lớn, stable |
| SIRI | El Paso | Office nails | Price sensitive, delayed closure |
| PANDA | xem memory/02_data_dictionary.md | — | — |

### 7. risk-alert — Cảnh báo rủi ro
**Auto-trigger khi:** Gross weight > carrier limit, Rate expiry < 7 ngày, Space tightening
**Output:** ⚠️ alert kèm action plan cụ thể

---

## 📋 Output Templates

### Quick Quote (Telegram — chuẩn bắt buộc)
```
📊 [POL] → [PLACE] | [Customer Tag]
━━━━━━━━━━━━━━━━━━━━
#  Carrier  20GP    40HQ   Transit  Free  Note
1. YML     $1,846  $3,150  35 days  14d   SOC
2. CMA     $2,100  $3,280  28 days  21d   DIRECT
3. ONE     $2,250  $3,400  30 days  14d   COC

💡 Tip: [Consultative selling note]
⚠️  Risk: [Weight/Space alert nếu có]
```

### Consultative Selling Notes
- Khách Price Sensitive (SIRI): "Đây là giá tốt nhất hiện tại, space đang siết"
- Khách delay (SIRI): "Nếu chờ tuần sau giá có thể tăng $50-100/cont"
- Khách volume (HML): "Volume lớn → propose long-term rate với MSK/CMA"

---

## 🔗 Liên kết quan trọng
- **Chi tiết carriers:** `references/carriers.md`
- **Customer profiles đầy đủ:** `references/customers.md`
- **Tất cả output templates:** `references/templates.md`
- **Pricing logic:** xem skill `erp-master` → sub-skill `pricing-formula`
- **Bot commands:** xem skill `bot-v5-dev` → sub-skill `command-registry`
