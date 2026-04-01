# -*- coding: utf-8 -*-
"""
rate_limit.py — Rate Limiting Middleware
==========================================
Simple in-memory rate limiting per IP address.
Configurable per route group (default, heavy, auth).

Scale path:
- Phase 1: In-memory dict (current) — single server
- Phase 2: Redis INCR + EXPIRE — multi-server

Config via environment:
    RATE_LIMIT_ENABLED=true
    RATE_LIMIT_DEFAULT=60      # requests per minute
    RATE_LIMIT_HEAVY=10        # for expensive endpoints
"""
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

log = logging.getLogger("nelson.ratelimit")


@dataclass
class RateBucket:
    """Track requests for a single client."""
    count: int = 0
    window_start: float = 0.0


# Heavy endpoints that need lower limits
HEAVY_PATHS = {
    "/api/dashboard/charts",
    "/api/rates/regions",
    "/api/rates/matrix",
    "/api/quotes/intelligence",
    "/api/intelligence/4c",
    "/api/intelligence/carriers",
    "/api/intelligence/market",
    "/api/workers/evaluator/run",
    "/api/workers/email/scan",
}

# Auth paths — no rate limit or very high
EXEMPT_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/api/auth/status",
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-IP rate limiting with tiered limits.

    Default: 60 req/min
    Heavy: 10 req/min (expensive endpoints)
    Exempt: unlimited (docs, health checks)
    """

    def __init__(self, app, default_limit: int = 60, heavy_limit: int = 10,
                 window_seconds: int = 60, enabled: bool = True):
        super().__init__(app)
        self.default_limit = default_limit
        self.heavy_limit = heavy_limit
        self.window = window_seconds
        self.enabled = enabled
        self._buckets: dict[str, RateBucket] = defaultdict(RateBucket)
        self._cleanup_counter = 0

    def _get_client_key(self, request: Request) -> str:
        """Get unique client identifier (IP or API key)."""
        api_key = request.headers.get("x-api-key")
        if api_key:
            return f"key:{api_key[:8]}"
        ip = request.client.host if request.client else "unknown"
        return f"ip:{ip}"

    def _get_limit(self, path: str) -> Optional[int]:
        """Get rate limit for path. Returns None for exempt paths."""
        if path in EXEMPT_PATHS:
            return None
        if path in HEAVY_PATHS:
            return self.heavy_limit
        return self.default_limit

    def _is_allowed(self, client_key: str, limit: int) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining)."""
        now = time.time()
        bucket = self._buckets[client_key]

        # Reset window if expired
        if now - bucket.window_start > self.window:
            bucket.count = 0
            bucket.window_start = now

        bucket.count += 1
        remaining = max(0, limit - bucket.count)
        return bucket.count <= limit, remaining

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        path = request.url.path
        limit = self._get_limit(path)

        # Exempt paths
        if limit is None:
            return await call_next(request)

        client_key = self._get_client_key(request)
        allowed, remaining = self._is_allowed(client_key, limit)

        if not allowed:
            log.warning("Rate limit exceeded: %s on %s (%d/%d)",
                        client_key, path, limit, limit)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "limit": limit,
                    "window": f"{self.window}s",
                    "retry_after": self.window,
                },
                headers={
                    "Retry-After": str(self.window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                }
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        # Periodic cleanup of old buckets
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self._cleanup()
            self._cleanup_counter = 0

        return response

    def _cleanup(self):
        """Remove expired buckets to prevent memory growth."""
        now = time.time()
        expired = [k for k, v in self._buckets.items()
                   if now - v.window_start > self.window * 2]
        for k in expired:
            del self._buckets[k]
        if expired:
            log.debug("Cleaned up %d expired rate limit buckets", len(expired))
