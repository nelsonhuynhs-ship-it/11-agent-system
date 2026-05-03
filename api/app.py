# -*- coding: utf-8 -*-
"""
app.py — Nelson Freight API Entry Point v2.3.0
=================================================
Modular FastAPI application: routers + middleware + event bus + workers.

Run:
    uvicorn app:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from config import cfg

log = logging.getLogger("nelson.api")


# ── Lifespan (startup/shutdown) ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start workers on startup, stop on shutdown."""
    log.info("Nelson Freight API v2.3.0 starting...")
    log.info("Config: %s", cfg.summary())

    # Start workers
    from workers.intelligence_worker import intelligence_worker
    from services.notification import notification_service

    intelligence_worker.start()     # Event-driven (no scheduler needed)
    notification_service.start()    # Event-driven

    # Optional: start scheduled workers
    if cfg.EMAIL_WORKER_ENABLED:
        try:
            from workers.email_worker import email_worker
            email_worker.start()
        except Exception as e:
            log.warning("Email worker not started: %s", e)

    if cfg.EVALUATOR_ENABLED:
        try:
            from workers.evaluator_worker import evaluator_worker
            evaluator_worker.start()
        except Exception as e:
            log.warning("Evaluator worker not started: %s", e)

    log.info("All workers started ✓")

    # Email send pipeline moved to email_engine/web_server.py (local PC + Outlook COM).
    # No DuckDB pre-warm or email queue reset here — handled by local worker.

    yield

    # Shutdown
    log.info("Shutting down workers...")
    try:
        from workers.email_worker import email_worker
        email_worker.stop()
    except Exception:
        pass
    try:
        from workers.evaluator_worker import evaluator_worker
        evaluator_worker.stop()
    except Exception:
        pass

    # Close database pools
    try:
        from database.connection import close_pools
        import asyncio
        await close_pools()
    except Exception:
        pass


# ── Create App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Nelson Freight API",
    version="2.3.0",
    description="Logistics automation — modular + event-driven + ERP bridge + rate limiting",
    lifespan=lifespan,
)

# ── Middleware (order matters: last added = first executed) ────────────────────
# 1. CORS (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Logging
from middleware.logging_middleware import LoggingMiddleware
app.add_middleware(LoggingMiddleware)

# 3. Rate Limiting
from middleware.rate_limit import RateLimitMiddleware
app.add_middleware(
    RateLimitMiddleware,
    default_limit=cfg.RATE_LIMIT_DEFAULT,
    heavy_limit=cfg.RATE_LIMIT_HEAVY,
    enabled=cfg.RATE_LIMIT_ENABLED,
)

# ── Error Handlers ────────────────────────────────────────────────────────────
from middleware.error_handler import register_error_handlers
register_error_handlers(app)

# ── Mount Routers ─────────────────────────────────────────────────────────────
from routers.rate_router import router as rate_router
from routers.quote_router import router as quote_router
from routers.shipment_router import router as shipment_router
from routers.dashboard_router import router as dashboard_router
from routers.intelligence_router import router as intelligence_router
from routers.email_router import router as email_router
from routers.voice_router import router as voice_router
from routers.auth_router import router as auth_router
from routers.worker_router import router as worker_router
from routers.erp_router import router as erp_router
from routers.health_router import router as health_router
from routers.reports_router import router as reports_router
from routers.pricing_router import router as pricing_router
from routers.job_router import router as job_router
from routers.data_router import router as data_router              # Email platform data
from routers.sync_router import router as sync_router                # ERP sync
from routers.customer_check_router import router as customer_check_router  # Tax code check
from routers.admin_router import router as admin_router                  # Token admin
# REMOVED 2026-04-17: email_rate_router, email_queue_router, auto_quote_router
# Email send pipeline now lives in email_engine/web_server.py (local PC + Outlook COM).
# See docs/EMAIL_PIPELINE_SOURCE_OF_TRUTH.md

app.include_router(rate_router)
app.include_router(quote_router)
app.include_router(shipment_router)
app.include_router(dashboard_router)
app.include_router(intelligence_router)
app.include_router(email_router)
app.include_router(voice_router)
app.include_router(auth_router)
app.include_router(worker_router)
app.include_router(erp_router)
app.include_router(health_router)
app.include_router(reports_router)
app.include_router(pricing_router)
app.include_router(job_router)
app.include_router(data_router)
app.include_router(sync_router)
app.include_router(customer_check_router)
app.include_router(admin_router)

# ── Event Bus ─────────────────────────────────────────────────────────────────
from event_bus import bus

@app.get("/api/events")
def get_events(event_type: str = Query(None), limit: int = Query(50)):
    """View recent events from the event bus (now persisted to JSONL)."""
    return {
        "events": bus.get_recent_events(event_type, limit),
        "stats": bus.stats,
    }

# ── Config Endpoint ───────────────────────────────────────────────────────────
@app.get("/api/config")
def get_config():
    """View current system configuration (non-sensitive values only)."""
    return cfg.summary()

# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "name": "Nelson Freight API",
        "version": "2.3.0",
        "architecture": "Modular (10 routers + DAL + EventBus + Workers + RateLimit)",
        "docs": "/docs",
    }
