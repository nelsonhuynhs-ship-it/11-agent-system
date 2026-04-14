# Plan: AI-Powered Email Sequence System
**Date:** 2026-04-13 | **Status:** PLANNING

## Overview

Xay dung he thong email sequence thong minh, noi dung tu dong thay doi theo:
- **AI Forecast** tu `rate_predictor.py` (trend, confidence, predicted_rate)
- **Market Signals** tu anomaly_detector, SCFI/FIX/FAK comparison
- **Real Rates** tu Parquet (Cleaned_Master_History.parquet, 9.87M rows)
- **Customer Behavior** tu email_log.csv (open/reply/bounce history)

**Nguyen tac:**
- Email CHI co noi dung — khong signature (Outlook tu dong append)
- Noi dung LINH DONG theo tinh hinh thi truong thuc te
- Ket hop AI forecast de tao urgency/value thuc su, khong phai marketing rong

---

## Sequence Types (4 loai)

### Type 1: Weekly Rate Blast (Main — moi tuan)
> Gui gia hang tuan cho customer list. Content thay doi theo market condition.

### Type 2: Market Alert (Event-triggered)
> Khi AI phat hien anomaly hoac trend manh, gui alert ngay.

### Type 3: Lead Nurture (4 emails / 3 tuan)
> Customer moi hoac chua reply — build trust tu tu.

### Type 4: Re-engagement (3 emails / 2 tuan)
> Customer da im lang 30+ ngay — keo lai.

---

## Data Sources Integration

```
┌──────────────────────┐
│  Parquet (9.87M rows) │──> Current rates, validity, carriers
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  rate_predictor.py    │──> trend (rising/falling/stable), predicted_rate, confidence
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  anomaly_detector.py  │──> deviation_pct, severity (warning/critical), route_median
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  market_report/       │──> FIX vs FAK comparison, capacity signals, catalysts
│  schemas.py           │
└──────────┬───────────┘
           │
┌──────────▼───────────┐
│  EMAIL CONTENT ENGINE │──> Dynamic HTML body (no signature)
└──────────────────────┘
```

---

## Type 1: Weekly Rate Blast — 3 Variants

### Market Condition Detection Logic
```python
def detect_market_condition(predictions: list[dict]) -> str:
    """Based on rate_predictor output for top 5 routes"""
    avg_trend_pct = mean([p["trend_pct"] for p in predictions])
    if avg_trend_pct < -3:
        return "FALLING"    # -> Template A: "Rates dropping, lock now"
    elif avg_trend_pct > 3:
        return "RISING"     # -> Template B: "Rates climbing, act fast"
    else:
        return "STABLE"     # -> Template C: "Market stable, competitive window"
```

### Template A: FALLING MARKET
**When:** AI detects avg trend < -3% across top routes
**Tone:** Opportunistic, helpful — "good news for your bottom line"

```
Subject Options:
  A1: "Rates dropping on {ROUTE} — lock in before rebound"
  A2: "{CARRIER} cuts {ROUTE} rates — W{WEEK} update"
  A3: "Good news: {POL}→US rates down {TREND_PCT}%"

Preview Text: "Current best: ${BEST_RATE}/40HQ to {TOP_DEST}"

Body:
---
Hi {FIRST_NAME},

{ROUTE} rates are trending down {TREND_PCT}% this week. Our AI pricing model shows {CONFIDENCE} confidence this trend continues short-term.

Here are the best rates we've secured for your routes:

{RATE_TABLE}

Key highlights:
• {CARRIER_1} offers the most competitive rate to {DEST_1}
• Validity through {EXP_DATE} — rates may adjust after
{IF_ANOMALY}• Note: {ANOMALY_CARRIER} pricing is {DEVIATION}% below market median — unusually competitive{/IF_ANOMALY}

Want to lock in these rates? Reply to this email and I'll prepare your booking confirmation.
---
```

### Template B: RISING MARKET
**When:** AI detects avg trend > +3%
**Tone:** Urgent but professional — "market moving, don't wait"

```
Subject Options:
  B1: "Transpacific rates climbing — current offers valid through {EXP}"
  B2: "{POL}→US rates up {TREND_PCT}% — W{WEEK} pricing inside"
  B3: "Rate increase alert: best available before {EXP_DATE}"

Preview Text: "Rates up {TREND_PCT}% — current offers expiring soon"

Body:
---
Hi {FIRST_NAME},

Market rates on the {POL}→US trade lane have increased {TREND_PCT}% over the past 2 weeks. Carrier capacity is {CAPACITY_STATUS} and we expect further adjustments.

Here are the rates we can still offer today:

{RATE_TABLE}

{IF_FIX_ADVANTAGE}
Tip: Fixed contract rates (FIX) are currently ${FIX_SAVINGS} cheaper than spot (FAK) on {LANE}. Consider locking a contract rate while the gap exists.
{/IF_FIX_ADVANTAGE}

These rates are valid through {EXP_DATE}. I'd recommend confirming your bookings this week to avoid the next round of increases.
---
```

### Template C: STABLE MARKET
**When:** Trend between -3% and +3%
**Tone:** Informative, value-building — "keeping you updated"

```
Subject Options:
  C1: "Vietnam→US rates stable — W{WEEK} competitive pricing"
  C2: "Your weekly freight update — best rates from {CARRIER_COUNT} carriers"
  C3: "Transpacific market steady — current offers inside"

Preview Text: "Stable market = good time to plan ahead"

Body:
---
Hi {FIRST_NAME},

The Vietnam→US market is stable this week with rates holding steady. This is a good window for planning your upcoming shipments.

Current best rates for your routes:

{RATE_TABLE}

Market snapshot:
• Average 40HQ rate: ${AVG_RATE} ({TREND_DIRECTION} {TREND_PCT}% vs last week)
• Best value carrier: {BEST_CARRIER} at ${BEST_RATE}
• {CARRIER_COUNT} carriers competing on your routes

Let me know your upcoming schedule and I'll secure the best available rates.
---
```

---

## Type 2: Market Alert (Event-Triggered)

### Trigger Conditions
```python
# Trigger 1: Anomaly detected
if anomaly.severity == "critical" and anomaly.deviation_pct < -20:
    send_alert("PRICE_DROP", anomaly)

# Trigger 2: Significant trend shift
if abs(prediction.trend_pct) > 8:
    send_alert("TREND_SHIFT", prediction)

# Trigger 3: Rate type advantage
if fix_rate < fak_rate * 0.9:  # FIX 10%+ cheaper than FAK
    send_alert("FIX_ADVANTAGE", comparison)
```

### Alert Template: PRICE DROP
```
Subject: "Alert: {CARRIER} drops {ROUTE} by {PCT}% — limited availability"
Preview: "Unusually low rate detected — ${RATE}/40HQ"

Body:
---
Hi {FIRST_NAME},

Quick heads-up — our pricing system detected an unusually competitive rate:

  Carrier: {CARRIER}
  Route: {POL} → {DEST}
  Rate: ${RATE}/40HQ (market median: ${MEDIAN})
  Savings: {DEVIATION_PCT}% below market
  Valid: {EFF} — {EXP}

This is {DEVIATION_PCT}% below the current market median. These promotional rates typically don't last more than 1-2 weeks.

Interested? Reply with your cargo details and I'll check space availability.
---
```

### Alert Template: TREND SHIFT
```
Subject: "Market shift: {ROUTE} rates {DIRECTION} {PCT}%"
Preview: "Significant rate movement detected on your trade lane"

Body:
---
Hi {FIRST_NAME},

Significant rate movement on {POL}→{POD}:

  Direction: {DIRECTION} {TREND_PCT}%
  Current avg: ${CURRENT_AVG}/40HQ
  Forecast next week: ${PREDICTED_RATE}/40HQ (AI confidence: {CONFIDENCE})
  Carriers affected: {TOP_CARRIERS}

{IF_RISING}
Recommendation: Consider booking sooner rather than later. Our model predicts continued upward pressure.
{/IF_RISING}
{IF_FALLING}
Recommendation: Good opportunity to compare rates. We're seeing competitive offers from multiple carriers.
{/IF_FALLING}

Want me to prepare a detailed rate comparison for your specific routes?
---
```

---

## Type 3: Lead Nurture (New Customer — 4 emails / 3 weeks)

### Sequence Flow
```
[New Contact Added] → Email 1 (Day 0)
                         |
                    Opened? ──Yes──→ Email 2 (Day 4)
                         |               |
                         No          Replied? ──Yes──→ [EXIT: Sales handoff]
                         |               |
                         v               No
                    Email 1b (Day 3)     |
                    (shorter version)    v
                         |          Email 3 (Day 10)
                         |               |
                         +───────────────+
                                         |
                                    Email 4 (Day 18)
                                         |
                                    [EXIT: Move to Weekly Blast]
```

### Email 1: Introduction + Value (Day 0)
```
Subject: "Your {POL}→{DEST} freight rates — from a local expert"
Preview: "Real-time rates, no middleman markup"

Body:
---
Hi {FIRST_NAME},

I'm Nelson from Pudong Prime Shipping. We specialize in Vietnam→US ocean freight with direct carrier relationships.

What makes us different:
• Real-time rate access from {CARRIER_COUNT}+ carriers
• AI-powered pricing that tracks market trends daily
• Direct communication — no call center, you deal with me

Here's a sample of current rates on your trade lane:

{MINI_RATE_TABLE_TOP3}

I'd love to understand your shipping needs better. What routes and volumes are you looking at?
---
```

### Email 2: Social Proof + Market Insight (Day 4)
```
Subject: "How {INDUSTRY} importers save on {ROUTE} freight"
Preview: "Market trend: {TREND_DIRECTION} — what it means for you"

Body:
---
Hi {FIRST_NAME},

Quick market update — {POL}→US rates are currently {TREND_DIRECTION} ({TREND_PCT}% this month).

{IF_FALLING}This means it's a buyer's market. Multiple carriers are competing for your business.{/IF_FALLING}
{IF_RISING}This means locking rates early saves money. Carriers are adjusting pricing upward.{/IF_RISING}
{IF_STABLE}This means predictable costs for your supply chain planning.{/IF_STABLE}

We currently work with importers in {INDUSTRY} who ship {COMMODITY} regularly on this lane. They value our:
• Rate alerts when prices shift significantly
• Booking confirmations within 2 hours
• Proactive tracking updates

Would a rate comparison for your specific routes be helpful?
---
```

### Email 3: Specific Value (Day 10)
```
Subject: "Saved ${SAVINGS_EXAMPLE} on {ROUTE} — here's how"
Preview: "FIX vs FAK rate comparison for your lane"

Body:
---
Hi {FIRST_NAME},

Did you know there are multiple rate types on the same route?

{RATE_TYPE_COMPARISON_TABLE}
  Lane      | FAK Rate  | FIX Rate  | Savings
  {ROUTE_1} | ${FAK_1}  | ${FIX_1}  | ${DIFF_1}
  {ROUTE_2} | ${FAK_2}  | ${FIX_2}  | ${DIFF_2}

{IF_FIX_ADVANTAGE}
Right now, FIX contract rates are ${AVG_SAVINGS} cheaper than spot (FAK) on {LANE}. If you ship regularly, a contract rate could save you significantly over the quarter.
{/IF_FIX_ADVANTAGE}

Happy to run a detailed cost analysis based on your actual shipping volume. Just reply with your typical monthly TEU count.
---
```

### Email 4: Soft Close (Day 18)
```
Subject: "Still looking for {ROUTE} freight rates?"
Preview: "Updated rates + a standing offer"

Body:
---
Hi {FIRST_NAME},

I wanted to share updated rates before they change:

{RATE_TABLE}

No pressure — I know timing matters in freight. I'll continue sending weekly rate updates so you always have current pricing when you need it.

When you're ready to ship, just reply to any of my emails. I typically confirm bookings within 2 hours.
---
```

---

## Type 4: Re-engagement (Silent 30+ days — 3 emails / 2 weeks)

### Email 1: Soft Touch (Day 0)
```
Subject: "Rates have changed since we last spoke — {ROUTE} update"
Preview: "{TREND_DIRECTION} {TREND_PCT}% since your last quote"

Body:
---
Hi {FIRST_NAME},

It's been a while — I wanted to share how rates have moved since we last connected:

  {ROUTE}: ${CURRENT_RATE} (was ${LAST_QUOTED_RATE} — {CHANGE_DIRECTION} {CHANGE_PCT}%)

{IF_CHEAPER}Good news — rates are lower than your last quote. Might be worth revisiting.{/IF_CHEAPER}
{IF_MORE_EXPENSIVE}Rates have gone up, but I can still find competitive options from multiple carriers.{/IF_MORE_EXPENSIVE}

Current best offers:

{MINI_RATE_TABLE_TOP3}

Any upcoming shipments I can help with?
---
```

### Email 2: Value Reminder (Day 5)
```
Subject: "3 things that changed in {POL}→US freight"
Preview: "Market update + new carrier options"

Body:
---
Hi {FIRST_NAME},

A few things have changed on the {POL}→US trade lane:

1. {MARKET_CHANGE_1} (e.g., "CMA CGM launched a new direct service to East Coast")
2. {MARKET_CHANGE_2} (e.g., "Average transit times improved by 2 days")
3. {MARKET_CHANGE_3} (e.g., "FIX rates are 12% cheaper than spot this month")

Want me to run a fresh rate comparison for your routes?
---
```

### Email 3: Final Touch (Day 12)
```
Subject: "Your freight rates — whenever you need them"
Preview: "Standing offer from Nelson at Pudong Prime"

Body:
---
Hi {FIRST_NAME},

Just a quick note — I'll keep sending weekly rate updates so you always have current pricing.

This week's snapshot:

  Best 40HQ to US West Coast: ${WC_RATE} ({CARRIER_WC})
  Best 40HQ to US East Coast: ${EC_RATE} ({CARRIER_EC})

No commitment needed. When the timing is right, just reply to any email and I'll handle the rest.
---
```

---

## Dynamic Content Engine — Implementation

### content_engine.py (NEW)
```python
"""
Generates dynamic email content blocks based on market data.
Called by GUI before email send.
"""
from intelligence.rate_predictor import RatePredictor
from intelligence.anomaly_detector import AnomalyDetector
from email_engine.core.auto_rate_builder import query_best_rates

class EmailContentEngine:
    
    def __init__(self):
        self.predictor = RatePredictor()
        self.detector = AnomalyDetector()
    
    def get_market_condition(self, routes: list[str]) -> str:
        """Detect FALLING/RISING/STABLE for template selection"""
        predictions = [self.predictor.predict(r) for r in routes]
        avg_trend = mean([p["trend_pct"] for p in predictions])
        if avg_trend < -3: return "FALLING"
        elif avg_trend > 3: return "RISING"
        return "STABLE"
    
    def build_email_body(self, customer: dict, template_type: str) -> str:
        """Build complete HTML body (no signature) with dynamic data"""
        rates = query_best_rates(customer["POL"], customer["destinations"])
        prediction = self.predictor.predict(customer["primary_route"])
        anomalies = self.detector.check_rates(rates)
        
        # Select template variant based on market condition
        condition = self.get_market_condition(customer["routes"])
        template = self.select_template(template_type, condition)
        
        # Fill template with real data
        return template.render(
            FIRST_NAME=customer["name"],
            RATE_TABLE=rates["html"],
            TREND_PCT=prediction["trend_pct"],
            TREND_DIRECTION=prediction["trend"],
            PREDICTED_RATE=prediction["predicted_rate"],
            CONFIDENCE=prediction["confidence"],
            BEST_CARRIER=rates["best_carrier"],
            BEST_RATE=rates["best_rate"],
            ANOMALIES=anomalies,
            # ... more vars
        )
    
    def should_send_alert(self, route: str) -> tuple[bool, str]:
        """Check if market alert should trigger"""
        prediction = self.predictor.predict(route)
        if abs(prediction["trend_pct"]) > 8:
            return True, "TREND_SHIFT"
        # Check anomalies on route
        anomaly = self.detector.check_route(route)
        if anomaly and anomaly.severity == "critical":
            return True, "PRICE_DROP"
        return False, None
```

### Subject Line Rotation — Enhanced
```python
SUBJECT_TEMPLATES = {
    "weekly_blast": {
        "FALLING": [
            "Rates dropping on {ROUTE} — lock in before rebound",
            "{CARRIER} cuts {ROUTE} rates — W{WEEK} update",
            "Good news: {POL}→US rates down {TREND_PCT}%",
        ],
        "RISING": [
            "Transpacific rates climbing — offers valid through {EXP}",
            "{POL}→US rates up {TREND_PCT}% — W{WEEK} pricing inside",
            "Rate increase alert: best available before {EXP_DATE}",
        ],
        "STABLE": [
            "Vietnam→US rates stable — W{WEEK} competitive pricing",
            "Your weekly freight update — best rates from {N} carriers",
            "Transpacific market steady — current offers inside",
        ],
    },
    "market_alert": [
        "Alert: {CARRIER} drops {ROUTE} by {PCT}% — limited",
        "Market shift: {ROUTE} rates {DIRECTION} {PCT}%",
    ],
    "nurture": [...],
    "re_engage": [...],
}
```

---

## GUI Integration (vao email-dashboard-v3)

### New Features for Quick Send tab:
1. **Market Condition Badge** — Show "FALLING/RISING/STABLE" with color next to campaign dropdown
2. **Template Preview** — Auto-select template variant based on market condition
3. **AI Insights Panel** — Show forecast summary before send:
   - "Trend: Falling -2.5% | Confidence: Medium | Forecast: $3,720 next week"
4. **Alert Queue** — Separate section for market alerts waiting to send

### New Tab: Market Intelligence
- Live forecast chart (8-week trend per route)
- Anomaly alerts feed
- FIX vs FAK comparison table
- "Generate Alert Email" button when anomaly detected

---

## Performance Benchmarks (Freight Industry)

| Metric | Weekly Blast | Market Alert | Lead Nurture | Re-engage |
|--------|-------------|--------------|--------------|-----------|
| Open rate | 25-35% | 40-55% | 30-45% | 15-25% |
| Reply rate | 3-5% | 8-12% | 5-8% | 2-4% |
| Booking conversion | 2-4% | 5-10% | 3-6% | 1-3% |
| Unsubscribe | <0.3% | <0.2% | <0.5% | 1-2% |

**Key insight:** Market Alert emails convert 2-3x better than regular blasts because content is TIME-SENSITIVE and DATA-DRIVEN (not generic marketing).

---

## Implementation Phases

### Phase 1: Template Engine (can lam truoc)
- [ ] Create `email_engine/core/content_engine.py`
- [ ] Define 4 template types with dynamic variables
- [ ] Wire rate_predictor + anomaly_detector into content engine
- [ ] Subject line rotation based on market condition

### Phase 2: GUI Integration
- [ ] Add market condition badge to Quick Send
- [ ] Template variant auto-selection
- [ ] AI insights panel (forecast + anomalies)
- [ ] Preview email with real dynamic data before send

### Phase 3: Alert Automation
- [ ] Market alert trigger logic (anomaly + trend shift)
- [ ] Alert queue in GUI
- [ ] One-click send alert to relevant customers
- [ ] Cooldown: max 1 alert per customer per week

### Phase 4: Nurture + Re-engage Sequences
- [ ] Sequence state machine (track where each customer is)
- [ ] Auto-advance based on email_log.csv events
- [ ] Exit conditions (replied, bounced, converted)
- [ ] Re-entry rules (silent 30+ days after last nurture)

---

## Key Files

| File | Purpose | Status |
|------|---------|--------|
| `email_engine/core/content_engine.py` | Dynamic content generation | NEW |
| `email_engine/core/auto_rate_builder.py` | Rate query from parquet | EXISTS — extend |
| `intelligence/rate_predictor.py` | AI trend/forecast | EXISTS — wire in |
| `intelligence/anomaly_detector.py` | Market anomaly detection | EXISTS — wire in |
| `email_engine/gui/views/auto_rate_view.py` | GUI rate & send | EXISTS — enhance |
| `email_engine/assets/email_template.html` | Base template | EMPTY — populate |
| `plans/email-sequence-ai-forecast/plan.md` | This plan | NEW |

---

## Verification Criteria

1. Weekly blast: market condition detected correctly, right template variant selected
2. Subject line: contains real trend data (not placeholder)
3. Rate table: shows current parquet rates with markup applied
4. AI insights: forecast visible in GUI before send
5. Market alert: triggers when anomaly detected, sends to relevant customers only
6. No signature in email body — Outlook appends automatically
7. Cooldown: same customer not emailed twice within 7 days
