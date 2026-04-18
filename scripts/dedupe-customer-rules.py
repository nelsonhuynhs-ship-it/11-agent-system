"""
dedupe-customer-rules.py
=========================
Remove duplicate customer entries where manual rule key (short) conflicts
with auto-discovered folder name (full). Keep the one with folder_name set
(i.e. the auto-discovered entry that matches the actual Outlook folder).

Also case-normalize: lowercase-case manual keys like 'Nafood' merged into
UPPERCASE version from auto-discovery.
"""
from __future__ import annotations
import json
from pathlib import Path

RULES_PATH = Path("D:/OneDrive/NelsonData/email/customer_rules.json")

# Manual duplicates to delete — their auto-discovered counterpart covers them
DUPLICATES_TO_REMOVE = {
    "SIRI",        # auto has SIRI LOG
    "PANDA",       # auto has PANDA GROUP
    "Nafood",      # auto has NAFOOD (case-normalized)
}


def main():
    rules = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    customers = rules["customers"]

    removed = []
    merged = {}

    # Case-insensitive key map
    lower_map = {cid.lower(): cid for cid in customers.keys()}

    for dup in DUPLICATES_TO_REMOVE:
        if dup in customers:
            cust = customers[dup]
            # Find the auto-discovered full-name equivalent
            for full in customers.keys():
                if full == dup:
                    continue
                if dup.lower() in full.lower() or full.lower() in dup.lower():
                    # Merge seen_senders, domains, prefixes into the full entry
                    full_cust = customers[full]
                    for field in ("seen_senders", "email_domains", "hbl_prefixes", "bkg_prefixes"):
                        fv = full_cust.setdefault(field, [])
                        for x in cust.get(field, []):
                            if x not in fv:
                                fv.append(x)
                    # Preserve priority/sla from manual if higher
                    if cust.get("priority") == "KEY":
                        full_cust["priority"] = "KEY"
                        full_cust["sla_hours"] = cust.get("sla_hours", full_cust.get("sla_hours", 4))
                    merged.setdefault(dup, []).append(full)
                    break
            del customers[dup]
            removed.append(dup)

    print(f"Removed {len(removed)} duplicate entries: {removed}")
    print(f"Merged data into: {merged}")
    print(f"Total customers now: {len(customers)}")

    rules.setdefault("_meta", {})["deduped_at"] = "2026-04-18"
    rules["_meta"]["duplicates_removed"] = removed

    RULES_PATH.write_text(
        json.dumps(rules, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ Wrote {RULES_PATH}")


if __name__ == "__main__":
    main()
