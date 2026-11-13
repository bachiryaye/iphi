"""`migrate` service entry point: schema to head, then the idempotent seed (architecture §02.1)."""

import sys

import structlog
from alembic import command
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock, WallClock
from app.core.db import create_db_engine, create_session_factory
from app.core.logging import configure_logging
from app.core.migrations import alembic_config
from app.core.settings import Settings
from app.health.config import DEFAULT_RULES_PATH, load_rules
from app.health.service import HealthRuleCatalog
from app.ingestion.domain.catalog import METRIC_CATALOG
from app.ingestion.service import MetricCatalogService
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.service import SimulationService, build_simulation
from app.topology.service import TopologyService

log = structlog.get_logger(__name__)


def seed(session_factory: sessionmaker[Session], wall: Clock, sim_seed: int) -> SimulationService:
    """Idempotent seed: topology, metric catalog, health rules, platform clock, baseline run."""
    TopologyService(session_factory).ensure(SIMULATED_PLATFORM.topology())
    MetricCatalogService(session_factory).ensure()
    keys = [c.key for c in SIMULATED_PLATFORM.components]
    HealthRuleCatalog(session_factory).ensure(load_rules(DEFAULT_RULES_PATH, METRIC_CATALOG, keys))
    simulation = build_simulation(session_factory, wall)
    simulation.initialize(sim_seed)
    return simulation


def bootstrap(settings: Settings) -> None:
    command.upgrade(alembic_config(settings.database_url.get_secret_value()), "head")
    engine = create_db_engine(settings)
    try:
        seed(create_session_factory(engine), WallClock(), settings.sim_seed)
    finally:
        engine.dispose()


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    bootstrap(settings)
    log.info("bootstrap.completed", platform=SIMULATED_PLATFORM.key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
