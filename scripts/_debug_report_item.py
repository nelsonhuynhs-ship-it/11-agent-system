# -*- coding: utf-8 -*-
"""Inspect 1 ReportItem to understand its properties."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import win32com.client

outlook = win32com.client.Dispatch('Outlook.Application').GetNamespace('MAPI')
inbox = outlook.GetDefaultFolder(6)
items = inbox.Items
items.Sort('[ReceivedTime]', True)

for msg in items:
    try:
        if msg.Class != 46:
            continue
        print(f"=== ReportItem sample ===")
        print(f"Subject: {msg.Subject!r}")
        print(f"Sender: {getattr(msg, 'SenderName', '<N/A>')!r}")
        print(f"SenderSMTP: {getattr(msg, 'SenderEmailAddress', '<N/A>')!r}")
        print(f"ReceivedTime: {msg.ReceivedTime}")
        print(f"Categories: {getattr(msg, 'Categories', '') or '<empty>'!r}")
        print(f"Body (first 500 chars):")
        body = getattr(msg, 'Body', '') or ''
        print(body[:500])
        print(f"\nHas Move method: {hasattr(msg, 'Move')}")
        print(f"Has Save method: {hasattr(msg, 'Save')}")
        break
    except Exception as e:
        print(f"ERROR: {e}")
        continue
