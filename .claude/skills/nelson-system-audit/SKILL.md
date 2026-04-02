---
name: nelson-system-audit
description: >
  Automated Architecture Audit System cho Nelson Freight Platform.
  Đánh giá architecture health, phát hiện drift, scan technical debt, 
  và tự đánh giá hệ thống hàng ngày. TRIGGER khi: trước/sau refactor,
  sprint review, pre-deploy, system health check, hoặc khi Sếp hỏi
  "kiến trúc có ổn không", "hệ thống có tuân thủ blueprint không".
---

# Nelson System Audit — Architecture Health Check System

> **Triết lý:** Platform tốt là platform biết tự chấm điểm mình.
> **RULE:** Mọi đánh giá phải có BẰNG CHỨNG từ codebase scan — không dùng giả định.

---

## 🎯 Khi nào TRIGGER skill này

| Tình huống | Command |
|-----------|---------|
| Trước refactor (baseline) | `python audit_engine.py --full` |
| Sau mỗi sprint | `python audit_engine.py --architecture` |
| Trước deploy production | `python audit_engine.py --drift --tech-debt` |
| Hàng ngày tự động | `python audit_engine.py --self-eval` |
| Sếp hỏi "kiến trúc OK?" | `python audit_engine.py --architecture` |
| Kiểm tra tech debt | `python audit_engine.py --tech-debt` |

---

## 📁 Cấu trúc Skill

```
nelson-system-audit/
├── SKILL.md                    # This file
├── scripts/
│   ├── audit_engine.py         # CLI entry point + orchestrator
│   ├── architecture_rules.py   # Blueprint definitions + scoring weights
│   ├── drift_detector.py       # Scan codebase for architecture violations
│   ├── tech_debt_scanner.py    # Detect debt patterns in code
│   ├── self_evaluator.py       # Runtime health check (API, DB, workers)
│   ├── report_generator.py     # Format audit results
│   └── rules/
│       ├── __init__.py
│       ├── data_rules.py       # Data layer rules
│       ├── api_rules.py        # API layer rules
│       ├── service_rules.py    # Service boundary rules
│       ├── security_rules.py   # Auth + access control rules
│       └── coupling_rules.py   # Module coupling rules
```

---

## 🔧 Commands

### Architecture Health Check
```bash
python audit_engine.py --architecture
```
Đánh giá 6 layers: Data, API, Service, Client Isolation, Event System, Security.
Output: Architecture Score X.X / 10.

### Architecture Drift Detection
```bash
python audit_engine.py --drift
```
Scan codebase tìm violations: file access ngoài DAL, bypass API, missing auth, hardcoded paths.

### Technical Debt Scan
```bash
python audit_engine.py --tech-debt
```
Tìm: large files, duplicate functions, legacy JSON, unused modules, circular deps.

### System Self-Evaluation
```bash
python audit_engine.py --self-eval
```
Runtime check: API health, worker status, event pipeline, DB integrity, latency.

### Full Audit
```bash
python audit_engine.py --full
```
Chạy tất cả 4 subsystems, tạo unified report.

---

## 📊 Scoring System

### Architecture Score (0-10)

| Layer | Weight | Checks |
|-------|--------|--------|
| Data Layer | 20% | Single source of truth, no JSON DBs, PostgreSQL usage |
| API Layer | 20% | Modular routers, proper error handling, <500 lines/file |
| Service Layer | 15% | Clean boundaries, no cross-service DB access |
| Client Isolation | 15% | Clients only via API, no file reads, no business logic |
| Event System | 15% | Event sourcing, immutable events, worker health |
| Security | 15% | Auth middleware, RBAC, no hardcoded secrets |

### Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| 🔴 CRITICAL | Blueprint violation, data risk | Fix before next deploy |
| 🟡 HIGH | Significant drift, scaling risk | Fix within sprint |
| 🟢 MEDIUM | Suboptimal but functional | Add to backlog |
| ⚪ LOW | Minor improvement opportunity | Nice to have |

---

## 🔗 Liên kết với skills khác

| Khi audit phát hiện... | Trigger skill |
|------------------------|---------------|
| Bot đọc file trực tiếp | `bot-v5-dev` → refactor to API client |
| API monolith >1000 lines | Refactor theo blueprint |
| WebApp bypass API | `webapp-rules` → fix data flow |
| ERP file coupling | `erp-master` → add API bridge |
| Data pipeline issues | `data-pipeline` → fix data flow |
| Security gaps | Fix auth middleware |
