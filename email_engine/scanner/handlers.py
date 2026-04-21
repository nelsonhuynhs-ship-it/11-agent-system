"""
email_engine.scanner.handlers
=============================
Per-class handlers invoked by inbox_scanner.run_scan.

Each handler:
    1. Normalises the item (extracts what it needs)
    2. Logs an intel event via email_engine.intel.memory.log_event
    3. Re-evaluates tier via email_engine.intel.tier_engine.evaluate_event
    4. Writes back to cnee_master_v2 via email_engine.intel.writeback.update_master
    5. Emits a Telegram alert (batch-friendly)

Intel modules may not exist yet (being built in parallel by dev-intel).
We import them under try/except and fall back to no-op stubs so this
package still imports cleanly on a fresh checkout.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from . import telegram as tg
from .classifier import classify_bounce_severity, load_patterns

log = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Intel module imports with graceful stubs (Round 2 wires real modules)
#
# Adapter layer: scanner was written against stub signatures
#   log_event(event_type, **fields)
#   evaluate_event(event_type, email, **fields) -> dict
# Real dev-intel modules use:
#   log_event(event: dict)
#   evaluate_event(event: dict) -> list[dict]
# We wrap real modules below to preserve the scanner call style.
# -------------------------------------------------------------------
try:
    from email_engine.intel.memory import log_event as _real_log_event  # type: ignore
    from email_engine.intel.memory import get_cnee_summary as _get_cnee_summary  # type: ignore
    _INTEL_MEMORY_AVAILABLE = True

    def _log_event(event_type: str, **fields) -> None:  # type: ignore
        # Adapt to dev-intel's dict-based API.
        evt = {"event_type": event_type}
        # dev-intel uses cnee_email as the key; scanner passes 'email'
        if "email" in fields:
            evt["cnee_email"] = fields.pop("email")
        evt.update(fields)
        try:
            _real_log_event(evt)
        except Exception as e:
            log.warning("log_event failed: %s", e)
except Exception:  # ImportError or sub-import failure
    _INTEL_MEMORY_AVAILABLE = False

    def _log_event(event_type: str, **fields) -> None:  # type: ignore
        log.debug("[STUB log_event] %s %s", event_type, fields)

    def _get_cnee_summary(email: str) -> dict:  # type: ignore
        return {}


try:
    from email_engine.intel.tier_engine import evaluate_event as _real_evaluate_event  # type: ignore
    _INTEL_TIER_AVAILABLE = True

    def _evaluate_event(event_type: str, email: str = "", **fields) -> dict:  # type: ignore
        evt = {"event_type": event_type, "cnee_email": email}
        evt.update(fields)
        try:
            actions = _real_evaluate_event(evt) or []
        except Exception as e:
            log.warning("evaluate_event failed: %s", e)
            return {"tier": None, "action": None, "changed": False}
        # Flatten list[dict] → single dict for scanner's use-case
        if not actions:
            return {"tier": None, "action": None, "changed": False}
        first = actions[0]
        return {
            "tier": first.get("new_tier"),
            "action": first.get("new_action"),
            "changed": True,
            "reason": first.get("reason"),
        }
except Exception:
    _INTEL_TIER_AVAILABLE = False

    def _evaluate_event(event_type: str, email: str = "", **fields) -> dict:  # type: ignore
        log.debug("[STUB evaluate_event] %s email=%s", event_type, email)
        return {"tier": None, "action": None, "changed": False}


try:
    from email_engine.intel.writeback import update_master as _update_master  # type: ignore
    _INTEL_WRITEBACK_AVAILABLE = True
except Exception:
    _INTEL_WRITEBACK_AVAILABLE = False

    def _update_master(email: str, updates: dict) -> bool:  # type: ignore
        log.debug("[STUB update_master] %s %s", email, updates)
        return True


# Reply analyzer (upgraded — see core/reply_analyzer.py)
try:
    from email_engine.core.reply_analyzer import analyze_reply as _analyze_reply  # type: ignore
except Exception:
    def _analyze_reply(subject: str, body: str) -> dict:  # type: ignore
        return {"sentiment": "UNKNOWN", "intent": "general", "confidence": 0.0}


# CNEE Memory vault (A1 — added 2026-04-19)
try:
    from email_engine.core.cnee_memory import append_event as _mem_append  # type: ignore
    _CNEE_MEMORY_AVAILABLE = True
except Exception:
    _CNEE_MEMORY_AVAILABLE = False
    def _mem_append(*args, **kwargs) -> bool:  # type: ignore
        return False

# LLM structured reply extractor (A1 — added 2026-04-19)
try:
    from email_engine.core.llm_extract_reply import extract_reply_context as _llm_extract  # type: ignore
    _LLM_EXTRACT_AVAILABLE = True
except Exception:
    _LLM_EXTRACT_AVAILABLE = False
    def _llm_extract(subject: str, body: str, cnee_email: str = "") -> dict:  # type: ignore
        return {}


# customer_rules.json for preference enrichment
import json as _json_mod
import pathlib as _pathlib_mod

_CUSTOMER_RULES_PATH = _pathlib_mod.Path(__file__).parent.parent / "data" / "customer_rules.json"


def _load_customer_rules() -> dict:
    """Load customer_rules.json. Returns {} on any error."""
    try:
        return _json_mod.loads(_CUSTOMER_RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_customer_rules(rules: dict) -> bool:
    """Write customer_rules.json atomically. Returns success flag."""
    try:
        _CUSTOMER_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CUSTOMER_RULES_PATH.with_suffix(".json.tmp")
        tmp.write_text(_json_mod.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
        import os as _os
        _os.replace(tmp, _CUSTOMER_RULES_PATH)
        return True
    except Exception as exc:
        log.warning("_save_customer_rules failed: %s", exc)
        return False


def _merge_cnee_preferences(cnee_email: str, structured: dict) -> None:
    """If CNEE is a known customer (matched by seen_senders), enrich their
    preferred_pods / preferred_carriers in customer_rules.json.
    Skips silently if not found (prospect-only flow handled by vault).
    """
    if not structured or not cnee_email:
        return
    pods = structured.get("preferred_pods") or []
    carriers = structured.get("preferred_carriers") or []
    if not pods and not carriers:
        return

    try:
        rules = _load_customer_rules()
        customers = rules.get("customers", {})
        matched_key = None

        # Search for matching customer by seen_senders list
        for key, cust_data in customers.items():
            senders = cust_data.get("seen_senders", [])
            if any(s.lower().strip() == cnee_email.lower().strip() for s in senders):
                matched_key = key
                break

        if not matched_key:
            return  # prospect — handled by vault only

        cust = customers[matched_key]
        changed = False

        if pods:
            existing_pods = set(cust.get("preferred_pods", []))
            new_pods = existing_pods | set(pods)
            if new_pods != existing_pods:
                cust["preferred_pods"] = sorted(new_pods)
                changed = True

        if carriers:
            existing_carriers = set(cust.get("preferred_carriers", []))
            new_carriers = existing_carriers | set(carriers)
            if new_carriers != existing_carriers:
                cust["preferred_carriers"] = sorted(new_carriers)
                changed = True

        if changed:
            rules["customers"][matched_key] = cust
            if _save_customer_rules(rules):
                log.info("customer_rules enriched for %s: pods=%s carriers=%s",
                         matched_key, pods, carriers)
    except Exception as exc:
        log.warning("_merge_cnee_preferences error: %s", exc)


# -------------------------------------------------------------------
# Public helpers
# -------------------------------------------------------------------
def extract_bounced_email(body: str) -> str | None:
    """Parse DSN body and return the failed recipient email, or None."""
    if not body:
        return None

    patterns = load_patterns().get(
        "bounce_regex",
        [
            r'(?:could not be delivered|undelivered|failed).*?([\w\.\-]+@[\w\.\-]+)',
            r'Final-Recipient:\s*rfc822;\s*([\w\.\-]+@[\w\.\-]+)',
        ],
    )
    for rx in patterns:
        m = re.search(rx, body, re.IGNORECASE | re.DOTALL)
        if m:
            candidate = m.group(1).strip().lower()
            if _is_plausible_email(candidate):
                return candidate

    # Last-ditch: find any email that isn't a daemon/postmaster.
    for m in re.finditer(r"[\w.+\-]+@[\w.\-]+\.[a-zA-Z]{2,}", body):
        c = m.group(0).lower()
        if any(s in c for s in ("mailer-daemon", "postmaster", "noreply", "no-reply")):
            continue
        return c
    return None


def _is_plausible_email(s: str) -> bool:
    if "@" not in s or s.count("@") != 1:
        return False
    local, _, domain = s.partition("@")
    return bool(local) and "." in domain


def _safe_attr(item: Any, attr: str, default: str = "") -> str:
    try:
        v = getattr(item, attr, default)
        return str(v) if v is not None else default
    except Exception:
        return default


_OL_FOLDER_DELETED_ITEMS = 3  # olFolderDeletedItems constant


def _move_to_deleted(item: Any) -> bool:
    """Move an Outlook MailItem to Deleted Items folder.

    Returns True on success. Failure is non-fatal — item stays in Inbox
    but bounce event is already logged. Uses win32com directly to avoid
    re-using the existing COM connection (may be on a different thread).
    """
    try:
        import win32com.client  # type: ignore
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        deleted_folder = ns.GetDefaultFolder(_OL_FOLDER_DELETED_ITEMS)
        item.Move(deleted_folder)
        return True
    except Exception as exc:
        log.warning("Could not move NDR to Deleted Items: %s", exc)
        return False


# -------------------------------------------------------------------
# Handlers
# -------------------------------------------------------------------
def handle_bounce(item: Any, bounced_email: str) -> None:
    """Bounce / DSN handler.

    `bounced_email` is the failed recipient extracted from the NDR body.
    If caller hasn't extracted yet, they can pass "" — we'll try again here.
    """
    body = _safe_attr(item, "Body")
    subject = _safe_attr(item, "Subject")

    target = (bounced_email or extract_bounced_email(body) or "").lower().strip()
    if not target:
        log.warning("handle_bounce: could not extract recipient from NDR; subject=%r", subject[:120])
        return

    severity = classify_bounce_severity(body)  # HARD | SOFT

    _log_event(
        "BOUNCE",
        email=target,
        severity=severity,
        subject=subject,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    decision = _evaluate_event("BOUNCE", email=target, severity=severity) or {}
    _update_master(
        target,
        {
            "EMAIL_STATUS": "HARD_BOUNCE" if severity == "HARD" else "SOFT_BOUNCE",
            "LAST_BOUNCE_AT": datetime.now(timezone.utc).isoformat(),
            "LAST_BOUNCE_SEVERITY": severity,
            **({"TIER": decision["tier"]} if decision.get("tier") else {}),
            **({"ACTION": decision["action"]} if decision.get("action") else {}),
        },
    )

    # === A1 BEGIN — CNEE Memory bounce trace ===
    try:
        _mem_append(
            cnee_email=target,
            event_type="BOUNCED",
            structured={"severity": severity},
            narrative=f"Email bounced ({severity}). Subject: {subject[:120]}",
            source_msg_id=str(getattr(item, "EntryID", "") or "") or None,
        )
    except Exception as exc:
        log.warning("handle_bounce vault error: %s", exc)
    # === A1 END ===

    # Phase C: Move NDR mail to Deleted Items (Inbox cleanup)
    if _move_to_deleted(item):
        log.info("BOUNCE logged + moved to Deleted: %s (%s)", target, severity)
    else:
        log.info("BOUNCE logged (move to Deleted failed, remains in Inbox): %s", target)

    tg.send_alert(
        f"<b>Bounce ({severity})</b>\n{target}\n<i>{subject[:140]}</i>"
    )


def handle_auto_reply(item: Any, cnee_email: str) -> None:
    """Out-of-office / automatic reply handler."""
    subject = _safe_attr(item, "Subject")
    body = _safe_attr(item, "Body")
    email = (cnee_email or "").lower().strip()

    _log_event(
        "AUTO_REPLY",
        email=email,
        subject=subject,
        body_preview=body[:400],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    decision = _evaluate_event("AUTO_REPLY", email=email) or {}
    _update_master(
        email,
        {
            "LAST_AUTO_REPLY_AT": datetime.now(timezone.utc).isoformat(),
            **({"TIER": decision["tier"]} if decision.get("tier") else {}),
            **({"ACTION": decision["action"]} if decision.get("action") else {}),
        },
    )

    # Low-priority alert — daily report is enough; don't spam Nelson mid-day.
    log.info("AUTO_REPLY logged for %s", email)


def handle_real_reply(item: Any, cnee_row: dict) -> None:
    """Real human reply from a known CNEE.

    `cnee_row` is a dict-like row from cnee_master_v2 (must contain EMAIL and
    optionally COMPANY / TIER / CAMPAIGN).
    """
    subject = _safe_attr(item, "Subject")
    body = _safe_attr(item, "Body")
    email = str(cnee_row.get("EMAIL") or cnee_row.get("email") or "").lower().strip()
    company = str(cnee_row.get("COMPANY") or cnee_row.get("company") or "").strip()

    analysis = _analyze_reply(subject, body)
    sentiment = analysis.get("sentiment", "UNKNOWN")
    intent = analysis.get("intent", "general")
    confidence = float(analysis.get("confidence", 0.0))

    _log_event(
        "REPLY",
        email=email,
        company=company,
        subject=subject,
        body_preview=body[:800],
        sentiment=sentiment,
        intent=intent,
        confidence=confidence,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    decision = _evaluate_event(
        "REPLY", email=email, sentiment=sentiment, intent=intent
    ) or {}
    _update_master(
        email,
        {
            "LAST_REPLY_AT": datetime.now(timezone.utc).isoformat(),
            "LAST_REPLY_INTENT": intent,
            "LAST_REPLY_SENTIMENT": sentiment,
            **({"TIER": decision["tier"]} if decision.get("tier") else {}),
            **({"ACTION": decision["action"]} if decision.get("action") else {}),
        },
    )

    # === A1 BEGIN — CNEE Memory + LLM extract ===
    try:
        # LLM structured extraction
        llm_structured: dict = {}
        if _LLM_EXTRACT_AVAILABLE:
            llm_result = _llm_extract(subject, body, cnee_email=email)
            if llm_result:
                llm_structured = llm_result

        # Override with basic fields from rule-based analysis
        structured_for_vault = dict(llm_structured)
        structured_for_vault["intent"] = intent
        structured_for_vault["sentiment"] = sentiment
        structured_for_vault["confidence"] = round(confidence, 3)

        # Build narrative summary
        narrative = (
            f"Intent: {intent} · Sentiment: {sentiment} · Confidence: {confidence:.0%}"
        )
        if llm_structured.get("urgency"):
            narrative += f" · Urgency: {llm_structured['urgency']}"
        if llm_structured.get("volume_est"):
            narrative += f" · Volume: {llm_structured['volume_est']}"

        # Write to vault
        msg_id = str(getattr(item, "EntryID", "") or "")
        _mem_append(
            cnee_email=email,
            event_type="REPLIED",
            structured=structured_for_vault,
            narrative=narrative,
            source_msg_id=msg_id or None,
        )

        # Enrich customer_rules.json if known customer
        _merge_cnee_preferences(email, llm_structured)

    except Exception as exc:
        log.warning("handle_real_reply vault/LLM error: %s", exc)
    # === A1 END ===

    # Hot-lead alert for booking / negotiating / price inquiry
    if intent in ("booking_intent", "negotiating", "price_inquiry"):
        hot_label = {
            "booking_intent": "HOT LEAD — booking",
            "negotiating": "HOT LEAD — negotiating",
            "price_inquiry": "WARM — price inquiry",
        }[intent]
        msg = (
            f"<b>{hot_label}</b>\n"
            f"{company or '(no company)'} &lt;{email}&gt;\n"
            f"Sentiment: {sentiment}  |  Intent: {intent}\n"
            f"<i>{subject[:140]}</i>"
        )
        tg.send_alert(msg)
    else:
        log.info("REPLY logged for %s (intent=%s, sentiment=%s)", email, intent, sentiment)


def handle_unsubscribe(item: Any, cnee_email: str) -> None:
    """Opt-out handler — suppress future sends."""
    subject = _safe_attr(item, "Subject")
    email = (cnee_email or "").lower().strip()

    _log_event(
        "UNSUBSCRIBE",
        email=email,
        subject=subject,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    _evaluate_event("UNSUBSCRIBE", email=email)
    _update_master(
        email,
        {
            "EMAIL_STATUS": "UNSUBSCRIBED",
            "ACTION": "SUPPRESS",
            "UNSUBSCRIBED_AT": datetime.now(timezone.utc).isoformat(),
        },
    )
    tg.send_alert(f"<b>Unsubscribe</b>\n{email}\n<i>{subject[:140]}</i>")
