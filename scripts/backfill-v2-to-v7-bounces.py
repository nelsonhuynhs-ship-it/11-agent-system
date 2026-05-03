"""
Backfill bounce EMAIL_STATUS from legacy v2 xlsx into v7 SOT.

Reads cnee_master_v2_final.xlsx, finds rows where EMAIL_STATUS is in
DEAD_STATUSES, and propagates those statuses into contact_unified_v7.xlsx
on the CNEE sheet. Preserves SHIPPER sheet untouched.

Safety:
- Creates timestamped backup of v7 before write
- Atomic write via .tmp + os.replace
- Skips rows where v7 already has a dead status (do not downgrade)
- Dry-run preview prints before persist

Run: python scripts/backfill-v2-to-v7-bounces.py [--apply]
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

V2_PATH = Path(r"D:/OneDrive/NelsonData/email/cnee_master_v2_final.xlsx")
V7_PATH = Path(r"D:/OneDrive/NelsonData/email/contact_unified_v7.xlsx")

DEAD_STATUSES = {
    "HARD_BOUNCE", "DEAD", "INVALID", "NO_MX",
    "UNSUBSCRIBED", "SOFT_SUPPRESSED", "SPAM", "SOFT_BOUNCE",
}


def main(apply: bool) -> int:
    if not V2_PATH.exists() or not V7_PATH.exists():
        print(f"missing file: v2={V2_PATH.exists()} v7={V7_PATH.exists()}")
        return 1

    print(f"[1/5] reading v2 {V2_PATH.name}")
    v2 = pd.read_excel(V2_PATH, engine="openpyxl")
    v2_email = v2["EMAIL"].astype(str).str.strip().str.lower()
    v2_status = v2["EMAIL_STATUS"].astype(str).str.upper().str.strip()
    v2_dead = v2[v2_status.isin(DEAD_STATUSES)].copy()
    v2_dead["_email_lc"] = v2_email[v2_status.isin(DEAD_STATUSES)]
    v2_dead["_status_norm"] = v2_status[v2_status.isin(DEAD_STATUSES)]
    print(f"      v2 dead rows: {len(v2_dead)}")
    print("      v2 dead breakdown:")
    for k, v in v2_dead["_status_norm"].value_counts().items():
        print(f"        {k}: {v}")

    print(f"[2/5] reading v7 {V7_PATH.name}")
    xl = pd.ExcelFile(V7_PATH, engine="openpyxl")
    sheet_names = list(xl.sheet_names)
    sheets = {name: xl.parse(name) for name in sheet_names}
    xl.close()
    print(f"      sheets: {sheet_names}")

    if "CNEE" not in sheets:
        print("missing CNEE sheet in v7")
        return 1

    v7 = sheets["CNEE"]
    v7_email = v7["EMAIL"].astype(str).str.strip().str.lower()
    v7_status = v7["EMAIL_STATUS"].astype(str).str.upper().str.strip()
    email_to_idx: dict[str, int] = {}
    for idx, em in enumerate(v7_email):
        if em and em not in email_to_idx:
            email_to_idx[em] = idx

    print(f"      v7 CNEE rows: {len(v7)}")
    print("      v7 existing dead breakdown:")
    for k, v in v7_status[v7_status.isin(DEAD_STATUSES)].value_counts().items():
        print(f"        {k}: {v}")

    print("[3/5] computing diff")
    matched = 0
    to_patch: list[tuple[int, str, str]] = []
    not_found = 0
    already_dead = 0
    for _, row in v2_dead.iterrows():
        em = row["_email_lc"]
        new_status = row["_status_norm"]
        if not em or em == "nan":
            continue
        idx = email_to_idx.get(em)
        if idx is None:
            not_found += 1
            continue
        matched += 1
        current = v7_status.iat[idx]
        if current in DEAD_STATUSES:
            already_dead += 1
            continue
        to_patch.append((idx, em, new_status))

    print(f"      v2 dead emails matching v7: {matched}")
    print(f"      not found in v7: {not_found}")
    print(f"      already dead in v7 (skipped): {already_dead}")
    print(f"      to patch: {len(to_patch)}")

    if not to_patch:
        print("      nothing to do")
        return 0

    print("      preview first 10 patches:")
    for idx, em, st in to_patch[:10]:
        print(f"        [{idx}] {em} -> {st}")

    if not apply:
        print("[4/5] DRY-RUN — re-run with --apply to persist")
        return 0

    print(f"[4/5] backing up v7")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = V7_PATH.with_name(f"{V7_PATH.stem}.backfill-{ts}{V7_PATH.suffix}")
    shutil.copy2(V7_PATH, backup)
    print(f"      backup -> {backup.name} ({backup.stat().st_size:,} bytes)")

    print(f"[5/5] writing {len(to_patch)} patches atomically")
    for idx, _em, new_status in to_patch:
        v7.at[idx, "EMAIL_STATUS"] = new_status
    sheets["CNEE"] = v7

    tmp = V7_PATH.with_suffix(V7_PATH.suffix + ".tmp")
    with pd.ExcelWriter(tmp, engine="openpyxl") as writer:
        for name in sheet_names:
            sheets[name].to_excel(writer, sheet_name=name, index=False)
    os.replace(tmp, V7_PATH)
    print(f"      v7 updated -> {V7_PATH}")

    print()
    print("      new v7 dead breakdown:")
    final = pd.read_excel(V7_PATH, sheet_name="CNEE", engine="openpyxl")
    final_status = final["EMAIL_STATUS"].astype(str).str.upper().str.strip()
    for k, v in final_status[final_status.isin(DEAD_STATUSES)].value_counts().items():
        print(f"        {k}: {v}")
    return 0


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv
    sys.exit(main(apply_flag))
