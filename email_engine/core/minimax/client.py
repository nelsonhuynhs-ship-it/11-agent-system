# -*- coding: utf-8 -*-
"""Unified MiniMax HTTP client — text, VL, image, speech."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx

from .models import TextModel, VLModel, ImageModel
from .token_tracker import track

log = logging.getLogger(__name__)

_MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY")
_IS_MOCK = _MINIMAX_API_KEY is None

_TEXT_ENDPOINT = "https://api.minimax.chat/v1/text/chatcompletion_v2"
_VL_ENDPOINT = "https://api.minimax.chat/v1/vision/chatcompletion_v2"
_IMAGE_ENDPOINT = "https://api.minimax.chat/v1/images/generations"
_SPEECH_ENDPOINT = "https://api.minimax.chat/v1/t2a_v2"


class MiniMaxClient:
    def text(
        self,
        prompt: str,
        system: Optional[str] = None,
        model: TextModel = TextModel.TEXT_01,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        if _IS_MOCK:
            return f"[MOCK] {prompt[:80]}"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model.value,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            payload["messages"].insert(0, {"role": "system", "content": system})

        headers = {
            "Authorization": f"Bearer {_MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(_TEXT_ENDPOINT, json=payload, headers=headers)
                resp.raise_for_status()
            data = resp.json()
            track(model.value, tokens_in=data.get("usage", {}).get("prompt_tokens", 0),
                  tokens_out=data.get("usage", {}).get("completion_tokens", 0))
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            log.warning("minimax.text error: %s", exc)
            return f"[ERROR] {exc}"

    def vision(self, image_path: str, prompt: str, model: VLModel = VLModel.VL_02) -> str:
        if _IS_MOCK:
            return f"[MOCK VL] image={image_path}, prompt={prompt[:50]}"

        with open(image_path, "rb") as f:
            import base64
            img_b64 = base64.b64encode(f.read()).decode()

        payload = {
            "model": model.value,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {_MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(_VL_ENDPOINT, json=payload, headers=headers)
                resp.raise_for_status()
            data = resp.json()
            track(model.value)
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            log.warning("minimax.vision error: %s", exc)
            return f"[ERROR] {exc}"

    def image(
        self,
        prompt: str,
        model: ImageModel = ImageModel.IMAGE_01,
        size: str = "1024x1024",
    ) -> str:
        if _IS_MOCK:
            return f"[MOCK IMAGE] {prompt[:60]}"

        payload = {
            "model": model.value,
            "prompt": prompt,
            "size": size,
        }
        headers = {
            "Authorization": f"Bearer {_MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=120) as client:
                resp = client.post(_IMAGE_ENDPOINT, json=payload, headers=headers)
                resp.raise_for_status()
            data = resp.json()
            track(model.value)
            return data["data"][0]["url"]
        except Exception as exc:
            log.warning("minimax.image error: %s", exc)
            return f"[ERROR] {exc}"

    def speech(
        self,
        text: str,
        model: str = "speech-2.8-hd",
        voice: str = "male-qn",
    ) -> bytes:
        if _IS_MOCK:
            return b"[MOCK AUDIO]"

        payload = {
            "model": model,
            "voice": voice,
            "text": text,
        }
        headers = {
            "Authorization": f"Bearer {_MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(_SPEECH_ENDPOINT, json=payload, headers=headers)
                resp.raise_for_status()
            data = resp.json()
            track(model)
            import base64
            return base64.b64decode(data["data"]["audio"])
        except Exception as exc:
            log.warning("minimax.speech error: %s", exc)
            return b"[ERROR]"

    def get_usage(self):
        from .token_tracker import get_usage
        return get_usage()

    def extract(self, email_text: str) -> str:
        result = self.text(
            system=(
                "Extract shipment event from this freight email. "
                "Return JSON: {\"shipment_ref\", \"event_type\"}. "
                "If none, return {\"shipment_ref\": null}."
            ),
            prompt=email_text[:2000],
            temperature=0.0,
        )
        return result


minimax = MiniMaxClient()


def extract(email_text: str) -> str:
    """Backward-compat wrapper — delegates to minimax.text()."""
    return minimax.extract(email_text)
