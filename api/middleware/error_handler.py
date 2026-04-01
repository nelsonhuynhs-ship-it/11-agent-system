# -*- coding: utf-8 -*-
"""
error_handler.py — Structured Error Handling
===============================================
Catches exceptions globally and returns consistent JSON error responses.
"""
import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("nelson.api")


def register_error_handlers(app: FastAPI):
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        log.warning("ValueError on %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad Request",
                "detail": str(exc),
                "path": request.url.path,
            },
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):
        log.warning("FileNotFoundError on %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=404,
            content={
                "error": "Resource Not Found",
                "detail": str(exc),
                "path": request.url.path,
            },
        )

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        log.warning("PermissionError on %s: %s", request.url.path, str(exc))
        return JSONResponse(
            status_code=403,
            content={
                "error": "Forbidden",
                "detail": str(exc),
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        log.error(
            "Unhandled exception on %s %s: %s\n%s",
            request.method, request.url.path, str(exc),
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "detail": str(exc) if log.isEnabledFor(logging.DEBUG) else "An unexpected error occurred",
                "path": request.url.path,
            },
        )
