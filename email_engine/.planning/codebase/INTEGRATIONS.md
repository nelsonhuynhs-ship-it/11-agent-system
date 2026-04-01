# INTEGRATIONS — External Services & APIs

## Microsoft Outlook (COM)
- **Protocol:** `win32com.client.Dispatch('Outlook.Application')`
- **Used by:** `core/main.py`, `core/scan_outlook_folders.py`, `core/pst_importer.py`, `core/shipment_brain.py`
- **Operations:** Read inbox, move mail items, save .msg, add/remove PST stores
- **MAPI Property:** `PR_SMTP = 'http://schemas.microsoft.com/mapi/proptag/0x39FE001E'` for SMTP address resolution

## Telegram Bot API
- **Protocol:** REST over HTTPS via `httpx`
- **Used by:** `core/shipment_brain.py`, `core/notify.py`
- **Endpoint:** `https://api.telegram.org/bot{token}/sendMessage`
- **Purpose:** Real-time alerts to Nelson when critical shipment events detected

## Anthropic Claude API
- **Protocol:** REST via `requests`
- **Used by:** `core/pst_importer.py` (Layer 3 AI classification)
- **Endpoint:** `https://api.anthropic.com/v1/messages`
- **Model:** `claude-sonnet-4-20250514`
- **Auth:** `ANTHROPIC_API_KEY` from environment or `.env` file

## SQLite Database
- **Path:** `logs/shipments.db`
- **Used by:** `core/data_collector.py`, `core/pst_importer.py`, `core/nelson_briefing.py`
- **Tables:** 6 (email_events, shipments, sales_replies, nelson_alerts, customers, email_maybe_review)
- **Access:** Direct `sqlite3.connect()`, no ORM

## Panjiva Data (Import/Trade Intelligence)
- **Path:** `data_panjiva/` directory + `data/cnee_master.xlsx`
- **Used by:** `ingest/combine_all.py`, `core/reply_analyzer.py`
- **Purpose:** Cross-reference customers with trade volume data for sales recommendations

## Windows Toast Notifications
- **Used by:** `core/notify.py` → imported by `core/main.py`
- **Purpose:** Desktop pop-up notifications for email routing events
