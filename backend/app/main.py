import structlog
from fastapi import FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import simulations, system
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
from app.identity.domain import MutationPolicy
from app.identity.service import AuditService
from app.monitor.service import ReadinessService
from app.simulation.service import build_simulation

API_VERSION = "0.2.0"

log = structlog.get_logger(__name__)


def create_app(settings: Settings) -> FastAPI:
    session_factory = create_session_factory(create_db_engine(settings))
    app = FastAPI(
        title="IPHI API",
        version=API_VERSION,
        summary="Health intelligence for a simulated industrial data platform.",
        openapi_url="/api/v1/openapi.json",
        responses={"default": {"model": Problem, "description": "RFC 9457 problem details."}},
    )
    wall = WallClock()
    app.state.readiness = ReadinessService(
        session_factory,
        wall,
        expected_revision=expected_head(),
        cycle_interval_s=settings.cycle_interval_s,
        llm_provider=settings.llm_provider,
    )
    app.state.simulation = build_simulation(session_factory, wall)
    app.state.audit = AuditService(session_factory, wall)
    app.state.sim_seed = settings.sim_seed
    policy = MutationPolicy.evaluate(settings.dev_mutations, settings.bind_host)
    app.state.mutation_policy = policy
    if settings.dev_mutations and not policy.enabled:
        log.warning("api.mutations_refused", reason=policy.reason)
    register_error_handlers(app)
    app.include_router(system.router)
    app.include_router(simulations.router)
    # Starlette runs the last added middleware first. Security headers wrap every response,
    # including the 413 and crash responses produced by the two inner middlewares.
    # Unauthenticated loopback mutations (ADR 0007) must not be reachable through a rebound
    # DNS name pointing a hostile page at 127.0.0.1.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    return app


def build() -> FastAPI:
    """Uvicorn factory entry point (`uvicorn app.main:build --factory`)."""
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    return create_app(settings)
