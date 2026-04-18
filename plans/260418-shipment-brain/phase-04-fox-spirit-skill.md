# Phase 04 — GoClaw Fox Spirit "shipment_brief" Skill

**Effort:** 2 days
**Priority:** MED (user-facing last mile)
**Status:** pending (blocked by Phase 03)

## Context Links

- Brainstorm: `../260416-email-nelson-solo-platform/reports/brainstorm-shipment-brain-20260418.md`
- API endpoint: Phase 03 `/api/shipment/brief`
- GoClaw agent: Fox Spirit (existing, polling bot)

## Overview

Tạo skill cho GoClaw Fox Spirit agent để nhận Telegram message từ Sếp, detect intent "shipment status query", call API `/api/shipment/brief`, format response, reply Telegram.

Giữ nguyên GoClaw bot polling (không kill). Chỉ thêm skill mới.

## Key Insights

- Fox Spirit đã là lead agent trong GoClaw Laptop VP (per memory project-goclaw-setup.md)
- GoClaw skill format: YAML file với trigger patterns + actions
- Bot token shared = response đi về đúng chat của Sếp không cần config thêm
- Nếu API trả markdown → Telegram parse_mode="Markdown" render trực tiếp

## Requirements

### Functional
- F1: Skill activate khi message chứa pattern: "lô", "shipment", "status", "đến đâu", shipment_ref regex
- F2: HTTP call tới `http://localhost:8100/api/shipment/brief` với `{query: message_text}`
- F3: Format response:
  - `status=ok` → reply brief markdown
  - `status=multiple` → reply "Tìm thấy N lô hàng, chọn: 1. ... 2. ..."
  - `status=not_found` → reply "Không tìm thấy. Gần nhất: ..." + suggestions
- F4: Add `/ship <ref> <customer>` slash command (explicit invocation)
- F5: Morning brief 7:00 AM: top 5 shipments active (via APScheduler hoặc GoClaw cron)

### Non-functional
- N1: Skill response <10s end-to-end (user send → Telegram reply)
- N2: Handle API down gracefully: reply "Brain offline, try later"
- N3: Max 20 queries/minute rate limit per user
- N4: Log mọi query + response về SQLite cho audit

## Architecture

```
Sếp Telegram: "Lô ACB của PANDA đến đâu?"
    │
    ▼
GoClaw Fox Spirit (polling)
    ├── Skill matcher: pattern match → "shipment_brief" skill
    ├── Extract text from Telegram message object
    ├── HTTP POST http://localhost:8100/api/shipment/brief
    │   body: {"query": "Lô ACB của PANDA đến đâu?"}
    ├── Receive response {status, brief/suggestions}
    ├── Format cho Telegram Markdown
    └── Reply Sếp via sendMessage API
```

### Skill YAML (GoClaw format — verify exact schema với GoClaw docs)

```yaml
# ~/.goclaw/skills/shipment_brief/skill.yml
name: shipment_brief
version: 1.0
description: Brief lô hàng khi user hỏi status shipment
agent: fox_spirit

triggers:
  patterns:
    - regex: "l[ôo].*c[uủ]a"
    - regex: "shipment.*status"
    - regex: "[đd][ếe]n [đd][âa]u r[ồo]i"
    - regex: "\\b[A-Z]{2,6}\\d{6,10}\\b"
  commands:
    - name: /ship
      args: [shipment_ref, customer]

action:
  type: http_post
  url: http://localhost:8100/api/shipment/brief
  body:
    query: "{{ message.text }}"
  timeout_seconds: 10
  retry: 2

response:
  when: "{{ response.status == 'ok' }}"
  reply:
    text: "{{ response.brief }}"
    parse_mode: Markdown

  when: "{{ response.status == 'multiple' }}"
  reply:
    text: |
      Tìm thấy {{ response.shipments | length }} lô:
      {% for s in response.shipments[:5] %}
      {{ loop.index }}. `{{ s.shipment_id }}` · {{ s.customer }} · {{ s.status }}
      {% endfor %}
      Gõ `/ship <ref>` để xem chi tiết.
    parse_mode: Markdown

  when: "{{ response.status == 'not_found' }}"
  reply:
    text: |
      Không tìm thấy lô hàng khớp query.
      Gần nhất: {{ response.suggestions | join(', ') }}

  on_error:
    reply:
      text: "Shipment brain offline, em thử lại sau 1 phút."
```

**⚠ Caveat:** GoClaw skill exact YAML schema cần verify — memory nói skill format `<slug>/SKILL.md` với YAML frontmatter. Nếu khác với template trên, adapt accordingly.

### Morning brief 7:00 AM

```yaml
# ~/.goclaw/cron/morning_brief.yml
schedule: "0 7 * * *"
timezone: Asia/Ho_Chi_Minh
action:
  type: http_get
  url: http://localhost:8100/api/shipment/top-active?limit=5
response:
  reply:
    chat_id: "{{ env.ADMIN_CHAT_ID }}"
    text: |
      🌅 Good morning Sếp — Top 5 shipment active:
      {{ response.brief }}
```

Requires new endpoint `/api/shipment/top-active` in Phase 03 extension.

## Related Code Files

### Create
- `~/.goclaw/skills/shipment_brief/skill.yml` (hoặc SKILL.md per GoClaw convention)
- `~/.goclaw/cron/morning_brief.yml`
- `email_engine/api/shipment_top.py` — `/api/shipment/top-active` endpoint

### Read (reference)
- GoClaw docs (verify skill schema + cron format)
- `scripts/notify-telegram.py` (one-way push pattern reference)

## Implementation Steps

### Day 1 — Skill setup
1. Verify GoClaw skill YAML schema trên Laptop VP Docker
2. Create skill folder + skill.yml
3. Test trigger patterns với 5 sample messages
4. Test HTTP call (mock API if Phase 03 not ready)
5. Verify Telegram reply renders Markdown OK

### Day 2 — Command + morning brief
1. Add `/ship` slash command
2. Create `/api/shipment/top-active` endpoint (minor extension Phase 03)
3. Setup cron 7:00 AM với morning_brief.yml
4. Test 10 query real qua Telegram
5. Audit log check (every query logged)

## Todo List

- [ ] Verify GoClaw skill YAML schema (read GoClaw docs hoặc existing skills)
- [ ] Create skills/shipment_brief/skill.yml
- [ ] Configure trigger patterns (regex + commands)
- [ ] Configure HTTP action to localhost:8100
- [ ] Configure 3 response branches (ok/multiple/not_found)
- [ ] Configure error fallback
- [ ] Test 5 sample messages trigger correctly
- [ ] Add /ship slash command
- [ ] Create /api/shipment/top-active endpoint
- [ ] Setup morning brief cron 7:00 AM
- [ ] End-to-end test 10 real queries
- [ ] Audit log table (goclaw_query_log)
- [ ] Update memory: shipment brain fully shipped

## Success Criteria

- ✅ 8/10 real Telegram queries trả response chính xác
- ✅ Response time <10s (end-to-end)
- ✅ Morning brief arrives đúng 7:00 AM hàng ngày
- ✅ Graceful fallback khi API offline
- ✅ Sếp confirm UX tốt sau 1 tuần dùng thật

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| GoClaw skill YAML schema khác template | HIGH | MED | Read GoClaw docs day 1, adapt |
| Fox Spirit agent bị disabled / not deployed | MED | HIGH | Verify agent alive trước khi code skill |
| localhost:8100 không reachable từ Docker Fox Spirit container | MED | HIGH | Use host.docker.internal hoặc bridge network |
| Trigger patterns false positive (skill activate khi không nên) | MED | LOW | Refine regex, add negative patterns |
| Rate limit Telegram bot | LOW | LOW | GoClaw đã handle |

## Security Considerations

- Sếp chat_id only — không leak brief cho chat khác
- API localhost only — không expose externally
- No credentials in skill YAML (env var ADMIN_CHAT_ID)

## Next Steps

Phase 04 ship → Shipment Brain end-to-end complete. Sếp sáng mở Telegram → có brief + có thể hỏi bất cứ shipment.

**Follow-on:**
- Week 4+: Extend sang CNEE (28K prospects) nếu Sếp thấy value
- Reply auto-drafter (từ evolution plan) — separate plan

**Status:** detailed enough to code after Phase 03 ships
