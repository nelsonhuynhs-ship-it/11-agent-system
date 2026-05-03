# Phase 2: Accessibility

## Overview
Add ARIA labels, keyboard navigation, focus indicators, and `prefers-reduced-motion` support to `email-dashboard.html` — targeting WCAG 2.1 AA compliance.

## Requirements
- Functional: All interactive elements have `aria-label` or `aria-labelledby`
- Functional: Navigation items keyboard-accessible (Enter/Space)
- Functional: Focus visible on all interactive elements
- Functional: `prefers-reduced-motion` media query disables all animations
- Functional: Color contrast minimum 4.5:1 for all text
- Non-functional: No change to visual appearance except focus indicators

## Architecture
All changes in `email-dashboard.html` only:

**Navigation sidebar:**
- Add `role="navigation"` to `.nav`
- Add `aria-label` to each `.nav-item`
- `tabindex="0"` already implicit on buttons — ensure `.nav-item` is `role="button"` or `<button>`

**Filter tags:**
- Add `role="group"` and `aria-label="Filter contacts"`
- Active filter: `aria-pressed="true"`

**Toggle switches:**
- `input[type="checkbox"]` inside `.toggle-switch` → add `aria-checked="${this.checked}"`

**KPI values:**
- Each `.kpi` → `aria-describedby` pointing to a hidden label describing the metric

**Bar chart:**
- Each `.bar` → `aria-label` with human-readable value: "FLOORING: 1,057 sent, 719 opened, 254 replied, 21 bounced"
- Alternatively: wrap chart in `<figure role="img" aria-label="...">`

**Sequence cards:**
- Add `role="button"` + `aria-label="FLOORING sequence, step 2 of 4, 847 sent"`

**Reduced motion:**
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

**Contrast fixes:**
- `.sidebar-foot` opacity `.3` → `.5`
- `.seq-step.pending` text color → darker or use CSS variable with higher contrast
- Sidebar label `rgba(255,255,255,.4)` → `rgba(255,255,255,.6)`

## Related Code Files
- Modify: `plans/visuals/email-dashboard.html`

## Implementation Steps

### 1. Sidebar navigation — keyboard + ARIA
```html
<nav class="nav" role="navigation" aria-label="Email Dashboard">
  <div class="nav-item" role="button" tabindex="0" data-view="viewSend" aria-label="Send emails">
    <span class="nav-icon">📧</span><span class="nav-label">Send</span>
  </div>
  <!-- repeat for all 9 nav items -->
</nav>
```

### 2. Add `aria-pressed` to filter tags
```html
<div class="filter-tag" role="button" aria-pressed="false">VIP</div>
```
JS: toggle `aria-pressed="true/false"` when clicked.

### 3. Toggle switches — `aria-checked`
```html
<input type="checkbox" id="setFu7" aria-checked="true">
```

### 4. KPI — `aria-describedby`
```html
<div class="kpi" id="kpi-sent" aria-describedby="kpi-sent-label">
  <div id="kpi-sent-label" class="sr-only">Total emails sent this month</div>
  <div class="kpi-label">Total Sent</div>
  <div class="kpi-value" id="kpiSent">—<span class="kpi-unit">emails</span></div>
</div>
```
Add CSS: `.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}`

### 5. Bar chart — accessibility
```html
<div class="bar-chart" role="img" aria-label="Campaign performance: FLOORING 1057 sent 719 opened 254 replied 21 bounced; FURNITURE 745 sent 387 opened 134 replied 12 bounced; PLASTIC 590 sent 284 opened 189 replied 8 bounced; CANDLE 495 sent 40 opened 10 replied 69 bounced">
  <!-- existing bar markup -->
</div>
```

### 6. Sequence cards — `role="button"`
```html
<div class="sequence-card" role="button" tabindex="0" aria-label="FLOORING sequence, Active, 847 sent, 156 replies, 12 bounces">
```

### 7. Add `prefers-reduced-motion` CSS
Add at end of existing `<style>` block:
```css
@media(prefers-reduced-motion:reduce){*,::before,::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
```

### 8. Fix sidebar foot contrast
```css
.sidebar-foot{opacity:.6} /* was .3 */
```

## Success Criteria
- [ ] All 9 nav items have `aria-label` (check: `aria-label` grep)
- [ ] All filter-tags have `aria-pressed` toggled on click
- [ ] Focus ring visible on all buttons, inputs when tabbing (`.btn:focus-visible`, `.filter-tag:focus-visible`)
- [ ] `prefers-reduced-motion` query present and animations disabled
- [ ] Sidebar foot text contrast ratio ≥ 4.5:1
- [ ] `.seq-step.pending` contrast ratio ≥ 4.5:1
- [ ] Bar chart has `role="img"` + `aria-label`