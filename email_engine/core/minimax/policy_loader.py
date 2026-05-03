# -*- coding: utf-8 -*-
"""policy_loader.py — Load Nelson Freight system policy schema."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_SCHEMA: Optional[dict] = None


def get_schema() -> dict:
    global _SCHEMA
    if _SCHEMA is None:
        path = Path(__file__).parent / "policy_schema.json"
        with open(path, encoding="utf-8") as f:
            _SCHEMA = json.load(f)
    return _SCHEMA


def build_system_prompt(task: str = "email_reply") -> str:
    """Return system prompt with policy schema injected."""
    schema = get_schema()
    return f"""System: You are Nelson Freight AI assistant — NVOCC freight expert for Vietnam → USA/Canada lanes.
You MUST follow this company policy for all responses:

COMPANY: {schema['company']['name']} ({schema['company']['type']})
LANES: {', '.join(schema['company']['lanes'])}
PORTS OF LOADING: {', '.join(schema['company']['ports_of_loading'])}
PORTS OF DISCHARGE: {', '.join(schema['company']['ports_of_discharge'])}

SERVICES: {json.dumps(schema['services'], indent=2)}

CARRIERS: {json.dumps(schema['carriers'], indent=2)}

CAMPAIGNS: {json.dumps(schema['campaigns'], indent=2)}

EMAIL TONE: {schema['email_policy']['tone']}
RESPONSE TIME: {schema['email_policy']['response_time']}
SIGN OFF: {schema['email_policy']['sign_off']}

INTENT MAPPING: {json.dumps(schema['intent_mapping'], indent=2)}

SERVICE RECOMMENDATION RULES: {json.dumps(schema['service_recommendation_rules'], indent=2)}

Task: {task}
"""
