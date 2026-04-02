---
name: email-intelligence
description: >
  Master skill cho 10 Email Intelligence Features — Nelson Freight Intelligence Platform.
  TRIGGER khi: session mới (via /intelligence-audit), planning sprint, build feature,
  hoặc bất kỳ khi nào cần biết trạng thái 10 features và skill coverage.
---

# Email Intelligence — Master Plan

> **Mission:** Biến Nelson Freight từ forwarder bình thường → Freight Intelligence Platform
> **Foundation:** Email dataset (`email_dataset.parquet` + `shipment_history.parquet`)
> **Rule:** KHÔNG tạo feature mới ngoài 10 features dưới đây

---

## 🎯 10 Features — Status Tracker

| # | Feature | Status | Phase | Skill Coverage |
|---|---------|--------|-------|----------------|
| 1 | 🔮 Churn Radar | ✅ DONE | Phase 2 | `ai_sales_intel.py` + `/churn` cmd + fallback |
| 2 | ⏱️ Response DNA | ❌ NOT STARTED | Phase 3 | `bot-v5-dev` partial |
| 3 | 🌊 Carrier Trouble Index | ✅ DONE | Phase 1 | `email_analytics.py` + `/trouble` cmd |
| 4 | 🧬 Commitment Score | ❌ NOT STARTED | Phase 3 | `freight-ops` partial |
| 5 | 🗺️ Route Health Map | ✅ DONE | Phase 1 | `email_analytics.py` + `/route` cmd |
| 6 | 👻 Ghost Pipeline Detector | ❌ NOT STARTED | Phase 2 | `bot-v5-dev` partial |
| 7 | 🎯 Coaching Radar | ❌ NOT STARTED | Phase 5 | `system-review` partial |
| 8 | 📡 Market Sentiment Tracker | ❌ NOT STARTED | Phase 4 | None |
| 9 | 💎 Relationship Depth Score | ✅ DONE | Phase 4 | `customer_intelligence.py` + `/intel` cmd + fallback |
| 10 | 🔄 Autopilot Mode | ❌ NOT STARTED | Phase 5 | None |

**Status legend:** ❌ NOT STARTED | 🔄 IN PROGRESS | ✅ DONE

---

## 📊 Skill → Feature Mapping Table

### Existing Skills → Feature Coverage

| Skill | Covers Features | Gaps |
|-------|----------------|------|
| `data-pipeline` | ①③⑤⑧ (Parquet query, data aggregation) | Chưa có aggregate functions cho frequency analysis, trend detection |
| `freight-ops` | ③④⑨ (carrier tips, customer profiles) | Chưa có scoring engine, chưa calculate từ email data |
| `bot-v5-dev` | ②⑥ (bot commands, module routing) | Chưa có analytics module, chưa expose Intelligence features via bot |
| `system-review` | ⑦ (health check, team audit) | Chưa integrate với email dataset, chỉ check static files |
| `erp-master` | ⑥ (quote/job data for pipeline) | Chưa cross-reference email activity với quote status |
| `webapp-scalable` | ALL (dashboard UI cho mọi feature) | WebApp chưa build xong, chưa có Intelligence pages |
| `auto-test-loop` | ALL (test cho mọi feature mới) | Chưa có test recipes cho Intelligence features |
| `brainstorm-upgrade` | Meta (sprint planning) | Cần update focus vào 10 features thay vì general brainstorm |
| `webapp-testing` | ALL (visual testing cho dashboard) | Chưa có test scenarios cho Intelligence UI |

### Skills Không Liên Quan Trực Tiếp (giữ nhưng không focus)

`cleanup-after-task`, `verification-before-completion`, `systematic-debugging`, `test-driven-development`
→ Infrastructure skills — dùng khi cần, không cần upgrade cho features

---

## 🔴 Skill Gaps — Cần tạo/nâng cấp

### GAP 1: Email Analytics Engine
- **Cần cho:** ①②③④⑤⑧⑨ (7/10 features)
- **Hiện tại:** `dataset_store.py` chỉ append data, KHÔNG có analytics functions
- **Cần tạo:** Module `email_analytics.py` trong `email_engine/` với functions:
  - `customer_frequency(customer, period)` → emails per week/month
  - `response_time(team_member, customer)` → avg reply seconds
  - `risk_frequency(carrier, route, period)` → trouble count
  - `thread_activity(thread_id)` → last activity, reply count
  - `stage_duration(shipment_id, from_stage, to_stage)` → hours/days
- **Update skill:** `data-pipeline` → thêm sub-skill `email-analytics`

### GAP 2: Scoring Engine
- **Cần cho:** ①④⑦⑨ (4/10 features)
- **Hiện tại:** Không có scoring framework
- **Cần tạo:** Module `scoring_engine.py` trong `email_engine/` với:
  - `ChurnScore(customer)` → 0-100
  - `CommitmentScore(customer, quote_thread)` → 0-100
  - `RelationshipDepthScore(customer)` → 0-100
  - `CoachingScore(team_member)` → multi-dimensional
- **New skill:** Có thể tích hợp vào `freight-ops` → sub-skill `intelligence-scoring`

### GAP 3: Market Intelligence Aggregator
- **Cần cho:** ⑧ Market Sentiment
- **Hiện tại:** Không có demand/supply signal detection
- **Cần tạo:** Module `market_intelligence.py` trong `email_engine/`
  - `demand_signals(route, period)` → inquiry frequency trend
  - `supply_signals(period)` → risk event frequency trend
  - `sentiment_score(route)` → TIGHTENING / NORMAL / LOOSENING
- **New sub-skill:** `freight-ops` → sub-skill `market-intelligence`

### GAP 4: Autopilot Decision Tree
- **Cần cho:** ⑩ Autopilot Mode
- **Hiện tại:** `shipment_brain.py` detects stages nhưng không auto-respond
- **Cần tạo:** Module `autopilot.py` trong `email_engine/`
  - `can_auto_handle(email, shipment_state)` → True/False
  - `generate_response(email, stage, customer_rules)` → draft email
  - `auto_cc(email, rules)` → correct CC list
- **New skill:** `email-intelligence` → sub-skill `autopilot`

### GAP 5: Intelligence Dashboard Pages
- **Cần cho:** ALL features (display layer)
- **Hiện tại:** WebApp có dashboard shell, chưa có Intelligence pages
- **Cần tạo:** Next.js pages cho mỗi feature khi build WebApp (Sprint 13+)
- **Update skill:** `webapp-scalable` → thêm Intelligence pages vào dashboard spec

---

## 🗺️ Implementation Roadmap

### Phase 1 (Sprint 12) — Data Foundation
**Features:** ③ Carrier Trouble Index + ⑤ Route Health Map
**Why first:** Data đã có trong `shipment_history.parquet`, chỉ cần aggregate functions.

```
Deliverables:
  1. email_analytics.py → risk_frequency(), stage_duration()
  2. Bot command: /trouble [carrier] → Trouble Index output
  3. Bot command: /route [POL] [PLACE] → Route Health output
  4. Update data-pipeline skill → sub-skill email-analytics
```

### Phase 2 (Sprint 13) — Customer Intelligence
**Features:** ① Churn Radar + ⑥ Ghost Pipeline Detector
**Why second:** High impact, builds on Phase 1 analytics.

```
Deliverables:
  1. email_analytics.py → customer_frequency(), thread_activity()
  2. scoring_engine.py → ChurnScore()
  3. Bot command: /churn → Churn Radar report
  4. Bot command: /ghost → Ghost Pipeline report
  5. Update freight-ops skill → sub-skill intelligence-scoring
```

### Phase 3 (Sprint 14) — Team & Sales Intelligence
**Features:** ④ Commitment Score + ② Response DNA
**Why third:** Needs follow-up engine integration.

```
Deliverables:
  1. email_analytics.py → response_time()
  2. scoring_engine.py → CommitmentScore()
  3. Bot: /dna [team_member] → Response DNA report
  4. Upgrade follow_up_engine.py → commitment scoring
```

### Phase 4 (Sprint 15) — Advanced Analytics
**Features:** ⑧ Market Sentiment + ⑨ Relationship Depth
**Why fourth:** Needs 3+ months of accumulated data for accuracy.

```
Deliverables:
  1. market_intelligence.py → demand/supply signals
  2. scoring_engine.py → RelationshipDepthScore()
  3. Bot: /market → Market Sentiment report
  4. Bot: /relationship [customer] → Depth Score
```

### Phase 5 (Sprint 16+) — AI-Powered
**Features:** ⑦ Coaching Radar + ⑩ Autopilot Mode
**Why last:** Highest complexity, needs Gemini AI integration.

```
Deliverables:
  1. coaching_radar.py → CC compliance + AI coaching notes
  2. autopilot.py → auto-handle routine emails
  3. Bot: /coach [mentee] → Coaching report
  4. Dashboard: Autopilot status page
```

---

## 📁 Email Engine File Map

```
D:\NELSON\email_engine\
├── shipment_brain.py       ← Stage detection + risk (EXISTING)
├── dataset_store.py        ← Parquet append (EXISTING)
├── follow_up_engine.py     ← Tier follow-up (EXISTING)
├── customer_rules.json     ← Customer profiles (EXISTING)
├── rules.json              ← Team org chart (EXISTING)
├── shipment_patterns.yaml  ← Identifier patterns (EXISTING)
├── ops_briefing.py         ← Daily briefing (EXISTING)
│
├── email_analytics.py      ← Analytics functions (NEW — Phase 1)
├── scoring_engine.py       ← Scoring framework (NEW — Phase 2)
├── market_intelligence.py  ← Market signals (NEW — Phase 4)
└── autopilot.py            ← Auto-response (NEW — Phase 5)
```

---

## 🔗 References
- **Feature details:** `email_intelligence_features.md` (brainstorm artifact)
- **Workflow:** `/intelligence-audit` — pre-session audit
- **Data paths:** `email_engine/datasets/email_dataset.parquet`, `shipment_history.parquet`
- **Bot modules:** `D:\NELSON\2. Areas\PricingSystem\Engine_test\TelegramBot\`
