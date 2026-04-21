# -*- coding: utf-8 -*-
"""
_audit_load_on_board_emails.py — one-shot audit

Scan Outlook Inbox + subfolders for carrier "Load on Board" / "Vessel Departed"
confirmations, matched against Bkg_No from Shipments.xlsx.

Output: report of which carriers send these emails + sample patterns.
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import win32com.client
from collections import defaultdict
from datetime import datetime, timedelta

SHIPMENTS = r"C:/Users/Nelson/OneDrive/Desktop/Shipments.xlsx"
DAYS_BACK = 120  # scan last 4 months

# Patterns that might indicate "load on board" confirmation
PATTERNS = [
    r"load(ed)?\s+on\s+board",
    r"shipped\s+on\s+board",
    r"vessel\s+depart",
    r"on\s*board\s*date",
    r"shipping\s+confirm",
    r"departure\s+notice",
    r"sailing\s+confirm",
    r"vessel\s+sail",
    r"cargo\s+loaded",
    r"ATD\s*[:=]",
]
PAT_RE = re.compile("|".join(PATTERNS), re.I)


def load_bkg_samples(n=50):
    xl = pd.ExcelFile(SHIPMENTS)
    frames = []
    for sh in ['Jan 2026','Feb 2026','Mar 2026','Apr 2026']:
        df = pd.read_excel(xl, sheet_name=sh, header=None)
        for i in range(5):
            if any('Bkg' in str(c) for c in df.iloc[i].values):
                df = pd.read_excel(xl, sheet_name=sh, header=i)
                break
        frames.append(df)
    all_df = pd.concat(frames, ignore_index=True)
    bkg_col = [c for c in all_df.columns if 'Bkg' in str(c)][0]
    bkgs = all_df[all_df[bkg_col].notna()][bkg_col].astype(str).str.strip().tolist()
    # filter out obvious empties + dedup
    bkgs = [b for b in bkgs if len(b) >= 6 and b.lower() != 'nan']
    return list(dict.fromkeys(bkgs))[:n]


def walk_folders(folder, depth=0, max_depth=3):
    yield folder
    if depth >= max_depth:
        return
    try:
        for sub in folder.Folders:
            yield from walk_folders(sub, depth + 1, max_depth)
    except Exception:
        pass


def get_sender_smtp(item):
    try:
        if item.SenderEmailType == 'EX':
            return item.Sender.GetExchangeUser().PrimarySmtpAddress or item.SenderEmailAddress
        return item.SenderEmailAddress or ''
    except Exception:
        return getattr(item, 'SenderEmailAddress', '') or ''


def main():
    bkgs = load_bkg_samples(50)
    print(f"[INFO] Loaded {len(bkgs)} Bkg_No samples")
    print(f"[INFO] Sample: {bkgs[:5]}")
    bkg_set = set(b.upper() for b in bkgs)

    outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    inbox = outlook.GetDefaultFolder(6)

    cutoff = datetime.now() - timedelta(days=DAYS_BACK)

    hits = []  # (sender_domain, subject, bkg_matched, pattern_matched, received, folder)
    sender_stats = defaultdict(int)
    pattern_stats = defaultdict(int)

    folders_scanned = 0
    items_scanned = 0

    for folder in walk_folders(inbox, max_depth=2):
        # Skip obvious non-carrier folders
        name = folder.Name
        if any(skip in name.upper() for skip in ['SENT','DRAFTS','DELETED','JUNK','RSS','OUTBOX','ARCHIVE']):
            continue
        folders_scanned += 1
        try:
            items = folder.Items
            items.Sort("[ReceivedTime]", True)  # newest first
            items.IncludeRecurrences = False
        except Exception:
            continue

        for item in items:
            try:
                if item.Class != 43:  # olMail
                    continue
                rt = getattr(item, 'ReceivedTime', None)
                if rt is None:
                    continue
                if rt.replace(tzinfo=None) < cutoff:
                    break  # items sorted newest-first, rest are older
                items_scanned += 1

                subject = (getattr(item, 'Subject', '') or '')
                body = (getattr(item, 'Body', '') or '')[:3000]
                text = f"{subject}\n{body}"
                text_upper = text.upper()

                # Check pattern
                pm = PAT_RE.search(text)
                if not pm:
                    continue

                # Check Bkg_No match
                bkg_hit = None
                for b in bkg_set:
                    if b in text_upper:
                        bkg_hit = b
                        break

                sender = get_sender_smtp(item)
                domain = sender.split('@')[-1].lower() if '@' in sender else sender

                hits.append({
                    'folder': name,
                    'sender': sender,
                    'domain': domain,
                    'subject': subject[:100],
                    'bkg_matched': bkg_hit or '',
                    'pattern': pm.group(0),
                    'received': rt.strftime('%Y-%m-%d'),
                })
                sender_stats[domain] += 1
                pattern_stats[pm.group(0).lower()] += 1
            except Exception:
                continue

    print(f"\n[STATS] Folders scanned: {folders_scanned}")
    print(f"[STATS] Items scanned: {items_scanned}")
    print(f"[STATS] Total hits: {len(hits)}")
    print(f"[STATS] Bkg-matched hits: {sum(1 for h in hits if h['bkg_matched'])}")

    print("\n=== TOP SENDER DOMAINS ===")
    for dom, cnt in sorted(sender_stats.items(), key=lambda x: -x[1])[:20]:
        print(f"  {cnt:4d}  {dom}")

    print("\n=== PATTERN FREQUENCY ===")
    for pat, cnt in sorted(pattern_stats.items(), key=lambda x: -x[1]):
        print(f"  {cnt:4d}  {pat}")

    print("\n=== SAMPLE HITS (with Bkg match) ===")
    matched = [h for h in hits if h['bkg_matched']][:15]
    for h in matched:
        print(f"\n[{h['received']}] {h['folder']} | {h['domain']}")
        print(f"  Subject: {h['subject']}")
        print(f"  Bkg: {h['bkg_matched']} | Pattern: {h['pattern']}")

    print("\n=== SAMPLE HITS (no Bkg match, carrier-looking) ===")
    carrier_domains = ['one-line','oocl','zim.com','cma-cgm','hapag','msc.com','cosco','hmm21','evergreen','maersk','yangming','wanhai']
    unmatched = [h for h in hits if not h['bkg_matched'] and any(c in h['domain'] for c in carrier_domains)][:10]
    for h in unmatched:
        print(f"\n[{h['received']}] {h['folder']} | {h['domain']}")
        print(f"  Subject: {h['subject']}")
        print(f"  Pattern: {h['pattern']}")

    # Save CSV
    out = r"D:/NELSON/2. Areas/Engine_test/plans/reports/load-on-board-audit.csv"
    pd.DataFrame(hits).to_csv(out, index=False, encoding='utf-8-sig')
    print(f"\n[OK] Full report: {out}")


if __name__ == '__main__':
    main()
