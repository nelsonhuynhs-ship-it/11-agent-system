# -*- coding: utf-8 -*-
import pytest
from email_engine.core.minimax import minimax, TextModel, VLModel, ImageModel


def test_text_returns_string():
    result = minimax.text("say hello")
    assert isinstance(result, str)
    assert len(result) > 0


def test_vision_returns_string():
    result = minimax.vision("/fake/path.jpg", "describe this")
    assert isinstance(result, str)


def test_image_returns_string():
    result = minimax.image("a blue square")
    assert isinstance(result, str)


def test_speech_returns_bytes():
    result = minimax.speech("hello world")
    assert isinstance(result, bytes)


def test_get_usage():
    usage = minimax.get_usage()
    assert isinstance(usage, dict)


def test_extract_backward_compat():
    from email_engine.core.minimax import extract
    result = extract("Booking confirmed for HPL2604001")
    assert isinstance(result, str)