---
name: auto-test-loop
description: >
  Automated test-fix-retry loop cho Nelson system. TRIGGER khi: code xong cần test,
  fix bug rồi chạy lại, deploy bot/ERP/WebApp cần verify, hoặc bất kỳ lúc nào cần
  chạy code → test → fix → retry tự động cho đến khi pass.
---

# Auto Test-Fix Loop — Nelson System

> **Vấn đề gốc:** Code xong phải quay qua test thủ công → tốn thời gian
> **Giải pháp:** AI tự chạy test → phân tích lỗi → fix → retry → cho đến khi pass
> **Inspired by:** Vercel's `ralph-loop-agent` verification loop pattern

---

## 🎯 Khi nào TRIGGER skill này

- Vừa code xong 1 module/function mới
- Fix bug và cần verify
- Deploy bot, cần đảm bảo chạy OK
- Chạy ERP refresh, cần verify data
- Bất kỳ khi Sếp nói: "chạy thử", "test đi", "verify", "fix rồi test lại"

---

## ⚡ Quy trình Auto Test Loop (5 bước)

```
┌─────────────────────────────────────────────────┐
│              AUTO TEST-FIX LOOP                  │
│                                                  │
│  1. DEFINE: Xác định test command               │
│  2. RUN: Chạy test command                      │
│  3. ANALYZE: Đọc output, phân tích lỗi          │
│  4. FIX: Sửa code dựa trên root cause           │
│  5. VERIFY: Chạy lại test                        │
│         ↓                                        │
│     Pass? → ✅ Báo Sếp thành công               │
│     Fail? → Quay bước 3 (max 5 iterations)       │
│                                                  │
│  ⚠️ Safety: max 5 retries → hỏi Sếp            │
└─────────────────────────────────────────────────┘
```

### Bước 1: DEFINE — Xác định Test Command

Tùy theo component đang làm:

| Component | Test Command | Success Criteria |
|-----------|-------------|-----------------|
| **Bot module** | `python -c "import module_name; print('OK')"` | Output "OK", exit 0 |
| **Bot startup** | `cd TelegramBot && timeout 10 python bot_v5.py` | Không crash trong 10s |
| **Bot full test** | `cd TelegramBot && python test_bot.py` | All tests pass |
| **ERP refresh** | `python ERP/core/refresh.py` | Exit 0, row count đúng |
| **Python syntax** | `python -m py_compile target_file.py` | Exit 0 |
| **WebApp build** | `cd webapp && npm run build` | Exit 0 |
| **WebApp dev** | `cd webapp && timeout 15 npm run dev` | Server starts OK |
| **Pytest suite** | `python -m pytest tests/ -v` | All tests pass |
| **Custom script** | `python C:\Temp\test_script.py` | User-defined criteria |

### Bước 2: RUN — Chạy Test

```bash
# Chạy command và capture TOÀN BỘ output
# KHÔNG cắt bớt output — cần đọc hết để phân tích
```

**Rules:**
- Chạy command THẬT, không giả lập
- Capture cả stdout và stderr
- Ghi nhận exit code
- Timeout hợp lý (10-30s cho unit test, 60s cho build)

### Bước 3: ANALYZE — Phân tích lỗi

Khi test FAIL, phân tích theo thứ tự:

1. **Đọc error message cuối cùng** — thường chứa root cause
2. **Tìm traceback** — file nào, dòng nào, function nào lỗi
3. **Phân loại lỗi:**

| Loại lỗi | Pattern | Cách fix |
|-----------|---------|----------|
| **Import Error** | `ModuleNotFoundError`, `ImportError` | Check path, add import |
| **Syntax Error** | `SyntaxError`, `IndentationError` | Fix syntax at exact line |
| **Type Error** | `TypeError`, wrong args | Check function signature |
| **Name Error** | `NameError`, undefined var | Define variable or import |
| **Logic Error** | Wrong output, assertion fail | Trace data flow |
| **File Error** | `FileNotFoundError` | Check path, create file |
| **Runtime Error** | `RuntimeError`, crash | Debug specific condition |

### Bước 4: FIX — Sửa code

**Rules:**
- Sửa DUY NHẤT vấn đề được phân tích ở bước 3
- KHÔNG sửa thêm thứ khác "tiện thể"
- KHÔNG refactor code xung quanh
- Giữ change nhỏ nhất có thể

### Bước 5: VERIFY — Chạy lại test

- Chạy LẠI chính xác command ở bước 2
- Đọc TOÀN BỘ output mới
- So sánh với output cũ

**Nếu PASS:** 
```
✅ Test passed sau [N] iteration(s)!
Changes made:
1. [Mô tả fix 1]
2. [Mô tả fix 2] (nếu retry > 1)
```

**Nếu FAIL:**
- Quay bước 3 với output mới
- Lỗi mới? Phân tích lại
- Lỗi giống cũ? Fix chưa đúng → approach khác

---

## 🛑 Safety Rules

### Max 5 Retries
Sau 5 lần fix-test mà vẫn fail:
```
⚠️ Đã thử 5 lần mà vẫn không pass.
Có thể là vấn đề kiến trúc, không phải bug đơn giản.
→ Báo Sếp để thảo luận approach khác.
```

### 3-Fix Escalation (từ systematic-debugging)
Nếu 3 fix liên tiếp không giải quyết được:
- STOP
- Xem lại architecture
- Có thể cần redesign, không phải patch

### KHÔNG được làm
- ❌ Tự ý xóa test khi fail
- ❌ Sửa assertion cho match output sai
- ❌ Bỏ qua warning/error
- ❌ Chạy partial test (phải chạy full suite)
- ❌ Claim "pass" khi chưa có evidence

---

## 📋 Nelson-Specific Test Recipes

### Recipe 1: Bot Module Mới
```bash
# Step 1: Syntax check
python -m py_compile TelegramBot/new_module.py

# Step 2: Import check  
python -c "from new_module import main_function; print('Import OK')"

# Step 3: Unit test
python -c "
from new_module import main_function
result = main_function(test_input)
assert result is not None, 'Result should not be None'
print(f'Result: {result}')
print('PASS')
"

# Step 4: Integration with bot
python -c "import bot_v5; print('Bot imports OK')"
```

### Recipe 2: ERP Script Changes
```bash
# Step 1: Syntax
python -m py_compile ERP/core/refresh.py

# Step 2: Dry run (if supported)
python ERP/core/refresh.py --dry-run

# Step 3: Full run
python ERP/core/refresh.py

# Step 4: Verify output
python -c "
import openpyxl
wb = openpyxl.load_workbook('ERP/data/ERP_Master.xlsm', data_only=True)
ws = wb['Pricing'] if 'Pricing' in wb.sheetnames else wb.active
print(f'Rows: {ws.max_row}, Cols: {ws.max_column}')
print('PASS' if ws.max_row > 8 else 'FAIL: too few rows')
"
```

### Recipe 3: Query Engine Changes
```bash
# Quick verification
python -c "
from query_engine import FreightQueryEngine
engine = FreightQueryEngine('Pricing_Engine/data/Cleaned_Master_History.parquet')
results = engine.query_rates(pol='HPH', place='Denver')
print(f'Results: {len(results)} rates found')
assert len(results) > 0, 'Should find rates for HPH→Denver'
print('PASS')
"
```

### Recipe 4: Generic Python Script
```bash
# Cho bất kỳ Python script nào
python -m py_compile target_file.py && echo "Syntax OK"
python target_file.py
```

---

## 🔄 Integration với các skill khác

| Skill | Khi nào dùng cùng |
|-------|-------------------|
| `test-driven-development` | Viết test TRƯỚC, rồi dùng auto-test-loop để verify |
| `verification-before-completion` | Sau khi loop pass, verify toàn bộ trước khi báo done |
| `systematic-debugging` | Khi loop fail > 3 lần, chuyển sang debug có hệ thống |
| `bot-v5-dev` | Test recipe cho bot modules |
| `erp-master` | Test recipe cho ERP changes |
| `cleanup-after-task` | Xóa file test tạm sau khi task xong |

---

## 📊 Output Template

### Khi PASS
```
✅ AUTO-TEST PASS — [Component Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Iterations: [N]/5
Test command: [command]
Exit code: 0

Changes made:
1. [file.py:L42] Fixed import path
2. [file.py:L67] Added null check

Evidence:
[Paste relevant output showing pass]
```

### Khi FAIL (max retries)
```
⚠️ AUTO-TEST FAIL — [Component Name]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Iterations: 5/5 (MAX)
Test command: [command]
Last error: [error summary]

Fixes attempted:
1. [Iteration 1] [what was tried]
2. [Iteration 2] [what was tried]
...

🔍 Root cause analysis: [hypothesis]
💡 Recommendation: [next steps / ask Sếp]
```

---

## 🔗 References
- **Vercel ralph-loop-agent:** Outer verification loop inspiration
- **obra/superpowers:** TDD + verification + debugging skills
- **Bot path:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\TelegramBot\`
- **ERP path:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\ERP\`
