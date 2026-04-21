#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inject A1 JavaScript into email-dashboard-v5.html before </script>.
Adds: Inbox tab, Insights tab, Settings kill-switch, Data Health,
      Overdue section, CNEE Memory modal, nav routing for new tabs.
"""

HTML_PATH = "D:/NELSON/2. Areas/Engine_test/plans/visuals/email-dashboard-v5.html"

NEW_JS = r"""
/* ═══════════════ A1 — INBOX TAB (unified feed) ═══════════════ */
const IB = { scope: 30, typeFilter: 'all' };

async function loadInbox() {
  const days = IB.scope;
  const el = document.getElementById('ibScopeLabel');
  if (el) el.textContent = days === 1 ? 'last 24h' : `last ${days} days`;

  // Parallel fetch: opens feed + alerts
  let openItems = [], alertItems = [];
  try {
    const [feed, alerts] = await Promise.all([
      api(`/api/opens/feed?days=${days}&limit=100`).catch(() => ({ items: [] })),
      api('/api/email-events/alerts?limit=100').catch(() => ({ alerts: [] })),
    ]);
    openItems = (feed.items || []).map(r => ({
      time: r.opened_at || '', type: 'open',
      cnee: r.cnee_email || '—', subject: r.subject || '',
      id: r.id, open_count: r.open_count || 1,
    }));
    alertItems = (alerts.alerts || alerts || []).map(a => ({
      time: a.time || a.created_at || a.received_at || '',
      type: (a.type || '').toLowerCase().includes('bounc') ? 'bounce'
           : (a.type || '').toLowerCase().includes('auto') ? 'auto'
           : 'reply',
      cnee: a.from || a.sender || '—',
      subject: a.subject || a.snippet || '',
      id: null, open_count: 0,
    }));
  } catch(e) {
    document.getElementById('inboxFeedBody').innerHTML = `<tr><td colspan="5" class="empty-state">${esc(e.message)}</td></tr>`;
    return;
  }

  // Merge + sort by time desc
  let all = [...openItems, ...alertItems];
  all.sort((a, b) => new Date(b.time) - new Date(a.time));

  // KPIs
  const setKpi = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
  setKpi('ibOpens', openItems.length);
  setKpi('ibReplies', alertItems.filter(a => a.type === 'reply').length);
  setKpi('ibBounces', alertItems.filter(a => a.type === 'bounce').length);
  setKpi('ibAuto', alertItems.filter(a => a.type === 'auto').length);
  const badge = document.getElementById('navBadgeInbox');
  if (badge) badge.textContent = all.length || '—';

  // Filter
  if (IB.typeFilter !== 'all') all = all.filter(r => r.type === IB.typeFilter);

  const typeIcon = { open: '👁', reply: '💬', bounce: '⚠', auto: '🤖' };
  const tbody = document.getElementById('inboxFeedBody');
  if (!all.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="empty-state-kanji">無</div>Inbox quiet</td></tr>';
    return;
  }
  tbody.innerHTML = all.slice(0, 200).map(r => {
    const t = (r.time || '').slice(0, 16).replace('T', ' ');
    const icon = typeIcon[r.type] || '?';
    const hot = r.type === 'open' && r.open_count >= 3 ? ' 🔥' : '';
    return `<tr>
      <td class="mono">${esc(t.slice(5))}</td>
      <td><span class="tag">${icon}</span></td>
      <td><div class="email-cell">${esc(r.cnee)}${hot}</div></td>
      <td><div style="font-size:12.5px;color:var(--ink-2)">${esc((r.subject || '').slice(0,80))}</div></td>
      <td style="display:flex;gap:4px;flex-wrap:wrap">
        ${r.type === 'open' && r.id ? `<button class="btn btn-xs" onclick="showOpenTrackerModal('${r.id}')">Preview</button>` : ''}
        <button class="btn btn-xs btn-ghost" data-ot-followup="${esc(r.cnee)}">Follow-up</button>
      </td>
    </tr>`;
  }).join('');
  // Wire follow-up buttons
  tbody.querySelectorAll('[data-ot-followup]').forEach(btn => {
    btn.onclick = async (e) => {
      e.stopPropagation();
      const email = btn.dataset.otFollowup;
      if (!email || !confirm(`Queue personal follow-up to ${email}?`)) return;
      try {
        await api('/api/email-rate/batch/enqueue', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ batch_id: 'IB_' + Date.now(), cnee_emails: [email], campaign_id: '', pol: 'HPH', destinations: '', markup: 20, dry_run: false, test_mode: Store.testMode }),
        });
        toast(`Queued ${email}`, 'success');
      } catch (err) { toast('Queue failed: ' + err.message, 'err'); }
    };
  });
}

function bindInboxControls() {
  // Scope toggle
  document.querySelectorAll('#inboxScopeToggle button[data-ib-scope]').forEach(b => {
    b.onclick = () => {
      IB.scope = parseInt(b.dataset.ibScope, 10);
      document.querySelectorAll('#inboxScopeToggle button').forEach(x => { x.style.background = ''; x.style.color = ''; });
      b.style.background = 'var(--accent)'; b.style.color = '#fff';
      loadInbox();
    };
  });
  // Type filter
  document.querySelectorAll('.ib-type-btn').forEach(b => {
    b.onclick = () => {
      IB.typeFilter = b.dataset.ibType;
      document.querySelectorAll('.ib-type-btn').forEach(x => { x.classList.remove('btn-primary'); x.classList.add('btn-ghost'); });
      b.classList.add('btn-primary'); b.classList.remove('btn-ghost');
      loadInbox();
    };
  });
  // Refresh
  const rb = document.getElementById('btnInboxReload');
  if (rb) rb.onclick = loadInbox;
  // Scan bounce button
  const sb = document.getElementById('btnScanBounce');
  if (sb) sb.onclick = async () => {
    sb.disabled = true; sb.textContent = '⏳ Đang quét...';
    try {
      const r = await api('/api/inbox/scan-bounce', { method: 'POST' });
      const msg = r.status === 'ok'
        ? `Quét xong: ${r.scanned} scanned · ${r.bounces_new} bounces · ${r.replies_new} replies (${r.duration_sec}s)`
        : `Lỗi: ${r.error || 'unknown'}`;
      toast(msg, r.status === 'ok' ? 'success' : 'err', 6000);
      loadInbox();
    } catch(e) { toast('Scan failed: ' + e.message, 'err'); }
    finally { sb.disabled = false; sb.textContent = '🧹 Quét bounce ngay'; }
  };
}

/* ═══════════════ A1 — INSIGHTS TAB ═══════════════ */
async function loadInsights() {
  loadAnalytics();
  loadDataHealth();
  // Load AI accordion status (not expanded by default)
  try {
    const m = await api('/api/model-status');
    const el = document.getElementById('aiTrainedAt');
    if (el) el.textContent = m.trained ? `Trained: ${m.trained_at || '?'}` : 'Not trained';
    const st = document.getElementById('aiStatus');
    if (st) { st.textContent = m.trained ? '● Trained' : '○ Not trained'; st.style.color = m.trained ? 'var(--good)' : 'var(--muted)'; }
    const acc = document.getElementById('aiAcc');
    if (acc) acc.innerHTML = ((m.metrics?.directional_accuracy || 0) * 100).toFixed(1) + '<span class="kpi-unit">%</span>';
    const accSub = document.getElementById('aiAccSub');
    if (accSub) accSub.textContent = `F1 ${(m.metrics?.f1 || 0).toFixed(3)}`;
    const corr = document.getElementById('aiCorr');
    if (corr) corr.textContent = m.corridors || 0;
  } catch(e) { /* silent */ }
  // Load pattern data if A4 is present
  if (typeof loadInsightsPatterns === 'function') { try { loadInsightsPatterns(); } catch(e) {} }
}

async function loadDataHealth() {
  const box = document.getElementById('dataHealthContent');
  if (!box) return;
  box.innerHTML = '<div class="empty-state" style="padding:12px 0"><div class="empty-state-kanji">読</div>Loading...</div>';
  try {
    const d = await api('/api/data-health/v2');
    if (d.error) { box.innerHTML = `<div class="empty-state" style="color:var(--err)">${esc(d.error)}</div>`; return; }
    const pct = (n, t) => t > 0 ? ` (${(n/t*100).toFixed(1)}%)` : '';
    box.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-bottom:16px">
        <div class="kpi"><div class="kpi-label">Total</div><div class="kpi-value" style="font-size:20px">${(d.total||0).toLocaleString()}</div><div class="kpi-foot"><span>${esc(d.source||'—')}</span></div></div>
        <div class="kpi"><div class="kpi-label">Clean %</div><div class="kpi-value" style="font-size:20px;color:var(--good)">${d.clean_pct||0}<span class="kpi-unit">%</span></div><div class="kpi-foot"><span>${(d.clean||0).toLocaleString()} rows</span></div></div>
        <div class="kpi"><div class="kpi-label">Hard bounce</div><div class="kpi-value" style="font-size:20px;color:var(--err)">${d.hard_bounce_pct||0}<span class="kpi-unit">%</span></div><div class="kpi-foot"><span>${(d.hard_bounce||0).toLocaleString()}</span></div></div>
        <div class="kpi"><div class="kpi-label">Soft bounce</div><div class="kpi-value" style="font-size:20px;color:var(--warn)">${(d.soft_bounce||0).toLocaleString()}</div><div class="kpi-foot"><span>suppressed</span></div></div>
        <div class="kpi"><div class="kpi-label">Unsent</div><div class="kpi-value" style="font-size:20px">${d.unsent_pct||0}<span class="kpi-unit">%</span></div><div class="kpi-foot"><span>${(d.unsent||0).toLocaleString()} rows</span></div></div>
      </div>
      ${Object.keys(d.state_distribution||{}).length > 0 ? `
        <div style="margin-bottom:12px">
          <div class="section-sub" style="margin-bottom:8px">STATE distribution (top 15)</div>
          <div style="display:flex;flex-wrap:wrap;gap:6px">
            ${Object.entries(d.state_distribution).slice(0,15).map(([s,c]) =>
              `<span class="tag" style="font-size:11px">${esc(s)}: ${c.toLocaleString()}</span>`
            ).join('')}
          </div>
        </div>` : ''}
      <div style="display:flex;gap:10px;align-items:center;margin-top:12px">
        <button class="btn btn-sm btn-danger" onclick="suppressHardBounce()">🗑 Loại bỏ hard bounce khỏi pool gửi</button>
        <span style="font-size:11.5px;color:var(--muted)">Marks EMAIL_STATUS=SUPPRESSED for all hard bounce rows</span>
      </div>
      ${!d.has_email_status_col ? '<div style="margin-top:8px;color:var(--warn);font-size:12px">⚠ EMAIL_STATUS column missing — run migrate_cnee_add_status_state.py</div>' : ''}
      ${!d.has_state_col ? '<div style="margin-top:4px;color:var(--warn);font-size:12px">⚠ STATE column missing — run migration script with --write</div>' : ''}
    `;
  } catch(e) {
    box.innerHTML = `<div class="empty-state" style="color:var(--err)">${esc(e.message)}</div>`;
  }
}

async function suppressHardBounce() {
  if (!confirm('Mark all HARD_BOUNCE rows as SUPPRESSED in cnee_master? This prevents them from being sent to.')) return;
  toast('Feature pending — suppression via writeback coming soon', 'warn', 4000);
}

/* ═══════════════ A1 — SETTINGS TAB ═══════════════ */
function bindSettingsControls() {
  // Kill switch in Settings
  const ks = document.getElementById('settingsKillStatus');
  const kArm = document.getElementById('settingsBtnKill');
  const kDisarm = document.getElementById('settingsBtnKillClear');
  async function refreshSettingsKill() {
    try {
      const r = await api('/api/email-rate/queue/kill-status');
      const armed = !!(r && r.active);
      if (ks) { ks.textContent = armed ? '🛑 ARMED' : '● Live'; ks.style.color = armed ? 'var(--err)' : 'var(--good)'; }
      if (kArm) kArm.style.display = armed ? 'none' : '';
      if (kDisarm) kDisarm.style.display = armed ? '' : 'none';
    } catch(e) { if (ks) ks.textContent = 'API offline'; }
  }
  if (kArm) kArm.onclick = async () => {
    if (!confirm('ARM kill switch?')) return;
    try { await api('/api/email-rate/queue/kill', { method: 'POST' }); toast('Kill switch ARMED', 'warn', 4000); refreshSettingsKill(); }
    catch(e) { toast('Failed: ' + e.message, 'err'); }
  };
  if (kDisarm) kDisarm.onclick = async () => {
    if (!confirm('DISARM kill switch? Worker will resume.')) return;
    try { await api('/api/email-rate/queue/kill-clear', { method: 'POST' }); toast('Kill switch cleared', 'success'); refreshSettingsKill(); }
    catch(e) { toast('Failed: ' + e.message, 'err'); }
  };
  refreshSettingsKill();
}

/* ═══════════════ A1 — OVERDUE SECTION in Priority ═══════════════ */
function renderOverdueSection(list) {
  const tbody = document.getElementById('overdueBody');
  if (!tbody) return;
  const now = Date.now();
  const overdue = list.filter(p => {
    const d = p.last_sent_date; if (!d || d === 'nan') return true;
    try { return (now - new Date(d).getTime()) / 864e5 >= 7; } catch { return false; }
  });
  document.getElementById('priOverdue').innerHTML = overdue.length + '<span class="kpi-unit">overdue</span>';
  if (!overdue.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="empty-state-kanji">完</div>No overdue — all good</td></tr>';
    return;
  }
  tbody.innerHTML = overdue.map(p => {
    const days = p.last_sent_date ? Math.floor((now - new Date(p.last_sent_date).getTime()) / 864e5) : '?';
    return `<tr data-email="${p.email}">
      <td><div class="company" data-mem="${esc(p.email)}" style="cursor:pointer;text-decoration:underline dotted" title="Click to view memory">${esc(p.pic || p.company || '—')}</div><div class="email-cell">${esc(p.email)}</div></td>
      <td>${p.tier ? `<span class="tag tag-${p.tier.toLowerCase()}">${p.tier}</span>` : '—'}</td>
      <td class="mono">${esc(String(p.last_sent_date || 'never').slice(0, 10))}</td>
      <td class="mono" style="color:var(--err);font-weight:600">${days}d</td>
      <td>${esc(p.campaign || '—')}</td>
      <td style="display:flex;gap:6px;flex-wrap:wrap">
        <button class="btn btn-xs" data-pri-preview="${esc(p.email)}">Preview</button>
        <button class="btn btn-xs btn-accent" data-pri-followup="${esc(p.email)}">Follow up</button>
      </td>
    </tr>`;
  }).join('');
  // Wire preview/followup same as VIP/HOT
  wirePriorityActions();
}

/* ═══════════════ A1 — CNEE MEMORY MODAL ═══════════════ */
async function openMemoryModal(email) {
  if (!email) return;
  const modal = document.getElementById('priMemoryModal');
  const emailEl = document.getElementById('memModalEmail');
  const summaryEl = document.getElementById('memModalSummary');
  const timelineEl = document.getElementById('memModalTimeline');
  if (!modal) return;
  emailEl.textContent = email;
  summaryEl.innerHTML = '<div class="empty-state" style="padding:8px 0">Loading...</div>';
  timelineEl.textContent = '';
  modal.style.display = 'flex';
  try {
    const r = await api(`/api/cnee/memory/${encodeURIComponent(email)}`);
    // Structured summary card
    const s = r.structured || {};
    const pods = (s.preferred_pods || []).join(', ') || '—';
    const carriers = (s.preferred_carriers || []).join(', ') || '—';
    const volume = s.volume_est || '—';
    const intent = s.intent || '—';
    const sentiment = s.sentiment || '—';
    summaryEl.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;font-size:12.5px">
        <div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Preferred POD</div><div class="mono">${esc(pods)}</div></div>
        <div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Preferred Carrier</div><div class="mono">${esc(carriers)}</div></div>
        <div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Volume Est</div><div class="mono">${esc(volume)}</div></div>
        <div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Last Intent</div><div class="mono" style="color:var(--accent)">${esc(intent)}</div></div>
        <div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Sentiment</div><div class="mono">${esc(sentiment)}</div></div>
        <div><div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px">Events</div><div class="mono">${r.event_count || 0} · last ${esc((r.last_event_at || '').slice(0, 10))}</div></div>
      </div>
    `;
    timelineEl.textContent = r.markdown || '(empty vault)';
  } catch(e) {
    if (e.message && e.message.includes('404')) {
      summaryEl.innerHTML = '<div style="color:var(--muted);font-size:12.5px;padding:8px 0">No memory yet — will be created after first reply or bounce.</div>';
      timelineEl.textContent = '';
    } else {
      summaryEl.innerHTML = `<div style="color:var(--err)">${esc(e.message)}</div>`;
    }
  }
}
// Wire memory modal close
(function _wireMemModal() {
  const closeBtn = document.getElementById('memModalClose');
  const modal = document.getElementById('priMemoryModal');
  if (closeBtn) closeBtn.onclick = () => { if (modal) modal.style.display = 'none'; };
  if (modal) modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
})();

/* ═══════════════ A1 — AI ACCORDION ═══════════════ */
(function _wireAIAccordion() {
  const head = document.getElementById('aiAccordionHead');
  const body = document.getElementById('aiAccordionBody');
  const arrow = document.getElementById('aiAccordionArrow');
  if (!head || !body) return;
  head.onclick = () => {
    const open = body.style.display === 'none';
    body.style.display = open ? '' : 'none';
    if (arrow) arrow.textContent = open ? '▼ collapse' : '▶ expand';
    if (open) loadAIModel();
  };
})();

/* ═══════════════ A1 — PATCH bindNav ═══════════════ */
// Override nav routing to handle 5-tab merge
const _origBindNav = typeof bindNav === 'function' ? bindNav : null;
function bindNav() {
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => {
      const view = el.dataset.view;
      if (!view) return;
      document.querySelectorAll('.nav-item').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.view').forEach(x => x.classList.remove('active'));
      el.classList.add('active');
      const viewEl = document.getElementById(view);
      if (viewEl) viewEl.classList.add('active');
      if (view === 'viewPriority') { loadPriority(); }
      if (view === 'viewInbox') { loadInbox(); }
      if (view === 'viewInsights') { loadInsights(); }
      if (view === 'viewSettings') { bindSettingsControls(); }
      // legacy compat
      if (view === 'viewAnalytics') loadAnalytics();
      if (view === 'viewAI') loadAIModel();
      if (view === 'viewAlerts') loadAlerts();
      if (view === 'viewOpenTracker') loadOpenTracker();
      if (view === 'viewQueue') loadQueue();
    });
  });
}

/* ═══════════════ A1 — PATCH loadPriority to include Overdue ═══════════════ */
const _origLoadPriority = typeof loadPriority === 'function' ? loadPriority.toString() : null;
const _loadPriorityOrig = typeof loadPriority === 'function' ? loadPriority : null;
async function loadPriority() {
  try {
    const r = await api('/api/prospects/priority');
    const list = r.prospects || [];
    const vip = list.filter(p => p.tier === 'VIP');
    const hot = list.filter(p => p.tier === 'HOT');
    document.getElementById('priVip').innerHTML = vip.length;
    document.getElementById('priHot').innerHTML = hot.length;
    document.getElementById('navBadgePriority').textContent = list.length;
    document.getElementById('vipBody').innerHTML = vip.length ? vip.map(renderPriRow).join('') : '<tr><td colspan="6" class="empty-state">No VIP prospects</td></tr>';
    document.getElementById('hotBody').innerHTML = hot.length ? hot.map(renderPriRow).join('') : '<tr><td colspan="6" class="empty-state">No HOT prospects</td></tr>';
    // A1: render overdue section
    renderOverdueSection(list);
    wirePriorityActions();
    // A1: wire [data-mem] click to open memory modal
    document.querySelectorAll('[data-mem]').forEach(el => {
      el.onclick = () => openMemoryModal(el.dataset.mem);
    });
  } catch(e) {
    document.getElementById('vipBody').innerHTML = '<tr><td colspan="6" class="empty-state">Failed: ' + e.message + '</td></tr>';
  }
}

/* ═══════════════ A1 — Insights nav buttons ═══════════════ */
(function _wireInsightsButtons() {
  const reload = document.getElementById('btnInsightsReload');
  if (reload) reload.onclick = loadInsights;
  const retrain = document.getElementById('btnInsightsAITrain');
  if (retrain) retrain.onclick = async () => {
    if (!confirm('Retrain ORACLE model? Takes 2-5 minutes.')) return;
    toast('Training started...', 'warn', 4000);
    try { await api('/api/train-model', { method: 'POST' }); toast('Training done', 'success'); loadAIModel(); }
    catch(e) { toast('Train failed: ' + e.message, 'err'); }
  };
  const analyticsReload = document.getElementById('btnAnalyticsReload');
  if (analyticsReload) analyticsReload.onclick = loadAnalytics;
  const aiReload = document.getElementById('btnAIReload');
  if (aiReload) aiReload.onclick = loadAIModel;
  const aiTrain = document.getElementById('btnAITrain');
  if (aiTrain) aiTrain.onclick = retrain ? retrain.onclick : null;
  const aiPredict = document.getElementById('btnAIPredict');
  if (aiPredict) aiPredict.onclick = predictLane;
})();

// Init inbox controls (called once at DOMReady)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => { bindInboxControls(); bindSettingsControls(); });
} else {
  bindInboxControls();
  bindSettingsControls();
}
"""

with open(HTML_PATH, encoding="utf-8") as f:
    content = f.read()

OLD_ANCHOR = "\ninit();\n\n/* \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 A5 \u2014 PANJIVA UPLOAD \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 */"

if OLD_ANCHOR not in content:
    # fallback anchor
    OLD_ANCHOR = "\ninit();\n"

assert OLD_ANCHOR in content, f"Anchor not found: {OLD_ANCHOR!r}"

replacement = "\ninit();\n" + NEW_JS + "\n\n/* \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 A5 \u2014 PANJIVA UPLOAD \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 */"

new_content = content.replace(OLD_ANCHOR, replacement, 1)
assert new_content != content, "No replacement made"

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"OK: JS injected. Old={len(content)}, New={len(new_content)}")
