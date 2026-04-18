# -*- coding: utf-8 -*-
"""
Nelson Customer Sort — Pass 2 after MenteeSort.
Move emails of Nelson's direct customers from Inbox root to DIRECT/FW sub-folders.
Reads customer_rules.json from OneDrive.

Match priority per email:
  1. sender email exact match in seen_senders[]
  2. sender domain in email_domains[]
  3. hbl_prefix or bkg_prefix regex match in subject + body[:500]
  4. company keyword from detection_rules.keywords in subject+body

Type to folder mapping:
  DIRECT → DIRECT/{customer_id}
  FWD    → FW/{customer_id}
  CNEE   → CNEE/{customer_id}  (skip for now — folder may not exist)
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────
RULES_PATH = Path("D:/OneDrive/NelsonData/email/customer_rules.json")

# Maps customer type → top-level Outlook folder name
TYPE_TO_FOLDER: dict[str, str] = {
    "DIRECT": "DIRECT",
    "FWD":    "FWD",   # Actual Outlook folder name (not "FW")
    "CNEE":   "CNEE",
}

# Generic email providers — never match as domain alone (too ambiguous).
# P1 sender exact still works for these; P2 domain is skipped.
GENERIC_EMAIL_DOMAINS: set[str] = {
    "gmail.com", "yahoo.com", "yahoo.com.vn", "hotmail.com", "outlook.com",
    "live.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com",
    "163.com", "qq.com", "126.com", "foxmail.com",
}

MAX_ITEMS_PER_RUN = 200

# Outlook MailItem class constant
OL_MAIL_CLASS = 43


# ==============================================================================
# 1. LOAD RULES
# ==============================================================================

def load_rules() -> dict:
    """Load customer_rules.json from OneDrive.

    Returns the parsed dict on success.
    Raises FileNotFoundError if the file is missing so the caller can
    handle gracefully (skip job, log error, Telegram alert).
    """
    if not RULES_PATH.exists():
        raise FileNotFoundError(
            f"customer_rules.json not found: {RULES_PATH}\n"
            "Check OneDrive sync status."
        )
    text = RULES_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    customers = data.get("customers", {})
    log.info("[customer_sort] Loaded rules: %d customers", len(customers))
    return data


# ==============================================================================
# 2. SENDER HELPERS
# ==============================================================================

PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"


def _get_sender_smtp(msg) -> str:
    """Extract the true SMTP sender address from an Outlook MailItem."""
    try:
        addr = msg.SenderEmailAddress
        if addr and "@" in addr and not addr.startswith("/O="):
            return addr.strip().lower()
    except Exception:
        pass

    # Exchange internal sender — use PropertyAccessor
    try:
        sender_obj = msg.Sender
        if sender_obj:
            pa = sender_obj.PropertyAccessor
            smtp = pa.GetProperty(PR_SMTP_ADDRESS)
            if smtp:
                return smtp.strip().lower()
    except Exception:
        pass

    return ""


# ==============================================================================
# 3. MATCH ENGINE
# ==============================================================================

def match_customer(
    sender_smtp: str,
    subject: str,
    body_snippet: str,
    rules: dict,
) -> tuple[Optional[str], Optional[str]]:
    """Match an email against customer rules.

    Parameters
    ----------
    sender_smtp   : lowercase SMTP address of sender
    subject       : email subject string
    body_snippet  : first 500 chars of body
    rules         : parsed customer_rules.json dict

    Returns
    -------
    (customer_id, type)  e.g. ("PANDA", "FWD")
    (None, None)         if no match
    """
    customers = rules.get("customers", {})
    search_text = f"{subject} {body_snippet}".lower()

    sender_domain = sender_smtp.split("@")[-1] if "@" in sender_smtp else ""

    for cid, cust in customers.items():
        ctype = cust.get("type", "")
        # Only process types we have folder mappings for
        if ctype not in TYPE_TO_FOLDER:
            continue

        # ── Priority 1: exact sender match ─────────────────────────────────
        seen = [s.strip().lower() for s in cust.get("seen_senders", [])]
        if seen and sender_smtp and sender_smtp in seen:
            log.debug("[customer_sort] Match P1 (sender exact): %s → %s", sender_smtp, cid)
            return cid, ctype

        # ── Priority 2: sender domain match (skip generic free-email providers) ──
        domains = [d.strip().lower() for d in cust.get("email_domains", [])]
        if (domains and sender_domain
                and sender_domain in domains
                and sender_domain not in GENERIC_EMAIL_DOMAINS):
            log.debug("[customer_sort] Match P2 (domain): %s → %s", sender_domain, cid)
            return cid, ctype

        # ── Priority 3: HBL/BKG prefix regex in subject+body ───────────────
        prefixes = cust.get("hbl_prefixes", []) + cust.get("bkg_prefixes", [])
        for prefix in prefixes:
            # Match prefix followed by digits, e.g. PELP12345 or HANG-2026-01
            pattern = rf"\b{re.escape(prefix.upper())}\w*\d"
            if re.search(pattern, subject.upper() + " " + body_snippet[:500].upper()):
                log.debug("[customer_sort] Match P3 (prefix %s): → %s", prefix, cid)
                return cid, ctype

    # ── Priority 4: detection_rules keywords (cross-customer fallback) ───────
    detection = rules.get("detection_rules", {})
    for dtype, drule in detection.items():
        # dtype = "FWD" or "DIRECT"
        if dtype not in TYPE_TO_FOLDER:
            continue
        for kw in drule.get("keywords", []):
            kw_lower = kw.strip().lower()
            if not kw_lower:
                continue
            if kw_lower in search_text:
                # Find which customer this keyword belongs to
                cid = _find_customer_for_keyword(kw_lower, dtype, customers)
                if cid:
                    log.debug(
                        "[customer_sort] Match P4 (keyword '%s'): → %s", kw_lower, cid
                    )
                    return cid, dtype

    return None, None


def _find_customer_for_keyword(
    kw_lower: str,
    dtype: str,
    customers: dict,
) -> Optional[str]:
    """Map a detection keyword back to a specific customer_id.

    Simple heuristic: keyword is a substring of customer_id (case-insensitive).
    Returns None if ambiguous or not found — conservative to avoid false positives.
    """
    matches = []
    for cid, cust in customers.items():
        if cust.get("type", "") != dtype:
            continue
        if kw_lower in cid.lower():
            matches.append(cid)
        # Also check notes field
        elif kw_lower in cust.get("notes", "").lower():
            matches.append(cid)

    if len(matches) == 1:
        return matches[0]
    # Multiple or zero matches — do not move, avoid false positive
    return None


# ==============================================================================
# 4. OUTLOOK FOLDER NAVIGATION
# ==============================================================================

def navigate_folder(root_folder, path: str):
    """Navigate from root_folder through a slash-separated folder path.

    Parameters
    ----------
    root_folder : Outlook MAPIFolder (mailbox root, NOT Inbox)
    path        : e.g. "DIRECT/Nafood" or "FW/PANDA"

    Returns
    -------
    MAPIFolder if found, None otherwise (logs warning).
    """
    parts = [p.strip() for p in path.split("/") if p.strip()]
    current = root_folder
    for part in parts:
        found = _find_child_folder(current, part)
        if found is None:
            log.warning("[customer_sort] Folder segment not found: '%s' in path '%s'", part, path)
            return None
        current = found
    return current


def _find_child_folder(parent_folder, name: str):
    """Case-insensitive search for a direct child folder by name."""
    name_lower = name.strip().lower()
    try:
        for folder in parent_folder.Folders:
            if folder.Name.strip().lower() == name_lower:
                return folder
    except Exception as exc:
        log.debug("[customer_sort] Error iterating folders under '%s': %s", name, exc)
    return None


# ==============================================================================
# 5. MAIN RUN FUNCTION
# ==============================================================================

def run(dry_run: bool = False) -> dict:
    """Scan Inbox root and move customer emails to DIRECT/FW sub-folders.

    Parameters
    ----------
    dry_run : if True, log "Would move" without actually moving anything.

    Returns
    -------
    dict with keys:
        status         : "ok" | "error"
        moved_direct   : int — emails moved to DIRECT/
        moved_fw       : int — emails moved to FW/
        skipped        : int — emails in Inbox root, no match
        errors         : int — per-email exceptions caught
        total_scanned  : int
        error           : str (only on top-level failure)
    """
    result: dict = {
        "status":       "ok",
        "moved_direct": 0,
        "moved_fw":     0,
        "skipped":      0,
        "errors":       0,
        "total_scanned": 0,
    }

    # ── Load rules ────────────────────────────────────────────────────────────
    try:
        rules = load_rules()
    except FileNotFoundError as exc:
        log.error("[customer_sort] %s", exc)
        result["status"] = "error"
        result["error"]  = str(exc)
        return result
    except Exception as exc:
        log.error("[customer_sort] Failed to load rules: %s", exc)
        result["status"] = "error"
        result["error"]  = str(exc)
        return result

    # ── Connect to Outlook ────────────────────────────────────────────────────
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns      = outlook.GetNamespace("MAPI")
        inbox   = ns.GetDefaultFolder(6)       # olFolderInbox = 6
        # Mailbox root is the parent of Inbox — DIRECT/FW live here
        mailbox_root = inbox.Parent
    except Exception as exc:
        log.error("[customer_sort] Outlook COM connection failed: %s", exc)
        result["status"] = "error"
        result["error"]  = str(exc)
        return result

    # ── Get inbox.Items snapshot ──────────────────────────────────────────────
    # Only scan Inbox root — NOT sub-folders (idempotency: already-moved items
    # are in sub-folders and will not appear in inbox.Items).
    # We snapshot the collection as a list to avoid COM iteration issues after
    # Move() removes items from the live collection.
    try:
        items_snapshot = _snapshot_inbox_root(inbox, MAX_ITEMS_PER_RUN)
    except Exception as exc:
        log.error("[customer_sort] Failed to snapshot Inbox: %s", exc)
        result["status"] = "error"
        result["error"]  = str(exc)
        return result

    log.info(
        "[customer_sort] Scanning %d Inbox root items (cap %d)%s",
        len(items_snapshot),
        MAX_ITEMS_PER_RUN,
        " [DRY RUN]" if dry_run else "",
    )

    # ── Process each item ─────────────────────────────────────────────────────
    for msg in items_snapshot:
        result["total_scanned"] += 1
        try:
            _process_item(msg, rules, inbox, dry_run, result)
        except Exception as exc:
            result["errors"] += 1
            try:
                subj = msg.Subject[:60]
            except Exception:
                subj = "(unreadable)"
            log.error("[customer_sort] Error processing '%s': %s", subj, exc)

    # ── Summary log ───────────────────────────────────────────────────────────
    log.info(
        "[customer_sort] Done. DIRECT: %d, FW: %d, Skipped: %d, Errors: %d (of %d scanned)",
        result["moved_direct"],
        result["moved_fw"],
        result["skipped"],
        result["errors"],
        result["total_scanned"],
    )
    return result


# ==============================================================================
# 6. HELPERS
# ==============================================================================

def _snapshot_inbox_root(inbox, cap: int) -> list:
    """Return up to `cap` MailItems from Inbox root as a Python list snapshot.

    Sorting newest-first ensures recent emails are processed within the cap.
    We build a list so Move() operations on later items don't shift COM indices.
    """
    items = inbox.Items
    items.Sort("[ReceivedTime]", True)   # newest first

    snapshot = []
    index = 1
    total = items.Count
    while index <= total and len(snapshot) < cap:
        try:
            item = items[index]
            if item.Class == OL_MAIL_CLASS:
                # Skip drafts (unsent items that landed in Inbox via send error)
                try:
                    if not item.Sent:
                        index += 1
                        continue
                except Exception:
                    pass
                snapshot.append(item)
        except Exception:
            pass
        index += 1

    return snapshot


def _process_item(msg, rules: dict, inbox, dry_run: bool, result: dict) -> None:
    """Classify and optionally move a single MailItem."""
    try:
        subject = msg.Subject or ""
    except Exception:
        subject = ""

    try:
        body_snippet = (msg.Body or "")[:500]
    except Exception:
        body_snippet = ""

    sender = _get_sender_smtp(msg)

    cid, ctype = match_customer(sender, subject, body_snippet, rules)

    if cid is None:
        result["skipped"] += 1
        return

    folder_root = TYPE_TO_FOLDER[ctype]   # "DIRECT" or "FW"
    folder_path = f"{folder_root}/{cid}"

    # Folders DIRECT/FW/CNEE live UNDER Inbox (not mailbox root).
    target = navigate_folder(inbox, folder_path)
    if target is None:
        log.warning(
            "[customer_sort] Target folder '%s' not found — leaving '%s' in Inbox",
            folder_path,
            subject[:60],
        )
        result["skipped"] += 1
        return

    if dry_run:
        log.info(
            "[DRY] Would move → %s | sender=%s | subject=%s",
            folder_path,
            sender or "(unknown)",
            subject[:70],
        )
    else:
        msg.Move(target)
        log.info(
            "[customer_sort] MOVED → %s | %s",
            folder_path,
            subject[:70],
        )

    # Update counters
    if ctype == "DIRECT":
        result["moved_direct"] += 1
    elif ctype == "FWD":
        result["moved_fw"] += 1
