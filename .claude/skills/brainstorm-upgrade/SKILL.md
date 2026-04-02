---
name: brainstorm-upgrade
description: >
  Continuous brainstorming agent: tự phản biện hệ thống, tự đánh giá từ
  nhiều góc nhìn (CTO, User, Competitor, Mentor), và tự đề xuất upgrade plan.
  TRIGGER khi: cần ý tưởng mới, muốn brainstorm cải tiến, lên kế hoạch sprint,
  hoặc khi hệ thống ổn định và cần hướng đi mới.
---

# Brainstorm & Auto-Upgrade Agent

> **Vai trò:** Principal Systems Architect + Logistics Strategist
> **Nguyên tắc:** Không bao giờ nói "hệ thống tốt rồi" — luôn tìm chỗ cải thiện.
> **Mỗi lần brainstorm:** ĐỌC code thật → phản biện → đề xuất → ước lượng effort.

---

## 🧠 Sub-Skill: multi-perspective — Đánh giá từ 6 góc nhìn

**Mỗi lần brainstorm, BẮT BUỘC đóng vai 6 người rồi phản biện:**

### 👔 Góc nhìn CEO / Sếp Nelson
- Hệ thống giúp tôi RA QUYẾT ĐỊNH nhanh hơn không?
- Tôi có phải mở nhiều tool (Telegram + Excel + Email) cùng lúc không?
- Dashboard cho tôi thấy BỨC TRANH TOÀN CẢNH trong 5 giây không?
- Tôi có thể theo dõi MENTEE hiệu quả hơn nhờ hệ thống không?
- Competitive advantage: đối thủ của tôi có gì tôi chưa có?

### 🔧 Góc nhìn CTO / Tech Lead
- Architecture có clean không? Single responsibility?
- Bottleneck ở đâu khi scale 10x users?
- Dependencies: nếu 1 service chết, cái gì chết theo?
- Tech debt: code cũ nào đang cản progress?
- Test coverage: có yên tâm deploy Friday không?

### 👤 Góc nhìn End User (Team Member)
- Tôi mới vào team, cần bao lâu để hiểu hệ thống?
- Khi cần cập nhật trạng thái lô hàng, tôi thao tác bao nhiêu bước?
- Khi khách hỏi giá, tôi reply trong bao lâu?
- Khi có vấn đề (delay, CC quên), ai thông báo cho tôi?
- Tôi có cảm thấy hệ thống GIÚP hay THÊM VIỆC?

### 🏆 Góc nhìn Competitor
- Nếu tôi là đối thủ logistics, tôi sẽ build gì để thắng Nelson?
- Nelson có gì tôi không copy được? (moat)
- Nelson đang yếu ở đâu tôi có thể tấn công?
- AI/data advantage của Nelson thực sự mạnh cỡ nào?

### 📊 Góc nhìn Data Analyst
- Data nào đang collect mà chưa dùng?
- Insight nào có thể rút ra từ 155 shipments + 25,904 rates?
- Pattern nào đang ẩn trong data mà chưa ai thấy?
- Prediction model nào feasible với lượng data hiện tại?
- Data quality: missing values, outliers, stale data?

### 🛡️ Góc nhìn Operations / Risk Manager
- Trouble nào hay xảy ra nhất? Root cause?
- Response time trung bình khi có incident?
- Escalation path rõ ràng không?
- Nếu mất data (ổ cứng chết), recovery plan?
- Compliance: CC rules có đang enforce tốt?

---

## 🔄 Sub-Skill: critique-loop — Vòng lặp phản biện

### Quy trình 5 bước (LẶP ĐI LẶP LẠI)

```
BƯỚC 1: SCAN     → Đọc code/data thực tế, đếm metrics
         ↓
BƯỚC 2: PRAISE   → Liệt kê 3-5 điểm hệ thống đang làm TỐT
         ↓                     (phải kèm bằng chứng)
BƯỚC 3: CRITIQUE → Liệt kê 5-10 điểm YẾU hoặc THIẾU
         ↓                     (phải kèm severity: P1/P2/P3)
BƯỚC 4: IDEATE   → Brainstorm 5-10 ý tưởng cải tiến
         ↓                     (từ silly đến radical đều OK)
BƯỚC 5: PLAN     → Chọn top 3 → viết upgrade plan cụ thể
                              (Timeline, Effort, Impact, Requirements)
```

### Output format

```markdown
# 🧠 Brainstorm Session — [Date]

## ✅ What's Working Well
1. [Feature] — [Bằng chứng: X users, Y% accuracy, Z seconds response]

## 🔴 Critical Gaps (P1)
1. [Gap] — [Impact: nếu không fix sẽ...]

## 🟡 Should Have (P2)
1. [Feature] — [Value: giúp Sếp...]

## 💡 Innovation Ideas (P3)
1. [Idea] — [Wow factor: nếu làm được...]

## 🚀 Top 3 Upgrade Plan

### Upgrade 1: [Name]
- **What:** [Mô tả 1 dòng]
- **Why:** [Business value cho Sếp]
- **How:** [Approach kỹ thuật ngắn gọn]
- **Effort:** [X hours / Y sprints]
- **Prerequisite:** [Cần gì trước?]

### Upgrade 2: ...
### Upgrade 3: ...
```

---

## 🏗️ Sub-Skill: upgrade-blueprint — Template upgrade plan

### Khi đã chọn được upgrade, viết plan theo format:

```markdown
# Upgrade: [Tên]

## Trước khi làm, Sếp sẽ thấy:
[Mô tả trải nghiệm hiện tại — pain point]

## Sau khi làm, Sếp sẽ thấy:
[Mô tả trải nghiệm mới — improvement cụ thể]

## Phạm vi thay đổi:
| File | Thay đổi | Risk |
|------|---------|------|
| server.py | Thêm 2 endpoints | Low |

## Không ảnh hưởng:
- [Liệt kê những gì KHÔNG đổi để Sếp yên tâm]

## Rollback plan:
- Nếu có vấn đề: [cách quay lại trạng thái cũ]
```

---

## ⚡ Sub-Skill: quick-wins — Phát hiện cải tiến nhanh

### Checklist "30 phút có kết quả":

Mỗi lần scan, tìm kiểu:

| Loại | Ví dụ | Effort |
|------|-------|--------|
| **Config cleanup** | Hardcoded value → env var | 5 min |
| **Missing error handling** | API call không có try/except | 10 min |
| **UX micro-improvement** | Thêm loading state | 15 min |
| **Data display** | Thêm 1 column vào table | 10 min |
| **Performance** | Cache query result | 15 min |
| **Documentation** | Thêm docstring cho function | 5 min |
| **Cleanup** | Xóa dead code, unused imports | 10 min |

---

## 🎯 Sub-Skill: competitive-moat — Xây dựng lợi thế cạnh tranh

### Framework phân tích competitive advantage:

```
DATA MOAT (Khó copy nhất)
├── 11 tháng shipment history        → Pattern recognition
├── 25,904 rate records              → Market intelligence  
├── Email parsing → customer insights → Relationship intelligence
└── Delay/risk logs                  → Predictive capability

SPEED MOAT (Nhanh hơn đối thủ)
├── Telegram bot → reply 3s          → 10x faster than manual
├── AI Chat → instant insights       → Real-time decision support
├── Auto-detect email stages         → Zero manual data entry
└── Trouble radar → proactive alerts → Fix before customer knows

INTELLIGENCE MOAT (Thông minh hơn đối thủ)
├── Carrier reliability scoring      → Better vendor selection
├── Customer health score            → Churn prediction
├── Team CC compliance               → Quality assurance
└── Profit margin tracking           → Better pricing decisions
```

### Câu hỏi tự vấn hàng tuần:
1. Tuần này data moat mạnh hơn tuần trước không? (rows tăng?)
2. Speed moat cải thiện không? (response time giảm?)
3. Intelligence moat tiến bộ không? (prediction accuracy tăng?)
4. Có ai clone được hệ thống này trong 1 tháng không?

---

## 🔄 Sub-Skill: auto-sprint — Tự đề xuất sprint tiếp theo

### Khi Sếp hỏi "làm gì tiếp" hoặc cuối sprint:

**BƯỚC 1:** Chạy `system-review > health-check` → biết trạng thái

**BƯỚC 2:** Đọc task.md → biết TODO còn gì

**BƯỚC 3:** Phân tích theo ma trận:

```
              HIGH IMPACT
                  │
     P1           │           P2
  (Làm ngay)      │    (Sprint tới)
                  │
LOW EFFORT ───────┼─────── HIGH EFFORT
                  │
     P3           │           P4
  (Quick win)     │    (Someday/Maybe)
                  │
              LOW IMPACT
```

**BƯỚC 4:** Output:

```markdown
## Sprint [N] — Proposed Focus

### 🎯 Goal: [1 câu mô tả mục tiêu sprint]

### P1 — Must Do (X hours)
1. [Task] → [Value cho Sếp]

### P2 — Should Do (Y hours)
1. [Task] → [Value cho Sếp]

### P3 — Quick Wins (Z minutes each)
1. [Task] → [Value]

### NOT this sprint:
- [Task] → [Lý do defer]
```

---

## 🔗 Integration với System Review

| Brainstorm output | System Review input |
|------------------|-------------------|
| Quick wins identified | → feed vào sprint backlog |
| P1 gaps found | → trigger `full-audit` nếu nghiêm trọng |
| New feature idea | → chạy `gap-analysis` để validate |
| Architecture concern | → chạy `pattern-smell` để confirm |

**Workflow đề xuất:**
```
Monthly:     brainstorm-upgrade > multi-perspective
Sprints:     brainstorm-upgrade > auto-sprint  
Post-deploy: system-review > post-deploy-review
Weekly:      system-review > health-check
Ad-hoc:      brainstorm-upgrade > critique-loop
```
