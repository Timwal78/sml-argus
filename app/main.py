"""
ARGUS — Main Application Entry Point
The organism awakens here.
"""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import set_session_factory
from storage.models import Base
from storage.repository import create_engine_and_session
from routes import scan, state, integrations, chart, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("argus")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start-up: create DB tables and session factory."""
    global _session_factory
    logger.info("ARGUS — Organism initializing...")

    engine, session_factory = create_engine_and_session(settings.database_url)
    set_session_factory(session_factory)

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database initialized.")
    logger.info("ARGUS — Organism online. Hidden state detection active.")

    yield  # app runs

    logger.info("ARGUS — Organism shutting down.")
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SML ARGUS",
        description=(
            "100 eyes. Always watching. Nothing hidden. "
            "A standalone market intelligence organism by ScriptMasterLabs. "
            "Detects, scores, debates, remembers, and narrates market pressure "
            "before it becomes obvious."
        ),
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # lock down in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(scan.router, tags=["Intelligence"])
    app.include_router(state.router, tags=["State & Memory"])
    app.include_router(integrations.router, tags=["Integrations"])
    app.include_router(chart.router, tags=["Chart Surface"])
    app.include_router(dashboard.router, tags=["Dashboard"])

    # ── Health ────────────────────────────────────────────────────────────────
    @app.get("/", tags=["System"])
    async def root():
        return {
            "system": "SML ARGUS",
            "version": settings.app_version,
            "status": "online",
            "tagline": "100 eyes. Always watching. Nothing hidden.",
            "by": "ScriptMasterLabs",
        }

    @app.get("/health", tags=["System"])
    async def health():
        return {"status": "healthy", "organism": "active"}

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "detail": str(exc)},
        )

    return app


app = create_app()
