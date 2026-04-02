# 📋 Output Templates — Nelson Freight System

## Template 1: Quick Quote (Telegram — CHUẨN BẮT BUỘC)

```
📊 [POL] → [PLACE] | [Customer Tag]
━━━━━━━━━━━━━━━━━━━━
#  Carrier  20GP    40HQ   Transit  Free  Note
1. YML     $1,846  $3,150  35 days  14d   SOC
2. CMA     $2,100  $3,280  28 days  21d   DIRECT
3. ONE     $2,250  $3,400  30 days  14d   COC

💡 Tip: [Consultative selling note]
⚠️  Risk: [Weight/Space alert nếu có]
```

**Ghi chú format:**
- Carrier: uppercase code (YML/CMA/ONE)
- Price: USD với $ prefix, làm tròn đến đơn vị
- Transit: số days, ví dụ "35 days"
- Free: freetime ngày, ví dụ "14d" / "21d"
- Note: SOC / COC / DIRECT / VIA [PORT]

---

## Template 2: Freetime Answer

```
🕐 Freetime — [CARRIER]
━━━━━━━━━━━━━━━━━━━━
📦 Destination Free:    [X] days
📋 Demurrage after:     $[Y]/day
🚛 Detention:           [X] days free, $[Y]/day after

💡 Tip: [Tips về cách tận dụng freetime]
```

---

## Template 3: Customer Profile Summary

```
👤 [CUSTOMER CODE] — Profile
━━━━━━━━━━━━━━━━━━━━
📍 Preferred lanes: [POL] → [PLACES]
📦 Commodity: [TYPE]
📊 Behavior: [TAGS]
📈 Win Rate: [X]% | Avg Quote → Close: [N] days

📋 Recent quotes:
• [DATE] [CARRIER] [PLACE] [STATUS] [PRICE]
• ...
```

---

## Template 4: Consultative Selling Notes

**Dùng khi nào:**

| Tình huống | Note để thêm |
|------------|-------------|
| Khách price sensitive | "Đây là giá tốt nhất tuần này. Space đang siết dần." |
| Khách hay delay | "Nếu chờ tuần sau có thể tăng $50-100/cont." |
| Space tight | "⚠️ Carrier X đang siết space HPH tuyến này. Khuyến cáo book sớm." |
| Khách volume lớn (HML) | "Volume lớn → có thể negotiate long-term rate với MSK/CMA để lock giá ổn định." |
| SOC carrier | "ONE/YML có SOC — phù hợp nếu KH có container riêng, freetime linh hoạt hơn." |

---

## Template 5: Weekly Report

```
📊 NELSON FREIGHT — WEEKLY REPORT W[XX] [YYYY]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 SECTION A: Sales Performance
• Quotes: [N] | Wins: [N] ([X]%) | Losses: [N]
• Revenue MTD: $[X] / Target $[Y] ([Z]%)

🌊 SECTION B: Market Trend  
• [Lane]: [UP/DOWN/STABLE] [notes]

⚠️ SECTION C: Active Risks
• [Risk items]

✅ SECTION D: Action Plan
1. [Action — owner — deadline]
```

---

## Template 6: Risk Alert

```
⚠️ CẢNH BÁO RỦI RO — [TYPE]
━━━━━━━━━━━━━━━━━━━━
📋 Vấn đề: [mô tả]
🎯 Ảnh hưởng: [chi phí/timeline/customer]
✅ Khuyến nghị: [action cụ thể]
⏰ Deadline: [nếu có]
```
