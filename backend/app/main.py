from fastapi import FastAPI

from app.api import system
from app.core.clock import WallClock
from app.core.db import create_db_engine, create_session_factory
from app.core.errors import Problem, register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    CorrelationIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.migrations import expected_head
from app.core.settings import Settings
from app.monitor.service import ReadinessService

API_VERSION = "0.1.0"


def create_app(settings: Settings) -> FastAPI:
    session_factory = create_session_factory(create_db_engine(settings))
    app = FastAPI(
        title="IPHI API",
        version=API_VERSION,
        summary="Health intelligence for a simulated industrial data platform.",
        openapi_url="/api/v1/openapi.json",
        responses={"default": {"model": Problem, "description": "RFC 9457 problem details."}},
    )
    app.state.readiness = ReadinessService(
        session_factory,
        WallClock(),
        expected_revision=expected_head(),
        cycle_interval_s=settings.cycle_interval_s,
        llm_provider=settings.llm_provider,
    )
    register_error_handlers(app)
    app.include_router(system.router)
    # Starlette runs the last added middleware first. Security headers wrap every response,
    # including the 413 and crash responses produced by the two inner middlewares.
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    return app


def build() -> FastAPI:
    """Uvicorn factory entry point (`uvicorn app.main:build --factory`)."""
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    return create_app(settings)
