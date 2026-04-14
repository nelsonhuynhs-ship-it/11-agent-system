# Permission Bypass — Cấu hình để Claude không hỏi approve nữa

## TL;DR

3 levels từ nhẹ → mạnh. Em recommend **Level 2 (allow list)** cho anh — an toàn + hands-off.

---

## Level 1 — YOLO mode (mạnh nhất, RỦI RO)

Launch Claude với flag bypass tất cả permission:

```bash
claude --dangerously-skip-permissions
```

**Hoặc** set env var:

```bash
# Windows PowerShell
$env:CLAUDE_SKIP_PERMISSIONS = "1"
claude

# Bash/Git Bash
export CLAUDE_SKIP_PERMISSIONS=1
claude
```

**Pros**: không bao giờ bị hỏi.
**Cons**: Claude có thể chạy BẤT KỲ lệnh nào — `rm -rf`, push force, edit file nhạy cảm. Anh mất visibility hoàn toàn.

**Em KHÔNG recommend** trừ khi anh 100% trust Claude + có backup đầy đủ.

---

## Level 2 — Allow list qua `settings.local.json` (RECOMMENDED)

Cho phép Claude tự chạy các tool cụ thể trong phạm vi cụ thể, vẫn hỏi cho cái ngoài phạm vi đó.

### File: `D:/NELSON/2. Areas/Engine_test/.claude/settings.local.json`

> **Lưu ý**: dùng `settings.local.json` (không phải `settings.json`) để KHÔNG commit vào git. File này chỉ ở máy anh.

```json
{
  "permissions": {
    "allow": [
      "Bash(python *)",
      "Bash(C:/Users/Nelson/anaconda3/python *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git log *)",
      "Bash(git branch *)",
      "Bash(git checkout *)",
      "Bash(git pull *)",
      "Bash(git push)",
      "Bash(git worktree *)",
      "Bash(gh pr *)",
      "Bash(gh issue *)",
      "Bash(ls *)",
      "Bash(mkdir *)",
      "Bash(cat *)",
      "Bash(echo *)",
      "Edit(D:/OneDrive/NelsonData/erp/**)",
      "Edit(D:/NELSON/2. Areas/Engine_test/tools/erp-helpers/**)",
      "Edit(D:/NELSON/2. Areas/Engine_test/plans/**)",
      "Edit(D:/NELSON/2. Areas/Engine_test/api/**)",
      "Edit(D:/NELSON/2. Areas/Engine_test/email_engine/**)",
      "Write(D:/OneDrive/NelsonData/erp/**)",
      "Write(D:/NELSON/2. Areas/Engine_test/tools/**)",
      "Write(D:/NELSON/2. Areas/Engine_test/plans/**)",
      "Read(**)",
      "Glob(**)",
      "Grep(**)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(git push --force*)",
      "Bash(git push -f*)",
      "Bash(git reset --hard*)",
      "Edit(D:/OneDrive/NelsonData/**/.env*)",
      "Edit(**/secrets/**)",
      "Edit(**/.ssh/**)",
      "Write(**/.env*)"
    ]
  }
}
```

### Pattern syntax giải thích

- `Bash(python *)` — allow bất kỳ lệnh `python ...`
- `Bash(git push)` — allow đúng `git push` (không có arg), không allow `git push --force`
- `Edit(path/**)` — allow edit bất kỳ file trong thư mục đó (và sub-dirs)
- `Read(**)` — allow đọc mọi file (an toàn, chỉ read)
- `deny` prevail over `allow` — `rm -rf` sẽ bị block dù allow có `Bash(*)`

### Cách apply

Cách 1 — anh tự tạo file:
1. Mở editor bất kỳ (VS Code, Notepad++)
2. Paste nội dung JSON trên
3. Save vào đúng path: `D:\NELSON\2. Areas\Engine_test\.claude\settings.local.json`
4. Restart Claude CLI

Cách 2 — cho phép Claude làm thay (duy nhất 1 lần):
- Anh nói: "OK apply permission bypass level 2"
- Claude dùng Write tool để tạo file (1 lần cuối cần approve manual)
- Từ session sau trở đi hands-off

---

## Level 3 — Per-session `/permissions` command (nhẹ nhất)

Trong session Claude đang chạy, gõ:

```
/permissions
```

UI sẽ hiện để anh toggle allow/deny cho từng tool. Chỉ áp dụng cho session hiện tại, session sau phải toggle lại.

**Pros**: nhẹ nhất, không commit gì.
**Cons**: phải làm lại mỗi session mới. Không phù hợp với anh (anh muốn 1 lần duy nhất).

---

## Khuyến nghị cuối

**Level 2** với config ở trên. Lý do:
1. Hands-off cho 95% task ERP (Python, git, edit file trong phạm vi)
2. Vẫn hỏi approve cho action nguy hiểm ngoài allow list
3. Explicit `deny` block những thứ phá hoại
4. 1 lần config, không phải đụng lại
5. Visible trong git (nếu anh muốn commit) hoặc local (nếu muốn riêng)

**Nếu anh muốn mạnh hơn**: thêm `Bash(*)` vào allow (cho phép mọi bash) — vẫn an toàn vì `deny` list block các lệnh phá hoại. Nhưng em vẫn khuyên explicit cho ERP workflow để visibility.

---

## Verify sau khi apply

Sau khi save file + restart Claude, thử trong session mới:

```
(Anh): chạy python -c "print('hello')"
```

Nếu Claude chạy luôn không hỏi → apply thành công.

```
(Anh): chạy rm -rf /tmp/test
```

Nếu Claude hỏi approve (hoặc refuse) → deny list đang hoạt động đúng.

---

## Rollback nếu có vấn đề

Xóa file `settings.local.json`:
```bash
rm "D:/NELSON/2. Areas/Engine_test/.claude/settings.local.json"
```

Restart Claude → về lại default (hỏi từng tool call).
