# -*- coding: utf-8 -*-
"""
cnee_memory.py — Per-CNEE Markdown vault (Prospect Memory System)
=================================================================
Mirrors vault_writer.py pattern but for CNEE prospects (not shipments).

Vault structure:
    vault/cnee/{cnee_email_sanitized}/memory.md

Sanitisation:
    @  →  _at_
    /  →  _
    spaces, special chars → _ (safe for filesystem)

Idempotency:
    Each event block is guarded by an HTML comment:
        <!-- cnee_event:{source_msg_id}:{event_type} -->

Event types: SENT, OPENED, REPLIED, BOUNCED, AUTO_REPLIED, NOTE

Public API:
    append_event(cnee_email, event_type, structured_dict, narrative, source_msg_id) -> bool
    read_memory(cnee_email) -> dict  {markdown_text, structured_fields_merged, event_count, last_event_at}
    get_vault_path(cnee_email) -> Path
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── Event emoji map ──────────────────────────────────────────────────────────
_EVENT_EMOJI: dict[str, str] = {
    "SENT":         "📤",
    "OPENED":       "👁",
    "REPLIED":      "💬",
    "BOUNCED":      "⚠",
    "AUTO_REPLIED": "🤖",
    "NOTE":         "📝",
}

_VALID_EVENT_TYPES = frozenset(_EVENT_EMOJI.keys())


def _vault_root() -> Path:
    """Return vault/cnee root. Override via CNEE_VAULT_PATH env."""
    env = os.environ.get("CNEE_VAULT_PATH")
    if env:
        return Path(env)
    # Default: repo_root/vault/cnee
    return Path(__file__).parent.parent.parent / "vault" / "cnee"


def _sanitize_email(email: str) -> str:
    """Convert email to safe directory name.

    example@domain.com  →  example_at_domain.com
    user/name@host.com  →  user_name_at_host.com
    """
    clean = email.strip().lower()
    clean = clean.replace("@", "_at_")
    # Replace any characters that are not alphanumeric, dot, hyphen, underscore
    clean = re.sub(r"[^\w.\-]", "_", clean)
    # Collapse multiple underscores
    clean = re.sub(r"_+", "_", clean)
    return clean.strip("_")


def get_vault_path(cnee_email: str) -> Path:
    """Return the memory.md path for a CNEE email (does not create file)."""
    safe = _sanitize_email(cnee_email)
    return _vault_root() / safe / "memory.md"


def _marker(source_msg_id: str, event_type: str) -> str:
    """HTML comment marker used for deduplication."""
    return f"<!-- cnee_event:{source_msg_id}:{event_type} -->"


def _ensure_header(filepath: Path, cnee_email: str, first_seen: str) -> None:
    """Create memory.md with header if it does not exist."""
    if filepath.exists():
        return
    filepath.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# CNEE Memory · {cnee_email}\n\n"
        f"**First seen:** {first_seen}  \n"
        f"**Last updated:** {first_seen}\n\n"
        f"## Timeline\n\n"
    )
    filepath.write_text(header, encoding="utf-8")
    log.info("Created CNEE memory vault: %s", filepath)


def _update_last_updated(filepath: Path, ts: str) -> None:
    """Patch the **Last updated:** line in the header."""
    try:
        text = filepath.read_text(encoding="utf-8")
        updated = re.sub(
            r"\*\*Last updated:\*\* [\w\-:T \.UTC]+",
            f"**Last updated:** {ts}",
            text,
            count=1,
        )
        if updated != text:
            filepath.write_text(updated, encoding="utf-8")
    except Exception as exc:
        log.warning("Could not update last_updated in %s: %s", filepath, exc)


def append_event(
    cnee_email: str,
    event_type: str,
    structured: Optional[dict] = None,
    narrative: Optional[str] = None,
    source_msg_id: Optional[str] = None,
) -> bool:
    """Append an event block to the CNEE memory vault.

    Args:
        cnee_email:     Recipient email address (prospect / customer).
        event_type:     One of SENT, OPENED, REPLIED, BOUNCED, AUTO_REPLIED, NOTE.
        structured:     Structured dict (preferred_pods, preferred_carriers, etc.)
        narrative:      Human-readable summary (from LLM or manual note).
        source_msg_id:  Outlook entry_id or message hash (dedup key).

    Returns:
        True if block written, False if skipped (already exists or invalid input).
    """
    if not cnee_email:
        log.warning("append_event: empty cnee_email — skipping")
        return False

    event_type = (event_type or "").upper().strip()
    if event_type not in _VALID_EVENT_TYPES:
        log.warning("append_event: unknown event_type '%s' — skipping", event_type)
        return False

    filepath = get_vault_path(cnee_email)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Dedup check
    if source_msg_id and filepath.exists():
        try:
            existing = filepath.read_text(encoding="utf-8")
            if _marker(source_msg_id, event_type) in existing:
                log.debug("CNEE event already in vault: %s / %s / %s",
                          cnee_email, event_type, source_msg_id)
                return False
        except Exception as exc:
            log.warning("vault read error (continuing): %s", exc)

    # Ensure file + header exist
    _ensure_header(filepath, cnee_email, now_str)

    emoji = _EVENT_EMOJI.get(event_type, "🔹")
    safe_msg_id = source_msg_id or "nosrc"

    block_lines = [
        f"\n{_marker(safe_msg_id, event_type)}",
        f"### {now_str} · {event_type} {emoji}",
    ]

    # Structured fields block (JSON)
    if structured:
        clean_struct = {k: v for k, v in structured.items() if v is not None}
        if clean_struct:
            block_lines.append(
                f"\n```json\n{json.dumps(clean_struct, ensure_ascii=False, indent=2)}\n```"
            )

    # Narrative text
    if narrative:
        block_lines.append(f"\n> {narrative}")

    block_lines.append("\n---\n")
    block = "\n".join(block_lines)

    try:
        with filepath.open("a", encoding="utf-8") as fh:
            fh.write(block)
    except Exception as exc:
        log.error("vault write error for %s: %s", cnee_email, exc)
        return False

    _update_last_updated(filepath, now_str)
    log.info("CNEE vault append: %s ← %s", cnee_email, event_type)
    return True


def read_memory(cnee_email: str) -> dict[str, Any]:
    """Read vault memory for a CNEE.

    Returns:
        dict with keys:
            markdown_text       : str  (full vault content)
            structured_fields   : dict (last known structured values merged from all events)
            event_count         : int
            last_event_at       : str  (ISO-ish UTC string from file header)
            exists              : bool
    """
    if not cnee_email:
        return _empty_memory()

    filepath = get_vault_path(cnee_email)
    if not filepath.exists():
        return _empty_memory()

    try:
        text = filepath.read_text(encoding="utf-8")
    except Exception as exc:
        log.warning("vault read error for %s: %s", cnee_email, exc)
        return _empty_memory()

    # Count events by counting markers
    event_count = len(re.findall(r"<!-- cnee_event:", text))

    # Extract last_updated from header
    m = re.search(r"\*\*Last updated:\*\*\s*([\w\-:T \.UTC]+)", text)
    last_event_at = m.group(1).strip() if m else ""

    # Merge structured JSON blocks (later events win)
    structured_merged: dict = {}
    for json_block in re.findall(r"```json\n(.*?)\n```", text, re.DOTALL):
        try:
            d = json.loads(json_block)
            if isinstance(d, dict):
                # Only update with non-null values from newer events
                structured_merged.update({k: v for k, v in d.items() if v is not None})
        except (json.JSONDecodeError, ValueError):
            pass

    return {
        "markdown_text": text,
        "structured_fields": structured_merged,
        "event_count": event_count,
        "last_event_at": last_event_at,
        "exists": True,
    }


def _empty_memory() -> dict[str, Any]:
    return {
        "markdown_text": "",
        "structured_fields": {},
        "event_count": 0,
        "last_event_at": "",
        "exists": False,
    }
