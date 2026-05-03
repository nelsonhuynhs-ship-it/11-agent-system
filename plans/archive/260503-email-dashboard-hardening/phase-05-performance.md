# Phase 5: Performance

## Overview
Optimize frontend rendering performance for large tables (200+ rows), add chart data lazy-loading, debounce search, and add backend query optimization for contact lookups.

## Requirements
- Functional: Contact table renders max 50 visible rows (virtual scroll or pagination)
- Functional: Search input debounced 300ms before filtering
- Functional: Bar chart data loads on tab activation, not on page load
- Functional: Backend `/api/contacts` endpoint supports pagination (page + page_size params)
- Functional: Backend `/api/send-stats` cache TTL is configurable via env var
- Non-functional: LCP < 2.5s on mobile, no jank during table scroll

## Architecture

### Frontend Performance

**1. Contact table — pagination (not virtual scroll, simpler)**
Add pagination controls to contacts table:
```html
<!-- Change pagination stub to real controls -->
<div style="margin-top:16px;display:flex;gap:12px;align-items:center">
  <button class="btn btn-sm" id="prevPage" onclick="prevContactsPage()">← Prev</button>
  <span id="pageInfo" style="font-size:12px;color:var(--muted)">Page 1 of 50</span>
  <button class="btn btn-sm" id="nextPage" onclick="nextContactsPage()">Next →</button>
</div>
```
JS: maintain `contactsPage` state, slice `Store.prospects` before render.

**2. Debounce search**
```javascript
let searchDebounce;
document.getElementById('searchRecip').addEventListener('input', e => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(() => renderProspects(), 300);
});
```

**3. Lazy-load chart data on tab activation**
```javascript
// In nav click handler for viewInsights:
if (viewId === 'viewInsights' && !window._insightsLoaded) {
  window._insightsLoaded = true;
  loadInsightsData();  // fetch from /api/analytics/campaign-stats etc.
}
```

**4. Table row hover — use `:hover` only on `tr`**
```css
/* Current (expensive — repaints all td children): */
.contacts-table tr:hover td { background: var(--paper-2) }

/* Optimized (single paint): */
.contacts-table tr:hover { background: var(--paper-2) }
.contacts-table tr:hover td { background: inherit } /* reset children */
```

**5. `will-change` for animated elements**
```css
.sequence-card { will-change: transform; }
.bar { will-change: height; }
```

### Backend Performance

**6. Add pagination to `/api/contacts`**
```python
@router.get("/api/contacts")
def get_contacts(
    campaign: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
):
    # ... existing filtering logic ...
    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "contacts": results[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
```

**7. Add pagination to `/api/campaigns`**
Already returns all data — frontend should paginate. Not critical.

**8. Verify `intel/events.db` query is indexed**
Check `intel/events.py` — ensure queries on `timestamp` and `event_type` use indexes.

## Related Code Files
- Modify: `plans/visuals/email-dashboard.html`
- Modify: `email_engine/web_server.py` (contacts endpoint)
- Check: `email_engine/intel/events.py`

## Implementation Steps

### 1. Implement real pagination for contacts table
Add `contactsPage` and `contactsPageSize` to `Store`, slice results in render:
```javascript
const pageSize = 50;
const start = (contactsPage - 1) * pageSize;
const end = start + pageSize;
const pageItems = filteredContacts.slice(start, end);
// render pageItems
```

### 2. Debounce search input
Add debounce timeout to `searchRecip` input listener. Clear on each keystroke, apply after 300ms idle.

### 3. Lazy-load insights data
Track `window._insightsLoaded` flag. On `viewInsights` tab activation, fetch campaign comparison data from `/api/analytics/campaign-stats`. Show skeleton loader while fetching.

### 4. Optimize table hover CSS
Replace `tr:hover td{background}` with `tr:hover{background}` and reset `td` to `inherit`.

### 5. Add `will-change` to animated elements
Add `will-change: transform` to `.sequence-card`, `.campaign-card` and `will-change: height` to `.bar`.

### 6. Add pagination to `/api/contacts` backend
Add `page` and `page_size` query params. Return total + page metadata.

### 7. Make `_SEND_STATS_TTL_SECONDS` configurable
```python
_SEND_STATS_TTL_SECONDS = int(os.environ.get("SEND_STATS_CACHE_TTL_SECONDS", 15))
```

## Success Criteria
- [ ] Contact table renders max 50 rows in DOM (pagination working)
- [ ] Search input filters after 300ms debounce (not on every keystroke)
- [ ] Insights charts load only when Insights tab is first activated
- [ ] Table hover is single-element repaint (not full row children)
- [ ] `/api/contacts` returns `page`, `page_size`, `total`, `total_pages`
- [ ] `will-change` applied to sequence-card and bar elements
- [ ] `SEND_STATS_CACHE_TTL_SECONDS` env var overrides default 15s