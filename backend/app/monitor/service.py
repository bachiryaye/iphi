from dataclasses import replace
from datetime import datetime

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.settings import LlmProvider
from app.monitor.domain import (
    CheckName,
    CheckStatus,
    Heartbeat,
    ProcessStatus,
    ReadinessCheck,
    ReadinessReport,
    assess_migrations,
    assess_worker,
)
from app.monitor.repository import HeartbeatRepository, SchemaRepository

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
        checks = (*self._storage_checks(now), self._ai_provider_check())
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

    def _ai_provider_check(self) -> ReadinessCheck:
        # US-08 adds real providers; "none" is a supported state, never a readiness failure.
        return ReadinessCheck(
            CheckName.AI_PROVIDER,
            CheckStatus.DISABLED,
            f"LLM provider '{self._llm_provider}'; deterministic diagnosis only.",
        )


class HeartbeatService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record(self, heartbeat: Heartbeat) -> None:
        with self._session_factory.begin() as session:
            HeartbeatRepository(session).save(heartbeat)

    def record_stopped(self) -> None:
        with self._session_factory.begin() as session:
            repository = HeartbeatRepository(session)
            last = repository.get(WORKER_PROCESS)
            if last is not None:
                repository.save(replace(last, status=ProcessStatus.STOPPED))
