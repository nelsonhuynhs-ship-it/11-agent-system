# Findings — Email Intelligence v1

## Existing AI Hooks trong code hiện tại

### web_server.py:180-184 — Hard-coded AI_INTROS
```python
AI_INTROS = {
    "URGENT": "Rates are trending upward — we recommend securing your booking soon...",
    "COMPETITIVE": "Market rates have softened recently — great timing to explore...",
    "STABLE": default_intro,
}
```
→ Cần nâng cấp thành YAML config + per-lane variation.

### build_rate_table_for_customer() — có trả `market_context`
```python
result = build_rate_table_for_customer(pol=pol, destinations=dest, markup=markup)
mkt = result.get("market_context")
if AI_MODEL and mkt:
    intro = AI_INTROS.get(mkt.get("template_type", "STABLE"))
```
→ Market detection đã có, chỉ cần expand per-lane (hiện global).

### `/api/intelligence/market` (VPS router)
Đã có 1 endpoint market intel. Logic có thể tái dùng cho local engine.

## Data Sources Available

| Source | Path | Use |
|--------|------|-----|
| Parquet rates | `Pricing_Engine/data/Cleaned_Master_History.parquet` (6.6M rows) | Market state detection |
| CNEE master | `email_engine/data/cnee_master_v2.xlsx` (5,316 rows) | Profile data |
| Email log | `email_engine/logs/email_log.csv` (585 rows) | Behavior (last send, reply) |
| Config | `email_engine/data/config.xlsx` (existing) | Legacy subject/intro — sẽ migrate sang YAML |
| Customer rules | `email_engine/data/customer_rules.json` | Nelson's direct customers |

## CNEE Fields có sẵn (cnee_master_v2.xlsx)

- EMAIL, CNEE_PIC, CNEE_NAME, POL, DESTINATION, CAMPAIGN_ID
- ALREADY_SENT, EMAIL_STATUS (HARD_BOUNCE, INVALID, NO_MX, OK)
- TIER (nếu có)
- CMD_NAME (campaign name)

Có thể thiếu:
- First name parsing từ CNEE_PIC ("Mr. John Smith" → "John")
- Typical container count
- Preferred carrier
→ Derive từ parquet query theo CNEE shipment history (nếu có match trong consignee field)

## Email Log Fields (email_log.csv)

`timestamp, email, subject, campaign_id, cycle_id, status, pol, dest`

Derive behavior:
- `last_send_date` = max(timestamp) per email
- `total_sends_90d` = count WHERE timestamp > now - 90d
- `days_since_last_send` = (now - last_send_date)

**Thiếu**: reply_count (cần scan Outlook Sent Items hoặc Inbox) — defer sang Tier 3.

## Market State Classification Logic

### URGENT (ưu tiên cao)
- Condition: delta_pct ≥ +3% WoW AND sample_size ≥ 30
- Subject: 🚨 + "Lock in NOW"
- CTA: Direct, urgent

### COMPETITIVE (rate thấp vs historical)
- Condition: current_rate < mean_90d × 0.95
- Subject: "Great rates this week"
- CTA: Compare/evaluate

### DECLINING (giá giảm)
- Condition: delta_pct ≤ -3% WoW
- Subject: "Rates softening"
- CTA: Renegotiate existing contract

### STABLE (default)
- Subject: Trung tính, informational
- CTA: Available for questions

## YAML vs JSON for template config

**YAML chọn vì:**
- Multi-line strings dễ viết (intro/cta có nhiều dòng)
- Anh có thể tự edit không cần quote escape
- Comments được (# this is for west coast urgent)

**JSON nếu:**
- Chỉ cần 1 dòng / field
- Kiểu thích stricter syntax

→ **Pick YAML** cho UX tốt hơn. Load với `pyyaml`.

## Token Engine Choice

- **Jinja2** — full-featured, overkill
- **str.format()** — đơn giản, KeyError nếu thiếu token
- **Custom regex `{{.*?}}`** — an toàn nhất, default khi missing

→ **Pick custom regex** + default value fallback.

## Open Questions

1. Forecast model: dùng gì?
   - Option A: Simple linear regression 90d → predict 7d (nhẹ, đơn giản)
   - Option B: Reuse GoClaw ML model đã build (memory nhắc 2026-04-07)
   - Option C: Skip forecast, chỉ dùng current state
   
2. Template YAML format: nested (groups) hay flat list? (em chọn flat list vì dễ đọc)

3. Per-sender identity: Nelson vs mentee có khác signature không? (defer Tier 2)

4. Multi-language: English only hay có Vietnamese cho CNEE VN-based? (defer Tier 2)

5. Unsubscribe link: có cần không? (some markets require — defer)
