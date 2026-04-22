# Sprint 1 v3 — Bounce Learning System (5h, Week 1)

**Goal:** Scanner tự học từ bounce thật → knowledge base grow → mọi import mới tự filter trước khi vào cnee_master.

**Success:**
- 100% bounces auto-ghi vào knowledge
- Panjiva import / CSV upload / manual add → tự drop dead domains
- Sau 1-3 tháng: bounce rate <0.1% (self-improving)

**Paradigm shift:** Thay vì pre-flight verify 22K, hệ thống **học từ kết quả gửi thật** và dùng knowledge để clean mọi data mới.

## Architecture

```
┌─ INPUT (tự học) ────────────────────────────────────────┐
│                                                           │
│  scanner.handle_bounce() (existing)                       │
│      ↓                                                    │
│  🆕 bounce_kb.learn_from_bounce(email, type, source)     │
│      ↓                                                    │
│  Update competitor_blacklist.json với:                    │
│    - auto_dead_domains: domain_X → {bounces: N, ...}     │
│    - auto_role_prefixes: "info" +1, "admin" +1           │
│                                                           │
└──────────────────────────────────────────────────────────┘

┌─ OUTPUT (auto apply) ────────────────────────────────────┐
│                                                           │
│  New emails incoming (Panjiva, CSV, manual add)           │
│      ↓                                                    │
│  🆕 bounce_kb.filter(emails) → (accepted, dropped, flagged)│
│      ↓                                                    │
│  Write cnee_master — data sạch từ đầu                     │
│                                                           │
└──────────────────────────────────────────────────────────┘

┌─ BROWSE (Nelson control) ────────────────────────────────┐
│                                                           │
│  Settings tab → Bounce Knowledge section                  │
│  • View top dead domains                                  │
│  • Manual add/remove                                      │
│  • Export / import KB                                     │
│  • Disable auto-learning toggle (emergency)               │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

## 1.1 Extend competitor_blacklist.json (1h)

### New structure

```json
{
  "_meta": {
    "version": 5,
    "last_updated": "2026-04-21",
    "structure": "manual_deliberate + auto_learned_from_bounces + disposable_weekly_sync"
  },
  "whitelist_domains": ["pudongprime.vn"],

  // ═══ MANUAL (deliberate block) ═══
  "domains": [
    "flexport.com", "airtiger.com", ...  // competitors Nelson chỉ định
  ],
  "emails": [
    "mike.bodack@us.airtiger.com", ...
  ],
  "keywords_in_company": [
    "FORWARDER", "NVOCC", "EXPEDITORS", ...
  ],

  // ═══ AUTO-LEARNED (scanner tự ghi) ═══
  "auto_dead_domains": {
    "woodmark.com": {
      "bounces": 5,
      "sends_total": 5,
      "bounce_rate": 1.0,
      "first_bounce": "2026-04-15",
      "last_bounce": "2026-04-20",
      "classification": "DEAD",  // DEAD | RISKY | LEARNING
      "evidence_emails": ["rprice@woodmark.com", ...]  // up to 5
    },
    "outerstuff.com": {...}
  },
  "auto_role_prefixes": {
    "info": 45,
    "admin": 22,
    "orderdesk": 3,
    "apinvoices": 2,
    "documents": 1
  },

  // ═══ EXTERNAL (weekly auto-refresh từ GitHub) ═══
  "disposable_domains_source": "https://raw.githubusercontent.com/disposable-email-domains/.../blocklist.conf",
  "disposable_domains_last_sync": "2026-04-21",
  "disposable_domains": [
    "10minutemail.com", "guerrillamail.com", "mailinator.com", ...
  ]
}
```

## 1.2 Learning hooks (1.5h)

`email_engine/core/bounce_knowledge.py`:

```python
import json
from pathlib import Path
from datetime import datetime
from filelock import FileLock

KB_PATH = Path("D:/OneDrive/NelsonData/email/competitor_blacklist.json")
LOCK_PATH = KB_PATH.with_suffix('.lock')

DEAD_THRESHOLD_BOUNCE_RATE = 0.8  # 80% bounce → DEAD
DEAD_THRESHOLD_MIN_SENDS = 3       # need at least 3 sends to judge
RISKY_THRESHOLD_BOUNCE_RATE = 0.3  # 30-80% → RISKY

_COMMON_ROLE_WORDS = {
    'info', 'admin', 'support', 'sales', 'contact', 'help',
    'noreply', 'no-reply', 'mailer', 'postmaster',
    'orderdesk', 'documents', 'apinvoices', 'webmaster',
    'marketing', 'billing', 'accounting', 'enquiry',
}


def load_kb() -> dict:
    with FileLock(LOCK_PATH):
        with open(KB_PATH, encoding='utf-8') as f:
            return json.load(f)


def save_kb(kb: dict):
    kb['_meta']['last_updated'] = datetime.now().isoformat()
    with FileLock(LOCK_PATH):
        with open(KB_PATH, 'w', encoding='utf-8') as f:
            json.dump(kb, f, indent=2, ensure_ascii=False)


def learn_from_bounce(email: str, bounce_type: str, source_mail_subject: str = ''):
    """Called from handlers.handle_bounce() after BOUNCE classified."""
    if bounce_type != 'HARD':  # only learn from hard bounces
        return
    
    kb = load_kb()
    domain = email.split('@')[-1].lower().strip()
    local = email.split('@')[0].lower().strip()
    
    # Count total sends to this domain (query email_log.csv)
    sends_total = count_sends_to_domain(domain)
    
    # Track domain
    kb.setdefault('auto_dead_domains', {})
    kb['auto_dead_domains'].setdefault(domain, {
        'bounces': 0,
        'sends_total': sends_total,
        'first_bounce': datetime.now().isoformat(),
        'evidence_emails': [],
        'classification': 'LEARNING',
    })
    
    entry = kb['auto_dead_domains'][domain]
    entry['bounces'] += 1
    entry['sends_total'] = sends_total
    entry['last_bounce'] = datetime.now().isoformat()
    entry['bounce_rate'] = entry['bounces'] / max(sends_total, 1)
    
    # Track evidence (up to 5 unique emails)
    if email not in entry['evidence_emails']:
        entry['evidence_emails'].append(email)
        entry['evidence_emails'] = entry['evidence_emails'][:5]
    
    # Classify
    if sends_total >= DEAD_THRESHOLD_MIN_SENDS:
        if entry['bounce_rate'] >= DEAD_THRESHOLD_BOUNCE_RATE:
            entry['classification'] = 'DEAD'
        elif entry['bounce_rate'] >= RISKY_THRESHOLD_BOUNCE_RATE:
            entry['classification'] = 'RISKY'
        else:
            entry['classification'] = 'LEARNING'
    
    # Learn role patterns
    if local in _COMMON_ROLE_WORDS:
        kb.setdefault('auto_role_prefixes', {})
        kb['auto_role_prefixes'].setdefault(local, 0)
        kb['auto_role_prefixes'][local] += 1
    
    save_kb(kb)
    log.info(f"KB learned: domain={domain} classification={entry['classification']} "
             f"role_local={local if local in _COMMON_ROLE_WORDS else '-'}")


def count_sends_to_domain(domain: str) -> int:
    """Count total sends to this domain from email_log.csv."""
    import pandas as pd
    log_path = Path("D:/NELSON/2. Areas/Engine_test/email_engine/logs/email_log.csv")
    if not log_path.exists():
        return 0
    try:
        df = pd.read_csv(log_path, usecols=['EMAIL'], low_memory=False)
        df['DOMAIN'] = df['EMAIL'].str.split('@').str[-1].str.lower()
        return int((df['DOMAIN'] == domain).sum())
    except Exception:
        return 0
```

### Hook into handlers.handle_bounce

```python
# email_engine/scanner/handlers.py (MODIFY handle_bounce)

def handle_bounce(item: Any, bounced_email: str) -> None:
    # ... existing logic ...
    
    # NEW: learn from this bounce
    try:
        from email_engine.core.bounce_knowledge import learn_from_bounce
        learn_from_bounce(target, severity, subject)
    except Exception as e:
        log.warning(f"bounce KB learn failed: {e}")
    
    # ... existing move_to_deleted ...
```

## 1.3 Apply filter on import (1h)

`email_engine/core/bounce_knowledge.py` (add):

```python
def filter_emails(emails: list[str]) -> dict:
    """Filter emails using learned KB.
    
    Returns:
        {
            'accepted': [str],
            'dropped': [{email, reason}],
            'flagged': [{email, reason}],  # role-based — keep but priority LOW
        }
    """
    kb = load_kb()
    
    # Build lookup sets
    manual_domains = set(d.lower() for d in kb.get('domains', []))
    manual_emails = set(e.lower() for e in kb.get('emails', []))
    keywords = kb.get('keywords_in_company', [])
    dead_domains = {d for d, meta in kb.get('auto_dead_domains', {}).items()
                    if meta.get('classification') == 'DEAD'}
    risky_domains = {d for d, meta in kb.get('auto_dead_domains', {}).items()
                     if meta.get('classification') == 'RISKY'}
    disposable = set(kb.get('disposable_domains', []))
    role_prefixes = set(kb.get('auto_role_prefixes', {}).keys())
    whitelist = set(kb.get('whitelist_domains', []))
    
    result = {'accepted': [], 'dropped': [], 'flagged': []}
    
    for email in emails:
        e = email.lower().strip()
        if not e or '@' not in e:
            result['dropped'].append({'email': email, 'reason': 'INVALID_FORMAT'})
            continue
        
        local, domain = e.split('@', 1)
        
        # Whitelist bypass
        if domain in whitelist:
            result['accepted'].append(email)
            continue
        
        # Manual competitor blocks
        if domain in manual_domains:
            result['dropped'].append({'email': email, 'reason': 'COMPETITOR_DOMAIN'})
            continue
        if e in manual_emails:
            result['dropped'].append({'email': email, 'reason': 'COMPETITOR_EMAIL'})
            continue
        
        # Auto-learned
        if domain in dead_domains:
            result['dropped'].append({'email': email, 'reason': 'AUTO_DEAD_DOMAIN'})
            continue
        if domain in disposable:
            result['dropped'].append({'email': email, 'reason': 'DISPOSABLE'})
            continue
        
        # Risky → accepted but flagged LOW priority
        if domain in risky_domains:
            result['flagged'].append({'email': email, 'reason': 'RISKY_DOMAIN'})
            continue
        
        # Role-based → flagged
        if local in role_prefixes:
            result['flagged'].append({'email': email, 'reason': 'ROLE_BASED'})
            continue
        
        result['accepted'].append(email)
    
    return result


def filter_company_name(company: str) -> tuple[bool, str | None]:
    """Check if company name contains competitor keyword."""
    kb = load_kb()
    company_upper = (company or '').upper()
    for kw in kb.get('keywords_in_company', []):
        if kw in company_upper:
            return True, kw
    return False, None
```

### Integrate into import points

Existing Panjiva clean pipeline (from A5 sprint) + any CSV import endpoint:

```python
# In panjiva_clean.py or csv_import endpoint
from email_engine.core.bounce_knowledge import filter_emails, filter_company_name

def process_import(rows: list[dict]) -> dict:
    emails_to_check = [r['email'] for r in rows]
    filter_result = filter_emails(emails_to_check)
    
    # Build accepted rows with flags
    accepted_set = set(filter_result['accepted'])
    flagged_map = {f['email']: f['reason'] for f in filter_result['flagged']}
    dropped_map = {d['email']: d['reason'] for d in filter_result['dropped']}
    
    accepted_rows = []
    dropped_rows = []
    for r in rows:
        e = r['email']
        if e in accepted_set:
            accepted_rows.append({**r, 'PRIORITY': 'NORMAL'})
        elif e in flagged_map:
            accepted_rows.append({**r, 'PRIORITY': 'LOW', 'FLAG_REASON': flagged_map[e]})
        else:
            r['DROP_REASON'] = dropped_map.get(e, 'UNKNOWN')
            dropped_rows.append(r)
    
    # Also check company name for keyword block
    accepted_rows_final = []
    for r in accepted_rows:
        blocked, kw = filter_company_name(r.get('company', ''))
        if blocked:
            dropped_rows.append({**r, 'DROP_REASON': f'COMPANY_KEYWORD:{kw}'})
        else:
            accepted_rows_final.append(r)
    
    return {
        'accepted': accepted_rows_final,
        'dropped': dropped_rows,
        'stats': {
            'total': len(rows),
            'accepted': len(accepted_rows_final),
            'dropped': len(dropped_rows),
            'flagged_as_low': sum(1 for r in accepted_rows_final if r.get('PRIORITY') == 'LOW'),
        }
    }
```

## 1.4 Weekly disposable-domain auto-sync (0.5h)

```python
def sync_disposable_domains():
    """Monday cron: refresh disposable list from GitHub."""
    import urllib.request
    url = 'https://raw.githubusercontent.com/disposable-email-domains/disposable-email-domains/master/disposable_email_blocklist.conf'
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            content = r.read().decode('utf-8')
        domains = [line.strip().lower() for line in content.split('\n') 
                   if line.strip() and not line.startswith('#')]
        
        kb = load_kb()
        kb['disposable_domains'] = sorted(set(domains))
        kb['disposable_domains_last_sync'] = datetime.now().isoformat()
        save_kb(kb)
        
        return len(domains)
    except Exception as e:
        log.error(f"Disposable sync failed: {e}")
        return 0
```

## 1.5 Knowledge Browser UI (1h)

Settings tab new section:

```html
<section id="bounceKnowledge">
  <h3>🧠 Bounce Knowledge Base</h3>
  <div class="kpi-row">
    <div class="kpi">
      <div class="kpi-label">Dead Domains</div>
      <div class="kpi-value" id="kbDeadCount">0</div>
      <div class="kpi-foot">auto-learned</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Risky Domains</div>
      <div class="kpi-value" id="kbRiskyCount">0</div>
      <div class="kpi-foot">30-80% bounce</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Disposable</div>
      <div class="kpi-value" id="kbDisposableCount">0</div>
      <div class="kpi-foot">from GitHub</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Role Prefixes</div>
      <div class="kpi-value" id="kbRoleCount">0</div>
      <div class="kpi-foot">low priority</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Manual Competitor</div>
      <div class="kpi-value" id="kbManualCount">0</div>
      <div class="kpi-foot">deliberate</div>
    </div>
  </div>
  
  <h4>🔴 Top Dead Domains (auto-learned)</h4>
  <table class="data-table">
    <thead>
      <tr><th>Domain</th><th>Bounces</th><th>Sends</th><th>Rate</th><th>Last Bounce</th><th>Actions</th></tr>
    </thead>
    <tbody id="kbDeadTable"></tbody>
  </table>
  
  <div style="margin-top:12px">
    <button class="btn" id="btnKbAddManual">➕ Add Manual Block</button>
    <button class="btn btn-ghost" id="btnKbExport">⬇ Export KB</button>
    <button class="btn btn-ghost" id="btnKbSyncDisposable">♻ Sync Disposable List</button>
  </div>
</section>
```

### Endpoints

```python
@app.get("/api/bounce-kb/summary")
def kb_summary():
    kb = load_kb()
    return {
        'dead_domains': sum(1 for d, m in kb.get('auto_dead_domains', {}).items()
                           if m.get('classification') == 'DEAD'),
        'risky_domains': sum(1 for d, m in kb.get('auto_dead_domains', {}).items()
                            if m.get('classification') == 'RISKY'),
        'disposable': len(kb.get('disposable_domains', [])),
        'role_prefixes': len(kb.get('auto_role_prefixes', {})),
        'manual_domains': len(kb.get('domains', [])),
        'manual_emails': len(kb.get('emails', [])),
    }


@app.get("/api/bounce-kb/dead-domains")
def kb_dead_domains(limit: int = 50):
    kb = load_kb()
    domains = kb.get('auto_dead_domains', {})
    return [
        {'domain': d, **meta}
        for d, meta in sorted(domains.items(), key=lambda x: -x[1]['bounces'])
        if meta.get('classification') in ('DEAD', 'RISKY')
    ][:limit]


@app.post("/api/bounce-kb/manual-add")
def kb_manual_add(domain: str = '', email: str = ''):
    kb = load_kb()
    if domain:
        kb.setdefault('domains', []).append(domain.lower())
    if email:
        kb.setdefault('emails', []).append(email.lower())
    save_kb(kb)
    return {'ok': True}


@app.post("/api/bounce-kb/remove-learned")
def kb_remove_learned(domain: str):
    kb = load_kb()
    if domain in kb.get('auto_dead_domains', {}):
        del kb['auto_dead_domains'][domain]
        save_kb(kb)
    return {'ok': True}


@app.post("/api/bounce-kb/sync-disposable")
def kb_sync_disposable():
    count = sync_disposable_domains()
    return {'synced': count}
```

## Files modified/created

| File | Type | Purpose |
|------|------|---------|
| `email_engine/core/bounce_knowledge.py` | NEW | Core learning + filter logic |
| `email_engine/scanner/handlers.py` | MODIFY | Hook learn_from_bounce() trong handle_bounce() |
| `email_engine/web_server.py` | MODIFY | 4 new endpoints /api/bounce-kb/* |
| `plans/visuals/email-dashboard-v5.html` | MODIFY | Knowledge Browser section trong Settings |
| `D:/OneDrive/NelsonData/email/competitor_blacklist.json` | MIGRATE | Add auto_dead_domains, auto_role_prefixes, disposable_domains fields |
| `scripts/run-kb-sync-disposable-weekly.py` | NEW | Monday cron: refresh disposable list |
| Existing panjiva_clean / csv_import endpoints | MODIFY | Wire filter_emails() before insert |

## Success Criteria

- [ ] `learn_from_bounce()` called on every HARD_BOUNCE; KB grows với mỗi scan
- [ ] Classification logic verified: 5/5 bounces → DEAD, 3/10 → RISKY
- [ ] `filter_emails()` blocks DEAD + DISPOSABLE, flags RISKY + ROLE
- [ ] Panjiva import test: 1 CSV upload → drop X emails, accept Y
- [ ] Knowledge Browser UI hiển thị numbers correct
- [ ] Manual add/remove endpoints work
- [ ] Weekly disposable sync scheduled + runs OK
- [ ] 1 tuần sau deploy: ≥ 20 auto dead domains learned from actual bounces

## Risks

| Risk | Mitigation |
|------|-----------|
| False positive DEAD classification (3 bounces all từ 1 test) | Require min 3 sends + 80% bounce rate + grace period 7d |
| KB file grow quá lớn (10K+ dead domains) | Compression + rotation after 1 year, archive evidence emails >5 |
| Concurrent write conflict | filelock + atomic write via temp file |
| Manual competitor list lẫn với auto-learned | Separate fields; manual explicit, auto-learned prefixed |
| Panjiva filter fail → skip safety | Try-except wrap: if filter fails, reject import entirely |
| Nelson muốn un-learn 1 domain | Manual remove endpoint |

## Out of scope (v3)

- ❌ DNS MX pre-flight scan 22K (rollback from v2 — không cần nếu learn từ bounce thật)
- ❌ SMTP probe (rủi ro)
- ❌ Paid verifier API
- ❌ ML model pattern detection (đơn giản heuristic đủ)
