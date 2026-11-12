"""Worker process: the single scheduler of run cycles (ADR 0001)."""

import signal
import sys
import threading
import time
from collections.abc import Callable
from types import FrameType

import structlog
from sqlalchemy import Connection, text
from sqlalchemy.exc import DBAPIError

from app.core.clock import Clock, WallClock
from app.core.db import create_db_engine, create_session_factory
from app.core.logging import configure_logging
from app.core.settings import Settings
from app.monitor.domain import Heartbeat, ProcessStatus
from app.monitor.service import WORKER_PROCESS, HeartbeatService

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


class Worker:
    def __init__(self, heartbeats: HeartbeatService, clock: Clock, cycle_interval_s: float) -> None:
        self._heartbeats = heartbeats
        self._clock = clock
        self._interval = cycle_interval_s

    def run_cycle(self, lag_ms: int) -> None:
        at = self._clock.now()
        started = time.perf_counter()
        # TODO(US-02): collect → ingest → evaluate → incidents (architecture §02.2).
        duration_ms = round((time.perf_counter() - started) * 1000)
        self._heartbeats.record(
            Heartbeat(WORKER_PROCESS, at, duration_ms, lag_ms, ProcessStatus.RUNNING)
        )
        log.debug("worker.cycle", duration_ms=duration_ms, lag_ms=lag_ms)

    def run(self, stop: threading.Event, lock_held: Callable[[], bool]) -> bool:
        """Cycles until stopped. Returns False if the scheduler lock was lost meanwhile."""
        due = time.monotonic()
        while not stop.is_set():
            if not lock_held():
                log.error("worker.lock_lost", lock_id=WORKER_LOCK_ID)
                return False
            lag_ms = max(0, round((time.monotonic() - due) * 1000))
            try:
                self.run_cycle(lag_ms)
            except Exception:
                # Process boundary (C-14): a failed cycle is logged; the stale heartbeat makes
                # /ready fail, so the failure is visible instead of silent.
                log.exception("worker.cycle_failed")
            due = next_deadline(due, self._interval, time.monotonic())
            stop.wait(max(0.0, due - time.monotonic()))
        self._heartbeats.record_stopped()
        return True


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
    worker = Worker(
        HeartbeatService(create_session_factory(engine)), WallClock(), settings.cycle_interval_s
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
