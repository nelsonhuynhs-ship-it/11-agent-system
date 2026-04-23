# Phase 3 — Dashboard Progress UI

**Status:** PENDING
**Effort:** 3h
**File:** `plans/visuals/email-dashboard-v6.html` (ADD only, KHÔNG đổi theme)

## Theme rule tuyệt đối

- Giữ `--paper: #FAF8F5`, `--ink: #1A1A1A`, `--accent: #B8572F`
- Font Inter
- KHÔNG dark color anywhere

## Add to view Quick Send (ngay trên form)

### A. Widget "Today's Plan"

```
┌──────────────────────────────────────────────────────────────┐
│ 📅 2026-04-23 · Vòng 1 · Tuần 2/5.3                           │
├──────────────────────────────────────────────────────────────┤
│ HÔM NAY: 423 / 700   ████████░░ 60%    [▶ Start batch]       │
│                                                              │
│ HÔM QUA: 650 sent · FLOORING 150 · CANDLE 100 · RUBBER 100  │
│                     PLASTIC 100 · FURNITURE 150 · OTHERS 50 │
└──────────────────────────────────────────────────────────────┘
```

HTML skeleton:
```html
<div class="rotation-widget" id="rotationToday">
  <div class="rt-header">
    <span class="rt-date" id="rtDate">—</span> ·
    <span class="rt-cycle" id="rtCycle">Vòng 1 · Tuần —/—</span>
  </div>
  <div class="rt-today-bar">
    <span class="rt-today-label">HÔM NAY: <b id="rtTodaySent">—</b> / <b id="rtTodayTarget">—</b></span>
    <progress id="rtTodayProgress" max="700" value="0"></progress>
    <span id="rtTodayPct">0%</span>
    <button class="btn btn-primary" id="rtStartBatch">▶ Start batch</button>
  </div>
  <div class="rt-yesterday" id="rtYesterday">HÔM QUA: — sent</div>
</div>
```

### B. Widget "Commodity Progress" (vơi dần — cảm giác hiệu quả)

```
┌─ TIẾN ĐỘ VÒNG 1 ─────────────────────────────────────────────┐
│ FLOORING          ██████████░░░░░░░░░░  1,750/4,265 (41%)    │
│ FURNITURE_INDOOR  ████████░░░░░░░░░░░░  1,440/4,044 (36%)    │
│ CANDLE            █████████░░░░░░░░░░░    987/2,187 (45%)    │
│ RUBBER            ██░░░░░░░░░░░░░░░░░░    300/2,584 (12%)    │
│ PLASTIC           █░░░░░░░░░░░░░░░░░░░    150/2,285 ( 7%)    │
│ PLYWOOD           ███████░░░░░░░░░░░░░    400/1,156 (35%)    │
└──────────────────────────────────────────────────────────────┘
```

HTML:
```html
<div class="rotation-progress" id="rotationProgress">
  <h3>Tiến độ Vòng 1</h3>
  <div class="rp-rows" id="rpRows"><!-- filled by JS --></div>
</div>
```

CSS (match v5 theme):
```css
.rotation-widget {
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 20px;
}
.rt-today-bar progress {
  width: 200px;
  height: 12px;
  accent-color: var(--accent);
}
.rp-row {
  display: grid;
  grid-template-columns: 140px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 6px 0;
  font-size: 13.5px;
}
.rp-bar {
  height: 8px;
  background: var(--line);
  border-radius: 4px;
  overflow: hidden;
}
.rp-bar-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s;
}
```

### C. Modal "Adjust Quota"

Click icon ⚙ cạnh "HÔM NAY" → modal với 6 slider:
```
Daily Total: [====o====] 700
FLOORING:    [===o=====] 150
FURNITURE:   [===o=====] 150
CANDLE:      [==o======] 100
RUBBER:      [==o======] 100
PLASTIC:     [==o======] 100
Others:      [==o======] 100

Sum: 700 ✓ (must = Daily Total)
[Cancel] [Save]
```

Save → POST /api/rotation/quota → re-render widgets.

## JS logic

```javascript
async function loadRotationToday() {
  const r = await fetch(`${API}/api/rotation/today`);
  const d = await r.json();
  document.getElementById('rtDate').textContent = d.date;
  document.getElementById('rtCycle').textContent = `Vòng ${d.cycle_number} · Tuần ${d.week_in_cycle}/${d.weeks_to_finish_cycle}`;
  document.getElementById('rtTodaySent').textContent = d.sent_so_far;
  document.getElementById('rtTodayTarget').textContent = d.target;
  document.getElementById('rtTodayProgress').value = d.sent_so_far;
  document.getElementById('rtTodayProgress').max = d.target;
  document.getElementById('rtTodayPct').textContent = Math.round(d.sent_so_far / d.target * 100) + '%';
}

async function loadRotationProgress() {
  const r = await fetch(`${API}/api/rotation/progress`);
  const d = await r.json();
  const rows = d.by_commodity.map(c => `
    <div class="rp-row">
      <span>${c.name}</span>
      <div class="rp-bar"><div class="rp-bar-fill" style="width:${c.pct_done}%"></div></div>
      <span>${c.sent_cycle.toLocaleString()}/${c.total.toLocaleString()} (${c.pct_done}%)</span>
    </div>
  `).join('');
  document.getElementById('rpRows').innerHTML = rows;
}

// Poll mỗi 30s khi tab Send active
setInterval(() => {
  if (currentView === 'viewSend') {
    loadRotationToday();
    loadRotationProgress();
  }
}, 30000);
```

## Implementation steps

1. CSS + HTML skeleton (1h)
2. JS fetch + render (1h)
3. Modal quota adjust (0.5h)
4. Polling + auto-refresh (0.5h)

## Tests manual

- Load dashboard → widget hiện data thật
- Click "▶ Start batch" → POST /api/rotation/run-today → batch kick off
- Chỉnh quota modal → Save → widget update ngay
- Wait 30s → auto-refresh progress

## Success criteria

- Widget render <1s
- Progress bar animate smooth khi số tăng
- Không phá theme trắng cream v5
- Mobile responsive (< 600px)
