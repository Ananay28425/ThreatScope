"""FastAPI assembly with explicit readiness, bounded input, and no hidden optional imports."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.config import Settings, get_settings
from backend.app.database import Database
from backend.app.explain_worker import process_one, recover_jobs
from backend.app.http_api import router
from backend.app.stream import router as stream_router
from backend.app.worker import correlate_once


def create_app(settings: Settings | None = None, database: Database | None = None, *,
               demo_workers: bool = False, frontend_dir: Path | None = None) -> FastAPI:
    config = settings or get_settings()
    db = database or Database(config)
    if demo_workers and (config.app_env != "demo" or db.engine.dialect.name != "sqlite"):
        raise ValueError("in_process_workers_require_the_single_process_sqlite_demo")

    async def loop(action, pause):
        while True:
            try:
                await action(db, config)
            except Exception:
                logging.getLogger(__name__).exception("Demo worker iteration failed")
            await asyncio.sleep(pause)

    @asynccontextmanager
    async def lifespan(app):
        async with db.engine.connect() as connection:
            await connection.execute(text("SELECT id FROM ts_organizations LIMIT 1"))
        tasks = []
        try:
            if demo_workers:
                await recover_jobs(db)
                tasks = [
                    asyncio.create_task(loop(correlate_once, config.worker_poll_seconds)),
                    asyncio.create_task(loop(process_one, 0.5)),
                ]
            yield
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await db.close()

    app = FastAPI(title="ThreatScope", version="0.2.0", lifespan=lifespan)
    app.state.settings, app.state.database = config, db
    if config.demo_access:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.add_middleware(
        CORSMiddleware, allow_origins=sorted(config.origins), allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type", "X-CSRF-Token", "X-Api-Key"],
    )

    @app.middleware("http")
    async def bound_request(request: Request, call_next):
        if request.method in {"POST", "PATCH", "PUT"}:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > config.max_body_bytes:
                    return JSONResponse({"detail": "body_too_large"}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": [
            {"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()
        ]}, status_code=422)

    @app.get("/health/live", include_in_schema=False)
    async def live():
        return {"status": "alive"}

    @app.get("/health/ready", include_in_schema=False)
    async def ready():
        try:
            async with db.engine.connect() as connection:
                await connection.execute(text("SELECT id FROM ts_organizations LIMIT 1"))
        except Exception:
            return JSONResponse({"status": "database_or_migration_unavailable"}, status_code=503)
        return {"status": "ready"}

    app.include_router(router)
    app.include_router(stream_router)
    if frontend_dir:
        app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="dashboard")
    return app


app = create_app()
