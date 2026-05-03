# -*- coding: utf-8 -*-
import pytest
from email_engine.core.minimax.policy_loader import get_schema, build_system_prompt


def test_get_schema_returns_dict():
    schema = get_schema()
    assert isinstance(schema, dict)
    assert schema["company"]["name"] == "Nelson Freight"


def test_build_system_prompt_returns_string():
    prompt = build_system_prompt("summarize_email")
    assert isinstance(prompt, str)
    assert "Nelson Freight" in prompt
    assert len(prompt) > 100


def test_policy_schema_has_required_keys():
    schema = get_schema()
    assert "company" in schema
    assert "services" in schema
    assert "campaigns" in schema
    assert "carriers" in schema
    assert "email_policy" in schema
    assert "intent_mapping" in schema