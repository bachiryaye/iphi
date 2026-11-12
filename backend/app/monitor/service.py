from dataclasses import dataclass, replace
from datetime import datetime

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.settings import LlmProvider
from app.ingestion.domain.collection import CollectionRun
from app.ingestion.service import ObservationQueryService
from app.monitor.domain import (
    CheckName,
    CheckStatus,
    CollectionAssessment,
    CollectionState,
    Heartbeat,
    ProcessStatus,
    ReadinessCheck,
    ReadinessReport,
    assess_collection,
    assess_migrations,
    assess_worker,
    worst_collection_state,
)
from app.monitor.repository import HeartbeatRepository, SchemaRepository
from app.simulation.service import ClockView, SimulationService

WORKER_PROCESS = "worker"

log = structlog.get_logger(__name__)


class ReadinessService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        clock: Clock,
        expected_revision: str,
        cycle_interval_s: float,
        llm_provider: LlmProvider,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._expected_revision = expected_revision
        self._cycle_interval_s = cycle_interval_s
        self._llm_provider = llm_provider

    def check(self) -> ReadinessReport:
        now = self._clock.now()
        checks = (*self._storage_checks(now), ai_provider_check(self._llm_provider))
        return ReadinessReport(now, self._cycle_interval_s, checks)

    def _storage_checks(self, now: datetime) -> tuple[ReadinessCheck, ...]:
        try:
            with self._session_factory() as session:
                schema = SchemaRepository(session)
                schema.ping()
                migrations = assess_migrations(schema.current_revision(), self._expected_revision)
                if migrations.status is not CheckStatus.OK:
                    # The heartbeat table may not exist yet; querying it would fail as if the
                    # database were down and hide the real cause.
                    worker = ReadinessCheck(
                        CheckName.WORKER, CheckStatus.FAILED, "Not checked: schema out of date."
                    )
                else:
                    heartbeat = HeartbeatRepository(session).get(WORKER_PROCESS)
                    worker = assess_worker(heartbeat, now, self._cycle_interval_s)
        except SQLAlchemyError as exc:
            log.warning("readiness.database_unreachable", error=type(exc).__name__)
            unreachable = "Not checked: database unreachable."
            return (
                ReadinessCheck(CheckName.DATABASE, CheckStatus.FAILED, "Database unreachable."),
                ReadinessCheck(CheckName.MIGRATIONS, CheckStatus.FAILED, unreachable),
                ReadinessCheck(CheckName.WORKER, CheckStatus.FAILED, unreachable),
            )
        database = ReadinessCheck(CheckName.DATABASE, CheckStatus.OK, "PostgreSQL reachable.")
        return (database, migrations, worker)


def ai_provider_check(provider: LlmProvider) -> ReadinessCheck:
    # US-08 adds real providers; "none" is a supported state, never a readiness failure.
    return ReadinessCheck(
        CheckName.AI_PROVIDER,
        CheckStatus.DISABLED,
        f"LLM provider '{provider}'; deterministic diagnosis only.",
    )


class HeartbeatService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def record(session: Session, heartbeat: Heartbeat) -> None:
        """Written in the cycle's unit of work, so a rolled-back cycle leaves no heartbeat."""
        HeartbeatRepository(session).save(heartbeat)

    def record_stopped(self) -> None:
        with self._session_factory.begin() as session:
            repository = HeartbeatRepository(session)
            last = repository.get(WORKER_PROCESS)
            if last is not None:
                repository.save(replace(last, status=ProcessStatus.STOPPED))


RECENT_COLLECTION_RUNS = 20


@dataclass(frozen=True, slots=True)
class ConnectorStatus:
    connector_key: str
    assessment: CollectionAssessment
    last_run: CollectionRun | None
    last_success_at: datetime | None


@dataclass(frozen=True, slots=True)
class SystemStatus:
    checked_at: datetime
    cycle_interval_s: float
    clock: ClockView
    worker: ReadinessCheck
    heartbeat: Heartbeat | None
    collection: CollectionState
    connectors: tuple[ConnectorStatus, ...]
    recent_runs: tuple[CollectionRun, ...]
    ai_provider: ReadinessCheck


@dataclass(frozen=True, slots=True)
class MonitoredParts:
    simulation: SimulationService
    observations: ObservationQueryService
    connector_keys: tuple[str, ...]


class SystemStatusService:
    """The monitor's own observability (architecture §04.1, system/status)."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        wall: Clock,
        cycle_interval_s: float,
        llm_provider: LlmProvider,
        parts: MonitoredParts,
    ) -> None:
        self._session_factory = session_factory
        self._wall = wall
        self._cycle_interval_s = cycle_interval_s
        self._llm_provider = llm_provider
        self._parts = parts

    def status(self) -> SystemStatus:
        now = self._wall.now()
        with self._session_factory() as session:
            heartbeat = HeartbeatRepository(session).get(WORKER_PROCESS)
        connectors = tuple(self._connector(key, now) for key in self._parts.connector_keys)
        return SystemStatus(
            checked_at=now,
            cycle_interval_s=self._cycle_interval_s,
            clock=self._parts.simulation.clock(),
            worker=assess_worker(heartbeat, now, self._cycle_interval_s),
            heartbeat=heartbeat,
            collection=worst_collection_state([c.assessment.state for c in connectors]),
            connectors=connectors,
            recent_runs=tuple(self._parts.observations.recent_runs(RECENT_COLLECTION_RUNS)),
            ai_provider=ai_provider_check(self._llm_provider),
        )

    def _connector(self, key: str, now: datetime) -> ConnectorStatus:
        last, last_success = self._parts.observations.latest_runs(key)
        return ConnectorStatus(
            key,
            assess_collection(last, now, self._cycle_interval_s),
            last,
            None if last_success is None else last_success.started_at,
        )
