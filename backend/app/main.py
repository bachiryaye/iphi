from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import Depends, FastAPI
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import (
    audit,
    auth,
    events,
    health,
    incidents,
    observations,
    reports,
    simulations,
    system,
)
from app.connectors.registry import enabled_connector_keys
from app.core.clock import WallClock
from app.core.db import create_db_engine, create_session_factory
from app.core.errors import Problem, register_error_handlers
from app.core.frontend import FrontendFiles
from app.core.logging import configure_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    CorrelationIdMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.migrations import expected_head
from app.core.settings import Settings
from app.diagnostics.providers import build_provider
from app.diagnostics.service import DiagnosticRuntime, DiagnosticsService
from app.health.history_service import StateHistoryQueries
from app.health.service import HealthQueries
from app.identity.audit_queries import AuditQueries
from app.identity.auth_service import AuthService
from app.identity.service import AuditService
from app.incidents.service import IncidentCommands, IncidentQueries
from app.ingestion.service import MetricCatalogService, ObservationQueryService
from app.monitor.events import EventHub
from app.monitor.service import MonitoredParts, ReadinessService, SystemStatusService
from app.reporting.pdf import PdfRenderer
from app.reporting.service import ReportingService
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.service import build_simulation
from app.topology.service import TopologyService

API_VERSION = "0.11.0"

log = structlog.get_logger(__name__)


def create_app(settings: Settings) -> FastAPI:
    session_factory = create_session_factory(create_db_engine(settings))
    wall = WallClock()
    simulation = build_simulation(session_factory, wall)
    hub = EventHub(
        settings.database_url.get_secret_value(), lambda: simulation.clock().platform_time
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with hub.running():
            yield

    app = FastAPI(
        title="IPHI API",
        version=API_VERSION,
        summary="Health intelligence for a simulated industrial data platform.",
        openapi_url="/api/v1/openapi.json",
        responses={"default": {"model": Problem, "description": "RFC 9457 problem details."}},
        lifespan=lifespan,
    )
    app.state.wall = wall
    app.state.events = hub
    app.state.auth = AuthService(session_factory, wall)
    app.state.audit_queries = AuditQueries(session_factory)
    app.state.cookie_secure = settings.deployment_mode != "local"
    topology = TopologyService(session_factory)
    observation_queries = ObservationQueryService(session_factory, topology, SIMULATED_PLATFORM.key)
    app.state.simulation = simulation
    app.state.observations = observation_queries
    app.state.metric_catalog = MetricCatalogService(session_factory)
    app.state.health = HealthQueries(session_factory, topology)
    app.state.state_history = StateHistoryQueries(session_factory, topology, simulation)

    def platform_now() -> datetime:
        return simulation.clock().platform_time

    app.state.incident_queries = IncidentQueries(session_factory)
    app.state.incident_commands = IncidentCommands(session_factory, wall, platform_now)
    app.state.reporting = ReportingService(session_factory, wall, topology, PdfRenderer())
    app.state.diagnostics = DiagnosticsService(
        session_factory,
        wall,
        platform_now,
        topology,
        DiagnosticRuntime(settings, build_provider(settings)),
    )
    app.state.readiness = ReadinessService(
        session_factory,
        wall,
        expected_revision=expected_head(),
        cycle_interval_s=settings.cycle_interval_s,
        llm_provider=app.state.diagnostics.provider_status,
    )
    app.state.system_status = SystemStatusService(
        session_factory,
        wall,
        settings.cycle_interval_s,
        app.state.diagnostics.provider_status,
        MonitoredParts(
            simulation, observation_queries, enabled_connector_keys(settings.connector_source)
        ),
    )
    app.state.cycle_interval_s = settings.cycle_interval_s
    app.state.audit = AuditService(session_factory, wall)
    app.state.sim_seed = settings.sim_seed
    register_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(audit.router)
    app.include_router(system.router)
    app.include_router(simulations.router, dependencies=[Depends(auth.require_read)])
    app.include_router(observations.router, dependencies=[Depends(auth.require_read)])
    app.include_router(health.router, dependencies=[Depends(auth.require_read)])
    app.include_router(incidents.router, dependencies=[Depends(auth.require_read)])
    app.include_router(reports.router, dependencies=[Depends(auth.require_read)])
    app.include_router(events.router, dependencies=[Depends(auth.require_read)])
    # Starlette runs the last added middleware first. Security headers wrap every response,
    # including the 413 and crash responses produced by the two inner middlewares.
    # A hostile page must not reach the local API through a rebound DNS name (ADR 0007).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    if settings.frontend_dir is not None:
        app.mount("/", FrontendFiles(settings.frontend_dir), name="frontend")
    return app


def build() -> FastAPI:
    """Uvicorn factory entry point (`uvicorn app.main:build --factory`)."""
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    return create_app(settings)
