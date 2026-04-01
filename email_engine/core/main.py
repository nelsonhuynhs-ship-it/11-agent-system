"""
Outlook Email Classification & CC Compliance System
====================================================
Author  : Senior Python / System Architect
Version : 1.0.0
Purpose : Automatically route Team Sunny inbox emails to per-member
          sub-folders and verify outbound CC compliance rules.

Architecture
------------
- Data  : rules.json  (org chart + required_cc, zero code changes needed)
- Logic : main.py     (this file, stateless service functions)

Two-Tier Routing Priority
--------------------------
Tier 1 (Active  – Sender match)  : Move + CC compliance check
Tier 2 (Passive – Recipient/CC)  : Move only (no compliance check)
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import sys
from datetime import time as dtime
from datetime import datetime
from pathlib import Path
from typing import Optional

import win32com.client  # pywin32

from notify import toast  # Windows system-tray notifications

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
RULES_FILE      = Path(__file__).parent / "rules.json"
INBOX_SCAN_LIMIT = 100          # Max emails scanned per run
TEAM_FOLDER_NAME = "TEAM SUNNY" # Top-level Outlook folder that must pre-exist

# ---------------------------------------------------------------------------
# Logging  –  console + rotating file (email_engine.log, 1 MB × 5 backups)
# ---------------------------------------------------------------------------
LOG_FILE = Path(__file__).parent / "email_engine.log"

_fmt     = logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")

_console = logging.StreamHandler(sys.stdout)
_console.setFormatter(_fmt)

_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_console, _file_handler])
log = logging.getLogger(__name__)


# ===========================================================================
# 1. CONFIG LAYER  –  Pure data loading, no business logic
# ===========================================================================

def load_rules(path: Path = RULES_FILE) -> dict:
    """
    Load and validate rules.json.

    Returns
    -------
    dict
        Raw config dict with keys: team_name, members.
    """
    if not path.exists():
        log.error("rules.json not found at: %s", path)
        sys.exit(1)

    with path.open(encoding="utf-8") as fh:
        config = json.load(fh)

    members = config.get("members", {})
    if not members:
        log.error("rules.json contains no members.")
        sys.exit(1)

    # Normalise all email keys and required_cc to lowercase for safe comparison
    normalised: dict = {}
    for email, data in members.items():
        key = email.strip().lower()
        data["required_cc"] = [e.strip().lower() for e in data.get("required_cc", [])]
        normalised[key] = data

    config["members"] = normalised
    log.info("Loaded %d member rules from %s", len(normalised), path.name)
    return config


# ===========================================================================
# 2. OUTLOOK HELPERS
# ===========================================================================

def get_outlook_namespace():
    """Connect to a running Outlook instance via COM and return the MAPI namespace."""
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        return outlook.GetNamespace("MAPI")
    except Exception as exc:
        log.error("Failed to connect to Outlook: %s", exc)
        sys.exit(1)


def resolve_smtp_address(recipient) -> Optional[str]:
    """
    Extract the Internet SMTP address from an Outlook Recipient object.

    Uses PR_SMTP_ADDRESS via PropertyAccessor to bypass Exchange Server X500
    addresses that appear on internal recipients.

    Parameters
    ----------
    recipient : win32com Recipient object

    Returns
    -------
    str | None
        Lowercased standard email address, or None if unresolvable.
    """
    try:
        pa = recipient.PropertyAccessor
        smtp = pa.GetProperty(PR_SMTP_ADDRESS)
        if smtp:
            return smtp.strip().lower()
    except Exception:
        pass

    # Fallback: attempt Address property directly (works for external senders)
    try:
        addr = recipient.Address
        if addr and "@" in addr:
            return addr.strip().lower()
    except Exception:
        pass

    return None


def get_sender_smtp(mail_item) -> Optional[str]:
    """
    Extract the sender's true SMTP address from a MailItem.

    Tries the SenderEmailAddress first (reliable for external mail), then
    falls back to PropertyAccessor on the Sender object for Exchange users.
    """
    try:
        addr = mail_item.SenderEmailAddress
        if addr and "@" in addr and not addr.startswith("/O="):
            return addr.strip().lower()
    except Exception:
        pass

    # Exchange internal sender: use Sender recipient object + PropertyAccessor
    try:
        sender_obj = mail_item.Sender
        if sender_obj:
            pa = sender_obj.PropertyAccessor
            smtp = pa.GetProperty(PR_SMTP_ADDRESS)
            if smtp:
                return smtp.strip().lower()
    except Exception:
        pass

    return None


def get_all_recipient_emails(mail_item) -> list[str]:
    """
    Return a deduplicated list of all SMTP addresses in To + CC fields.

    Parameters
    ----------
    mail_item : win32com MailItem

    Returns
    -------
    list[str]
        Lowercase SMTP addresses.
    """
    emails: list[str] = []
    try:
        for recipient in mail_item.Recipients:
            addr = resolve_smtp_address(recipient)
            if addr:
                emails.append(addr)
    except Exception as exc:
        log.debug("Error reading recipients: %s", exc)
    return list(set(emails))


# ===========================================================================
# 3. FOLDER MANAGEMENT
# ===========================================================================

def get_or_create_subfolder(parent_folder, name: str):
    """
    Return an Outlook MAPIFolder by name, creating it if it does not exist.

    Parameters
    ----------
    parent_folder : MAPIFolder
    name          : str  – Display name of the desired sub-folder.
    """
    try:
        return parent_folder.Folders[name]
    except Exception:
        pass  # Folder does not exist yet

    try:
        log.info("Creating sub-folder: '%s'", name)
        return parent_folder.Folders.Add(name)
    except Exception as exc:
        log.error("Cannot create folder '%s': %s", name, exc)
        return None


def _search_folder_recursive(parent_folder, target_name: str, depth: int = 0):
    """
    Recursively search for a folder by display name within a parent MAPIFolder.

    Parameters
    ----------
    parent_folder : MAPIFolder
    target_name   : str   – Exact display name to match (case-insensitive)
    depth         : int   – Current recursion depth (guards against deep trees)

    Returns
    -------
    MAPIFolder | None
    """
    if depth > 5:  # Safety guard: don't recurse too deep
        return None
    try:
        for folder in parent_folder.Folders:
            if folder.Name.strip().lower() == target_name.strip().lower():
                return folder
            # Recurse into sub-folders
            found = _search_folder_recursive(folder, target_name, depth + 1)
            if found:
                return found
    except Exception:
        pass
    return None


def resolve_team_folder(namespace, team_folder_name: str):
    """
    Locate the TEAM SUNNY folder with a 3-tier search strategy:

    Tier A : Direct child of the mailbox root (e.g. alongside Inbox)
    Tier B : Direct child of the default Inbox folder
    Tier C : Full recursive search across all stores

    This handles the common case where users place the folder *inside* Inbox.

    Parameters
    ----------
    namespace        : MAPI namespace
    team_folder_name : str – Expected display name (e.g. 'TEAM SUNNY')

    Returns
    -------
    MAPIFolder | None
    """
    for store in namespace.Stores:
        try:
            root = store.GetRootFolder()
        except Exception:
            continue

        # --- Tier A: root-level child (e.g. same level as Inbox) -------------
        try:
            folder = root.Folders[team_folder_name]
            log.info("Found '%s' at root level in store: %s", team_folder_name, store.DisplayName)
            return folder
        except Exception:
            pass

        # --- Tier B: direct child of Inbox ------------------------------------
        try:
            inbox = namespace.GetDefaultFolder(6)  # olFolderInbox = 6
            folder = inbox.Folders[team_folder_name]
            log.info("Found '%s' inside Inbox in store: %s", team_folder_name, store.DisplayName)
            return folder
        except Exception:
            pass

        # --- Tier C: recursive deep search ------------------------------------
        log.debug("Performing recursive folder search in store: %s", store.DisplayName)
        found = _search_folder_recursive(root, team_folder_name)
        if found:
            log.info("Found '%s' via recursive search in store: %s", team_folder_name, store.DisplayName)
            return found

    log.error(
        "Team folder '%s' not found in any Outlook store (searched root, Inbox, and all sub-folders).",
        team_folder_name,
    )
    return None


def build_member_folders(team_folder, members: dict) -> dict[str, object]:
    """
    Ensure one sub-folder exists per team member under the team folder.

    Parameters
    ----------
    team_folder : MAPIFolder
    members     : dict  (email → member config from rules.json)

    Returns
    -------
    dict  email → MAPIFolder  mapping
    """
    folder_map: dict[str, object] = {}
    for email, data in members.items():
        if data.get("skip_routing", False):
            log.info("Skipping folder creation for '%s' (skip_routing=true)", data["name"])
            continue
        folder_name = data["folder"]
        sub = get_or_create_subfolder(team_folder, folder_name)
        if sub:
            folder_map[email] = sub
    return folder_map


# ===========================================================================
# 4. CC COMPLIANCE ENGINE
# ===========================================================================

def check_cc_compliance(
    mail_item,
    sender_email: str,
    members: dict,
    recipient_emails: list[str],
) -> None:
    """
    Verify that a sent email contains all required_cc addresses for the sender.

    Logs a warning for every missing required recipient.

    Parameters
    ----------
    mail_item        : MAPIItem  (used for subject logging)
    sender_email     : str       Sender SMTP address (lowercase)
    members          : dict      Full member config from rules.json
    recipient_emails : list[str] All To + CC addresses already extracted
    """
    member_cfg    = members.get(sender_email, {})
    required_cc   = member_cfg.get("required_cc", [])
    sender_name   = member_cfg.get("name", sender_email)

    if not required_cc:
        # Leader / Mentor – no outbound CC constraint
        return

    recipient_set = set(recipient_emails)
    missing       = [cc for cc in required_cc if cc not in recipient_set]

    try:
        subject = mail_item.Subject or "(no subject)"
    except Exception:
        subject = "(unreadable subject)"

    if missing:
        log.warning(
            "Violation: Missing CC | Sender: %-20s | Subject: %s | Missing: %s",
            sender_name,
            subject[:60],
            ", ".join(missing),
        )
    else:
        log.info(
            "CC OK      | Sender: %-20s | Subject: %s",
            sender_name,
            subject[:60],
        )


# ===========================================================================
# 5. REPORT PROCESSING HOOK  (Extensibility Stub)
# ===========================================================================

def process_reports(mail_item, sender_email: str, member_cfg: dict) -> None:
    """
    Hook for future attachment / report processing logic.

    This function is intentionally a no-op stub. Extend it to:
    - Extract specific attachment file types (xlsx, pdf, csv …)
    - Save them to a configured network path
    - Trigger downstream ERP import workflows
    - Parse structured report data and write to a database

    Parameters
    ----------
    mail_item    : win32com MailItem
    sender_email : str  Lowercased sender SMTP
    member_cfg   : dict Member's config section from rules.json
    """
    # TODO: Implement attachment extraction when needed
    pass


# ===========================================================================
# 5b. SAVE .MSG TO LOCAL DISK (for data pipeline)
# ===========================================================================

MSG_PROJECT_ROOT = Path(__file__).parent.parent
MSG_OUTLOOK_DIR  = MSG_PROJECT_ROOT / 'outlook'


def save_msg_local(
    mail_item,
    folder_type: str,
    sub_name: str,
) -> Optional[Path]:
    """
    Save Outlook MailItem as .msg file to local disk for the data pipeline.

    Parameters
    ----------
    mail_item   : win32com MailItem
    folder_type : str   'TEAM SUNNY', 'CNEE', 'SHIPPER', 'AGENT', 'INTERNAL'
    sub_name    : str   Subfolder name (member name or customer name)

    Returns
    -------
    Path | None  — Path to the saved .msg file, or None on failure.
    """
    try:
        if folder_type == 'TEAM SUNNY':
            save_dir = MSG_OUTLOOK_DIR / 'TEAM_SUNNY' / sub_name.upper()
        else:
            save_dir = MSG_OUTLOOK_DIR / folder_type / sub_name.upper()

        save_dir.mkdir(parents=True, exist_ok=True)

        received = mail_item.ReceivedTime
        dt_str   = received.strftime('%Y%m%d_%H%M%S')
        subject  = mail_item.Subject or 'no_subject'
        slug     = re.sub(r'[^\w\s-]', '', subject)[:80].strip().replace(' ', '_')
        filename = f"{dt_str}__{slug}.msg"
        filepath = save_dir / filename

        mail_item.SaveAs(str(filepath), 3)   # 3 = olMSG format
        log.info("Saved .msg → %s", filepath.relative_to(MSG_PROJECT_ROOT))
        return filepath
    except Exception as e:
        log.error("SaveAs failed: %s", e)
        return None


# ===========================================================================
# 6. TWO-TIER ROUTING ENGINE
# ===========================================================================

def route_mail_item(
    mail_item,
    members: dict,
    folder_map: dict[str, object],
) -> bool:
    """
    Apply two-tier routing logic to a single MailItem.

    Tier 1 (Active  – Sender priority):
        If sender is a team member → move to their folder + CC compliance check.

    Tier 2 (Passive – Recipient/CC):
        If sender is NOT a team member but a recipient/CC is → move to that
        member's folder (first match wins; no compliance check).

    Parameters
    ----------
    mail_item  : win32com MailItem
    members    : dict             Member config keyed by email address
    folder_map : dict[str, obj]   Email → target MAPIFolder

    Returns
    -------
    bool  True if the item was routed, False if no match.
    """
    try:
        subject = mail_item.Subject or "(no subject)"
    except Exception:
        subject = "(unreadable)"

    # --- Extract addresses --------------------------------------------------
    sender_email     = get_sender_smtp(mail_item)
    recipient_emails = get_all_recipient_emails(mail_item)

    # -----------------------------------------------------------------------
    # TIER 1: Active – Sender is a known team member
    # -----------------------------------------------------------------------
    if sender_email and sender_email in members and not members[sender_email].get("skip_routing", False):
        target_folder = folder_map.get(sender_email)
        if target_folder:
            try:
                # CC compliance check BEFORE move (MailItem still accessible)
                check_cc_compliance(mail_item, sender_email, members, recipient_emails)

                # Report processing hook
                process_reports(mail_item, sender_email, members[sender_email])

                # Save .msg locally for data pipeline BEFORE move
                save_msg_local(mail_item, 'TEAM SUNNY', members[sender_email]['folder'])

                mail_item.Move(target_folder)
                log.info(
                    "Tier1 MOVE | %-15s → %-15s | %s",
                    members[sender_email]["name"],
                    members[sender_email]["folder"],
                    subject[:50],
                )
                return True
            except Exception as exc:
                log.error("Tier1 move failed for '%s': %s", subject[:40], exc)
        return False

    # -----------------------------------------------------------------------
    # TIER 2: Passive – A recipient/CC is a known team member
    # -----------------------------------------------------------------------
    for email in recipient_emails:
        if email in members and not members[email].get("skip_routing", False) and email in folder_map:
            target_folder = folder_map[email]
            try:
                # Save .msg locally for data pipeline BEFORE move
                save_msg_local(mail_item, 'TEAM SUNNY', members[email]['folder'])

                mail_item.Move(target_folder)
                log.info(
                    "Tier2 MOVE | recipient %-15s → %-15s | %s",
                    members[email]["name"],
                    members[email]["folder"],
                    subject[:50],
                )
                return True
            except Exception as exc:
                log.error("Tier2 move failed for '%s': %s", subject[:40], exc)
            break  # First matching member wins; stop after first move attempt

    return False


# ===========================================================================
# 7. MAIN SCAN LOOP
# ===========================================================================

def scan_inbox(namespace, members: dict, folder_map: dict) -> None:
    """
    Scan the MAPI Inbox and route the most recent INBOX_SCAN_LIMIT items.

    Iterates in reverse chronological order (newest first) so the most recent
    emails are processed regardless of total mailbox size.

    Parameters
    ----------
    namespace  : MAPI namespace object
    members    : dict   Loaded from rules.json
    folder_map : dict   email → MAPIFolder
    """
    inbox = namespace.GetDefaultFolder(6)  # olFolderInbox = 6
    items = inbox.Items
    items.Sort("[ReceivedTime]", True)     # Descending – newest first

    total   = items.Count
    limit   = min(total, INBOX_SCAN_LIMIT)
    routed  = 0
    skipped = 0

    log.info("=" * 70)
    log.info("Inbox scan started | Total items: %d | Scanning latest: %d", total, limit)
    log.info("=" * 70)

    # Outlook COM collections are 1-indexed; iterate from newest
    index = 1
    processed = 0

    while processed < limit:
        try:
            item = items[index]
        except IndexError:
            break  # No more items

        # Only process MailItems (skip Meeting Requests, Task items, etc.)
        if item.Class == 43:  # olMail = 43
            matched = route_mail_item(item, members, folder_map)
            if matched:
                routed += 1
                # After Move, the item is removed from Inbox collection;
                # index stays the same (next item shifts into current slot).
            else:
                skipped += 1
                index += 1
        else:
            index += 1

        processed += 1

    log.info("=" * 70)
    log.info("Scan complete | Routed: %d | Skipped/Unmatched: %d", routed, skipped)
    log.info("=" * 70)

    # ── Windows notification ────────────────────────────────────────────────
    if routed > 0:
        toast(
            "📧 Team Sunny – Scan xong",
            f"Đã phân loại {routed} email, bỏ qua {skipped}.",
            kind="info",
        )
    else:
        toast(
            "📧 Team Sunny – Scan xong",
            f"Không có email mới cần phân loại ({skipped} bỏ qua).",
            kind="none",
        )


# ===========================================================================
# 8. ENTRY POINT
# ===========================================================================

# ---------------------------------------------------------------------------
# Schedule window: only run between START_TIME and END_TIME (inclusive)
# ---------------------------------------------------------------------------
START_TIME = dtime(8, 0)   # 08:00 AM
END_TIME   = dtime(17, 30) # 05:30 PM


def main() -> None:
    """
    Entry point. Initialises all subsystems then triggers inbox scan.

    Call sequence:
        load_rules → connect Outlook → resolve team folder
        → build member sub-folders → scan inbox

    Note: A time-guard exits quietly when called outside START_TIME–END_TIME.
    This lets Windows Task Scheduler fire the trigger unconditionally every
    30 minutes while still respecting the 08:00–17:30 working-hours window.
    """
    now = datetime.now().time()
    if not (START_TIME <= now <= END_TIME):
        log.info(
            "Outside scheduled window (%s – %s). Current time: %s. Exiting.",
            START_TIME.strftime("%H:%M"),
            END_TIME.strftime("%H:%M"),
            now.strftime("%H:%M"),
        )
        return

    log.info("Email Classification & CC Compliance Engine starting …")

    # 1. Load data layer
    config  = load_rules()
    members = config["members"]
    team_name = config.get("team_name", TEAM_FOLDER_NAME)

    # 2. Connect to Outlook
    ns = get_outlook_namespace()  # exits with sys.exit(1) if Outlook not running

    # 3. Locate team root folder
    team_folder = resolve_team_folder(ns, team_name)
    if team_folder is None:
        toast("⚠️ Email Engine – Lỗi", f"Không tìm thấy folder '{team_name}' trong Outlook.", kind="error")
        sys.exit(1)

    # 4. Ensure per-member sub-folders exist
    folder_map = build_member_folders(team_folder, members)
    if not folder_map:
        log.error("No member folders could be resolved. Aborting.")
        sys.exit(1)

    log.info("Ready. Member folders resolved: %s", ", ".join(
        data["folder"] for data in members.values() if data["folder"]
    ))

    # 5. Run the scan
    scan_inbox(ns, members, folder_map)

    log.info("Engine run finished.")


if __name__ == "__main__":
    main()
