"""
PST Importer — Import Outlook PST via COM into shipments.db
============================================================
Opens PST via Outlook COM, scans named folders (CNEE, SHIPPER,
AGENT, INTERNAL, TEAM SUNNY) with a 3-layer filter:
  Layer 1: instant_reject (blacklist domains/subjects/senders)
  Layer 2: fast_keep (HBL/BKG patterns, stage keywords, carrier domains)
  Layer 3: AI classify via Claude API (batch of 20)

Usage:
  python core/pst_importer.py --dry-run --folder-only --since 2024-01-01
  python core/pst_importer.py --folder-only --since 2024-01-01
  python core/pst_importer.py --since 2024-01-01
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

import win32com.client

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH      = PROJECT_ROOT / 'logs' / 'shipments.db'
PST_PATH     = PROJECT_ROOT / 'backup.pst'
LOG_PATH     = PROJECT_ROOT / 'logs' / 'pst_import.log'

PR_SMTP = 'http://schemas.microsoft.com/mapi/proptag/0x39FE001E'

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_fmt = logging.Formatter(
    "[%(asctime)s] %(levelname)-8s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
_console = logging.StreamHandler(sys.stdout)
_console.setFormatter(_fmt)

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8",
)
_file_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_console, _file_handler])
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# FILTER CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

BLACKLIST_DOMAINS = [
    'linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com',
    'zoom.us', 'teams.microsoft.com', 'calendly.com',
    'mailchimp.com', 'hubspot.com', 'constantcontact.com',
    'accounts.google.com', 'googleapis.com',
    'apple.com', 'icloud.com', 'github.com',
    'grab.com', 'shopee.vn', 'lazada.vn', 'tiki.vn',
]

BLACKLIST_SUBJECT = [
    'unsubscribe', 'newsletter', 'webinar', 'free trial',
    'password reset', 'verification code', 'otp', 'one-time pin',
    'payslip', 'salary slip', 'leave request', 'attendance',
    'happy birthday', 'party invitation',
    'your order', 'your receipt', 'order confirmed',
    'liked your post', 'commented on', 'new connection',
    'zoom meeting', 'teams meeting', 'calendar invite',
]

BLACKLIST_SENDERS = [
    r'noreply@', r'no-reply@', r'donotreply@',
    r'notification@', r'notifications@',
    r'mailer@', r'bounce@', r'postmaster@',
    r'auto@', r'automated@',
]

FREIGHT_FAST_KEEP_SUBJECTS = [
    'draft b/l', 'draft bl', 'draft b l', 'draft b_l',
    'dn //', 'dn __', 'debit note', 'debit //',
    'update atd', ' atd ', 'vessel departed',
    'booking confirmation', 'bkg confirmed', 'keep booking',
    'change vessel', 'changed mother vessel',
    'delay notice',
    'pre-alert', 'arrival notice',
    'nelson week',
    'si //', 'shipping instruction',
    'update cy', 'cy cut',
    'release//', 'do released',
    'invoice', 'payment received',
]

CARRIER_DOMAINS = [
    'hapag-lloyd.com', 'hlag.com', 'zim.com', 'msc.com',
    'one-line.com', 'evergreen-marine.com', 'yangming.com',
    'cma-cgm.com', 'cosco.com', 'wanhai.com',
    'gsl.com', 'smartlinklogistics.com',
    'seaspancontainer.com',
]

HBL_QUICK = (
    r'\b(P(?:NYC|SAV|HOU|DEN|CHS|SEA|OMA|YTO|ELP|MAN|LAX|HAI|ATL)\d{7,}'
    r'|HLCU[A-Z]{3}\d{9,}'
    r'|ZIMU(?:HCM|HAI|SGN)\d{8,}'
    r'|HANG\d{8,}'
    r'|ESLV[A-Z0-9]{5,}'
    r'|PATL\d{8,})\b'
)
BKG_QUICK = (
    r'\b(SGN\d{7,}|HANFG\d{7,}|EBKG\d{8,}'
    r'|ZIMUHCM\d{8,}|ZIMUHAI\d{8,})\b'
)


# ═══════════════════════════════════════════════════════════════════════════
# 3 FILTER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def instant_reject(subject: str, sender: str, body: str) -> tuple[bool, str]:
    """Layer 1: discard obvious noise instantly."""
    s = (subject or '').lower()
    e = (sender or '').lower()
    b = (body or '')[:200].lower()

    for d in BLACKLIST_DOMAINS:
        if d in e:
            return True, f'domain:{d}'
    for p in BLACKLIST_SENDERS:
        if re.search(p, e):
            return True, 'sender_pattern'
    for kw in BLACKLIST_SUBJECT:
        if kw in s:
            return True, f'subject:{kw}'
    if 'unsubscribe' in b and 'booking' not in s:
        return True, 'newsletter_body'
    return False, ''


def fast_keep(subject: str, sender: str) -> bool:
    """Layer 2: immediately keep emails with freight signals."""
    s = (subject or '').upper()
    e = (sender or '').lower()

    if re.search(HBL_QUICK, s):
        return True
    if re.search(BKG_QUICK, s):
        return True
    if any(kw.upper() in s for kw in FREIGHT_FAST_KEEP_SUBJECTS):
        return True
    if any(d in e for d in CARRIER_DOMAINS):
        return True
    return False


def ai_classify_batch(emails: list) -> list[str]:
    """Layer 3: batch classify uncertain emails via Claude API."""
    items_text = '\n'.join(
        f"{i+1}. Subject: {e['subject'][:100]} | From: {e['sender'][:50]}"
        for i, e in enumerate(emails)
    )
    prompt = (
        "Classify each email for a Vietnamese ocean freight forwarder.\n"
        "KEEP = freight/business relevant (shipments, rates, customers, agents, ops)\n"
        "SKIP = spam, newsletter, personal, social media, food delivery, OTP\n"
        "MAYBE = uncertain\n\n"
        f"{items_text}\n\n"
        "Reply ONLY with lines like:\n1. KEEP\n2. SKIP\n(one per line, nothing else)"
    )

    try:
        import requests
        # Read API key from environment or .env
        import os
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            env_file = PROJECT_ROOT / '.env'
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith('ANTHROPIC_API_KEY='):
                        api_key = line.split('=', 1)[1].strip().strip('"').strip("'")
                        break

        if not api_key:
            log.warning('No ANTHROPIC_API_KEY found. Treating batch as MAYBE.')
            return ['MAYBE'] * len(emails)

        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': 300,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=30,
        )
        text = r.json()['content'][0]['text']
        results = {}
        for line in text.strip().split('\n'):
            m = re.match(r'(\d+)\.\s+(KEEP|SKIP|MAYBE)', line.strip())
            if m:
                results[int(m.group(1)) - 1] = m.group(2)
        return [results.get(i, 'MAYBE') for i in range(len(emails))]
    except Exception as ex:
        log.error('AI classify failed: %s', ex)
        return ['MAYBE'] * len(emails)


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def get_smtp(item) -> str:
    """Extract sender SMTP address from Outlook MailItem."""
    try:
        addr = item.SenderEmailAddress
        if addr and '@' in addr and not addr.startswith('/O='):
            return addr.lower().strip()
    except Exception:
        pass
    try:
        pa = item.Sender.PropertyAccessor
        smtp = pa.GetProperty(PR_SMTP)
        if smtp:
            return smtp.lower().strip()
    except Exception:
        pass
    return ''


def is_duplicate(conn, subject: str, received_iso: str) -> bool:
    """Check if email already exists in DB (by subject + timestamp prefix)."""
    r = conn.execute(
        "SELECT 1 FROM email_events WHERE subject_raw=? AND received_at LIKE ?",
        (subject, received_iso[:16] + '%'),
    ).fetchone()
    return r is not None


def ensure_maybe_table(conn):
    """Create email_maybe_review table if it doesn't exist."""
    conn.execute("""CREATE TABLE IF NOT EXISTS email_maybe_review (
        review_id      TEXT PRIMARY KEY,
        received_at    TEXT,
        sender         TEXT,
        subject_raw    TEXT,
        folder_context TEXT,
        body_preview   TEXT,
        is_reviewed    INTEGER DEFAULT 0,
        review_verdict TEXT,
        reviewed_at    TEXT,
        created_at     TEXT
    )""")
    conn.commit()


def insert_email(conn, parsed: dict, folder_path: str):
    """Insert parsed email into email_events table."""
    event_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    conn.execute("""INSERT OR IGNORE INTO email_events
        (event_id, received_at, processed_at, email_type, member_owner,
         folder_context, sender, subject_raw, shipment_key, hbl, bkg, member_ref,
         customer_name, primary_stage, stages_detected, risk_level, risk_reasons,
         route, pol, pod, carrier, container_type, etd, incoterm, commodity,
         intent, next_action, urgency, campaign_week, campaign_type,
         parse_confidence, needs_review, msg_filename)
        VALUES (?,?,?,?,?, ?,?,?,?,?,?,?, ?,?,?,?,?, ?,?,?,?,?,?,?,?, ?,?,?,?,?, ?,?,?)""",
        (event_id, parsed.get('received_at'), now,
         parsed.get('email_type', 'TYPE_SHIPMENT'),
         parsed.get('member_owner', 'NELSON'),
         folder_path,
         parsed.get('sender'),
         parsed.get('subject_raw'),
         parsed.get('shipment_key'),
         parsed.get('hbl'), parsed.get('bkg'), parsed.get('member_ref'),
         parsed.get('customer_name'),
         parsed.get('primary_stage'),
         json.dumps(parsed.get('stages_detected', [])),
         parsed.get('risk_level', 'NORMAL'),
         json.dumps(parsed.get('risk_reasons', [])),
         parsed.get('route'), parsed.get('pol'), parsed.get('pod'),
         parsed.get('carrier'), parsed.get('container_type'),
         parsed.get('etd'), parsed.get('incoterm'), parsed.get('commodity'),
         parsed.get('intent'), parsed.get('next_action'), parsed.get('urgency'),
         parsed.get('campaign_week'), parsed.get('campaign_type'),
         parsed.get('parse_confidence', 0),
         1 if parsed.get('needs_review') else 0,
         f'PST:{folder_path}'))


def insert_maybe(conn, subject, sender, body, folder_path, received):
    """Insert uncertain email into email_maybe_review table."""
    conn.execute("""INSERT OR IGNORE INTO email_maybe_review
        (review_id, received_at, sender, subject_raw, folder_context,
         body_preview, is_reviewed, created_at)
        VALUES (?,?,?,?,?, ?,0,?)""",
        (str(uuid.uuid4()), received, sender, subject,
         folder_path, (body or '')[:500], datetime.now().isoformat()))


# ═══════════════════════════════════════════════════════════════════════════
# MAIN IMPORT FUNCTION
# ═══════════════════════════════════════════════════════════════════════════

def import_pst(
    pst_path: str,
    since_date: str = '2023-01-01',
    folder_filter: str | None = None,
    dry_run: bool = False,
    folder_only: bool = False,
):
    """
    Import emails from a PST file via Outlook COM.

    Parameters
    ----------
    pst_path     : str    Path to .pst file
    since_date   : str    Only import emails after this date (YYYY-MM-DD)
    folder_filter: str    Only process folders containing this string
    dry_run      : bool   Preview only, don't insert to DB
    folder_only  : bool   Skip Inbox root, only scan named folders (faster)
    """
    # Ensure email_parser is importable
    sys.path.insert(0, str(Path(__file__).parent))
    from email_parser import EmailClassifier
    classifier = EmailClassifier()

    # Connect to Outlook
    outlook = win32com.client.Dispatch('Outlook.Application')
    ns = outlook.GetNamespace('MAPI')

    log.info('Opening PST: %s', pst_path)
    ns.AddStore(pst_path)

    # Find the PST store
    pst_store = None
    for store in ns.Stores:
        try:
            if pst_path.lower() in store.FilePath.lower():
                pst_store = store
                break
        except Exception:
            continue

    if not pst_store:
        log.error('Cannot find PST store after AddStore. Check Outlook.')
        return

    root = pst_store.GetRootFolder()
    cutoff = datetime.fromisoformat(since_date)

    log.info('PST root folder: %s', root.Name)
    log.info('Date cutoff: %s', since_date)
    log.info('Folder filter: %s', folder_filter or '(all)')
    log.info('Dry run: %s', dry_run)
    log.info('Folder only: %s', folder_only)

    # List top-level folders in PST
    log.info('--- PST Folders ---')
    for folder in root.Folders:
        try:
            count = folder.Items.Count
            log.info('  %s (%d items)', folder.Name, count)
        except Exception:
            log.info('  %s (error reading)', folder.Name)
    log.info('---')

    # Stats
    stats = {k: 0 for k in [
        'scanned', 'instant_reject', 'fast_keep',
        'ai_keep', 'ai_maybe', 'ai_skip',
        'inserted', 'duplicates', 'errors',
    ]}

    # DB setup
    from shared.db_connect import get_db
    conn = get_db(DB_PATH)
    ensure_maybe_table(conn)
    ai_batch = []

    def detect_member(path: str) -> str:
        p = path.upper()
        for name in ['BLUE', 'JENNIE', 'OTIS', 'JUN', 'MARK', 'LINA', 'JOHNNY']:
            if name in p:
                return name
        return 'NELSON'

    def flush_ai_batch():
        nonlocal ai_batch
        if not ai_batch:
            return
        log.info('    AI batch: classifying %d emails...', len(ai_batch))
        verdicts = ai_classify_batch(ai_batch)
        for email_data, verdict in zip(ai_batch, verdicts):
            if verdict == 'KEEP':
                stats['ai_keep'] += 1
                if not dry_run:
                    email_type = email_data['email_type']
                    if email_type == 'TYPE_SHIPMENT':
                        parsed = classifier.parse_shipment(
                            email_data['subject'], email_data['sender'],
                            email_data['recipients'], email_data['received'],
                            email_data['member'], email_data['folder_path'],
                        )
                    else:
                        parsed = classifier.parse_sales_reply(
                            email_data['subject'], email_data['sender'],
                            email_data['body'], email_data['received'],
                            email_data['folder_path'],
                        )
                    insert_email(conn, parsed, email_data['folder_path'])
                    stats['inserted'] += 1
            elif verdict == 'MAYBE':
                stats['ai_maybe'] += 1
                if not dry_run:
                    insert_maybe(
                        conn, email_data['subject'], email_data['sender'],
                        email_data['body'], email_data['folder_path'],
                        email_data['received'],
                    )
            else:
                stats['ai_skip'] += 1
        ai_batch.clear()
        conn.commit()

    def process_folder(folder, folder_path: str, is_named: bool = False):
        """Process all MailItems in a folder and recurse into subfolders."""
        try:
            count = folder.Items.Count
        except Exception:
            return
        if count == 0 and not any(True for _ in folder.Folders):
            return

        if count > 0:
            log.info('  Scanning: %s (%d items)', folder_path, count)

        member = detect_member(folder_path)

        # Apply folder filter
        if folder_filter and folder_filter.upper() not in folder_path.upper():
            for sub in folder.Folders:
                process_folder(sub, f"{folder_path}\\{sub.Name}", is_named)
            return

        items = folder.Items
        try:
            items.Sort('[ReceivedTime]', True)  # newest first
        except Exception:
            pass

        for item in items:
            try:
                if item.Class != 43:  # olMail = 43
                    continue

                received = item.ReceivedTime
                # Handle timezone-aware datetimes
                try:
                    received_naive = received.replace(tzinfo=None)
                except Exception:
                    received_naive = received
                if received_naive < cutoff:
                    break  # sorted newest first, so all remaining are older

                subject = item.Subject or ''
                sender  = get_smtp(item)

                # Read body safely
                body = ''
                try:
                    body = (item.Body or '')[:400]
                except Exception:
                    pass

                recip = ''
                try:
                    recip = item.To or ''
                except Exception:
                    pass

                stats['scanned'] += 1
                if stats['scanned'] % 200 == 0:
                    log.info(
                        '    Progress: %d scanned | keep=%d skip=%d maybe=%d dup=%d err=%d',
                        stats['scanned'],
                        stats['fast_keep'] + stats['ai_keep'],
                        stats['instant_reject'] + stats['ai_skip'],
                        stats['ai_maybe'], stats['duplicates'], stats['errors'],
                    )

                # Layer 1: instant reject
                rejected, reason = instant_reject(subject, sender, body)
                if rejected:
                    stats['instant_reject'] += 1
                    continue

                # Layer 2: fast keep (clear freight signals OR named folder)
                if fast_keep(subject, sender) or is_named:
                    stats['fast_keep'] += 1
                    if not dry_run:
                        received_iso = ''
                        try:
                            received_iso = received.isoformat()
                        except Exception:
                            received_iso = str(received)

                        if is_duplicate(conn, subject, received_iso):
                            stats['duplicates'] += 1
                            continue

                        email_type = classifier.classify(subject, sender, folder_path)
                        if email_type == 'TYPE_SHIPMENT':
                            parsed = classifier.parse_shipment(
                                subject, sender, recip,
                                received_iso, member, folder_path,
                            )
                        else:
                            parsed = classifier.parse_sales_reply(
                                subject, sender, body,
                                received_iso, folder_path,
                            )
                        insert_email(conn, parsed, folder_path)
                        stats['inserted'] += 1
                    continue

                # Layer 3: queue for AI (only for non-named / Inbox root)
                if not folder_only:
                    received_iso = ''
                    try:
                        received_iso = received.isoformat()
                    except Exception:
                        received_iso = str(received)

                    ai_batch.append({
                        'subject': subject, 'sender': sender,
                        'body': body, 'recipients': recip,
                        'received': received_iso,
                        'folder_path': folder_path,
                        'member': member,
                        'email_type': classifier.classify(subject, sender, folder_path),
                    })
                    if len(ai_batch) >= 20:
                        flush_ai_batch()

            except Exception as e:
                stats['errors'] += 1
                log.debug('Item error in %s: %s', folder_path, e)

        # Commit periodically
        if stats['scanned'] % 500 == 0:
            conn.commit()

        # Recurse into subfolders
        for sub in folder.Folders:
            sub_path = f"{folder_path}\\{sub.Name}"
            process_folder(sub, sub_path, is_named)

    # ─── Determine which folders to scan ─────────────────────────────
    NAMED_FOLDERS = ['CNEE', 'SHIPPER', 'AGENT', 'INTERNAL', 'TEAM SUNNY']

    for folder in root.Folders:
        fname = folder.Name.upper().strip()
        if fname in NAMED_FOLDERS:
            process_folder(folder, fname, is_named=True)
        elif fname in ('INBOX', 'BOITE DE RECEPTION', 'HOP THU DEN') and not folder_only:
            process_folder(folder, 'INBOX_ROOT', is_named=False)
        else:
            # Check if any named folder is a child
            try:
                for sub in folder.Folders:
                    if sub.Name.upper().strip() in NAMED_FOLDERS:
                        process_folder(sub, sub.Name.upper().strip(), is_named=True)
            except Exception:
                pass

    # Flush remaining AI batch
    flush_ai_batch()
    conn.commit()
    conn.close()

    # Remove PST from Outlook stores
    try:
        for store in ns.Stores:
            try:
                if pst_path.lower() in store.FilePath.lower():
                    ns.RemoveStore(store.GetRootFolder())
                    log.info('Removed PST from Outlook stores.')
                    break
            except Exception:
                continue
    except Exception:
        log.warning('Could not auto-remove PST from Outlook. Remove manually if needed.')

    # ─── Final report ────────────────────────────────────────────────
    total_kept = stats['fast_keep'] + stats['ai_keep']
    total_skip = stats['instant_reject'] + stats['ai_skip']
    scanned = max(stats['scanned'], 1)

    log.info('')
    log.info('=' * 55)
    log.info('PST IMPORT COMPLETE')
    log.info('=' * 55)
    log.info('Total scanned   : %d', stats['scanned'])
    log.info('Instant rejected: %d (%.1f%%) -- spam/noise',
             stats['instant_reject'],
             stats['instant_reject'] / scanned * 100)
    log.info('Fast kept       : %d -- clear freight emails', stats['fast_keep'])
    log.info('AI kept         : %d', stats['ai_keep'])
    log.info('AI maybe        : %d -- review: email_maybe_review table', stats['ai_maybe'])
    log.info('AI skipped      : %d', stats['ai_skip'])
    log.info('Duplicates      : %d', stats['duplicates'])
    log.info('Errors          : %d', stats['errors'])
    log.info('-' * 55)
    log.info('INSERTED TO DB  : %d emails', stats['inserted'])
    log.info('=' * 55)

    if not dry_run:
        log.info('Next: python core/nelson_briefing.py')

    return stats


# ═══════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Import PST into shipments.db')
    p.add_argument('--pst', default=str(PST_PATH),
                   help='Path to PST file')
    p.add_argument('--since', default='2023-01-01',
                   help='Only import emails after this date (YYYY-MM-DD)')
    p.add_argument('--folder', default=None,
                   help='Only import specific folder, e.g. "CNEE"')
    p.add_argument('--dry-run', action='store_true',
                   help='Preview only, do not insert to DB')
    p.add_argument('--folder-only', action='store_true',
                   help='Skip Inbox root, only named folders (faster)')
    args = p.parse_args()

    import_pst(args.pst, args.since, args.folder,
               args.dry_run, args.folder_only)
