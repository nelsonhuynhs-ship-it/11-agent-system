# Phase 3: Frontend Architecture

## Overview
Fix CSS duplications, extract design tokens, fix responsive KPI grid, deduplicate `email-table` definitions, and establish component structure for future maintainability.

## Requirements
- Functional: `email-table` CSS defined once, not twice
- Functional: KPI grid uses `auto-fit minmax(200px, 1fr)` — adapts to 3/4/5 columns
- Functional: Design tokens extracted to CSS variables at `:root`
- Functional: No duplicate `.recipients-panel` / `.panel-header` definitions
- Non-functional: Zero visual changes to existing UI

## Architecture
**CSS deduplication + design tokens:**
Extract spacing/sizing to `:root` variables:
```css
:root {
  /* Space scale */
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 20px; --space-6: 24px; --space-8: 32px; --space-12: 48px;

  /* Type scale */
  --text-xs: 10px; --text-sm: 12px; --text-base: 14px;
  --text-lg: 16px; --text-xl: 18px; --text-2xl: 22px; --text-3xl: 26px;

  /* Border radius */
  --radius-sm: 2px; --radius: 4px; --radius-lg: 8px; --radius-pill: 20px;

  /* Transitions */
  --transition-fast: .15s; --transition: .2s; --transition-slow: .3s;
}
```

**KPI grid fix:**
```css
/* OLD: */
.kpi-row{display:grid;grid-template-columns:repeat(3,1fr)}

/* NEW: */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:0}
```

**CSS deduplication:**
- Find second definition of `.email-table`, `.recipients-panel`, `.panel-header` — remove
- Keep one definition with all properties combined

**Button audit:**
- Enforce `.btn-sm` for table actions (Prev/Next pagination)
- `.btn-primary` for primary CTAs (Import CSV, Save Settings)
- `.btn` (default) for secondary actions
- Add `.btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}`

## Related Code Files
- Modify: `plans/visuals/email-dashboard.html`

## Implementation Steps

### 1. Add design tokens to `:root`
Append to existing `:root` block at line 11 — do not replace existing color variables.

### 2. Fix KPI grid
Replace `repeat(3,1fr)` with `repeat(auto-fit,minmax(200px,1fr))` in `.kpi-row` CSS.

### 3. Deduplicate CSS — find and remove second definitions
Search for duplicate selectors in email-dashboard.html:
```
.recipients-panel → appears twice
.panel-header → appears twice
.email-table → appears twice
```
Keep first definition, ensure it contains all properties from second. Delete second occurrence.

### 4. Button size audit
Audit all buttons in HTML and enforce:
- Pagination: `.btn btn-sm` only
- Primary CTAs: `.btn btn-primary`
- Secondary: `.btn`
- Danger: `.btn btn-danger`
Add focus-visible rule for all `.btn` variants.

### 5. Update existing CSS to use tokens (where already applicable)
This is cleanup only — replace hardcoded values with tokens where found:
- `padding: 12px 24px` → `padding: var(--space-3) var(--space-6)`
- `border-radius: 4px` → `border-radius: var(--radius)`
- `transition: all .2s` → `transition: all var(--transition)`

### 6. Add `.sr-only` utility class
```css
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
```

## Success Criteria
- [ ] `.kpi-row` adapts to 3/4/5 KPIs without breaking (test with 5 KPI elements rendered)
- [ ] `grep 'recipients-panel' email-dashboard.html` returns exactly 2 lines (1 CSS rule + 1 HTML class usage)
- [ ] `.sr-only` utility class defined
- [ ] All buttons have consistent sizing classes
- [ ] No CSS rule appears twice in the file