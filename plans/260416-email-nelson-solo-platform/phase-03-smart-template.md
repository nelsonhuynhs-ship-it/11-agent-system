# Phase 03 — Smart Template Engine (CẠNH TRANH + YÊN TÂM)

**Priority:** HIGH
**Status:** Pending approval
**Slogan map:** CẠNH TRANH (giá sát thị trường), YÊN TÂM (khách hiểu thị trường qua email)

## Context

Email hiện tại dùng 1 template hard-code với 3 variants URGENT/COMPETITIVE/STABLE global. Cần:
- Per-lane state (West Coast khác East Coast)
- YAML config editable (không sửa code)
- Personalization sâu (dùng intel từ Phase 02)
- Market forecast + delta% chèn tự động (yên tâm)

## Key Insights

- Parquet đã có 6.6M rows rate history → đủ data market intel
- Simple stats đủ (median WoW + 90d mean) — không cần ML phức tạp
- YAML > JSON cho multi-line intro/cta
- Hot-reload YAML: check mtime mỗi request

## Requirements

**Functional:**
1. `market_engine.analyze_lane(pol, dest)` → state + delta% + forecast
2. `template_selector.match(destinations, states)` → template id
3. `template_renderer.render(template, tokens)` → subject + html
4. YAML config: `email_engine/templates/email_rules.yaml` — hot-reload
5. Tokens supported: `{{first_name}}`, `{{company}}`, `{{delta}}`, `{{current_rate_40hq}}`, `{{prev_rate_40hq}}`, `{{mean_90d}}`, `{{forecast_next_week}}`, `{{last_rate_quoted}}`, `{{days_since_last}}`, `{{week}}`, `{{suffix}}`
6. Per-lane table rendered in email body with color-coded state:
   - 🔴 URGENT rows red
   - 🟢 STABLE rows green
   - 🟡 COMPETITIVE rows yellow
   - 🔽 DECLINING rows blue

**Non-functional:**
- Analyze 1 lane < 200ms (DuckDB cached)
- Render email < 100ms
- Cache market state per lane 30 minutes

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ IntelligenceBuilder.build_email(cnee_email, lanes)        │
│                                                           │
│ 1. profile = intel.get_profile(cnee_email)               │
│ 2. for d in destinations:                                 │
│      lane_intel[d] = market_engine.analyze_lane(pol, d)  │
│ 3. dominant_state = max_priority(lane_intel)             │
│ 4. template = template_selector.match(dests, states)     │
│ 5. html = template_renderer.render(template, {           │
│      profile: profile,                                    │
│      lanes: lane_intel,                                   │
│      rate_table: rate_table_html,                         │
│      ...tokens                                            │
│    })                                                     │
│ 6. return {subject, html_body, meta: {template_id, ...}}  │
└──────────────────────────────────────────────────────────┘
```

### Market state rules
- `URGENT`: delta_pct ≥ +3% WoW AND sample_size ≥ 30 AND confidence ≥ 0.7
- `DECLINING`: delta_pct ≤ -3% WoW
- `COMPETITIVE`: current < mean_90d × 0.95
- `STABLE`: default

### Template match priority (most-specific first)
1. Exact lane + state (e.g., `west_coast_urgent`)
2. Region + state (e.g., `west_coast_any`)
3. Any dest + state (e.g., `declining_market`)
4. Default (`default`)

## Related Code Files

**Create:**
- `email_engine/intelligence/__init__.py`
- `email_engine/intelligence/market_engine.py` (~200 dòng)
- `email_engine/intelligence/template_selector.py` (~150 dòng)
- `email_engine/intelligence/template_renderer.py` (~100 dòng)
- `email_engine/intelligence/builder.py` (~120 dòng)
- `email_engine/templates/email_rules.yaml` — 6-8 templates draft
- `email_engine/templates/rate_table.html` — HTML partial for rate table

**Modify:**
- Phase 01 `web_server.py` `v4_bulk_send` — dùng `builder.build_email()` thay inline logic

## Example YAML Template

```yaml
version: 1
defaults:
  signature: |
    Best regards,
    Nelson Huynh — Nelson Freight (NVOCC)
    ✉️ nelsonhuynhs@gmail.com | 📱 +84 xxx
    🌐 Asia-US Ocean Freight Specialist
  subject_suffix: "NELSON"

templates:
  - id: west_coast_urgent
    match:
      destinations: [USLAX, USLGB, USOAK]
      states: [URGENT]
    subject: "🚨 West Coast rates +{{delta}}% next week | Lock NOW"
    intro: |
      Dear {{first_name}},
      Urgent update for {{company}} — Asia-US West Coast rates 
      trending up {{delta}}% this week and forecast to rise further 
      next Monday. Current: ${{current_rate_40hq}}/40HQ vs 90-day 
      mean ${{mean_90d}}.
    cta: |
      Recommend you secure space this week. Reply today to lock 
      current rates before next increase.

  - id: west_coast_stable
    match:
      destinations: [USLAX, USLGB, USOAK]
      states: [STABLE]
    subject: "Asia-US West Coast Rate Update | Week {{week}}"
    intro: |
      Dear {{first_name}},
      This week's update for {{company}}: West Coast market stable 
      at ${{current_rate_40hq}}/40HQ (90d mean ${{mean_90d}}).
    cta: |
      Good time to compare options. Happy to discuss routing for 
      your typical {{typical_pol}}→{{typical_dest}} shipments.

  - id: east_coast_any
    match:
      destinations: [USNYC, USSAV, USCHS, USMIA, USHOU]
      states: [any]
    subject: "Asia-US East Coast Rates | Week {{week}}"
    intro: |
      Dear {{first_name}},
      East Coast weekly update for {{company}}.
    cta: |
      Let me know if you need specific routing.

  - id: declining_market
    match:
      destinations: [any]
      states: [DECLINING]
    subject: "Rates softening {{delta}}% — renegotiate time | Week {{week}}"
    intro: |
      Dear {{first_name}},
      Good news — rates dropping {{delta}}% this week. 
      Current ${{current_rate_40hq}}/40HQ is ${{gap_to_mean}} 
      below 90-day mean. Forecast to stay soft next 2 weeks.
    cta: |
      Opportunity to renegotiate your current contracts. 
      Want me to run numbers on your typical lanes?

  - id: default
    match:
      destinations: [any]
      states: [any]
    subject: "Asia-US Ocean Freight Weekly | Week {{week}}"
    intro: "{{default_intro}}"
    cta: "Let me know if you need rate quotes."
```

## Implementation Steps

1. **`market_engine.py`:**
   - DuckDB query Parquet filtered last 14 days per (pol, dest)
   - Compute: median current week, median prev week, delta%, 90d mean, sample_size
   - Simple forecast: linear regression of last 4 weeks → predict next week
   - Return dict with state classification

2. **`template_selector.py`:**
   - Load YAML (with mtime cache)
   - `match(destinations, states)` — iterate templates, first match wins
   - Fallback to default

3. **`template_renderer.py`:**
   - `render(template, tokens)` — regex `{{key}}` → value, missing → default
   - Support nested: `{{profile.first_name}}`
   - Escape HTML safely

4. **`builder.py`:**
   - Orchestrate profile + market + template + rate table → final email dict

5. **Integration Phase 01:**
   - `v4_bulk_send` → for each email: `builder.build_email()` → enqueue

## Todo List

- [ ] Draft `email_rules.yaml` với 6 templates
- [ ] `market_engine.analyze_lane()` với cache 30 min
- [ ] `template_selector.match()` + YAML hot-reload
- [ ] `template_renderer.render()` + token regex
- [ ] `builder.build_email()` orchestrator
- [ ] Rate table HTML partial (color-coded by state)
- [ ] Integration Phase 01 bulk-send
- [ ] Preview endpoint `GET /api/email-rate/preview?cnee=...` trả HTML render
- [ ] Test: 5 CNEE khác lane, verify subject + body đa dạng

## Success Criteria

- Bấm Send 50 CNEE khác nhau → 5+ variants subject/body
- West Coast CNEE trong URGENT week → subject chứa "🚨" + delta%
- East Coast CNEE → subject trung tính
- CNEE HOT profile → intro personalized "John, following up"
- Edit YAML → next email dùng template mới (no restart)
- Rate table HTML: URGENT row có background đỏ nhạt, STABLE xanh

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| YAML syntax error | Validate on load, fallback default template, log error |
| Token missing (profile no first_name) | Default "Team" |
| Market state wrong (small sample) | Require sample_size ≥ 30, else STABLE |
| DuckDB query slow | Cache 30 min per lane; limit columns fetched |
| Over-URGENT spam | Cap: max 1 URGENT subject per CNEE per 7 days |

## Security Considerations

- YAML file local — no server upload
- HTML escape tokens to prevent injection
- Don't expose raw SQL to YAML

## Next Steps

Phase 03 done → emails có NHANH-CẠNH TRANH-YÊN TÂM feel. Phase 04 scanner sẽ feed reply events back into intel → future templates smarter.
