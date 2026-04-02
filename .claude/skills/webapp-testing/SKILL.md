---
name: webapp-testing
description: >
  Toolkit for interacting with and testing local web applications using Playwright.
  Supports verifying frontend functionality, debugging UI behavior, capturing browser
  screenshots, and viewing browser logs. TRIGGER khi: test WebApp Nelson, verify
  Next.js dashboard UI, debug frontend issues.
---

# WebApp Testing Skill

> **Source:** Adapted from Vercel webapp-testing skill pattern
> **Applied to:** Nelson WebApp Dashboard testing (Sprint 13-14+)
> **Tool:** Playwright (browser automation)

---

## 🚀 Quick Start — Test Nelson WebApp

### Setup
```bash
# Install Playwright
pip install playwright  # Python
# or
pnpm add -D @playwright/test  # Node.js

# Install browser
playwright install chromium
```

### Basic test structure
```python
# tests/test_dashboard.py
from playwright.sync_api import sync_playwright

def test_rate_lookup():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Navigate to WebApp
        page.goto("http://localhost:3000/dashboard/rates")

        # Test rate search
        page.fill('[data-testid="pol-input"]', 'HPH')
        page.fill('[data-testid="place-input"]', 'Denver')
        page.click('[data-testid="search-button"]')

        # Verify results
        page.wait_for_selector('[data-testid="rate-table"]')
        rows = page.locator('[data-testid="rate-row"]').count()
        assert rows > 0, "Rate table should have results"

        browser.close()
```

---

## 📋 Test Scenarios cho Nelson System

### Sprint 13-14 — WebApp MVP Tests

| Test | Priority | Description |
|------|----------|-------------|
| Login flow | 🔴 MUST | Supabase auth → redirect to dashboard |
| Rate lookup | 🔴 MUST | POL + Place → Top 3 results hiển thị đúng |
| Quote creation | 🔴 MUST | Form submit → quote saved → confirmation |
| KPI dashboard | 🟡 SHOULD | Charts render, numbers = SQLite/PostgreSQL data |
| Role access | 🟡 SHOULD | Sales user không thấy admin pages |
| Mobile responsive | 🟢 NICE | Dashboard usable trên mobile |

### Regression Tests (chạy sau mỗi deploy)
```python
CRITICAL_PATHS = [
    "/",                    # Landing/login
    "/dashboard",           # KPI overview
    "/dashboard/rates",     # Rate lookup
    "/dashboard/quotes",    # Quote management
]
```

---

## 🔍 Debug Tools

### Screenshot on failure
```python
def test_with_screenshot():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto("http://localhost:3000/dashboard")
            # ... test steps
        except Exception as e:
            # Screenshot for debugging
            page.screenshot(path=f"debug_{datetime.now().strftime('%H%M%S')}.png")
            raise
        finally:
            browser.close()
```

### Browser console logs
```python
# Capture console errors
errors = []
page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
page.goto("http://localhost:3000/dashboard")
if errors:
    print("Console errors:", errors)
```

---

## ✅ Pre-Deploy Checklist (WebApp)

Chạy trước mỗi production deploy:
- [ ] Login với admin account → dashboard load OK
- [ ] Login với sales account → admin pages bị block
- [ ] Rate lookup HPH + Denver → có kết quả
- [ ] Create quote → lưu vào database
- [ ] KPI charts render không có JS errors
- [ ] Mobile viewport (375px) → không bị layout break

---

## 🔗 References
- **Playwright docs:** https://playwright.dev/docs/intro
- **Nelson WebApp plan:** skill `webapp-scalable`
- **Test environment:** `http://localhost:3000` (dev) | WebApp production URL (prod)