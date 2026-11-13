"""Worker process: the single scheduler of run cycles (ADR 0001)."""

import signal
import sys
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import FrameType
from typing import Protocol

import structlog
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.connectors.registry import build_connectors
from app.core.clock import Clock, WallClock
from app.core.db import create_db_engine, create_session_factory
from app.core.logging import configure_logging
from app.core.retention import RetentionJob
from app.core.settings import Settings
from app.health.service import HealthEvaluation, purge_evaluations
from app.ingestion.domain.validation import IngestionPolicy
from app.ingestion.service import CollectionService, purge_observations
from app.monitor.domain import Heartbeat, ProcessStatus
from app.monitor.service import WORKER_PROCESS, HeartbeatService
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.service import build_simulation
from app.topology.service import TopologyService

# Arbitrary but fixed: every IPHI worker must contend for the same PostgreSQL advisory lock.
WORKER_LOCK_ID = 0x1F4E_0001
EXIT_LOCK_LOST = 3

log = structlog.get_logger(__name__)


def try_acquire_worker_lock(connection: Connection) -> bool:
    acquired = connection.execute(
        text("SELECT pg_try_advisory_lock(:id)"), {"id": WORKER_LOCK_ID}
    ).scalar_one()
    connection.commit()
    return bool(acquired)


def holds_worker_lock(connection: Connection) -> bool:
    """False when the lock connection died: PostgreSQL then released the lock to other workers."""
    try:
        held = connection.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks WHERE locktype = 'advisory' "
                "AND classid = 0 AND objid = CAST(:id AS oid) AND objsubid = 1 "
                "AND pid = pg_backend_pid() AND granted)"
            ),
            {"id": WORKER_LOCK_ID},
        ).scalar_one()
        connection.commit()
    except DBAPIError:
        return False
    return bool(held)


def release_worker_lock(connection: Connection) -> None:
    # Pooled connections outlive `with engine.connect()`, so the lock is released explicitly.
    try:
        connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": WORKER_LOCK_ID})
        connection.commit()
    except DBAPIError:
        log.warning("worker.lock_release_failed")


def next_deadline(previous: float, interval: float, now: float) -> float:
    """Next cycle start on a fixed cadence; missed slots are skipped, never replayed in a burst."""
    deadline = previous + interval
    return deadline if deadline > now else now


class CycleClock(Protocol):
    def begin_cycle(self, session: Session) -> datetime: ...


class CollectionStep(Protocol):
    def collect(self, session: Session, platform_now: datetime) -> Sequence[object]: ...


class HealthStep(Protocol):
    def evaluate(self, session: Session, platform_now: datetime) -> object: ...


class RetentionStep(Protocol):
    def purge_if_due(
        self, session_factory: sessionmaker[Session], platform_now: datetime
    ) -> int: ...


@dataclass(frozen=True, slots=True)
class CycleSteps:
    """Steps of `run_cycle` in order (§02.2); US-05 adds incidents after health."""

    clock: CycleClock
    collection: CollectionStep
    health: HealthStep
    retention: RetentionStep


class Worker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        heartbeats: HeartbeatService,
        wall: Clock,
        cycle_interval_s: float,
        steps: CycleSteps,
    ) -> None:
        self._session_factory = session_factory
        self._heartbeats = heartbeats
        self._wall = wall
        self._interval = cycle_interval_s
        self._steps = steps

    def run_cycle(self, lag_ms: int) -> None:
        """One unit of work and a single commit: on this host a commit costs an fsync (ADR 0014).

        Connectors and health evaluation are isolated in savepoints; any other failure rolls
        the whole cycle back, heartbeat included, so /ready reports it. Retention follows in its
        own transaction, at most once per platform hour.
        """
        with _cycle_logs():
            self._run_cycle(lag_ms)

    def _run_cycle(self, lag_ms: int) -> None:
        at = self._wall.now()
        started = time.perf_counter()
        with self._session_factory.begin() as session:
            platform_now = self._steps.clock.begin_cycle(session)
            self._steps.collection.collect(session, platform_now)
            self._steps.health.evaluate(session, platform_now)
            duration_ms = round((time.perf_counter() - started) * 1000)
            self._heartbeats.record(
                session, Heartbeat(WORKER_PROCESS, at, duration_ms, lag_ms, ProcessStatus.RUNNING)
            )
        purged = self._steps.retention.purge_if_due(self._session_factory, platform_now)
        # The heartbeat cannot include its own commit; this event does.
        log.debug(
            "worker.cycle",
            duration_ms=round((time.perf_counter() - started) * 1000),
            lag_ms=lag_ms,
            platform_time=platform_now,
            purged=purged,
        )

    def run(self, stop: threading.Event, lock_held: Callable[[], bool]) -> bool:
        """Cycles until stopped. Returns False if the scheduler lock was lost meanwhile."""
        due = time.monotonic()
        while not stop.is_set():
            if not lock_held():
                log.error("worker.lock_lost", lock_id=WORKER_LOCK_ID)
                return False
            lag_ms = max(0, round((time.monotonic() - due) * 1000))
            with _cycle_logs():
                try:
                    self._run_cycle(lag_ms)
                except Exception:
                    # Process boundary (C-14): a failed cycle is logged; the stale heartbeat
                    # makes /ready fail, so the failure is visible instead of silent.
                    log.exception("worker.cycle_failed")
            due = next_deadline(due, self._interval, time.monotonic())
            stop.wait(max(0.0, due - time.monotonic()))
        self._heartbeats.record_stopped()
        return True


def _cycle_logs() -> AbstractContextManager[None]:
    """Every log event of one cycle (collection, evaluations, transitions) shares an ID."""
    return structlog.contextvars.bound_contextvars(correlation_id=f"cycle-{uuid.uuid7()}")


def build_cycle_steps(
    session_factory: sessionmaker[Session], wall: Clock, retention: timedelta
) -> CycleSteps:
    simulation = build_simulation(session_factory, wall)
    policy = IngestionPolicy()
    topology = TopologyService(session_factory)
    collection = CollectionService(
        build_connectors(simulation), topology, SIMULATED_PLATFORM.key, policy, wall
    )
    # Slots older than the lateness bound cannot receive observations any more (ADR 0015).
    health = HealthEvaluation(topology, SIMULATED_PLATFORM.key, policy.late_tolerance)
    purges = (purge_observations, purge_evaluations)
    return CycleSteps(simulation, collection, health, RetentionJob(retention, purges))


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level, settings.log_format)
    stop = threading.Event()

    def request_stop(signum: int, _frame: FrameType | None) -> None:
        log.info("worker.stopping", signal=signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    wall = WallClock()
    worker = Worker(
        session_factory,
        HeartbeatService(session_factory),
        wall,
        settings.cycle_interval_s,
        build_cycle_steps(session_factory, wall, timedelta(days=settings.retention_days)),
    )
    # The advisory lock lives as long as this connection: a second worker waits (ADR 0001).
    with engine.connect() as lock_connection:
        while not try_acquire_worker_lock(lock_connection):
            log.info("worker.lock_wait", lock_id=WORKER_LOCK_ID)
            if stop.wait(settings.cycle_interval_s):
                return 0
        log.info("worker.started", cycle_interval_s=settings.cycle_interval_s)
        try:
            completed = worker.run(stop, lambda: holds_worker_lock(lock_connection))
        finally:
            release_worker_lock(lock_connection)
    log.info("worker.stopped")
    # A lost lock exits non-zero so the supervisor restarts the worker, which contends again.
    return 0 if completed else EXIT_LOCK_LOST


if __name__ == "__main__":
    sys.exit(main())
