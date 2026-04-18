"""
auto-discover-customer-rules.py
================================
Scan Outlook folders DIRECT/, FW/, CNEE/ and all their sub-folders.
For each customer sub-folder, sample recent emails and extract:
  - Unique sender emails (top 5 by frequency)
  - Unique sender domains
  - HBL/BKG-style prefix patterns from subjects

Output: customer_rules_v2.json
  - Merges manual rules from customer_rules.json (preserves existing fields)
  - Adds auto-discovered rules for new customers
  - Each auto-rule has "_auto_discovered": true marker for traceability

Usage: python scripts/auto-discover-customer-rules.py [--sample 30]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import io
from collections import Counter
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import win32com.client
import pythoncom

RULES_PATH = Path("D:/OneDrive/NelsonData/email/customer_rules.json")
OUT_PATH = Path("D:/OneDrive/NelsonData/email/customer_rules_v2.json")

TOP_FOLDERS = {
    "DIRECT": "DIRECT",
    "FWD": "FWD",
    "CNEE": "CNEE",
}

SKIP_SUBFOLDERS = {
    "IMPORT SHIPMENT", "Công Nợ",  # NAFOOD nested
    "HANKS", "Menards", "PFS", "FISHMAN",  # SRS WORLWIDE nested
    "HENGLI-MATBOOK",  # MATBOOK nested
    "BALANCE",  # SEAN nested in PUDONG (not in TOP_FOLDERS anyway)
}

PREFIX_RE = re.compile(r"\b([A-Z]{3,6})(\d{4,10})\b")


def scan_folder(folder, sample_size: int = 30) -> dict:
    """Sample recent emails, extract senders/domains/prefixes."""
    try:
        total = folder.Items.Count
    except Exception:
        return {"total": 0, "senders": [], "domains": [], "prefixes": []}
    if total == 0:
        return {"total": 0, "senders": [], "domains": [], "prefixes": []}

    items = folder.Items
    try:
        items.Sort("[ReceivedTime]", True)  # newest first
    except Exception:
        pass

    sender_counter: Counter = Counter()
    domain_counter: Counter = Counter()
    prefix_counter: Counter = Counter()

    taken = 0
    for i in range(1, total + 1):
        if taken >= sample_size:
            break
        try:
            m = items.Item(i)
            if m.Class != 43:  # olMail
                continue
            sender = (m.SenderEmailAddress or "").lower().strip()
            if sender and "@" in sender and not sender.startswith("/o="):
                sender_counter[sender] += 1
                domain = sender.split("@", 1)[1]
                domain_counter[domain] += 1
            subject = m.Subject or ""
            for pfx, _ in PREFIX_RE.findall(subject.upper())[:3]:
                prefix_counter[pfx] += 1
            taken += 1
        except Exception:
            continue

    return {
        "total": total,
        "sampled": taken,
        "senders": [s for s, _ in sender_counter.most_common(5)],
        "domains": [d for d, _ in domain_counter.most_common(5)],
        "prefixes": [p for p, c in prefix_counter.most_common(5) if c >= 2],
    }


def walk_top_folder(root, top_name: str, ctype: str, sample_size: int) -> dict[str, dict]:
    """Return {customer_name: scan_result_dict} for all sub-folders."""
    try:
        top = root.Folders[top_name]
    except Exception:
        print(f"  [WARN] top folder '{top_name}' not found in root")
        return {}

    results: dict[str, dict] = {}
    for sub in top.Folders:
        name = sub.Name.strip()
        if name in SKIP_SUBFOLDERS:
            continue
        r = scan_folder(sub, sample_size)
        r["type"] = ctype
        r["folder_name"] = name
        results[name] = r
        print(f"  [{ctype}] {name:30} total={r['total']:5} sampled={r.get('sampled',0):3}  senders={len(r['senders'])} domains={len(r['domains'])} prefixes={r['prefixes']}")
    return results


def build_merged_rules(existing: dict, discovered: dict[str, dict]) -> dict:
    """Merge discovered into existing. Preserve manual entries; add auto-discovered."""
    merged = dict(existing)
    if "customers" not in merged:
        merged["customers"] = {}

    added = 0
    enriched = 0
    for name, scan in discovered.items():
        # Use uppercase customer_id for consistency
        cid = name.upper()

        if cid in merged["customers"]:
            # Enrich existing — add any new senders/domains/prefixes not already there
            cust = merged["customers"][cid]
            before = (len(cust.get("seen_senders", [])),
                      len(cust.get("email_domains", [])),
                      len(cust.get("hbl_prefixes", [])))
            for s in scan["senders"]:
                cust.setdefault("seen_senders", [])
                if s not in cust["seen_senders"]:
                    cust["seen_senders"].append(s)
            for d in scan["domains"]:
                cust.setdefault("email_domains", [])
                if d not in cust["email_domains"]:
                    cust["email_domains"].append(d)
            for p in scan["prefixes"]:
                cust.setdefault("hbl_prefixes", [])
                if p not in cust["hbl_prefixes"]:
                    cust["hbl_prefixes"].append(p)
            after = (len(cust.get("seen_senders", [])),
                     len(cust.get("email_domains", [])),
                     len(cust.get("hbl_prefixes", [])))
            if after != before:
                enriched += 1
                cust["_enriched_at"] = "2026-04-18"
        else:
            # New customer — auto-add
            merged["customers"][cid] = {
                "type": scan["type"],
                "folder_name": scan["folder_name"],
                "priority": "NORMAL",
                "sla_hours": 4,
                "seen_senders": scan["senders"],
                "email_domains": scan["domains"],
                "hbl_prefixes": scan["prefixes"],
                "bkg_prefixes": [],
                "routes": [],
                "carrier_affinity": [],
                "_auto_discovered": True,
                "_discovered_at": "2026-04-18",
                "_sample_size": scan.get("sampled", 0),
            }
            added += 1

    merged["_meta"] = {
        "version": 2,
        "auto_discovered_run_at": "2026-04-18",
        "total_customers": len(merged["customers"]),
        "added_this_run": added,
        "enriched_this_run": enriched,
    }
    return merged, added, enriched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=30, help="Emails sampled per folder")
    args = parser.parse_args()

    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    inbox = ns.GetDefaultFolder(6)
    print(f"Scanning mailbox: {inbox.Parent.Name}")
    print(f"Customer folders live UNDER Inbox (not mailbox root)")
    print(f"Sample size per folder: {args.sample}")
    print()

    all_scans: dict[str, dict] = {}
    for top_name, ctype in TOP_FOLDERS.items():
        print(f"=== {top_name} ===")
        scans = walk_top_folder(inbox, top_name, ctype, args.sample)
        all_scans.update(scans)
        print()

    print(f"Total sub-folders scanned: {len(all_scans)}")
    print()

    # Merge with existing rules
    existing = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    merged, added, enriched = build_merged_rules(existing, all_scans)

    # Write output
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Wrote {OUT_PATH}")
    print(f"   - {merged['_meta']['total_customers']} total customers")
    print(f"   - {added} new auto-discovered")
    print(f"   - {enriched} existing enriched with new senders/domains/prefixes")


if __name__ == "__main__":
    main()
