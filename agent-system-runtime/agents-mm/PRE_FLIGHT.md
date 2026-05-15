# PRE_FLIGHT.md — Auto-injected into every spawn

> **BẮT BUỘC đọc trước khi apply bất kỳ code change nào**

---

## Pre-flight Checklist

### ✅ Trước khi implement bất kỳ thay đổi nào:

1. **Chạy lint check**
   ```bash
   bash D:/NELSON/2. Areas/Engine_test/scripts/verify-pipeline.bat <path-to-changes>
   ```
   - Exit 0 → proceed
   - Exit 1 → block, fix violations trước

2. **Check golden-principles.md**
   - Đọc `D:/NELSON/2. Areas/Engine_test/scripts/golden-principles.md`
   - Tìm rule liên quan đến change
   - Apply fix pattern từ rule

3. **Check Failure DB context**
   - Đọc `~/.claude/agent-failures.db`
   - Tìm recent failures cùng loại
   - Avoid repeat same mistake

4. **Surgical change**
   - Chỉ change phần cần thiết
   - Không refactor surrounding code
   - Không add feature ngoài scope

5. **Sau khi thay đổi: re-run lint**
   ```bash
   bash D:/NELSON/2. Areas/Engine_test/scripts/verify-pipeline.bat <path-to-changes>
   ```
   - Pass mới được commit

---

## Golden Rules (never bypass)

| Rule | Why | How |
|------|-----|-----|
| R1: No hardcoded D:/ or C:/ | Path portability | Use shared/paths.py |
| R5: No bare except: | Error swallowing | Use except Exception: |
| R9: No f-string SQL | SQL injection risk | Parameterized queries |
| G1: Check None before parquet | AttributeError on None | `if df is None or df.empty` |

---

## Violation Handling

- **R1-R10 (verify-pipeline.bat):** Block spawn, log violation
- **G-rules (golden-principles.md):** Warn but allow with `# noqa: G<N>` comment
- **Unclear:** Stop và hỏi, không đoán

---

## Whitelist Pattern

```python
# noqa: R3 — third-party SDK, cannot add type hint
def external_api_call(param):
    return sdk.process(param)
```

Whitelist entries expire annually — review with `golden-principles.md` monthly review.

---

## File Paths Reference

| Purpose | Path |
|---------|------|
| Lint script | `D:/NELSON/2. Areas/Engine_test/scripts/verify-pipeline.bat` |
| Golden principles | `D:/NELSON/2. Areas/Engine_test/scripts/golden-principles.md` |
| Failure DB | `~/.claude/agent-failures.db` |
| Metrics DB | `~/.claude/agent-metrics.db` |
| Plans | `D:/NELSON/2. Areas/Engine_test/plans/` |

---

**Last updated:** 2026-04-29 (auto-generated, do not edit manually)