# Task Plan — Email Intelligence v1 (Local)

**Created:** 2026-04-16
**Depends on:** `plans/260416-email-stack-refactor/` (local queue + worker MUST ship first)
**Scope:** T1.1-T1.4 Core Email Intelligence cho dashboard v4 local
**Nelson confirmed:** Cần file config template + AI-driven subject/body theo market state + advice "keep space" khi giá tăng

## 🎯 Mục tiêu

Build **1 lớp AI intelligence + template engine** để email thật sự thông minh:
- AI phân tích Parquet → nhận diện lane nào đang URGENT/STABLE/DECLINING
- Template YAML config → edit dễ không cần đụng code
- Mỗi email build per-lane content riêng (West Coast tăng 5% → advice khác East Coast stable)
- Token personalization: tên, công ty, lane, giá gần nhất

## 📐 Architecture Overview

```
[Dashboard v4] → POST /api/email-rate/campaign/bulk-send
                    │
                    ▼
            ┌─────────────────────────────┐
            │  IntelligenceBuilder         │
            │                              │
            │  1. Load CNEE profile       │
            │     (last quote, typical    │
            │      carrier, tier)         │
            │                              │
            │  2. MarketIntelEngine       │
            │     → query Parquet per lane│
            │     → state: URGENT/STABLE/ │
            │       DECLINING + delta%    │
            │                              │
            │  3. TemplateSelector        │
            │     → read email_rules.yaml │
            │     → match by POD + state  │
            │     → render with tokens    │
            │                              │
            │  4. GuardrailCheck          │
            │     → suppression list      │
            │     → cooldown              │
            │     → rate ≥ min threshold  │
            │                              │
            │  Output: {subject, html}    │
            └──────────┬──────────────────┘
                       │
                       ▼
              [enqueue to SQLite]
                       │
                       ▼
              [worker → Outlook COM]
```

## 📁 New Files

### `email_engine/intelligence/` (new package)
```
intelligence/
├── __init__.py
├── market_engine.py          ← AI market state per lane (~200 dòng)
├── template_selector.py      ← YAML template matcher + renderer (~150 dòng)
├── cnee_profile.py           ← Load CNEE profile from cnee_master + email_log (~100 dòng)
└── builder.py                ← Orchestrator: profile + market + template → rendered email (~120 dòng)
```

### `email_engine/templates/email_rules.yaml` (new, editable)
Structure ví dụ:
```yaml
version: 1
defaults:
  signature: |
    Best regards,
    Nelson Huynh — Nelson Freight (NVOCC)
    nelsonhuynhs@gmail.com | +84 xxx
  subject_suffix: "NELSON"

templates:
  - id: west_coast_urgent
    match:
      destinations: [USLAX, USLGB, USOAK]
      states: [URGENT]
    subject: "🚨 West Coast rates +{{delta}}% — Lock in NOW | {{suffix}} WEEK {{week}}"
    intro: |
      Dear {{first_name}},
      Asia-US West Coast rates are trending up {{delta}}% this week. 
      Recommend securing your space ASAP before further increases.
    cta: |
      Reply today to lock current rates. Space filling fast for next 2 sailings.

  - id: west_coast_stable
    match:
      destinations: [USLAX, USLGB, USOAK]
      states: [STABLE]
    subject: "Asia-US West Coast Rates | {{suffix}} WEEK {{week}}"
    intro: |
      Dear {{first_name}},
      Market stable this week. Good time to compare rates across carriers.
    cta: |
      Let me know if you need a specific lane or carrier.

  - id: east_coast_any
    match:
      destinations: [USNYC, USSAV, USCHS, USMIA]
      states: [any]
    subject: "Asia-US East Coast Rates | {{suffix}} WEEK {{week}}"
    intro: |
      Dear {{first_name}},
      East Coast rates steady this week.
    cta: |
      Happy to discuss routing options.

  - id: declining_market
    match:
      destinations: [any]
      states: [DECLINING]
    subject: "Rates softening — shop around | {{suffix}} WEEK {{week}}"
    intro: |
      Dear {{first_name}},
      Rates dropping {{delta}}% this week. Good opportunity to renegotiate.
    cta: |
      Let's revisit your current contract.

  - id: default
    match:
      destinations: [any]
      states: [any]
    subject: "Asia-US Ocean Freight Update | {{suffix}} WEEK {{week}}"
    intro: "{{default_intro}}"
    cta: "{{default_cta}}"
```

### `email_engine/intelligence/market_engine.py` — AI state detection per lane
```python
def analyze_lane(pol: str, destination: str) -> dict:
    """
    Returns:
        {
          "state": "URGENT" | "COMPETITIVE" | "STABLE" | "DECLINING",
          "delta_pct": 5.2,                  # % change vs last week
          "current_rate_40hq": 2500,         # median this week
          "prev_rate_40hq": 2375,            # median last week
          "mean_90d": 2300,                  # 90d historical
          "forecast_next_week": 2575,        # AI prediction
          "confidence": 0.87,                 # model confidence
          "sample_size": 142,                 # rows counted
        }
    """
```

Rules:
- `URGENT` — delta ≥ +3% WoW AND sample_size ≥ 30
- `COMPETITIVE` — rate < mean_90d AND sample_size ≥ 30
- `DECLINING` — delta ≤ -3% WoW
- `STABLE` — default

### `email_engine/intelligence/cnee_profile.py`
```python
def get_profile(email: str) -> dict:
    """Load CNEE profile from cnee_master + email_log CSV.
    Returns:
        {
          "first_name": "John",
          "company": "ABC Furniture Co",
          "typical_pol": "HPH",
          "typical_destinations": ["USLAX", "USLGB"],
          "preferred_carriers": ["ONE", "MSC"],
          "tier": "HOT" | "WARM" | "COLD" | "DEAD",
          "last_send_date": "2026-04-10",
          "last_rate_quoted_40hq": 2400,
          "days_since_last_send": 6,
          "reply_count_90d": 2,
          "prospect_type": "FURNITURE",
        }
    """
```

### `email_engine/intelligence/template_selector.py`
```python
def select_and_render(profile: dict, lane_intel: dict, template_config: dict) -> dict:
    """Match template by POD+state, render with tokens.
    Returns:
        {
          "subject": "🚨 West Coast rates +5.2% — Lock in NOW | NELSON WEEK 16",
          "intro_html": "<p>Dear John,</p>...",
          "cta_html": "<p>Reply today...</p>",
          "template_id": "west_coast_urgent",
          "tokens_used": {"first_name": "John", "delta": "5.2", ...}
        }
    """
```

### `email_engine/intelligence/builder.py`
```python
def build_email(cnee_email: str, pol: str, destinations: list, markup: float) -> dict:
    """Main orchestrator. Returns full ready-to-send email dict."""
    profile = get_profile(cnee_email)
    rate_table = build_rate_table_for_customer(pol, ",".join(destinations), markup)
    
    # Per-lane intel
    lanes = []
    for d in destinations:
        intel = market_engine.analyze_lane(pol, d)
        lanes.append({"destination": d, "intel": intel, "rates": rate_table_for(d)})
    
    # Dominant state for subject line (most urgent wins)
    dominant_state = max_state(lanes)
    
    # Template select based on dominant lane
    template = template_selector.select_and_render(profile, dominant_state, rules)
    
    # Build HTML body
    html_body = render_html(template, lanes, profile, rate_table)
    
    return {
        "to": cnee_email,
        "subject": template["subject"],
        "html_body": html_body,
        "meta": {
            "template_id": template["template_id"],
            "dominant_state": dominant_state["state"],
            "lanes_analyzed": len(lanes),
            "profile_tier": profile["tier"],
        }
    }
```

## 📅 Phases

### Phase I1 — Market Intelligence Engine (3-4h)
- [ ] I1.1: `market_engine.py` — analyze_lane() với DuckDB query Parquet
- [ ] I1.2: State classification rules (URGENT/COMPETITIVE/STABLE/DECLINING)
- [ ] I1.3: Delta calculation (WoW comparison)
- [ ] I1.4: Forecast baseline (simple regression, có thể upgrade ML sau)
- [ ] I1.5: Unit test với sample lanes (HPH-USLAX, HPH-USNYC, HCM-USLGB)

### Phase I2 — CNEE Profile (2h)
- [ ] I2.1: `cnee_profile.py` — load từ cnee_master_v2.xlsx
- [ ] I2.2: Enrich với email_log.csv (last send, reply count)
- [ ] I2.3: Tier classification (HOT/WARM/COLD/DEAD based on reply behavior)
- [ ] I2.4: Cache profile in-memory (TTL 5 min) để không load excel mỗi lần

### Phase I3 — Template YAML System (2-3h)
- [ ] I3.1: `email_rules.yaml` — draft 6-8 templates (per-coast × state)
- [ ] I3.2: `template_selector.py` — match logic (most-specific first)
- [ ] I3.3: Jinja2-style token renderer ({{first_name}}, {{delta}}, etc.)
- [ ] I3.4: Fallback to default template if no match
- [ ] I3.5: Hot-reload YAML (mtime check mỗi request)

### Phase I4 — Builder Orchestrator (1-2h)
- [ ] I4.1: `builder.py` — wire profile + intel + template → rendered email
- [ ] I4.2: HTML body render (intro + per-lane rate table + CTA + signature)
- [ ] I4.3: Meta fields cho log (template_id, dominant_state, tier)

### Phase I5 — Integration với web_server.py (1h)
- [ ] I5.1: Sửa `v4_bulk_send` dùng `builder.build_email()` thay hard-coded logic
- [ ] I5.2: Log meta fields vào email_log.csv
- [ ] I5.3: Dashboard v4: preview modal show subject + template_id + state

### Phase I6 — Dashboard Features (1-2h)
- [ ] I6.1: Dashboard v4 add "Market Intel" panel — show state per active lane
- [ ] I6.2: Per-prospect preview modal (xem trước khi bulk send)
- [ ] I6.3: Template config editor (mở YAML file trong VSCode nút click)

### Phase I7 — Test (1h)
- [ ] I7.1: End-to-end test: gửi 5 email thật với 5 CNEE khác lane+tier khác nhau
- [ ] I7.2: Verify email log ghi đúng template_id + state
- [ ] I7.3: Edit YAML → verify hot-reload không cần restart

## 🎯 Acceptance Criteria

- [ ] Bấm Send 50 → 50 email render với subject + body khác nhau tùy per-lane state
- [ ] West Coast URGENT → subject chứa "🚨" + "Lock in NOW" + delta %
- [ ] East Coast STABLE → subject trung tính
- [ ] Email chứa rate table per-lane với advice riêng (URGENT row đỏ, STABLE row xanh)
- [ ] Edit `email_rules.yaml` đổi subject → email mới dùng subject mới (không restart)
- [ ] CNEE HOT → template nhẹ ("Hi again"), CNEE COLD → introductory
- [ ] email_log.csv có thêm cột template_id, dominant_state
- [ ] Dashboard v4 show "Market Intel panel": HPH-USLAX: 🔴 +5.2% | HPH-USNYC: 🟢 Stable

## ⚠️ Risks

| Risk | Mitigation |
|------|-----------|
| Parquet query chậm khi gửi bulk 50 | Cache per-lane intel in-memory 5min |
| YAML syntax error → email không render | Validate YAML on load, fallback to default template |
| Token missing ({{first_name}} nhưng CNEE không có PIC) | Default token values ("Team") |
| CNEE profile load excel 5,316 rows mỗi lần = slow | In-memory cache với mtime invalidation |
| Forecast model sai → spam "urgent" mọi tuần | Confidence threshold + manual override flag trong YAML |

## 📚 References

- Market intel có sẵn: `/api/intelligence/market` (VPS) — có thể tái dùng logic
- Existing AI_INTROS trong `web_server.py:180-184` — upgrade thành YAML-driven
- Parquet schema: xem `db/duckdb_engine.py` + `Pricing_Engine/data/Cleaned_Master_History.parquet`
- CNEE master: `email_engine/data/cnee_master_v2.xlsx` hoặc `cnee_master.xlsx`
- Email log: `email_engine/logs/email_log.csv`

## 🚦 Dependencies

**MUST complete first:**
- ✅ `plans/260415-email-dashboard-v4-build/` Phase 3 (dashboard wired)
- ⏳ `plans/260416-email-stack-refactor/` Phase B (local queue + worker)

**Parallel OK:**
- Phase A (VPS cleanup) có thể chạy song song

**Blocks:**
- Cannot ship Email Intelligence trước khi queue local hoàn thiện

## 📊 Effort Estimate

| Phase | Effort |
|-------|--------|
| I1 Market Engine | 3-4h |
| I2 CNEE Profile | 2h |
| I3 Template YAML | 2-3h |
| I4 Builder | 1-2h |
| I5 Integration | 1h |
| I6 Dashboard | 1-2h |
| I7 Test | 1h |
| **Total** | **11-15h** (1.5-2 days) |
