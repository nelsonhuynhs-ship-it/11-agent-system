# -*- coding: utf-8 -*-
"""Prove hypothesis: MS NDR is ReportItem (Class 46), not MailItem (43)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import win32com.client

outlook = win32com.client.Dispatch('Outlook.Application').GetNamespace('MAPI')
inbox = outlook.GetDefaultFolder(6)

print('=== Class distribution in Inbox ===')
class_count = {}
sample_by_class = {}
for msg in inbox.Items:
    try:
        c = getattr(msg, 'Class', None)
        class_count[c] = class_count.get(c, 0) + 1
        if c not in sample_by_class:
            sample_by_class[c] = {
                'subject': getattr(msg, 'Subject', '') or '',
                'sender': getattr(msg, 'SenderName', '') or '<N/A>',
            }
    except Exception:
        continue

for c, n in sorted(class_count.items()):
    sample = sample_by_class.get(c, {})
    print(f'  Class {c}: {n} items  | Sample: {sample.get("sender","")[:25]:25s} | {sample.get("subject","")[:70]}')

# OlObjectClass reference
CLASS_NAMES = {
    43: 'olMail (normal)',
    46: 'olReport (NDR/DSN)',
    53: 'olAppointment',
    26: 'olContact',
    48: 'olMeeting',
    40: 'olDocument',
}
print('\n=== Class reference ===')
for c in sorted(class_count.keys()):
    print(f'  Class {c} = {CLASS_NAMES.get(c, "unknown")}')
