# -*- coding: utf-8 -*-
"""Consolidate knowledge/ JSON files into structured email_knowledge.parquet."""
import io, sys, json, re, os
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
elif sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
import pandas as pd
from pathlib import Path

# Load org_rules
org_rules = json.loads(Path(r'D:\NELSON\2. Areas\PricingSystem\Engine_test\email_engine\core\org_rules.json').read_text(encoding='utf-8'))
email_lookup = org_rules.get('email_lookup', {})
mentee_emails = set(email_lookup.get('mentee_emails', []))
sale_emails = set(email_lookup.get('sale_emails', []))
doc_emails = set(email_lookup.get('doc_emails', []))
cs_emails = set(email_lookup.get('cs_emails', []))
pricing_emails = set(email_lookup.get('pricing_emails', []))
accounting_emails = set(email_lookup.get('accounting_emails', []))

def get_department(email):
    e = email.lower().strip()
    if e in sale_emails: return 'sale'
    if e in doc_emails: return 'doc'
    if e in cs_emails: return 'cs'
    if e in pricing_emails: return 'pricing'
    if e in accounting_emails: return 'accounting'
    return 'external'

customers = org_rules.get('customer_identification', {}).get('known_customers', {})
def detect_customer(text):
    text_lo = text.lower()
    for name, data in customers.items():
        for kw in data.get('keywords', []):
            if kw.lower() in text_lo:
                return name
    return ''

hbl_re = re.compile(r'\b(P(?:NYC|SAV|HOU|DEN|CHS|SEA|OMA|YTO|ELP|MAN|LAX|OAK|BAL|ORD|ATL|MSP)\d{7,12})\b', re.I)
bkg_re = re.compile(r'\bBKG[\s#]*([A-Z0-9]{5,12})\b', re.I)

def extract_ids(text):
    hbls = hbl_re.findall(text.upper())
    bkgs = bkg_re.findall(text.upper())
    return '|'.join(set(hbls)) if hbls else '', '|'.join(set(bkgs)) if bkgs else ''

# Process all JSON files
kdir = Path(r'D:\NELSON\2. Areas\PricingSystem\Engine_test\Pricing_Engine\data\knowledge')
records = []
for f in kdir.glob('*.json'):
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        subject = data.get('subject', '')
        sender = data.get('sender', '')
        date_str = data.get('date', '')
        body = data.get('body_preview', '')

        hbl, bkg = extract_ids(subject)
        customer = detect_customer(subject)
        dept = get_department(sender)
        mentee = sender if sender.lower().strip() in mentee_emails else ''

        records.append({
            'date': date_str,
            'subject': subject[:120],
            'sender': sender,
            'department': dept,
            'mentee_pic': mentee,
            'customer': customer,
            'hbl': hbl,
            'bkg': bkg,
            'type': data.get('type', ''),
            'body_preview': body[:200] if body else '',
            'source_file': f.name,
        })
    except Exception:
        pass

df = pd.DataFrame(records)
print(f'Total emails processed: {len(df)}')

print(f'\nBy department:')
for dept, cnt in df['department'].value_counts().items():
    print(f'  {dept}: {cnt}')

print(f'\nBy customer (top 10):')
for cust, cnt in df['customer'].value_counts().head(10).items():
    label = cust if cust else '(unidentified)'
    print(f'  {label}: {cnt}')

print(f'\nMentees active:')
mentee_df = df[df['mentee_pic'] != '']
for m, cnt in mentee_df['mentee_pic'].value_counts().items():
    print(f'  {m}: {cnt} emails')

print(f'\nIdentifiers found:')
print(f'  With HBL: {(df["hbl"] != "").sum()}')
print(f'  With BKG: {(df["bkg"] != "").sum()}')

# Dedup by (date, subject, sender)
before = len(df)
df = df.drop_duplicates(subset=['date', 'subject', 'sender'], keep='last')
print(f'\nDedup: {before} -> {len(df)} (removed {before - len(df)})')

# Save
out = kdir.parent / 'email_knowledge.parquet'
df.to_parquet(out, index=False)
print(f'Saved: email_knowledge.parquet ({len(df)} rows, {out.stat().st_size / 1024:.0f} KB)')
