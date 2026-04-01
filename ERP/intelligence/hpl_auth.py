# -*- coding: utf-8 -*-
"""
hpl_auth.py — HPL API Authentication
=====================================
Manages X-IBM-Client-ID + X-IBM-Client-Secret headers for HPL API calls.
Supports both direct API credentials and OAuth 2.0 token flow.

Usage:
    from ERP.intelligence.hpl_auth import HPLAuth
    auth = HPLAuth()
    headers = auth.headers()
    response = requests.get(url, headers=headers)
"""
import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger("nelson.hpl_auth")

# ── HPL API Endpoints ─────────────────────────────────────────
HPL_BASE_URL = "https://api.hlag.com"

HPL_ENDPOINTS = {
    "schedule": f"{HPL_BASE_URL}/cs/v3/point-to-point-routes",
    "track":    f"{HPL_BASE_URL}/tt/v2/events",
    "offers":   f"{HPL_BASE_URL}/qtn/v4/offers",
    "oauth":    f"{HPL_BASE_URL}/oauth2/token",
}


class HPLAuth:
    """
    HPL API authentication handler.

    Reads credentials from environment variables:
        HPL_CLIENT_ID     — X-IBM-Client-ID
        HPL_CLIENT_SECRET — X-IBM-Client-Secret

    Supports two auth modes:
        1. API Key (headers only) — for Schedule, T&T
        2. OAuth 2.0 (Bearer token) — for Offers API
    """

    def __init__(self):
        self.client_id = os.getenv("HPL_CLIENT_ID", "")
        self.client_secret = os.getenv("HPL_CLIENT_SECRET", "")
        self._oauth_token: Optional[str] = None
        self._token_expiry: float = 0

        if not self.client_id:
            logger.warning("[HPL Auth] HPL_CLIENT_ID not set — using mock mode")

    @property
    def is_configured(self) -> bool:
        """Check if API credentials are configured."""
        return bool(self.client_id and self.client_secret)

    def headers(self, use_oauth: bool = False) -> dict:
        """
        Build request headers for HPL API calls.

        Args:
            use_oauth: If True, use OAuth 2.0 Bearer token (for Offers API).
                       If False, use X-IBM-Client headers (for Schedule, T&T).
        """
        base = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        if not self.is_configured:
            return base  # Mock mode — no auth headers

        if use_oauth:
            token = self._get_oauth_token()
            if token:
                base["Authorization"] = f"Bearer {token}"
        else:
            base["X-IBM-Client-Id"] = self.client_id
            base["X-IBM-Client-Secret"] = self.client_secret

        return base

    def _get_oauth_token(self) -> Optional[str]:
        """Get or refresh OAuth 2.0 token."""
        now = time.time()

        # Return cached token if still valid (with 60s buffer)
        if self._oauth_token and now < (self._token_expiry - 60):
            return self._oauth_token

        try:
            resp = requests.post(
                HPL_ENDPOINTS["oauth"],
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            self._oauth_token = data["access_token"]
            self._token_expiry = now + data.get("expires_in", 3600)

            logger.info("[HPL Auth] OAuth token refreshed, expires in %ds",
                        data.get("expires_in", 3600))
            return self._oauth_token

        except Exception as e:
            logger.error("[HPL Auth] OAuth token refresh failed: %s", e)
            return None

    @staticmethod
    def get_endpoint(api: str) -> str:
        """Get the full URL for an HPL API endpoint."""
        return HPL_ENDPOINTS.get(api, "")


# ── Module-level singleton ────────────────────────────────────
_auth_instance: Optional[HPLAuth] = None


def get_auth() -> HPLAuth:
    """Get or create the singleton HPLAuth instance."""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = HPLAuth()
    return _auth_instance
