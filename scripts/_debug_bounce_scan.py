# -*- coding: utf-8 -*-
"""Debug: count real bounces in Inbox, compare with current scanner coverage."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import win32com.client
from datetime import datetime, timedelta

BROAD_NDR_SENDER = ['postmaster', 'mailer-daemon', 'daemon@', 'abuse@', 'bounce-', 'mdaemon']
BROAD_NDR_SUBJECT = ['undeliverable', 'delivery status', 'delivery failed', 'mail delivery',
                     'returned mail', 'failure notice', 'could not be delivered',
                     'rejected', 'bounce', 'not delivered']
BROAD_NDR_BODY = ['does not exist', 'user unknown', 'mailbox full', 'recipient rejected',
                  'address not found', 'invalid recipient', 'relay access denied']
CURRENT_POSTMASTER = ['postmaster@', 'mailer-daemon@', 'noreply@', 'no-reply@']
CURRENT_SUBJECT = ['delivery status notification', 'undelivered mail', 'undeliverable',
                   'mail delivery failed', 'returned mail', 'failure notice', 'delivery failure']

outlook = win32com.client.Dispatch('Outlook.Application').GetNamespace('MAPI')
inbox = outlook.GetDefaultFolder(6)
items = inbox.Items
items.Sort('[ReceivedTime]', True)

cutoff = datetime.now() - timedelta(days=30)

total = hits_sender = hits_subject = hits_body = hits_any = tagged = missed_by_current = 0
samples = []

for msg in items:
    try:
        if msg.Class != 43:
            continue
        rt = msg.ReceivedTime.replace(tzinfo=None)
        if rt < cutoff:
            break
        total += 1
        subj = (msg.Subject or '').lower()
        sender = (msg.SenderEmailAddress or '').lower()
        body = (msg.Body or '')[:2000].lower()

        match_sender = any(p in sender for p in BROAD_NDR_SENDER)
        match_subj = any(p in subj for p in BROAD_NDR_SUBJECT)
        match_body = any(p in body for p in BROAD_NDR_BODY)

        if match_sender: hits_sender += 1
        if match_subj: hits_subject += 1
        if match_body: hits_body += 1

        if match_sender or match_subj or match_body:
            hits_any += 1
            cats = (msg.Categories or '')
            if 'Nelson-Scanned' in cats:
                tagged += 1
            would_current = any(p in sender for p in CURRENT_POSTMASTER) or any(p in subj for p in CURRENT_SUBJECT)
            if not would_current:
                missed_by_current += 1
                if len(samples) < 12:
                    samples.append(f'{rt.strftime("%m-%d")} | {sender[:35]:35s} | {subj[:75]}')
    except Exception:
        continue

print(f'Total emails 30d: {total}')
print(f'NDR by broad sender: {hits_sender}')
print(f'NDR by broad subject: {hits_subject}')
print(f'NDR by body: {hits_body}')
print(f'NDR any match: {hits_any}')
print(f'Already tagged Nelson-Scanned: {tagged}')
print(f'MISSED by current scanner patterns: {missed_by_current}')
print()
print('=== Samples MISSED by current patterns ===')
for s in samples:
    print(f'  {s}')
