#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch email-dashboard-v5.html: insert new views before legacy Analytics view."""
import os
import sys

HTML_PATH = "D:/NELSON/2. Areas/Engine_test/plans/visuals/email-dashboard-v5.html"

with open(HTML_PATH, encoding="utf-8") as f:
    content = f.read()

OLD = (
    "<!-- Placeholder views (keep nav clickable; full impl in v4 for now) -->\n"
    "<!-- \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550"
    " ANALYTICS VIEW \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 -->\n"
    '<section class="view" id="viewAnalytics">'
)

assert OLD in content, "PATCH FAILED: old marker not found"

NEW_VIEWS = """\
<!-- \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 INBOX VIEW (Alerts + OpenTracker merged) \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 -->
<section class="view" id="viewInbox">
  <header class="page-head">
    <div>
      <h1 class="page-title">\U0001f4ec Inbox</h1>
      <div class="page-sub">Unified feed \xb7 opens \xb7 replies \xb7 bounces \xb7 auto</div>
    </div>
    <div class="page-actions">
      <div id="inboxScopeToggle" style="display:inline-flex;gap:0;border:1px solid var(--line);border-radius:6px;overflow:hidden">
        <button class="btn btn-xs btn-ghost" data-ib-scope="1"  style="border-radius:0;border:none">24h</button>
        <button class="btn btn-xs btn-ghost" data-ib-scope="7"  style="border-radius:0;border:none">7d</button>
        <button class="btn btn-xs btn-ghost" data-ib-scope="30" style="border-radius:0;border:none;background:var(--accent);color:#fff">30d</button>
      </div>
      <div id="inboxTypeFilter" style="display:inline-flex;gap:4px;flex-wrap:wrap;margin-left:6px">
        <button class="btn btn-xs ib-type-btn btn-primary" data-ib-type="all">All</button>
        <button class="btn btn-xs ib-type-btn btn-ghost" data-ib-type="open">\U0001f441 Open</button>
        <button class="btn btn-xs ib-type-btn btn-ghost" data-ib-type="reply">\U0001f4ac Reply</button>
        <button class="btn btn-xs ib-type-btn btn-ghost" data-ib-type="bounce">\u26a0 Bounce</button>
        <button class="btn btn-xs ib-type-btn btn-ghost" data-ib-type="auto">\U0001f916 Auto</button>
      </div>
      <button class="btn btn-sm" id="btnInboxReload">Refresh</button>
      <button class="btn btn-sm btn-accent" id="btnScanBounce">\U0001f9f9 Qu\xe9t bounce ngay</button>
    </div>
  </header>
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-label">Opens (scope)</div><div class="kpi-value" id="ibOpens">\u2014</div><div class="kpi-foot"><span id="ibScopeLabel">last 30 days</span></div></div>
    <div class="kpi"><div class="kpi-label">Replies</div><div class="kpi-value" id="ibReplies">\u2014</div><div class="kpi-foot"><span>real replies</span></div></div>
    <div class="kpi"><div class="kpi-label">Bounces</div><div class="kpi-value" id="ibBounces">\u2014</div><div class="kpi-foot"><span>last 7 days</span></div></div>
    <div class="kpi"><div class="kpi-label">Auto-replies</div><div class="kpi-value" id="ibAuto">\u2014</div><div class="kpi-foot"><span>OOO / auto</span></div></div>
  </div>
  <section class="section">
    <div class="section-head">
      <div class="section-title">\u901a\u77e5 \xb7 Unified feed</div>
      <div class="section-sub" id="ibFeedSub">Click row for action</div>
    </div>
    <table class="tbl">
      <thead><tr>
        <th style="width:130px">Time</th>
        <th style="width:60px">Type</th>
        <th>CNEE</th>
        <th>Subject / snippet</th>
        <th style="width:160px">Action</th>
      </tr></thead>
      <tbody id="inboxFeedBody"><tr><td colspan="5" class="empty-state">Loading...</td></tr></tbody>
    </table>
  </section>
</section>

<!-- \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 INSIGHTS VIEW (Analytics + Data Health + AI) \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 -->
<section class="view" id="viewInsights">
  <header class="page-head">
    <div>
      <h1 class="page-title">Insights</h1>
      <div class="page-sub">Analytics \xb7 Data Health \xb7 AI Model \xb7 Pattern Learning</div>
    </div>
    <div class="page-actions">
      <button class="btn btn-sm" id="btnInsightsReload">Refresh all</button>
      <button class="btn btn-sm btn-accent" id="btnInsightsAITrain">Retrain ORACLE</button>
    </div>
  </header>
  <div class="kpi-row">
    <div class="kpi"><div class="kpi-label">Total sent</div><div class="kpi-value" id="anTotal">\u2014</div><div class="kpi-foot"><span id="anTotalSub">lifetime</span></div></div>
    <div class="kpi"><div class="kpi-label">Today</div><div class="kpi-value" id="anToday">\u2014<span class="kpi-unit">emails</span></div><div class="kpi-foot"><span>24h</span></div></div>
    <div class="kpi"><div class="kpi-label">Active campaigns</div><div class="kpi-value" id="anCampaigns">\u2014</div><div class="kpi-foot"><span id="anCampaignsSub">with sent history</span></div></div>
  </div>
  <section class="section">
    <div class="section-head"><div class="section-title">\u9001\u4fe1 \xb7 Performance rates</div></div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)">
      <div class="kpi"><div class="kpi-label">Reply rate</div><div class="kpi-value" id="anReply">\u2014<span class="kpi-unit">%</span></div><div class="kpi-foot"><span>lifetime</span></div></div>
      <div class="kpi"><div class="kpi-label">Bounce rate</div><div class="kpi-value" id="anBounce">\u2014<span class="kpi-unit">%</span></div><div class="kpi-foot"><span>hard + soft</span></div></div>
      <div class="kpi"><div class="kpi-label">Lead score</div><div class="kpi-value" id="anLead">\u2014<span class="kpi-unit">avg</span></div><div class="kpi-foot"><span>0-100 scale</span></div></div>
    </div>
  </section>
  <section class="section">
    <div class="section-head"><div class="section-title">\u5b9f\u7e3e \xb7 7-day timeline</div></div>
    <div id="anTimeline" style="padding:24px 0;border-top:1px solid var(--line-2);border-bottom:1px solid var(--line-2)">
      <div class="empty-state"><div class="empty-state-kanji">\u7a7a</div>No send activity yet</div>
    </div>
  </section>
  <section class="section">
    <div class="section-head"><div class="section-title">\u30ad\u30e3\u30f3\u30da\u30fc\u30f3 \xb7 Campaign breakdown</div></div>
    <table class="tbl">
      <thead><tr><th>Campaign</th><th>Sent</th><th>Opened</th><th>Reply</th><th>Bounce</th></tr></thead>
      <tbody id="anCampaignBody"><tr><td colspan="5" class="empty-state">Loading...</td></tr></tbody>
    </table>
  </section>
  <!-- Data Health (A1) -->
  <section class="section" id="dataHealthSection">
    <div class="section-head">
      <div class="section-title">\U0001f5c4 Data Health</div>
      <div class="section-sub">cnee_master_v2_final \xb7 EMAIL_STATUS + STATE distribution</div>
    </div>
    <div id="dataHealthContent">
      <div class="empty-state" style="padding:24px 0"><div class="empty-state-kanji">\u8aad</div>Loading data health...</div>
    </div>
  </section>
  <!-- A2 send-time hint placeholder -->
  <div id="qsSendTimeHint" style="display:none"></div>
  <!-- Pattern Learning placeholder (A4) -->
  <div id="insightsPatterns"></div>
  <!-- AI Model accordion -->
  <section class="section">
    <div class="section-head" style="cursor:pointer" id="aiAccordionHead">
      <div class="section-title">\u25c8 AI Model (ORACLE) <span id="aiAccordionArrow" style="font-size:12px;color:var(--muted)">\u25b6 expand</span></div>
      <div class="section-sub" id="aiTrainedAt">loading...</div>
    </div>
    <div id="aiAccordionBody" style="display:none">
      <div class="kpi-row" style="margin-bottom:20px">
        <div class="kpi"><div class="kpi-label">Status</div><div class="kpi-value" id="aiStatus" style="font-size:18px;font-family:'Inter',sans-serif">\u2014</div></div>
        <div class="kpi"><div class="kpi-label">Accuracy</div><div class="kpi-value" id="aiAcc">\u2014<span class="kpi-unit">%</span></div><div class="kpi-foot"><span id="aiAccSub">walk-forward</span></div></div>
        <div class="kpi"><div class="kpi-label">Corridors</div><div class="kpi-value" id="aiCorr">\u2014</div><div class="kpi-foot"><span id="aiCorrSub">trained</span></div></div>
      </div>
      <div class="form-row">
        <div class="field"><div class="field-label">POL</div>
          <select class="field-select" id="aiPol"><option>HPH</option><option>HCM</option></select>
        </div>
        <div class="field"><div class="field-label">POD</div>
          <select class="field-select" id="aiPod">
            <option>USLAX</option><option>USLGB</option><option>USNYC</option>
            <option>USSAV</option><option>USHOU</option><option>USCHS</option>
            <option>USCHI</option><option>USSEA</option><option>CAVAN</option>
          </select>
        </div>
        <div class="field"></div><div class="field"></div><div class="field"></div>
        <button class="btn btn-primary" id="btnAIPredict">Predict</button>
      </div>
      <div id="aiForecast" style="padding:24px 0">
        <div class="empty-state"><div class="empty-state-kanji">\u554f</div>Pick a lane \u2192 Predict</div>
      </div>
    </div>
  </section>
</section>

<!-- \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 SETTINGS VIEW \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 -->
<section class="view" id="viewSettings">
  <header class="page-head">
    <div><h1 class="page-title">\u2699 Settings</h1>
      <div class="page-sub">Control center \u2014 ARM/DISARM \xb7 rules \xb7 integrations</div>
    </div>
  </header>
  <section class="section">
    <div class="section-head">
      <div class="section-title">\U0001f6d1 Kill Switch</div>
      <div class="section-sub">ARM = worker stops picking new jobs \xb7 DISARM = resume</div>
    </div>
    <div style="padding:20px;border:1px solid var(--line);display:flex;align-items:center;gap:16px">
      <span id="settingsKillStatus" style="font-size:13px;color:var(--muted)">Checking...</span>
      <button class="btn btn-danger" id="settingsBtnKill">ARM</button>
      <button class="btn btn-sm" id="settingsBtnKillClear" style="display:none;background:var(--good);color:#fff;border-color:var(--good)">DISARM</button>
    </div>
  </section>
  <section class="section" id="settingsAutoLearn">
    <div class="section-head"><div class="section-title">\U0001f9e0 Auto-learn Rules</div><div class="section-sub" style="color:var(--muted)">S\u1eafp c\xf3... (A4 Pattern Learning)</div></div>
    <div style="padding:16px;background:var(--paper-2);color:var(--muted);font-size:12.5px;border-left:2px solid var(--line)">Ch\u01b0a c\xf3. Module Pattern Learning (A4) s\u1ebd th\xeam g\u1ee3i \xfd t\u1ef1 \u0111\u1ed9ng v\xe0o \u0111\xe2y.</div>
  </section>
  <section class="section" id="settingsPanjiva">
    <div class="section-head"><div class="section-title">\U0001f4e6 Panjiva Import</div><div class="section-sub" style="color:var(--muted)">S\u1eafp c\xf3... (A5 Panjiva Clean Pipeline)</div></div>
    <div style="padding:16px;background:var(--paper-2);color:var(--muted);font-size:12.5px;border-left:2px solid var(--line)">Upload Panjiva export \u2192 blacklist filter \u2192 LLM classify \u2192 dedup \u2192 merge v\xe0o cnee_master.</div>
  </section>
  <section class="section" id="settingsScheduled">
    <div class="section-head"><div class="section-title">\u23f1 Scheduled Jobs</div><div class="section-sub" style="color:var(--muted)">S\u1eafp c\xf3... (Task Scheduler inventory)</div></div>
    <div style="padding:16px;background:var(--paper-2);color:var(--muted);font-size:12.5px;border-left:2px solid var(--line)">Qu\u1ea3n l\xfd 7 scheduled tasks t\u1eeb dashboard \u2014 enable/disable kh\xf4ng c\u1ea7n m\u1edf Task Scheduler.</div>
  </section>
  <section class="section" id="settingsRules">
    <div class="section-head"><div class="section-title">\U0001f464 Customer Rules</div><div class="section-sub" style="color:var(--muted)">S\u1eafp c\xf3... (customer_rules.json editor)</div></div>
    <div style="padding:16px;background:var(--paper-2);color:var(--muted);font-size:12.5px;border-left:2px solid var(--line)">Edit preferred_pods, preferred_carriers, markup per customer tr\u1ef1c ti\u1ebfp t\u1eeb UI.</div>
  </section>
  <section class="section" id="settingsHealth">
    <div class="section-head"><div class="section-title">\U0001f49a System Health</div><div class="section-sub" style="color:var(--muted)">S\u1eafp c\xf3... (system health checks)</div></div>
    <div style="padding:16px;background:var(--paper-2);color:var(--muted);font-size:12.5px;border-left:2px solid var(--line)">Parquet freshness \xb7 Outlook COM status \xb7 API ping \xb7 Worker queue depth.</div>
  </section>
</section>

<!-- Keep old view shells as hidden stubs (JS backward-compat \u2014 don't delete these IDs) -->
<section class="view" id="viewAnalytics" style="display:none!important"></section>
<section class="view" id="viewAI" style="display:none!important"></section>
<section class="view" id="viewAlerts" style="display:none!important"></section>
<section class="view" id="viewOpenTracker" style="display:none!important"></section>
<section class="view" id="viewQueue" style="display:none!important"></section>

<!-- \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 LEGACY VIEWS (content moved above) \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 -->
<!-- Placeholder views (keep nav clickable; full impl in v4 for now) -->
<!-- \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 ANALYTICS VIEW \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550 -->
<section class="view" id="viewAnalyticsOldLegacy" style="display:none!important">
  <header class="page-head">
    <div>
      <h1 class="page-title">Analytics</h1>"""

new_content = content.replace(OLD, NEW_VIEWS, 1)
assert new_content != content, "No replacement made"

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"OK: patched. Old len={len(content)}, New len={len(new_content)}")
