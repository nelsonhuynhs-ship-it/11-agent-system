"""
clean-rules-prefixes.py
========================
Post-process customer_rules.json to remove ambiguous hbl_prefixes that appear
in multiple customers (port-code-like patterns shared across shippers).

Keeps prefixes that uniquely identify ONE customer.
Also blacklists well-known port codes explicitly.
"""
from __future__ import annotations
import json
from collections import Counter
from pathlib import Path

RULES_PATH = Path("D:/OneDrive/NelsonData/email/customer_rules.json")

# Explicit blacklist: these are port codes (origin/destination), not customer
# identifiers. Always strip from hbl_prefixes.
PORT_CODE_BLACKLIST = {
    # US destinations
    "PLAX", "PNYC", "PCHS", "POAK", "PHOU", "PSEA", "PTIW", "PLGB", "PBAL",
    "PSAV", "PMIA", "PNOR", "PORF", "PCHI", "PDAL", "PTAC", "PJAX",
    # Vietnam origins
    "SGN", "SGNG", "HPH", "HAN",
    # Generic/ambiguous
    "NELSON", "PUDONG",
    # Duplicate port prefixes (double-P prefix malformation)
    "PPLAX", "PPNYC",
}


def main():
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    customers = rules.get("customers", {})

    # Step 1: collect all prefixes per customer
    prefix_to_customers: dict[str, set] = {}
    for cid, cust in customers.items():
        for pfx in cust.get("hbl_prefixes", []):
            prefix_to_customers.setdefault(pfx, set()).add(cid)

    # Step 2: a prefix is "unique" if it appears in <=1 customer AND not blacklisted
    ambiguous = {p for p, owners in prefix_to_customers.items() if len(owners) > 1}
    blacklisted = PORT_CODE_BLACKLIST
    to_strip = ambiguous | blacklisted

    print(f"Ambiguous prefixes (used by ≥2 customers): {sorted(ambiguous)}")
    print(f"Blacklisted port codes: {sorted(blacklisted & set(prefix_to_customers.keys()))}")
    print(f"Total prefixes to strip: {len(to_strip)}")
    print()

    # Step 3: strip from each customer
    stripped_total = 0
    for cid, cust in customers.items():
        before = list(cust.get("hbl_prefixes", []))
        after = [p for p in before if p not in to_strip]
        if before != after:
            cust["hbl_prefixes"] = after
            stripped_total += len(before) - len(after)
            strip_list = [p for p in before if p in to_strip]
            print(f"  {cid:30} stripped: {strip_list}  kept: {after}")

    # Step 4: bump meta
    if "_meta" not in rules:
        rules["_meta"] = {}
    rules["_meta"]["prefix_cleaned_at"] = "2026-04-18"
    rules["_meta"]["prefixes_stripped_total"] = stripped_total
    rules["_meta"]["ambiguous_prefixes"] = sorted(ambiguous)
    rules["_meta"]["blacklisted_prefixes"] = sorted(blacklisted)

    # Step 5: write back
    RULES_PATH.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    print(f"✅ Wrote {RULES_PATH}")
    print(f"   Stripped {stripped_total} prefix entries across {len(customers)} customers.")


if __name__ == "__main__":
    main()
