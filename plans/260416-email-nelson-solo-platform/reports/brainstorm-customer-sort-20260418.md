# Brainstorm — Nelson Customer Sort (Outlook folder routing)

**Date:** 2026-04-18
**Status:** Design approved, scope locked — ready for `/ck:plan`
**Related:** Extends existing `outlook_scanner.py` job framework (mentee sort)

---

## 1. Problem

Email của khách RIÊNG Nelson (DIRECT shippers + FW co-loaders) **đang nằm lẫn lộn Inbox chính** — không được auto-move vào folder con như email mentee. Lý do: `rules.json` có `skip_routing: true` cho `nelson@pudongprime.vn` → mentee sort bỏ qua email Nelson-facing.

Kết quả: Sếp phải scan tay Inbox mỗi ngày để tìm email khách trong đống thư rác/alert/newsletter.

---

## 2. Data sẵn có — không build lại

**`D:/OneDrive/NelsonData/email/customer_rules.json`** đã định nghĩa 8 khách:

| Type | Customer | Detection fields |
|------|----------|------------------|
| FWD | SIRI | `hbl_prefixes: [PELP]`, carrier: CMA |
| FWD | PANDA | `email_domains: [panda4u.com]`, `hbl_prefixes: [PHOU, PNYC, PCHS]` |
| FWD | HML | `hbl_prefixes: [PDEN]`, `bkg_prefixes: [HANG]` |
| DIRECT | CREATIVE LIGHT | routes: HPH-LAX |
| DIRECT | Nafood | `bkg_prefixes: [EBKG]`, carrier: MSC, reefer |
| DIRECT | VINARES | `hbl_prefixes: [PYTO]`, `bkg_prefixes: [HANFG]` |
| DIRECT | PT FOOD | (no samples yet) |
| DIRECT | HER HUI WOOD | (no samples yet) |

Mỗi khách có `seen_senders`, `email_domains`, `hbl_prefixes`, `bkg_prefixes`, `detection_rules.keywords` → đủ material để match email.

---

## 3. Outlook folder structure có sẵn (Sếp confirm)

```
DIRECT/
  Nafood/
  VINARES/
  CREATIVE LIGHT/
  PT FOOD/
  HER HUI WOOD/
FW/
  SIRI/
  PANDA/
  HML/
CNEE/                ← future expansion từ cnee_master_v2.xlsx
```

---

## 4. Design — thêm 1 job vào outlook_scanner.py

### Architecture
```
[Task Scheduler 30min] → outlook_scanner.py
    ├── run_mentee_classification (cũ)
    └── run_nelson_customer_sort (MỚI)
         ├── load customer_rules.json
         ├── scan Inbox root (skip items đã trong sub-folder)
         ├── match priority: sender → domain → hbl/bkg prefix → keyword
         ├── move vô `{type}/{CustomerName}/`
         └── telegram summary
```

### Match priority (per email)
1. **sender in `seen_senders`** (exact) → move
2. **sender domain in `email_domains`** → move
3. **`hbl_prefixes` or `bkg_prefixes`** regex match trong subject/body → move
4. **company keyword** (detection_rules.keywords) trong subject/body → fuzzy match → move
5. Không match → leave in Inbox

### Folder resolution
```python
folder = get_folder(f"{type_to_folder[rule.type]}/{rule.name}")
# type_to_folder = {"DIRECT": "DIRECT", "FWD": "FW"}
```

---

## 5. Decisions locked

| Item | Choice | Rationale |
|------|--------|-----------|
| Scope | 8 khách hiện có, không expand CNEE | Ship fast, Sếp thêm khách mới vô JSON khi cần |
| Integration với Phase 02 | **Ship riêng** — Customer Sort trước, Second Brain tuần sau | Tránh scope creep, folder sạch giúp Second Brain tốt hơn |
| Infrastructure | Thêm job vô `outlook_scanner.py` (không file riêng) | Tái dùng config/timeout/telegram summary |
| Schedule | Cùng lịch MenteeSort (30min 8:00-17:30 hoặc all-time) | 1 task scan, 2 passes |
| Idempotency | Skip item đã trong sub-folder | Prevent double-move |
| Dry-run support | Yes (`--job nelson_customer_sort --dry-run`) | An toàn khi test |

---

## 6. Integration với MenteeSort

**Thứ tự trong 1 lần scan:**
1. `run_mentee_classification` — move email Team Sunny sang mentee folder
2. `run_nelson_customer_sort` — quét email CÒN LẠI trong Inbox root, move sang customer folder
3. Email không match cả 2 → để lại Inbox (noise/new prospects)

Không conflict vì:
- Mentee sort match sender/recipient là `*@pudongprime.vn`
- Customer sort match sender/domain/prefix từ customer_rules.json (bên ngoài domain company)

---

## 7. Success metrics

- ≥90% email từ 8 khách tự động vào đúng folder trong tuần đầu
- False positive rate ≤1% (email không phải khách bị move nhầm)
- Dry-run report: list email dự kiến move kèm customer matched + rule triggered → Sếp audit trước khi enable live

---

## 8. Next step

→ Invoke `/ck:plan --auto` để break thành phase file:
- phase-XX-nelson-customer-sort.md
- Sub-tasks: loader, matcher, mover, telegram summary, Task Scheduler registration, dry-run test

Effort estimate: **~4-6 hours** (1 buổi) — đơn giản vì tái dùng toàn bộ infra MenteeSort.

---

**Status:** DONE
**Summary:** Customer Sort design approved — add 1 job vào outlook_scanner.py, match qua customer_rules.json sẵn có, move vào DIRECT/FW folder structure đã có. Ship riêng trước Second Brain.
