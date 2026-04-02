---
name: system-review
description: >
  Tự đánh giá toàn bộ hệ thống Nelson Freight, tự phản biện điểm mạnh/yếu,
  và đề xuất upgrade plan cụ thể. TRIGGER khi: review hệ thống, sprint planning,
  end-of-sprint retro, hoặc khi Sếp hỏi "hệ thống đang thiếu gì",
  "cần cải thiện gì", "đánh giá hệ thống".
---

# System Review — Tự đánh giá & Phản biện hệ thống

> **Triết lý:** Hệ thống tốt nhất là hệ thống liên tục tự chất vấn bản thân.
> **RULE:** Mỗi đánh giá phải kèm BẰNG CHỨNG từ code/data thực tế — không phỏng đoán.

---

## 🎯 Khi nào TRIGGER skill này

| Tình huống | Chạy sub-skill |
|-----------|---------------|
| Sprint planning / retro | `full-audit` |
| Sếp hỏi "thiếu gì" | `gap-analysis` |
| Sau khi deploy feature mới | `post-deploy-review` |
| Hàng tháng tự động | `health-check` |
| Có bug lặp lại 2+ lần | `pattern-smell` |

---

## 📊 Sub-Skill: full-audit — Đánh giá toàn diện

### BƯỚC 1: Scan hệ thống (ĐỌC code thực tế)

Scan chính xác 5 layers theo thứ tự:

```
Layer 1: DATA        → Parquet, SQLite, JSON files, Shipments.xlsx, Jobs_Master.xlsx
Layer 2: ENGINE      → query_engine, markup_engine, shipment_brain, ERP VBA
Layer 3: API         → FastAPI bridge, endpoints, response times
Layer 4: INTERFACE   → Bot v5 commands, WebApp pages, ERP UI
Layer 5: AI/INSIGHT  → AI Chat tools, win_loss_analyzer, Gemini integration
```

**Cho mỗi layer, đọc files thực tế rồi trả lời:**

| Câu hỏi | Ghi kết quả |
|---------|-------------|
| Có bao nhiêu file? Lines of code? | Đếm chính xác |
| Code có dead code/unused imports? | Liệt kê |
| Tests coverage? | % hoặc "không có" |
| Error handling đầy đủ chưa? | Liệt kê chỗ thiếu try/except |
| Single point of failure? | Ở đâu? |
| Data freshness? | File modified khi nào? |

### BƯỚC 2: Rubric chấm điểm (1-5)

| Tiêu chí | Mô tả | Chấm |
|----------|-------|------|
| **Reliability** | Hệ thống chạy ổn định hay lỗi thường xuyên? | ⬜ |
| **Data Quality** | Data sạch, đầy đủ, cập nhật? | ⬜ |
| **Automation** | Bao nhiêu % workflow là tự động? | ⬜ |
| **Intelligence** | AI/ML add value hay chỉ gimmick? | ⬜ |
| **Usability** | Người dùng (Sếp) thao tác dễ hay phức tạp? | ⬜ |
| **Scalability** | 10 user → 100 user → 1000 user OK? | ⬜ |
| **Maintainability** | AI mới vào có hiểu được code không? | ⬜ |
| **Security** | Tokens, API keys, data access control? | ⬜ |
| **Speed** | Response time đủ nhanh cho real-time? | ⬜ |
| **Business Value** | Feature nào tạo competitive advantage? | ⬜ |

### BƯỚC 3: Output format bắt buộc

```markdown
# 🔍 System Review — [Date]

## Overall Score: X.X / 5.0

### ✅ Điểm mạnh (Giữ nguyên, phát huy)
1. [Mô tả + bằng chứng từ code]
2. ...

### ⚠️ Điểm yếu (Cần cải thiện ngay)
1. [Mô tả + file cụ thể + đề xuất fix]
2. ...

### 🔴 Rủi ro nghiêm trọng (Fix trước sprint tới)
1. [Risk + impact + mitigation]

### 📋 Upgrade Backlog (Ưu tiên cao → thấp)
| # | Việc cần làm | Impact | Effort | Priority |
|---|-------------|--------|--------|----------|
| 1 | ...         | H/M/L  | H/M/L  | P1/P2/P3 |
```

---

## 🔎 Sub-Skill: gap-analysis — Phân tích thiếu sót

### So sánh What We Have vs What We Should Have

**Đọc các file sau để biết "đang có gì":**
```
D:\NELSON\2. Areas\PricingSystem\Engine_test\
├── TelegramBot\bot_v5.py                    → Bot commands
├── TelegramBot\*.py                         → Bot modules
├── ERP\data\ERP_Master.xlsm                 → ERP system
├── Pricing_Engine\data\*.parquet            → Pricing data
├── api\server.py                            → API layer
├── webapp\src\app\dashboard\**\page.tsx     → WebApp pages
├── Jobs\data\*.xlsx                         → Shipment data

D:\NELSON\email_engine\
├── shipment_brain.py                        → Email automation
├── dataset_store.py                         → Parquet datasets
├── rules.json                               → Team structure
├── customer_rules.json                      → Customer profiles
```

**So sánh với "nên có" dựa trên:**
1. Roadmap trong GEMINI.md
2. Industry standard logistics platform
3. Competitive advantages Sếp muốn

**Output format:**

```
| Feature | Có chưa | Chất lượng | Gap |
|---------|---------|------------|-----|
| Rate search | ✅ | 4/5 | Thiếu multi-port compare |
| Shipment tracking | ✅ | 3/5 | Chưa real-time, chỉ batch scan |
| Customer health | ⚠️ | 2/5 | Cần 1+ tháng data |
| Auto alerts | ❌ | 0/5 | Chưa build |
```

---

## 🏥 Sub-Skill: health-check — Kiểm tra sức khỏe nhanh

**Chạy 60 giây, trả lời 10 câu Y/N:**

1. [ ] Bot v5 đang chạy? (check process hoặc /status)
2. [ ] API server port 8000 responding? (`/api/status`)
3. [ ] WebApp port 3000 responding?
4. [ ] Parquet file > 0 rows? (check file size > 1KB)
5. [ ] shipment_state.json exists và < 24h old?
6. [ ] email_dataset.parquet exists?
7. [ ] shipment_history.parquet exists?
8. [ ] freight_bot.db accessible?
9. [ ] ERP_Master.xlsm accessible?
10. [ ] Không có file tạm (inspect_, patch_, test_) nằm trôi nổi?

---

## 🧹 Sub-Skill: post-deploy-review — Review sau deploy

Sau khi deploy feature mới, tự hỏi:

1. **Có break gì không?** → Chạy build, check console errors
2. **User path rõ ràng không?** → Sếp vào trang mới có hiểu ngay?
3. **Data flows end-to-end?** → Input → Processing → Output kiểm tra
4. **Error handling đủ?** → API down thì UI hiện gì?
5. **Có tạo tech debt không?** → Hardcoded values? Copy-paste code?
6. **Memory/workflow cập nhật chưa?** → GEMINI.md, active_context.md

---

## 🦨 Sub-Skill: pattern-smell — Phát hiện code smell

### Patterns xấu cần flag:

| Smell | Ví dụ | Fix |
|-------|-------|-----|
| **Hardcoded values** | Port, path, carrier list trong code | → Config file / env var |
| **God function** | Function > 100 lines | → Split ra modules |
| **No error handling** | `data = json.load(f)` without try | → Add try/except + fallback |
| **Duplicated logic** | Same query in 3 files | → Extract shared module |
| **Stale data** | JSON file > 7 days old | → Auto-refresh hoặc alert |
| **Missing types** | Python functions no type hints | → Add type annotations |
| **No tests** | Module without test file | → Create basic tests |
| **Magic numbers** | `if days > 7` without constant name | → Named constants |
| **Implicit coupling** | Module A reads Module B's file directly | → API/interface contract |

---

## 🔗 Liên kết với skills khác

| Khi review phát hiện... | Trigger skill |
|------------------------|---------------|
| Bug cần debug | `systematic-debugging` |
| Cần test | `auto-test-loop` |
| Bot cần sửa | `bot-v5-dev` |
| ERP cần sửa | `erp-master` |
| WebApp UI gaps | `frontend-design` |
| Data pipeline issue | `data-pipeline` |
| Deploy cần verify | `verification-before-completion` |
