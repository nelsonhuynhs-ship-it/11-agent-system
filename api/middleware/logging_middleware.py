# -*- coding: utf-8 -*-
"""
logging_middleware.py — Request/Response Logging
==================================================
Logs every API request with timing, status, and errors.
"""
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = logging.getLogger("nelson.api")

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with:
    - Method + Path
    - Response status code
    - Latency (ms)
    - Client IP
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        method = request.method
        path = request.url.path
        client = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000
            status = response.status_code

            if status >= 500:
                log.error(
                    "%s %s → %d (%.0fms) client=%s",
                    method, path, status, elapsed_ms, client,
                )
            elif status >= 400:
                log.warning(
                    "%s %s → %d (%.0fms) client=%s",
                    method, path, status, elapsed_ms, client,
                )
            elif elapsed_ms > 2000:
                log.warning(
                    "%s %s → %d (%.0fms SLOW) client=%s",
                    method, path, status, elapsed_ms, client,
                )
            else:
                log.info(
                    "%s %s → %d (%.0fms)",
                    method, path, status, elapsed_ms,
                )

            return response

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            log.error(
                "%s %s → EXCEPTION (%.0fms): %s",
                method, path, elapsed_ms, str(exc),
            )
            raise
