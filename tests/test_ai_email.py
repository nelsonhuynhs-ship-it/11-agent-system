# -*- coding: utf-8 -*-
import pytest
from email_engine.core.ai_email import summarize_email, draft_reply, suggest_next_sentence


def test_summarize_email_returns_dict():
    result = summarize_email("Hello, I need a quote for shipping to USA", "test@example.com")
    assert isinstance(result, dict)


def test_draft_reply_returns_string():
    incoming = {"subject": "Quote?", "body": "Please quote 40HQ to LA", "sender": "test@example.com"}
    cnee = {"name": "ABC Corp", "campaign": "FURNITURE", "preferred_pods": ["USLAX"], "preferred_carriers": ["MSC"]}
    result = draft_reply(incoming, cnee)
    assert isinstance(result, str)
    assert len(result) > 0


def test_suggest_next_sentence_returns_string():
    result = suggest_next_sentence(["Hello", "I need shipping"], "Thank you for your inquiry")
    assert isinstance(result, str)