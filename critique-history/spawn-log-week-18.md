[mm-claude] model=MiniMax-M2.7


## Fact / Tình hình

- **26,149 LOC** Python across api/ + email_engine/core/ (confirmed via wc -l)
- **85,276 rows** pricing parquet (Cleaned_Master_History.parquet)
- **585 rows** email_log.csv — manual read only, no dashboard
- **0 test files** in email_engine/ confirmed (tests/ folder has no pytest files)
- **Week 18 stale**: 4/7 items marked "shipped" but git evidence thin

## Option

- **A**: Proceed with 3 upgrade proposals as new (archival policy, observability, pytest) — effort 2-3h each
- **B**: Flag verification blockers first (git log + grep Graph API), then approve proposals

## Recommend

**B for weak items, A for strong ones** — Pytest + Bot VPS systemd + Graph API migration need ship verification before Week 19 stale propagation.

## Hỏi

**Xác nhận hay defer 3 proposal mới (archival, observability, pytest)?**

- **Confirm** → dispatch to MiniMax M2.7
- **Defer** → mark pending Week 20

---

📄 Full report: `D:/OneDrive/NelsonData/reports/2026-05-02/self-critique-week-18.html`  
🔗 Tailscale: `https://laptop-no6f8ibp.tail82dc4e.ts.net/2026-05-02/self-critique-week-18.html`
