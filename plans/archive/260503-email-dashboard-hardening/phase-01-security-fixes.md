# Phase 1: Security Fixes

## Overview
Fix critical XSS vulnerabilities and security gaps in `email-dashboard.html` (frontend) and `web_server.py` (backend) before production deployment.

## Requirements
- Functional: `esc()` must escape all HTML special characters including single quote
- Functional: Remove all inline `onclick` handlers using template interpolation
- Functional: Add CSP meta tag to HTML
- Functional: Backend must distinguish error types (401/403/500) vs silent `.catch(() => [])`
- Non-functional: No breaking changes to existing API contracts

## Architecture
**Frontend (`email-dashboard.html`):**
- Fix `esc()`: add `'` → `&apos;` mapping
- Replace all `${}` inside `onclick` attributes with `data-*` + event delegation pattern
- Add CSP meta tag: `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' http://localhost:*">`
- Add `aria-live` region for toast notifications

**Backend (`web_server.py`):**
- Replace all `.catch(() => [])` with typed error handling
- Add retry logic for transient failures (3 retries, exponential backoff)
- Add `aria-live` support on backend is N/A — done in frontend

## Related Code Files
- Modify: `plans/visuals/email-dashboard.html` (esc function, inline handlers, CSP)
- Modify: `email_engine/web_server.py` (async error handling)

## Implementation Steps

### 1. Fix `esc()` function — add single quote escape
```javascript
// OLD (line 1499):
function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// NEW:
function esc(s) {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');  // Prevent ' used in onclick attributes
}
```

### 2. Replace inline `onclick` handlers — event delegation
- Find all `onclick="${...}"` in template strings (campaign rendering, prospect rendering)
- Replace with: `data-campaign="${esc(c.name)}"` on parent element + single delegated event listener at top of script
- Pattern:
```javascript
// OLD:
`<div class="campaign-card" onclick="selectCampaign('${esc(c.name)}')">`

// NEW:
`<div class="campaign-card" data-campaign="${esc(c.name)}">`
// + in JS:
document.getElementById('campaignGrid').addEventListener('click', e => {
  const card = e.target.closest('.campaign-card');
  if (card) selectCampaign(card.dataset.campaign);
});
```

### 3. Add CSP meta tag
Add as first child of `<head>` in `email-dashboard.html`:
```html
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self' http://localhost:*">
```

### 4. Add toast ARIA live region
```html
<div id="toastRegion" aria-live="polite" aria-atomic="true" style="position:fixed;bottom:24px;right:24px;z-index:100"></div>
```
Update `toast()` function to inject into `#toastRegion` instead of `document.body`.

### 5. Backend — distinguish error types in API calls
```javascript
// OLD (in loadSendView):
const [campaigns, stats, opens] = await Promise.all([
  api('/api/campaigns').catch(() => []),
  api('/api/history/stats').catch(() => null),
  api('/api/email-rate/analytics/opens?days=7').catch(() => null),
]);

// NEW — add retry for network errors:
async function apiWithRetry(path, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const r = await fetch(API + path);
      if (!r.ok) {
        if (r.status === 401 || r.status === 403) throw new Error(`Auth error ${r.status}`);
        if (r.status >= 500) throw new Error(`Server error ${r.status}`);
        return { ok: false, status: r.status, data: null };
      }
      return { ok: true, data: await r.json() };
    } catch (e) {
      if (i === retries - 1) throw e;
      await new Promise(r => setTimeout(r, 500 * Math.pow(2, i)));
    }
  }
}
```

## Success Criteria
- [ ] `esc()` escapes single quote — verify with `esc("O'Brien")` → `O&#39;Brien`
- [ ] Zero inline `onclick="${...}"` in template HTML (grep for `onclick="\$\{`)
- [ ] CSP meta tag present and allows Google Fonts
- [ ] Toast notifications announced via ARIA live region
- [ ] Backend API errors show user-visible error (not silently swallowed)
- [ ] No XSS possible via campaign name, prospect email, or any user-controlled field