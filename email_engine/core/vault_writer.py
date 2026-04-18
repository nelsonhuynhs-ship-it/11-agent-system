# -*- coding: utf-8 -*-
"""
vault_writer.py — Markdown Vault Writer for Shipment Brain  v1.0
=================================================================
Appends shipment lifecycle events to per-shipment Markdown files
and regenerates _index.md per customer folder.

Vault structure:
    vault/customers/{customer_id}/{shipment_ref}.md   <- per-shipment timeline
    vault/customers/{customer_id}/_index.md           <- customer shipment list

Idempotency:
    Each event block is guarded by an HTML comment marker:
        <!-- event:{source_msg_id}:{event_type} -->
    If the marker already exists in the file, the block is skipped.

Usage:
    from email_engine.core.vault_writer import append_event, regen_index

    append_event(
        customer_id="PANDA",
        shipment_ref="HPL2604001",
        event_dict={...},         # from llm_client.extract()
        narrative_text="...",     # optional human-readable summary
        source_msg_id="ABCD1234",
        source_filename="booking_confirm.msg",
    )
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# ─── Event emoji map ──────────────────────────────────────────────────────────
_EVENT_EMOJI: dict[str, str] = {
    "BKG_ISSUED":           "📋",
    "DRAFT_BL_ISSUED":      "📄",
    "DRAFT_BL_CONFIRMED":   "✅",
    "LOADED":               "🚢",
    "ATD":                  "⛵",
    "DN_SENT":              "📬",
    "INVOICE_ISSUED":       "🧾",
    "PAYMENT_REQUESTED":    "💳",
    "PAYMENT_CONFIRMED":    "💚",
    "COMPLETED":            "🏁",
}

_RISK_BANNER = "> ⚠ **RISK FLAGGED** — review required\n"


def _vault_root() -> Path:
    """Return vault root directory. Override via SHIPMENT_VAULT_PATH env."""
    env = os.environ.get("SHIPMENT_VAULT_PATH")
    if env:
        return Path(env)
    # Default: repo_root/vault
    return Path(__file__).parent.parent.parent / "vault"


def _customer_dir(customer_id: str) -> Path:
    return _vault_root() / "customers" / customer_id


def _shipment_file(customer_id: str, shipment_ref: str) -> Path:
    return _customer_dir(customer_id) / f"{shipment_ref}.md"


def _index_file(customer_id: str) -> Path:
    return _customer_dir(customer_id) / "_index.md"


def _marker(source_msg_id: str, event_type: str) -> str:
    """Unique HTML comment used to detect if event block already written."""
    return f"<!-- event:{source_msg_id}:{event_type} -->"


def _ensure_shipment_header(
    filepath: Path,
    shipment_ref: str,
    customer_id: str,
    customer_name: Optional[str],
    carrier: Optional[str],
    pol: Optional[str],
    pod: Optional[str],
    svc_type: Optional[str],
    first_seen: str,
) -> None:
    """
    Create the shipment file with header block if it does not exist.
    Never overwrites an existing file.
    """
    if filepath.exists():
        return

    filepath.parent.mkdir(parents=True, exist_ok=True)

    lane = f"{pol or '?'} → {pod or '?'}"
    carrier_str = carrier or "Unknown"
    svc_str = svc_type or "—"
    cname = customer_name or customer_id

    header = (
        f"# {shipment_ref} · {cname}\n\n"
        f"**Lane:** {lane} · **Carrier:** {carrier_str} · **Svc:** {svc_str}  \n"
        f"**First seen:** {first_seen} · **Last update:** {first_seen}\n\n"
        f"## Timeline\n\n"
    )
    filepath.write_text(header, encoding="utf-8")
    log.info("Created vault file: %s", filepath)


def _update_header_last_update(filepath: Path, last_update: str) -> None:
    """Patch the **Last update:** line in the file header."""
    try:
        text = filepath.read_text(encoding="utf-8")
        import re
        updated = re.sub(
            r"\*\*Last update:\*\* [\w\-:T ]+",
            f"**Last update:** {last_update}",
            text,
            count=1,
        )
        if updated != text:
            filepath.write_text(updated, encoding="utf-8")
    except Exception as exc:
        log.warning("Could not update header timestamp in %s: %s", filepath, exc)


def append_event(
    customer_id: str,
    shipment_ref: str,
    event_dict: dict,
    narrative_text: Optional[str] = None,
    source_msg_id: Optional[str] = None,
    source_filename: Optional[str] = None,
    customer_name: Optional[str] = None,
    carrier: Optional[str] = None,
    pol: Optional[str] = None,
    pod: Optional[str] = None,
    svc_type: Optional[str] = None,
) -> bool:
    """
    Append a lifecycle event block to the shipment vault file.

    Args:
        customer_id:    folder key (e.g. "PANDA")
        shipment_ref:   shipment identifier (e.g. "HPL2604001")
        event_dict:     dict from llm_client.extract() — must have event_type
        narrative_text: optional prose from LLM synthesis
        source_msg_id:  Outlook entry_id or msg filename hash (dedup key)
        source_filename: original .msg filename for display link
        customer_name, carrier, pol, pod, svc_type: metadata for header

    Returns:
        True if block written, False if skipped (already exists or invalid input)
    """
    event_type = event_dict.get("event_type")
    if not event_type:
        log.warning("append_event: event_dict missing event_type — skipping")
        return False

    filepath = _shipment_file(customer_id, shipment_ref)
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Dedup check
    if source_msg_id and filepath.exists():
        marker = _marker(source_msg_id, event_type)
        existing = filepath.read_text(encoding="utf-8")
        if marker in existing:
            log.debug(
                "Event block already in vault: %s / %s / %s",
                shipment_ref, event_type, source_msg_id,
            )
            return False

    # Ensure file + header exist
    first_seen = event_dict.get("event_date", now_str) or now_str
    _ensure_shipment_header(
        filepath, shipment_ref, customer_id,
        customer_name, carrier, pol, pod, svc_type,
        first_seen=str(first_seen)[:19],
    )

    # Build event block
    event_date_raw = event_dict.get("event_date") or now_str
    event_date_str = str(event_date_raw)[:19]
    emoji = _EVENT_EMOJI.get(event_type, "🔹")
    confidence = event_dict.get("confidence", 1.0)
    risk_flag = event_dict.get("risk_flag", False)
    excerpt = event_dict.get("excerpt", "")

    src_marker = _marker(source_msg_id or "nosrc", event_type)
    src_link = f"[{source_filename}]" if source_filename else "*(source unknown)*"

    block_lines = [
        f"\n{src_marker}",
        f"### {event_date_str} · {event_type} {emoji}",
    ]

    if risk_flag:
        block_lines.append(_RISK_BANNER)

    if excerpt:
        block_lines.append(f"> {excerpt}")

    if narrative_text:
        block_lines.append(f"\n{narrative_text}")

    block_lines.append(
        f"\n*Source: {src_link} · confidence {confidence:.0%}*"
    )
    block_lines.append("\n---\n")

    block = "\n".join(block_lines)

    with filepath.open("a", encoding="utf-8") as fh:
        fh.write(block)

    _update_header_last_update(filepath, now_str)
    log.info("Appended %s event to %s", event_type, filepath.name)

    # Refresh customer index
    regen_index(customer_id)
    return True


def regen_index(customer_id: str) -> None:
    """
    Regenerate _index.md for a customer folder.
    Lists all shipment .md files with first-line title.
    Idempotent — overwrites index each time.
    """
    cdir = _customer_dir(customer_id)
    if not cdir.exists():
        return

    md_files = sorted(
        [f for f in cdir.iterdir() if f.suffix == ".md" and f.name != "_index.md"]
    )

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# {customer_id} — Shipment Index\n",
        f"*Auto-generated: {now_str}*\n",
        f"*Total shipments: {len(md_files)}*\n\n",
        "| Shipment | File |\n",
        "|----------|------|\n",
    ]

    for f in md_files:
        try:
            first_line = f.read_text(encoding="utf-8").split("\n")[0].lstrip("# ").strip()
        except Exception:
            first_line = f.stem
        lines.append(f"| {first_line} | [{f.name}](./{f.name}) |\n")

    index_path = _index_file(customer_id)
    index_path.write_text("".join(lines), encoding="utf-8")
    log.debug("Regenerated _index.md for customer %s (%d files)", customer_id, len(md_files))
