---
phase: 4
status: done
priority: MEDIUM
effort: ~2h
blockedBy: [phase-03]
blocks: [phase-05]
completed: 2026-04-24
---

# Phase 04 — HTML Template Update (Side-by-Side + Theme + Inland Styling)

## Context Links
- **Design:** `plans/reports/rate-table-v2-design-20260424.md` §3.D5
- **Visual reference:** `plans/visuals/rate-table-v2-preview.html` ✅ approved
- **Plan overview:** [plan.md](plan.md)
- **Predecessor:** [phase-03-gateway-routing.md](phase-03-gateway-routing.md)

## Overview
**Priority:** 🟢 MEDIUM (visual only, không affect rate logic)
**Effort:** ~2h
**Status:** ⏳ Pending (blocked by Phase 3)

Port approved HTML design từ visual preview vào actual email renderer. Side-by-side HPH/HCM, green/blue theme, inland POD styling với badge + city subtitle.

## Key Insights
- Visual preview đã approved — copy CSS + HTML structure as-is
- Outlook desktop compat: dùng `<table>` + inline styles, không dùng flexbox/grid
- Media query cho mobile stack vertical (< 600px)
- Template data binding: rate rows từ Phase 2/3 output → loop render

## Requirements

### Functional
1. Email renders HPH + HCM tables side-by-side khi POL cả hai
2. Chỉ 1 POL → render 1 table full-width (không dummy empty side)
3. Inland POD (USATL/USCHI/USDAL/USDEN) hiện blue tint + border-left + city subtitle + RIPI/IPI badge
4. `BEST` badge cho row 1, `SCFI 7d` badge cho rows có `rate_type="SCFI"`
5. Meta line format: `"{rate_type} · {suffix_label}{' · to ' + exp_date}"`

### Non-functional
- HTML output < 50KB for 10 POD × 2 POL × 3 carriers = 60 rate cells
- Outlook 2016/2019/365 desktop render OK
- Outlook Web + Gmail render OK
- Mobile < 600px stack vertical (no horizontal scroll)

## Architecture

Template renderer location varies by codebase — need scout:
- Likely `email_engine/intelligence/builder.py:build_email()` returns HTML body
- Or separate template file trong `email_engine/templates/`

**Template structure (copy from preview):**
```html
<style> /* inline CSS từ preview */ </style>
<table class="dual-wrap">  <!-- outer wrapper -->
  <tr>
    <td width="50%">  <!-- HPH block -->
      <div class="section-title section-title-hph">...</div>
      <table class="rate rate-hph"> ... </table>
    </td>
    <td width="50%">  <!-- HCM block -->
      <div class="section-title section-title-hcm">...</div>
      <table class="rate rate-hcm"> ... </table>
    </td>
  </tr>
</table>
```

**Row template:**
```python
def render_pod_row(pod_info: dict, rates: list[dict]) -> str:
    """Render 1 <tr> cho 1 POD với up-to-3 carriers."""
    pod_class = "pod-inland" if pod_info["type"] == "inland" else "pod-cell"
    city_span = f'<span class="pod-sub">{pod_info["city"]}</span>' if pod_info["type"] == "inland" or pod_info["code"] == "USTIW" else ""
    badge = ""
    if pod_info["type"] == "inland":
        gateway = pod_info.get("gateway", "IPI")
        badge_class = "badge-ripi" if gateway == "RIPI" else "badge-ipi"
        badge = f'<span class="{badge_class}">{gateway}</span>'

    # Best + 2nd + 3rd
    carrier_cells = "".join(render_carrier_cell(r, is_best=(i==0)) for i, r in enumerate(rates[:3]))

    return f'<tr><td class="{pod_class}">{pod_info["code"]}{badge}{city_span}</td>{carrier_cells}</tr>'
```

## Related Code Files

### Modify
- `email_engine/intelligence/builder.py` or `email_engine/templates/*.py` — template renderer (scout first)
- `email_engine/templates/email_rules.yaml` — add/update `default_cross_sell` template để match 10 POD

### Read for context
- Current email body generation (how HTML được construct)
- Existing CSS conventions

### Reference (copy from)
- `plans/visuals/rate-table-v2-preview.html` — authoritative styling

## Implementation Steps

1. **Scout:** grep để tìm current HTML rendering function
   ```bash
   grep -rn "rate_table\|build_email\|render_" email_engine/intelligence/ email_engine/templates/
   ```
2. **Extract CSS** từ preview vào một string constant trong renderer module
3. **Implement** `render_dual_rate_table(hph_rates, hcm_rates, pod_list)`:
   - Detect 1 POL vs 2 POL mode
   - Single POL → full-width single table
   - Dual POL → side-by-side wrapper
4. **Implement** `render_pod_row()` per spec above
5. **Implement** `render_carrier_cell(rate, is_best)` với BEST/SCFI badges
6. **Update** `email_rules.yaml`:
   ```yaml
   - id: default_cross_sell
     match:
       destinations: [USLAX, USSAV, USNYC, USHOU, USMIA, USTIW, USATL, USCHI, USDAL, USDEN]
       states: [any]
     subject: "Ocean Freight Update — Asia to USA | Week {{week}} | {{suffix}}"
     intro: |
       Dear {{first_name}},
       Please find our latest ocean freight rates for our main US corridors.
       Rates valid through {{earliest_exp}}.
     cta: |
       Please confirm booking 7 days before ETD.
   ```
7. **Render test** — generate 1 sample email, open trong browser, verify layout
8. **Outlook desktop test** — send test email to Nelson's inbox, check render

## Todo List
- [ ] Scout current template renderer location
- [ ] Read current rendering function
- [ ] Extract CSS string từ preview
- [ ] Implement `render_dual_rate_table()` with 1-POL fallback
- [ ] Implement `render_pod_row()` với inland detection
- [ ] Implement `render_carrier_cell()` với BEST/SCFI badges
- [ ] Update `email_rules.yaml` template
- [ ] Sample render → save to `/tmp/sample-render.html` → open browser
- [ ] Send test email to Nelson inbox
- [ ] Verify Outlook desktop render
- [ ] Verify Outlook Web render
- [ ] Verify Gmail render
- [ ] Verify mobile (< 600px) stack
- [ ] Measure HTML size — must be < 50KB
- [ ] Commit: `feat(email-template): side-by-side layout + inland POD styling + color theme`

## Success Criteria
1. ✅ 2 POL email → side-by-side HPH/HCM visible
2. ✅ 1 POL email → full-width single table (no empty right side)
3. ✅ USATL row shows: blue tint + "RIPI" badge + "Atlanta" subtitle + "via CHS" meta
4. ✅ USCHI/USDAL/USDEN rows: blue tint + "IPI" badge + city subtitle
5. ✅ HPH header green theme, HCM header blue theme — distinct
6. ✅ HTML < 50KB for full 10 POD × 2 POL
7. ✅ Outlook desktop + Web + Gmail render correctly
8. ✅ Mobile stacks vertical clean

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Outlook 2016 doesn't support `table-layout: fixed` | Fallback: inline `width=""` attributes on `<col>` |
| HTML size blows up > 50KB | Minify CSS, remove comments, use class names (not inline styles) |
| `@media` query không support Outlook desktop | OK — only needed for mobile client, desktop fixed layout |
| Border-left trick breaks with cell bg override | Test specifically — preview shows working |
| Gmail clips CSS `<style>` | Keep CSS inline OR in `<head>` (Gmail supports `<head>` CSS now) |

## Security Considerations
- HTML escape rate_type, carrier names (XSS defense — low risk but defensive)
- Template inputs từ internal data, not user input — but still escape

## Next Phase
→ Phase 5: Smoke tests — 5 real CNEE sends (1 Quick, 1 Priority, 3 rotation) + regression check.
