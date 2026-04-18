# Phase 04 — GoClaw Fox Spirit Skill MANUAL GUIDE

**Effort:** 30-45 phút manual config (agents không tự động được)
**Priority:** LAST MILE — chỉ làm sau Phase 01/02/03 ship + API endpoint verify OK
**Status:** documented — chờ Sếp bấm nút

> **Tại sao manual?**
> GoClaw là 3rd-party platform, skill YAML schema có thể khác với template em đoán. Cần Sếp login GoClaw Dashboard + verify schema trước khi code.

## Bước 1 — Verify GoClaw skill schema hiện tại

Mở **GoClaw Dashboard** (Laptop VP port 18790) → Agent "Fox Spirit" → Skills tab.

Kiểm tra:
- [ ] Fox Spirit agent còn alive không?
- [ ] Có sẵn skill mẫu nào đang chạy? Mở xem YAML structure
- [ ] Skill folder path: `D:/GoClaw/workspace/little-fox/skills/` (theo memory project-goclaw-setup.md)

## Bước 2 — Chuẩn bị API endpoint test

Sau khi Phase 03 agent ship, test endpoint bằng curl:

```bash
curl -X POST http://localhost:8100/api/shipment/brief \
  -H "Content-Type: application/json" \
  -d '{"query": "Lô ACB2604 của PANDA đến đâu?"}'
```

Expected response: `{"status": "ok", "brief": "📦 ACB2604..."}` hoặc `{"status": "not_found", ...}` nếu chưa có data.

## Bước 3 — Tạo skill file

**Path:** `D:/GoClaw/workspace/little-fox/skills/shipment_brief/`

### skill.yml (adapt theo GoClaw docs thật)

```yaml
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
    - /ship

action:
  type: http_post
  url: http://host.docker.internal:8100/api/shipment/brief
  headers:
    Content-Type: application/json
  body:
    query: "{{ message.text }}"
  timeout_seconds: 10
  retry: 2

response_templates:
  ok: |
    {{ response.brief }}
  multiple: |
    Tìm thấy {{ response.shipments|length }} lô khớp:
    {% for s in response.shipments[:5] %}
    {{ loop.index }}. `{{ s.shipment_id }}` · {{ s.customer_name }}
    {% endfor %}
    → gõ `/ship <ref>` để xem chi tiết
  not_found: |
    Không thấy lô nào khớp.
    {% if response.suggestions %}Gần nhất: {{ response.suggestions|join(', ') }}{% endif %}
  error: "Shipment brain offline, thử lại sau."

reply:
  parse_mode: Markdown
```

**⚠ Nếu GoClaw YAML schema khác:** adapt fields — nhưng giữ nguyên:
- Trigger regex patterns
- HTTP POST to `http://host.docker.internal:8100/api/shipment/brief` (Docker → host)
- Body: `{query: message_text}`
- Reply parse_mode=Markdown

## Bước 4 — Morning brief cron (7:00 AM)

Tạo cron mới trong GoClaw Dashboard → Cron jobs:

| Field | Value |
|-------|-------|
| Name | morning_brief |
| Schedule | `0 7 * * *` |
| Timezone | Asia/Ho_Chi_Minh |
| Action | HTTP GET http://host.docker.internal:8100/api/shipment/top-active?limit=5 |
| Reply to | Nelson chat_id |
| Template | `🌅 Good morning Sếp — Top 5 shipment active:\n{{ response.brief }}` |

## Bước 5 — Test end-to-end

Mở Telegram Sếp, gửi cho bot:

| Test | Expected |
|------|----------|
| `Lô ACB2604 của PANDA đến đâu?` | Brief markdown hiện đẹp |
| `/ship ACB2604 PANDA` | Same brief |
| `status shipment EBKG1234` | Not_found hoặc brief Nafood |
| Random message "hello" | Không trigger skill (normal chat) |

## Troubleshooting

| Triệu chứng | Fix |
|-------------|-----|
| Docker container không gọi được localhost | Đổi `localhost` → `host.docker.internal` trong URL |
| Skill không trigger | Check regex patterns — có thể GoClaw parse pattern khác (escape backslash) |
| Response không render markdown | Add `parse_mode: Markdown` (hoặc `MarkdownV2`) |
| Timeout >10s | Tăng `timeout_seconds` hoặc verify Phase 02 LLM latency |
| Morning brief không chạy | Check cron log GoClaw + verify chat_id env var |

## Rollback nhanh

Nếu skill phá flow hiện tại:
1. GoClaw Dashboard → Fox Spirit → Skills → Toggle OFF `shipment_brief`
2. Bot trở lại behavior cũ không đụng skill

## Integration checklist

- [ ] Phase 01 ship (folder đã sạch)
- [ ] Phase 02 ship (DB + vault có data ≥10 shipments)
- [ ] Phase 03 API endpoint verified via curl
- [ ] GoClaw Dashboard accessible (port 18790)
- [ ] Skill YAML created + enabled
- [ ] Morning brief cron created
- [ ] 5/5 sample queries work
- [ ] Nelson confirm UX OK sau 1 ngày dùng

---

**Tổng effort:** 30-45 phút sau khi tất cả prerequisite đã ship.

**Next:** Nếu Sếp dùng thấy hay → extend sang CNEE (28K prospects). Brainstorm tiếp sau 1 tuần observe.
