# -*- coding: utf-8 -*-
"""
EmailIntel — parse customer emails for sentiment, intent, urgency.
================================================================
Runs daily via SENTINEL scheduler (21:00).
Feeds ORACLE customer profiles with intelligence signals.
Uses google.genai SDK (same as ai_chat.py).

Source: email_engine/logs/shipments.db → emails table (135 rows)
Target: TelegramBot/memory/oracle.db → customer_profiles

Usage:
    from intelligence.email_intel import EmailIntel
    intel = EmailIntel()
    signals = intel.analyze_email("JUN", "SUPPORT URGENTLY // PLAX26030654...")
"""

import os
import sys
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "TelegramBot"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Signals to extract from each customer email
EXTRACT_PROMPT = """Analyze this freight forwarding customer email. Extract JSON only, no prose:
{{
  "sentiment": "positive|neutral|negative|urgent",
  "intent": "booking|complaint|inquiry|rate_request|tracking|payment|other",
  "urgency_score": 1-5,
  "mentioned_routes": ["HCM→LAX"],
  "mentioned_carriers": ["HPL"],
  "price_sensitivity": "high|medium|low|unknown",
  "key_signal": "one sentence summary of what customer wants/feels"
}}

Email:
---
Subject: {subject}

{email_body}
---
"""

# Path to email engine database
EMAIL_DB = ROOT / "email_engine" / "logs" / "shipments.db"


class EmailIntel:
    """Parse customer emails for sentiment, intent, urgency using Gemini."""

    def __init__(self):
        self._oracle = None
        try:
            from memory.oracle import Oracle
            self._oracle = Oracle()
        except Exception as e:
            log.warning("[EmailIntel] Oracle not available: %s", e)

    @property
    def oracle(self):
        return self._oracle

    def analyze_email(self, user_id: str, email_body: str,
                      subject: str = "") -> dict:
        """Send email to Gemini, extract structured signals."""
        if not GEMINI_API_KEY:
            return {"error": "GEMINI_API_KEY not set", "sentiment": "unknown"}

        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)

            prompt = EXTRACT_PROMPT.format(
                subject=subject,
                email_body=email_body[:2000]
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            text = response.text.strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            signals = json.loads(text)

        except json.JSONDecodeError as e:
            log.warning("[EmailIntel] JSON parse failed: %s", e)
            signals = {"error": "json_parse_failed", "sentiment": "unknown"}
        except Exception as e:
            log.warning("[EmailIntel] Gemini error: %s", e)
            signals = {"error": str(e)[:100], "sentiment": "unknown"}

        # Save signals to Oracle customer profile
        if signals.get("sentiment") != "unknown" and user_id:
            self._update_profile(user_id, signals)

        return signals

    def _update_profile(self, user_id: str, signals: dict):
        """Auto-update Oracle profile from email signals."""
        if not self._oracle:
            return

        updates = {}

        # Price sensitivity → risk level
        ps = signals.get("price_sensitivity", "unknown")
        if ps == "high":
            updates["risk_level"] = "price_sensitive"
        elif ps == "low":
            updates["risk_level"] = "loyal"

        # Urgency → segment
        urgency = signals.get("urgency_score", 0)
        if urgency >= 4:
            updates["segment"] = "hot_lead"
        elif urgency >= 3:
            updates["segment"] = "active"

        # Most mentioned route → top_route
        routes = signals.get("mentioned_routes", [])
        if routes:
            updates["top_route"] = routes[0]

        # Append key signal to notes (rolling window)
        signal_note = signals.get("key_signal", "")
        if signal_note:
            existing = self._oracle.get_profile(user_id)
            old_notes = existing.get("notes") or ""
            date = datetime.now().strftime("%m/%d")
            new_notes = f"{old_notes} | [{date}] {signal_note}"
            updates["notes"] = new_notes[-500:]  # Keep last 500 chars

        if updates:
            self._oracle.upsert_profile(user_id, **updates)
            log.info("[EmailIntel] Updated profile %s: %s", user_id, list(updates.keys()))

    def batch_analyze_today(self, emails: list[dict]) -> list[dict]:
        """
        Batch analyze a list of emails.
        
        Args:
            emails: [{"user_id": ..., "body": ..., "subject": ...}]
        Returns:
            list of {"user_id": ..., "signals": {...}}
        """
        results = []
        for email in emails:
            signals = self.analyze_email(
                email["user_id"],
                email["body"],
                email.get("subject", "")
            )
            results.append({
                "user_id": email["user_id"],
                "signals": signals
            })
        return results

    def scan_email_db(self, days: int = 1, limit: int = 50) -> list[dict]:
        """
        Pull recent emails from shipments.db and analyze them.
        Skips internal senders (pudongprime, harry).
        """
        if not EMAIL_DB.exists():
            log.warning("[EmailIntel] Email DB not found: %s", EMAIL_DB)
            return []

        try:
            with sqlite3.connect(EMAIL_DB) as c:
                c.row_factory = sqlite3.Row
                rows = c.execute("""
                    SELECT sender, subject, body, customer_name
                    FROM emails
                    WHERE DATE(received_at) >= DATE('now', ?)
                      AND sender NOT LIKE '%pudongprime%'
                      AND customer_name IS NOT NULL
                      AND customer_name != ''
                    ORDER BY received_at DESC
                    LIMIT ?
                """, (f"-{days} days", limit)).fetchall()

            if not rows:
                log.info("[EmailIntel] No new customer emails found")
                return []

            emails = [{
                "user_id": r["customer_name"],
                "body": r["body"] or "",
                "subject": r["subject"] or "",
            } for r in rows]

            log.info("[EmailIntel] Found %d emails to analyze", len(emails))
            return self.batch_analyze_today(emails)

        except Exception as e:
            log.error("[EmailIntel] DB scan error: %s", e)
            return []


# ── Standalone test ──────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(name)s] %(message)s")

    from dotenv import load_dotenv
    load_dotenv(ROOT / "TelegramBot" / ".env")

    intel = EmailIntel()

    # Quick test with a sample email
    test_result = intel.analyze_email(
        "TEST_CUSTOMER",
        "Can you check HPL rate HCM to LAX for 40HQ? We need urgent booking "
        "for next week. Price must be under $2000.",
        subject="URGENT RATE REQUEST // HCM-LAX // 40HQ"
    )
    print(f"\n=== Test Result ===")
    print(json.dumps(test_result, indent=2, ensure_ascii=False))
