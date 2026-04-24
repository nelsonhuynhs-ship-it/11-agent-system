# Phase 5B — WhatsApp PRODUCTION

**Status:** PENDING (requires Phase 5A GO decision)
**Effort:** 4h
**Cost:** $20/month hard cap
**Depends on:** Phase 5A success

## Overview

Upgrade từ SANDBOX 5 test contact → production unlimited (cap $20/tháng). Add số DN thật, BUDGET GUARD hard cap, quality monitor.

## Nelson preparation

1. Business Settings → Add Phone Number → số Pudong Prime DN
2. Display Name review (Meta 1-3 ngày) → "Pudong Prime"
3. Billing → Add payment method (thẻ visa quốc tế)
4. Nạp $20 credit đầu tiên
5. Confirm với em → switch mode

## Files to create

- `email_engine/core/wa_budget_guard.py` — hard cap logic
- `email_engine/core/wa_quality_monitor.py` — check rating periodically

## Files to update

- `wa_sender.py` — switch SANDBOX ↔ PRODUCTION mode
- Tab 6 UI — BUDGET GUARD widget + quality indicator

## BUDGET GUARD logic

```python
# Before every send:
current_month_cost = sum(costs for msgs this month)
daily_cost         = sum(costs today)

if current_month_cost >= 20.00:
    → HARD STOP until month rollover
    → alert Telegram
elif current_month_cost >= 18.00:  # 90%
    → pause batch, alert Telegram "Còn $2 budget"
elif daily_cost >= 0.60:  # ~20 tin VN
    → pause until tomorrow

# Message pricing (current Apr 2026):
VN marketing    = $0.038
US marketing    = $0.025
IN marketing    = $0.012
Service reply   = $0.00 (first 1000/month)
```

## Smart queue priority (tiết kiệm budget)

```
Priority order when sending 20 msgs/day:
1. TIER=HOT + has_WA + US destination  (cheaper, higher value)
2. TIER=HOT + has_WA + VN origin
3. TIER=WARM + has_WA + replied before
4. TIER=WARM + has_WA (cooldown 14d)
5. Skip COLD tier until more budget
```

## Implementation steps

1. `wa_budget_guard.py` — cost calculator + pre-send check (1h)
2. `wa_quality_monitor.py` — Meta quality API poll every 1h (0.5h)
3. Update `wa_sender.py` PRODUCTION mode + budget integration (1h)
4. BUDGET GUARD widget UI (1h)
5. Smart queue implementation (0.5h)

## Todo checklist

- [ ] Nelson nạp $20 credit Meta billing
- [ ] Display Name "Pudong Prime" verified
- [ ] Dashboard toggle SANDBOX → PRODUCTION
- [ ] BUDGET GUARD blocks send at $20
- [ ] Daily cap 20 tin enforced
- [ ] Telegram alert when reach 90%
- [ ] Quality monitor polls + auto-pause on YELLOW
- [ ] Smart queue picks TIER=HOT first
- [ ] Dashboard shows real-time cost counter

## Success criteria

- First month: ~500 tin sent, $20 exactly (not $20.01)
- Quality rating stays GREEN
- 75+ conversations generated
- Zero unexpected charges

## Risk assessment

| Risk | Mitigation |
|---|---|
| Cost overrun | Hard cap pre-send check + daily cap + 90% pause |
| Quality drops YELLOW | Auto-pause + investigate before resume |
| Messaging tier downgrade | Monitor weekly, reduce send if flagged |
| Meta suspend account | Follow policy strictly — opt-out, consent, relevant content |

## Review milestone (end month 1)

- Check: $20 spent exactly, 75+ conversations, 1+ HĐ ký
- If yes → consider raising cap to $30-50
- If no → debug (template quality? audience? timing?)
