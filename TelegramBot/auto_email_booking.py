# -*- coding: utf-8 -*-
"""
auto_email_booking.py — Bot v6 Feature #2
Auto-Email Booking Agent — given a Quote ID (or job dict), automatically
generates a carrier-specific booking request email draft.

Will attempt to open Outlook draft via win32com if available.
Falls back to Telegram message with the full email content.

Usage:
  Called after /win QUOTE_ID via erp_writer.convert_quote_to_job()
  Also callable directly: /book QUOTE_ID
"""
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Carrier email templates ──────────────────────────────────────────────────
# Each carrier has a subject line pattern and body template
# Use {placeholders} that get filled from the job dict

CARRIER_BOOKING_EMAILS = {
    "CMA": {
        "to": "bookings.vietnam@cma-cgm.com",
        "subject": "BOOKING REQUEST — CMA CGM | {routing} | {container} × {qty} | ETD {etd}",
        "body": """\
Dear CMA CGM Booking Team,

We would like to request a booking for the following shipment:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOOKING REQUEST DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shipper      : NELSON FREIGHT CO.
Customer     : {customer}
Job Ref      : {job_id}

Port of Loading   : {pol}
Port of Discharge : {pod}
Final Destination : {place}
Routing           : {routing}

Equipment    : {container} × {qty} units
Commodity    : {commodity}
Gross Weight : {weight} (please confirm weight acceptance)
ETD (Approx) : {etd}

Rate Reference : {quote_id}
Service Type   : {service_type}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Please confirm space availability and provide booking number at your earliest convenience.

Please note: Cargo may contain heavy stone/slab products. Please verify weight compliance per equipment.

Best regards,
Nelson Freight
""",
    },
    "ONE": {
        "to": "booking.viet@one-line.com",
        "subject": "SPACE REQUEST — ONE | {routing} | {container} × {qty} | ETD {etd}",
        "body": """\
Dear ONE Booking Team,

Please accept our booking request as follows:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shipper      : NELSON FREIGHT CO.
Customer     : {customer}
Internal Ref : {job_id} / {quote_id}

POL : {pol}  |  POD : {pod}  |  Place : {place}
Equipment    : {container} × {qty}
Commodity    : {commodity}
Gross Weight : {weight}
ETD          : {etd}
Service      : {service_type}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Kindly confirm booking number and vessel schedule.

Thank you,
Nelson Freight
""",
    },
    "MSK": {
        "to": "vn.booking@maersk.com",
        "subject": "Booking Request — MAERSK | {routing} | ETD {etd}",
        "body": """\
Dear Maersk Booking Team,

Booking request details below:

Customer     : {customer}
Job Ref      : {job_id}
Route        : {pol} → {pod} → {place}
Equipment    : {container} × {qty} units
Commodity    : {commodity}
Est. Weight  : {weight} per unit
ETD          : {etd}
Quote Ref    : {quote_id}

Please confirm availability and provide booking reference.

Best regards,
Nelson Freight
""",
    },
    "YML": {
        "to": "yvnhan.booking@yml.com.tw",
        "subject": "BKG REQUEST — YANG MING | {routing} | {container} × {qty} | ETD {etd}",
        "body": """\
Dear Yang Ming Booking,

Please arrange booking as below:

Shipper: NELSON FREIGHT | Ref: {job_id}
Route  : {pol} → {pod} → {place} | Equipment: {container} × {qty}
Commodity: {commodity} | Weight: {weight} | ETD: {etd}
Service: {service_type} | Quote: {quote_id}

Please confirm space and issue booking number.

Thank you,
Nelson Freight
""",
    },
    # Default template for any other carrier
    "DEFAULT": {
        "to": "",
        "subject": "BOOKING REQUEST — {carrier} | {routing} | {container} × {qty} | ETD {etd}",
        "body": """\
Dear {carrier} Booking Team,

Please confirm space and issue booking for:

Shipper: NELSON FREIGHT CO.
Job Ref: {job_id} | Quote: {quote_id}
Customer: {customer}
Route: {pol} → {pod} → {place}
Equipment: {container} × {qty} | Commodity: {commodity}
Est. Weight: {weight} | ETD: {etd}
Service Type: {service_type}

Please confirm booking number at your earliest convenience.

Best regards,
Nelson Freight
""",
    },
}


def _get_template(carrier: str) -> dict:
    """Get the carrier-specific email template, fall back to DEFAULT."""
    carrier_upper = carrier.upper().strip()
    for key in CARRIER_BOOKING_EMAILS:
        if key != "DEFAULT" and key in carrier_upper:
            return CARRIER_BOOKING_EMAILS[key]
    return CARRIER_BOOKING_EMAILS["DEFAULT"]


def _fill_template(template: str, job: dict) -> str:
    """Fill template placeholders from job dict."""
    etd_str = job.get('etd')
    if hasattr(etd_str, 'strftime'):
        etd_str = etd_str.strftime('%d %b %Y')
    elif not etd_str or str(etd_str) in ('nan', 'NaT', 'None'):
        etd_str = 'TBD'
    else:
        etd_str = str(etd_str)

    replacements = {
        'job_id':       job.get('job_id', 'N/A'),
        'quote_id':     job.get('quote_id', 'N/A'),
        'customer':     job.get('customer', 'N/A'),
        'carrier':      job.get('carrier', 'N/A'),
        'pol':          job.get('pol', job.get('routing', 'N/A').split('→')[0].strip()),
        'pod':          job.get('pod', 'USTIW'),
        'place':        job.get('place', job.get('routing', '').split('→')[-1].strip()),
        'routing':      job.get('routing', 'N/A'),
        'container':    job.get('container', '40HQ'),
        'qty':          str(job.get('quantity', 1)),
        'commodity':    job.get('commodity', 'General Cargo'),
        'weight':       job.get('weight', 'Per PKG'),
        'etd':          etd_str,
        'service_type': job.get('service_type', 'COC'),
    }

    result = template
    for key, value in replacements.items():
        result = result.replace('{' + key + '}', str(value))
    return result


def generate_booking_email(job: dict) -> dict:
    """
    Generate a complete booking email for a given job dict.

    Returns dict:
        carrier, to, subject, body, draft_cmd (for Outlook)
    """
    carrier  = str(job.get('carrier', 'CARRIER'))
    template = _get_template(carrier)

    subject = _fill_template(template['subject'], {**job, 'carrier': carrier})
    body    = _fill_template(template['body'],    {**job, 'carrier': carrier})
    to_addr = template.get('to', '')

    return {
        'carrier':   carrier,
        'to':        to_addr,
        'subject':   subject,
        'body':      body,
        'generated': datetime.now().strftime('%d/%m/%Y %H:%M'),
    }


def try_open_outlook_draft(email: dict) -> bool:
    """
    Attempt to create an Outlook draft via win32com.
    Returns True if successful, False if Outlook not available.
    """
    try:
        import win32com.client
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail    = outlook.CreateItem(0)
        mail.To      = email['to']
        mail.Subject = email['subject']
        mail.Body    = email['body']
        mail.Display(True)  # Opens Outlook compose window
        logger.info(f"[Booking] Opened Outlook draft for {email['carrier']}")
        return True
    except ImportError:
        logger.info("[Booking] win32com not available — skipping Outlook draft")
        return False
    except Exception as e:
        logger.warning(f"[Booking] Outlook error: {e}")
        return False


def format_booking_telegram(job: dict, email: dict, outlook_opened: bool) -> str:
    """
    Format a Telegram message confirming the booking email was generated.
    Includes the full email body if Outlook wasn't opened.
    """
    lines = [
        f"✅ BOOKING EMAIL GENERATED",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"Job:    {job.get('job_id', 'N/A')}",
        f"Quote:  {job.get('quote_id', 'N/A')}",
        f"Customer: {job.get('customer', 'N/A')}",
        f"Carrier: {email['carrier']}",
        f"Route:  {job.get('routing', 'N/A')}",
        f"ETD:    {job.get('etd', 'TBD')}",
        f"",
    ]

    if outlook_opened:
        lines.append("📧 Outlook draft đã mở — Sếp review và click Send!")
    else:
        lines.append(f"📧 EMAIL DRAFT (copy & paste):")
        lines.append(f"To:      {email['to'] or '[Nhập email carrier]'}")
        lines.append(f"Subject: {email['subject']}")
        lines.append(f"")
        lines.append("─── BODY ───")
        # Truncate body for Telegram (4096 char limit)
        body_preview = email['body'][:1500] + ("..." if len(email['body']) > 1500 else "")
        lines.append(body_preview)

    lines.append("")
    lines.append("⚠️ Nhớ kiểm tra: Gross Weight, ETD date, Container type trước khi gửi!")

    return "\n".join(lines)


async def handle_booking_request(bot, chat_id: int, job: dict) -> None:
    """
    Main entry point called after /win or /book command.
    Generates email, tries Outlook, sends Telegram confirmation.
    """
    try:
        email = generate_booking_email(job)
        opened = try_open_outlook_draft(email)
        msg = format_booking_telegram(job, email, opened)
        await bot.send_message(chat_id=chat_id, text=msg)
        logger.info(f"[Booking] Email generated for {job.get('job_id')} via {job.get('carrier')}")
    except Exception as e:
        logger.error(f"[Booking] Error: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ Lỗi tạo booking email: {e}\nVui lòng tạo email thủ công."
        )
