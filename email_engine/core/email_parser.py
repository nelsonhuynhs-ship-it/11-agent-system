"""
Email Parser & Classifier
==========================
Classify Outlook emails into TYPE_SHIPMENT | TYPE_SALES | TYPE_INTERNAL
and parse structured fields for the data pipeline.
"""

from __future__ import annotations

import re
import logging

log = logging.getLogger(__name__)


class EmailClassifier:
    """Determine email type from subject + sender + folder context."""

    SALES_PATTERN = r'NELSON\s+WEEK\s+\d+'

    STAGE_KEYWORDS = {
        'BOOKING':            ['new shipment', 'booking request', 'booking confirmation',
                               'bkg confirmed', 'keep booking'],
        'RATES_CHECKING':     ['rates checking', 'rate inquiry', 'checking rate'],
        'SI_SUBMITTED':       ['si //', 'si bkg', 'shipping instruction', 'si-', 'si hang'],
        'DRAFT_BL_ISSUED':    ['draft b/l', 'draft bl', 'draft b_l', 'draft b l', 'bill nháp'],
        'DRAFT_BL_CONFIRMED': ['draft ok', 'confirm draft', 'bl ok', 'confirmed draft'],
        'CY_UPDATE':          ['update cy', 'cy cut', 'update cot', 'cy/'],
        'PRE_ALERT':          ['pre-alert', 'pre alert', 'prealert'],
        'LOADED':             ['loaded', 'on board', 'đã lên tàu'],
        'ATD':                ['update atd', 'atd', 'vessel departed'],
        'RELEASE':            ['release', 'do released'],
        'DN_SENT':            ['dn //', 'dn __', 'debit note', 'debit //', 'giấy báo tiền'],
        'INVOICE_ISSUED':     ['invoice', 'e-invoice', 'xuất hóa đơn'],
        'PAYMENT_CONFIRMED':  ['payment received', 'paid', 'đã thanh toán',
                               'xác nhận thanh toán'],
        'DELAY_NOTICE':       ['delay notice', 'delay', 'rollover', 'postpone'],
        'CHANGE_VESSEL':      ['change vessel', 'vessel change', 'changed mother vessel'],
        'AMENDMENT':          ['amendment', 'amend'],
        'CONFIRM_EXW':        ['confirm exw', 'exw confirmed'],
    }

    HBL_PATTERNS = [
        r'\b(P(?:NYC|SAV|HOU|DEN|CHS|SEA|OMA|YTO|ELP|MAN|LAX|HAI|ATL)\d{7,12})\b',
        r'\b(HLCU[A-Z]{3}\d{9,})\b',
        r'\b(ZIMU(?:HCM|HAI|SGN)\d{8,})\b',
        r'\b(HANG\d{8,12})\b',
        r'\b(ESLV[A-Z0-9]{5,15})\b',
        r'\b(PATL\d{8,})\b',
        r'\b(HLCUSGN\d{8,})\b',
        r'\b(N\d{5}SMLE)\b',
    ]

    BKG_PATTERNS = [
        r'\b(SGN\d{7,10})\b',
        r'\b(HANFG\d{7,10})\b',
        r'\bEBKG(\d{8,12})\b',
        r'BKG#?\s*(\d{6,12})',
        r'\b(\d{10})\b',
        r'\b(\d{8,9})\b',
        r'\b(\d{6,7})\b',
    ]

    MEMBER_REF_PATTERN = r'\b([A-Z]{2,8})(\d{6})-(\d{2,})\b'

    STAGE_PRECEDENCE = [
        'PAYMENT_CONFIRMED', 'INVOICE_ISSUED', 'DN_SENT', 'RELEASE', 'ATD',
        'LOADED', 'PRE_ALERT', 'DRAFT_BL_CONFIRMED', 'DRAFT_BL_ISSUED',
        'CY_UPDATE', 'SI_SUBMITTED', 'CONFIRM_EXW', 'BOOKING', 'RATES_CHECKING',
        'AMENDMENT', 'CHANGE_VESSEL', 'DELAY_NOTICE',
    ]

    RISK_KEYWORDS = {
        'CRITICAL': ['change vessel', 'urgent', 'gấp', 'asap', 'poa',
                     'changed mother vessel'],
        'HIGH':     ['delay notice', 'delay', 'rollover', 'amendment'],
        'MEDIUM':   ['update atd', 'update cy', 'update cot'],
    }

    # -----------------------------------------------------------------
    # classify
    # -----------------------------------------------------------------
    def classify(self, subject: str, sender: str, folder_path: str) -> str:
        """Returns: TYPE_SHIPMENT | TYPE_SALES | TYPE_INTERNAL"""
        subj_up = subject.upper()

        if re.search(self.SALES_PATTERN, subj_up):
            return 'TYPE_SALES'

        if 'pudongprime.vn' in sender.lower() and 'TEAM SUNNY' not in folder_path:
            return 'TYPE_INTERNAL'

        hbl_found = any(re.search(p, subj_up) for p in self.HBL_PATTERNS)
        bkg_found = any(re.search(p, subj_up) for p in self.BKG_PATTERNS)
        stage_found = any(
            kw.upper() in subj_up
            for keywords in self.STAGE_KEYWORDS.values()
            for kw in keywords
        )

        if hbl_found or bkg_found or stage_found:
            return 'TYPE_SHIPMENT'

        return 'TYPE_SALES'  # default: treat unknown as potential sales

    # -----------------------------------------------------------------
    # parse_shipment
    # -----------------------------------------------------------------
    def parse_shipment(self, subject: str, sender: str, recipients: str,
                       received_at: str, member_owner: str,
                       folder_context: str) -> dict:
        """Parse TYPE_SHIPMENT email. Returns structured dict."""
        subj_up = subject.upper()

        # Extract HBL
        hbl = None
        for pat in self.HBL_PATTERNS:
            m = re.search(pat, subj_up)
            if m:
                hbl = m.group(1)
                break

        # Extract BKG (skip if matches HBL)
        bkg = None
        for pat in self.BKG_PATTERNS:
            m = re.search(pat, subj_up)
            if m:
                candidate = m.group(1).strip()
                if candidate != hbl:
                    bkg = candidate
                    break

        # Member internal ref (JENNIE260204-01)
        ref_m = re.search(self.MEMBER_REF_PATTERN, subject)
        member_ref = ref_m.group(0) if ref_m else None

        # Shipment key: hbl > bkg > member_ref
        shipment_key = hbl or bkg or member_ref

        # Stages
        stages = []
        for stage, keywords in self.STAGE_KEYWORDS.items():
            if any(kw.upper() in subj_up for kw in keywords):
                stages.append(stage)

        # Primary stage (highest precedence)
        primary_stage = next(
            (s for s in self.STAGE_PRECEDENCE if s in stages), None
        )

        # Risk
        risk_level = 'NORMAL'
        risk_reasons = []
        for level in ['CRITICAL', 'HIGH', 'MEDIUM']:
            hits = [kw for kw in self.RISK_KEYWORDS[level]
                    if kw.upper() in subj_up]
            if hits:
                risk_level = level
                risk_reasons = hits
                break

        # Route
        route_m = re.search(
            r'\b(HPH|HCM|SGN|DAD|HAIPHONG)\s*[-–/]\s*([^/\n]{3,30}?)(?://|\s{2,}|ETD|$)',
            subj_up,
        )
        pol = route_m.group(1) if route_m else None
        pod = route_m.group(2).strip()[:30] if route_m else None

        # Other fields
        cont_m = re.search(r'(\d+[X*]\s*\d+\s*(?:DC|HC|RF|GP))', subj_up)
        etd_m  = re.search(r'ETD\s*[:#]?\s*(\d{1,2}\s*[A-Z]{3}|\d{2}[A-Z]{3})', subj_up)
        inco_m = re.search(r'\b(EXW|FOB|CIF|DAP|DDP|CFR|FCA|CIP)\b', subj_up)
        carr_m = re.search(
            r'\b(HPL|ZIM|MSC|ONE|CMA|EVERGREEN|YM|HAPAG|GSL|DANMAR|COSCO)\b',
            subj_up,
        )
        comm_m = re.search(r'COMM(?:ODITY)?:\s*([^/\n]{3,40})', subj_up)

        # Customer from folder context (e.g. "CNEE\PADDY WAX" → "PADDY WAX")
        customer_name = None
        folder_parts = folder_context.replace('\\', '/').split('/')
        if len(folder_parts) >= 2:
            customer_name = folder_parts[-1].strip().upper()

        # Confidence
        score = sum([
            20 if hbl else 0,
            20 if bkg or member_ref else 0,
            20 if primary_stage else 0,
            15 if pol and pod else 0,
            15 if etd_m else 0,
            10 if cont_m else 0,
        ])

        return {
            'email_type':       'TYPE_SHIPMENT',
            'subject_raw':      subject,
            'sender':           sender,
            'recipients':       recipients,
            'received_at':      received_at,
            'member_owner':     member_owner,
            'folder_context':   folder_context,
            'hbl':              hbl,
            'bkg':              bkg,
            'member_ref':       member_ref,
            'shipment_key':     shipment_key,
            'customer_name':    customer_name,
            'primary_stage':    primary_stage,
            'stages_detected':  stages,
            'risk_level':       risk_level,
            'risk_reasons':     risk_reasons,
            'pol':              pol,
            'pod':              pod,
            'route':            f"{pol}-{pod}" if pol and pod else None,
            'carrier':          carr_m.group(1) if carr_m else None,
            'container_type':   cont_m.group(1).replace(' ', '') if cont_m else None,
            'etd':              etd_m.group(1).strip() if etd_m else None,
            'incoterm':         inco_m.group(1) if inco_m else None,
            'commodity':        comm_m.group(1).strip() if comm_m else None,
            'parse_confidence': score,
            'needs_review':     score < 40,
        }

    # -----------------------------------------------------------------
    # parse_sales_reply
    # -----------------------------------------------------------------
    def parse_sales_reply(self, subject: str, sender: str, body: str | None,
                          received_at: str,
                          folder_context: str) -> dict:
        """Parse TYPE_SALES email. Returns intent + next action."""
        text = (subject + ' ' + (body or '')).upper()

        INTENT_MAP = {
            'HOT':           ['PLEASE QUOTE', 'SEND RATE', 'WHAT RATE',
                              'INTERESTED', 'WHEN CAN YOU', 'ASAP', 'URGENT',
                              'NEED BOOKING', 'PLEASE PROVIDE', 'CAN YOU SEND'],
            'WARM':          ['TELL ME MORE', 'WHAT SERVICE', 'TRANSIT TIME',
                              'SCHEDULE', 'WEEKLY SAILING', 'RELIABILITY',
                              'MORE INFO'],
            'PRICE_FIGHT':   ['CHEAPER', 'BETTER RATE', 'COMPETITOR',
                              'MARKET RATE', 'TOO HIGH', 'CAN YOU MATCH',
                              'BEAT THIS', 'LOWER PRICE'],
            'TIMING':        ['NEXT MONTH', 'NEXT QUARTER', 'AFTER PEAK',
                              'NOT NOW', 'MAYBE LATER', 'Q3', 'Q4'],
            'WRONG_PERSON':  ['NOT MY AREA', 'PLEASE CONTACT', 'OUR FORWARDER',
                              'WRONG EMAIL', 'FORWARD TO', 'NOT RESPONSIBLE'],
            'REFERRAL':      ['MY COLLEAGUE', 'CONTACT NAME', 'CC THIS PERSON',
                              'LOGISTICS TEAM', 'SUPPLY CHAIN'],
            'NEGATIVE':      ['NOT INTERESTED', 'REMOVE ME', 'UNSUBSCRIBE',
                              'DO NOT CONTACT', 'STOP EMAILING'],
            'AUTO_REPLY':    ['AUTOMATIC REPLY', 'OUT OF OFFICE', 'AUTO-REPLY',
                              'CURRENTLY UNAVAILABLE', 'ON VACATION'],
        }

        NEXT_ACTION = {
            'HOT':          'CALL_NOW',
            'WARM':         'EMAIL_TODAY',
            'PRICE_FIGHT':  'CHECK_SC',
            'TIMING':       'SCHEDULE_30D',
            'WRONG_PERSON': 'UPDATE_CONTACT',
            'REFERRAL':     'EMAIL_REFERRAL',
            'NEGATIVE':     'UNSUBSCRIBE',
            'AUTO_REPLY':   'WAIT_RETURN',
        }

        URGENCY = {
            'HOT': 'IMMEDIATE', 'WARM': 'TODAY', 'PRICE_FIGHT': 'TODAY',
            'TIMING': 'SCHEDULED', 'WRONG_PERSON': 'THIS_WEEK',
            'REFERRAL': 'THIS_WEEK', 'NEGATIVE': 'NONE', 'AUTO_REPLY': 'NONE',
        }

        # Detect intent
        intent = 'UNKNOWN'
        for intent_type, keywords in INTENT_MAP.items():
            if any(kw in text for kw in keywords):
                intent = intent_type
                break

        # Campaign detection from subject
        week_m = re.search(r'NELSON\s+WEEK\s+(\d+)', subject.upper())
        campaign_week = int(week_m.group(1)) if week_m else None

        # Extract campaign type from subject prefix
        campaign_type = None
        if '//' in subject:
            prefix = subject.split('//')[0].strip().upper()
            for tag in ['FURNITURE', 'CANDLE', 'PLASTIC', 'PLYWOOD', 'FLOORING',
                        'FROZEN', 'SEAFOOD', 'RUBBER', 'TOY', 'GARMENT']:
                if tag in prefix:
                    campaign_type = tag
                    break

        # Customer from folder (CNEE\PADDY WAX → PADDY WAX)
        customer_name = None
        folder_parts = folder_context.replace('\\', '/').split('/')
        if len(folder_parts) >= 2 and folder_parts[0].upper() == 'CNEE':
            customer_name = folder_parts[-1].strip().upper()

        return {
            'email_type':     'TYPE_SALES',
            'subject_raw':    subject,
            'sender':         sender,
            'received_at':    received_at,
            'folder_context': folder_context,
            'customer_name':  customer_name,
            'campaign_week':  campaign_week,
            'campaign_type':  campaign_type,
            'intent':         intent,
            'next_action':    NEXT_ACTION.get(intent, 'REVIEW'),
            'urgency':        URGENCY.get(intent, 'THIS_WEEK'),
            'body_preview':   (body or '')[:500],
        }
