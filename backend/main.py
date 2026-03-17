"""
ThreatScope backend application entrypoint.

This module creates and configures the FastAPI application used by the
central ThreatScope backend. The structure is intentionally lightweight so
the rest of the backend can evolve independently.

Responsibilities:
- create the FastAPI app
- register API routers
- register WebSocket routes
- expose health and root metadata endpoints
- configure CORS
- wire the correlation engine to the WebSocket broadcaster
- expose Prometheus metrics endpoint through the existing websocket module

This file avoids assuming every optional subsystem is fully implemented.
Where imports are not available yet, it degrades gracefully instead of
preventing the app from starting.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Callable

import structlog
import uvicorn
from app.core.config import settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Optional / existing backend modules.
# These imports are isolated so the entrypoint remains resilient while the
# repository is still being structured.
try:
    from app.api.routes import alerts, auth, nodes, signals
except Exception:  # pragma: no cover - defensive bootstrap import
    alerts = None
    auth = None
    nodes = None
    signals = None

try:
    from app.api.websocket import manager
    from app.api.websocket import router as websocket_router
except Exception:  # pragma: no cover - defensive bootstrap import
    manager = None
    websocket_router = None

try:
    from app.correlation.engine import correlation_engine
except Exception:  # pragma: no cover - defensive bootstrap import
    correlation_engine = None


# ── Logging ──────────────────────────────────────────────────────────────────

def configure_logging() -> None:
    """Configure structlog + stdlib logging once at startup."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=logging.INFO)


configure_logging()
log = structlog.get_logger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_cors_origins() -> list[str]:
    """
    Return allowed CORS origins.

    Development defaults are permissive to keep local iteration simple.
    Production should be narrowed to known frontend origins.
    """
    if settings.app_env.lower() == "development":
        return ["*"]

    return [
        "http://localhost:5173",
        "https://your-frontend-domain.com",
    ]


def _include_router_if_present(app: FastAPI, maybe_router_module) -> None:
    """Register a router module if it imported successfully."""
    if maybe_router_module is None:
        return

    router = getattr(maybe_router_module, "router", None)
    if router is not None:
        app.include_router(router)


def _wire_broadcast() -> None:
    """
    Inject the WebSocket broadcast callback into the correlation engine.

    The correlation engine emits alert events; the connection manager handles
    fan-out to connected dashboard clients.
    """
    if correlation_engine is None or manager is None:
        return

    broadcast: Callable | None = getattr(manager, "broadcast", None)
    if broadcast is not None:
        correlation_engine.broadcast = broadcast
        log.info("correlation_engine_broadcast_wired")


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(
        "threatscope_starting",
        app_name=settings.app_name,
        environment=settings.app_env,
    )

    _wire_broadcast()

    yield

    log.info("threatscope_stopped")


# ── App Factory ──────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ThreatScope Backend",
        description="Privacy-preserving real-time cyber threat intelligence backend.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_get_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Core API routers
    _include_router_if_present(app, auth)
    _include_router_if_present(app, nodes)
    _include_router_if_present(app, alerts)
    _include_router_if_present(app, signals)

    # WebSocket / metrics router
    if websocket_router is not None:
        app.include_router(websocket_router)

    @app.get("/", tags=["system"])
    async def root() -> dict:
        return {
            "name": settings.app_name,
            "service": "backend",
            "environment": settings.app_env,
            "status": "ok",
        }

    @app.get("/health", tags=["system"], include_in_schema=False)
    async def health() -> dict:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
        }

    @app.get("/healthz", tags=["system"], include_in_schema=False)
    async def healthz() -> dict:
        return {"ok": True}

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env.lower() == "development",
    )
