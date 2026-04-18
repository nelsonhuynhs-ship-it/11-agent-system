# Brainstorm — Second Brain Two-Vault (Karpathy-style)

**Date:** 2026-04-18
**Related plan:** `plans/260416-email-nelson-solo-platform/plan.md` (extends phase-02 Intel Memory)
**Status:** ⏸ PARKED — Nelson chose to polish Email Dashboard v5 trước. Second Brain sẽ resume sau khi v5 hoàn hảo.
**Inspiration:** Karpathy LLM-wiki gist + Obsidian graph approach

---

## 1. Problem statement

Nelson cần 2 "bộ não thứ hai" để đạt KPI 2 tháng (100 TEU / $10K / 10 lead / 1-2 direct):

- **Goal 1 — Customer Brain**: biến mỗi email thành ghi chú sống cho từng CNEE/co-loader/shipper — AI dự đoán & soạn reply dựa trên hồ sơ cá nhân + hành vi nhóm.
- **Goal 2 — System Brain**: bản đồ toàn bộ code + resource + sự cố + cách xử lý — Nelson nhìn thấu hệ thống, tận dụng 1000% nội lực.

Gốc rễ: hệ thống hiện ghi log email nhưng **không có memory** — `email_log.csv` chỉ outgoing, `LAST_REPLY` 0/5316 CNEE (xem memory `event-memory-gap.md`). `process_reply.py v3.0` có sẵn nhưng chưa chạy.

---

## 2. Approach — Karpathy 3-layer × 2 vaults

| Lớp | Customer Vault | System Vault |
|-----|----------------|--------------|
| Raw sources (bất biến) | Email PST, email_log.csv | File code `.py/.ts`, git history |
| Wiki (AI-generated) | CNEE page, Group page, Lane/Carrier/Campaign page, daily log | Module page, Data-lineage page, Resource catalog, Trouble log |
| Schema | `customer.schema.md` — fields bắt buộc | `system.schema.md` — fields bắt buộc |

Dùng chung: Markdown + `[[wiki-link]]` + Obsidian Desktop (graph view) + git commit nightly + `index.md` + `log.md` append-only.

---

## 3. Evaluated approaches (debate đã xong)

| Option | Ưu | Nhược | Verdict |
|--------|-----|-------|---------|
| A. Database-centric (PG schema cho customer memory) | Query SQL mạnh, join được với rate | Rigid schema, khó evolve, không có graph linking | ❌ Skip — đã có cnee_master_v2 |
| B. RAG vector-only (embed tất cả email) | Semantic search OK | Không có structure, khó audit, không back-link | ❌ Skip — bổ trợ Copilot thôi |
| **C. Karpathy markdown wiki × 2 (CHỌN)** | Human-readable, evolve được, Obsidian graph, compound value | Cần LLM extractor tốt, schema drift | ✅ Primary |
| D. Obsidian vault không AI | Đơn giản nhất | Nelson phải viết tay — không scale 28K CNEE | ❌ Skip — thiếu automation |

---

## 4. Final design — 5 tầng (stacks)

### TẦNG 1 — VAULT HAI BỘ NÃO (foundation)
1. `brain/customer/` + `brain/system/` trong OneDrive (sync 3 máy)
2. `schema.md` mỗi vault (CNEE required fields: LIKES/DISLIKES/PRICE_BAND/SHIPMENTS/LAST_REPLY/STATUS; Module required fields: PURPOSE/INPUTS/OUTPUTS/DEPS/BUGS)
3. `index.md` + `log.md` append-only
4. Obsidian Desktop mở vault → graph view
5. Git commit nightly — xem lịch sử khách như xem code history

### TẦNG 2 — CUSTOMER INGESTION DAILY
1. Task Scheduler `NelsonCustomerBrain` — 23:00 mỗi đêm
2. Parser Outlook PST — Inbox + Sent hôm nay → JSON (tái dùng `process_reply.py v3.0`)
3. LLM extractor (MiniMax 2.7, fallback Claude): mỗi email → `{sentiment, likes, dislikes, price_mentioned, services, complaint, tone, urgency}`
4. Page writer — append block dưới section đúng, không đè cũ
5. Back-link fan-out — 1 email touch 10-15 trang (CNEE + Carrier + Lane + Campaign + log)
6. ~~Backfill~~ SKIP (Nelson chốt forward-only T+1)

### TẦNG 3 — GROUP INTELLIGENCE (Tuần 3+)
1. Classifier regex domain → CNEE USA / Co-loader VN / Shipper VN
2. Trang nhóm tự sinh `[[GROUP-CNEE-FURNITURE]]` aggregate từ member
3. Kho "reply vàng" 5-10 reply chốt deal hay nhất mỗi nhóm → seed Copilot
4. Cluster embedding find-similar
5. Tab `Groups` v5.1 trong dashboard

### TẦNG 4 — SYSTEM BRAIN (Tuần 4+)
1. Module page auto-gen — git hook `post-commit` → LLM update `brain/system/modules/{file}.md`
2. Data lineage graph — `[[Parquet]]` → `[[DuckDB]]` → `[[auto_rate_builder]]` → `[[outlook_queue]]` → `[[Outlook-COM]]` → `[[email_log]]`
3. Resource catalog — 28K CNEE, 6.6M rows Parquet, VPS endpoint, GoClaw agent, 7 Task Scheduler task, 23 campaign
4. Trouble log — stuck queue / bounce / Softek fail / SSH lỗi + resolution link
5. Semantic search `sqlite-vss` local

### TẦNG 5 — AI COPILOT + NORTH STAR (Tuần 5-8)
1. AI Draft Reply — dashboard nút mới cạnh Preview, pull CNEE page + Group page + Rate + Reply Vàng
2. EV Score per CNEE = P(reply) × deal_value × recency
3. Funnel tracker 2 tháng: Sent → Open → Reply → Quote → Direct
4. Morning Telegram brief 7:00 — top 5 lead + 3 follow-up + 2 red flag
5. Weekly lint AI: mâu thuẫn / orphan / gap

---

## 5. Decisions locked

| Config | Value | Rationale |
|--------|-------|-----------|
| Thứ tự triển khai | Tầng 1+2 (2 tuần) → 3/4/5 sau | Có data trước, insight sau |
| LLM engine | **MiniMax 2.7** (quota 4500 req/5h đã có sẵn) | Dư sức cho 100-500 email/đêm, $0 extra cost |
| Backfill | **None** — forward-only T+1 | An toàn, nhẹ, vault rỗng 2 tuần đầu là chấp nhận được |
| Vault location | `D:/OneDrive/NelsonData/brain/` (central) | Single source of truth, sync 3 máy qua OneDrive + rclone VPS |
| Writer machine | **Laptop VP** — Task Scheduler 23:00 mỗi đêm | Sếp làm việc office Laptop VP hằng ngày, Outlook profile local tại đây |
| Readers | GoClaw agent (bind mount RO) + Dashboard v5 (API endpoint `/brain/customer/{domain}`) + Obsidian Desktop | Central vault ngoài sandbox → shared context |
| GoClaw integration | Mount `/mnt/onedrive/brain/:ro` vào sandbox | Central vault đọc được từ GoClaw, không phụ thuộc agent cụ thể |
| Version control | Git nightly commit | Xem lịch sử khách như code |
| Obsidian | Desktop app, optional | Graph view — không bắt buộc |

---

## 6. Integration với hệ thống hiện có

| Tầng | Tái dùng | Build mới |
|------|----------|-----------|
| 1 Vault | OneDrive, git | `schema.md`, `index.md` init |
| 2 Ingest | `process_reply.py v3.0`, Task Scheduler | LLM extractor + page writer |
| 3 Group | `cnee_master_v2_final` (TIER 6 bậc, 48 campaign) | Classifier + group page gen |
| 4 System | — | Module auto-gen + lineage |
| 5 Copilot | Dashboard v5 nút Preview, `outlook_queue`, ORACLE, `notify-telegram.py` | Draft UI + EV scorer |

Không xung đột với phase-02-intel-memory.md hiện tại — **extends** nó từ flat JSON → linked markdown vault.

---

## 7. Risks & mitigation

| Risk | Severity | Mitigation |
|------|----------|------------|
| Outlook COM PST parser crash trên Laptop VP | MEDIUM | Reuse `process_reply.py v3.0` đã test |
| MiniMax rate limit 4500/5h bị vượt (weekly lint + embedding cộng dồn) | LOW | Log request/ngày tuần 1, batch lint theo tuần (không daily) |
| Schema drift — thêm field sau phải migrate trang cũ | LOW | Append-only design, field mới để trống cho trang cũ |
| Vault sync conflict: OneDrive chưa sync xong mà VPS đã đọc | LOW | rclone sync chạy 23:30 (sau cron 23:00), chỉ Laptop VP ghi |
| GoClaw sandbox không thấy mount mới | LOW | Restart sandbox config sau khi thêm bind mount |

---

## 8. Success metrics — 2 tuần đầu

| Checkpoint | Target |
|------------|--------|
| Cuối tuần 1 | Vault structure + Obsidian mở được + `schema.md` + 1 CNEE page mẫu + cron chạy 7 đêm không crash |
| Cuối tuần 2 | ≥100 CNEE page tạo (từ reply thật), ≥5 field/email được extract, log token/cost daily, group page aggregate prototype |
| Go/no-go Tầng 3 | Nếu extractor sai >30% hoặc cost >$2/ngày → pause, fix trước khi sang Tầng 3 |

---

## 9. Open questions (ghi lại để check tuần 1)

1. MiniMax 2.7 — endpoint chính xác? Giá/1K token? Prompt caching không?
2. Vault sync: OneDrive conflict resolution khi PC Home và Laptop VP cùng edit → chọn 1 máy master?
3. Obsidian mobile (nếu có) → iOS/Android app hay web only?
4. Multi-language: CNEE email tiếng Anh, Co-loader VN email tiếng Việt lẫn lộn — extractor cần prompt bilingual?
5. PII/GDPR: vault chứa email khách → encrypt-at-rest không? Hiện OneDrive chưa encrypt.

---

## 10. Next step

→ Invoke `/ck:plan --auto` để break **Tầng 1 + Tầng 2** thành phase files chi tiết (schema design, extractor prompt, cron script, page writer logic, backlink algo, Obsidian setup guide).

Plan mới sẽ đặt tại: `plans/260418-second-brain-customer-vault/` hoặc gộp vào `plans/260416-email-nelson-solo-platform/phase-02-intel-memory.md` (extend).

---

**Status:** DONE
**Summary:** 5-stack design approved. Scope locked Tầng 1+2 x 2 tuần, LLM=MiniMax 2.7 (fallback Claude), forward-only. Ready for `/ck:plan`.
**Concerns:** MiniMax verification must happen day 1 — nếu fail, fallback Claude đã preset.
