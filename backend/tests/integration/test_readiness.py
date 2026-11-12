import threading
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.db import create_db_engine, create_session_factory
from app.core.migrations import expected_head
from app.core.settings import LlmProvider, Settings
from app.monitor.domain import CheckName, CheckStatus, ReadinessReport
from app.monitor.service import HeartbeatService, ReadinessService
from app.worker import (
    Worker,
    holds_worker_lock,
    release_worker_lock,
    try_acquire_worker_lock,
)
from tests.fakes import FixedClock, NoScenarios

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 12, 10, 42, 7, tzinfo=UTC)
INTERVAL_S = 5.0


def readiness(factory: sessionmaker[Session], clock: FixedClock) -> ReadinessService:
    return ReadinessService(factory, clock, expected_head(), INTERVAL_S, LlmProvider.NONE)


def statuses(report: ReadinessReport) -> dict[CheckName, CheckStatus]:
    return {check.name: check.status for check in report.checks}


def test_fresh_database_is_not_ready_until_the_worker_has_cycled(
    session_factory: sessionmaker[Session],
) -> None:
    report = readiness(session_factory, FixedClock(NOW)).check()

    assert not report.ready
    assert statuses(report) == {
        CheckName.DATABASE: CheckStatus.OK,
        CheckName.MIGRATIONS: CheckStatus.OK,
        CheckName.WORKER: CheckStatus.FAILED,
        CheckName.AI_PROVIDER: CheckStatus.DISABLED,
    }


def test_worker_cycle_makes_platform_ready(session_factory: sessionmaker[Session]) -> None:
    clock = FixedClock(NOW)
    Worker(HeartbeatService(session_factory), clock, INTERVAL_S, NoScenarios()).run_cycle(lag_ms=0)

    report = readiness(session_factory, clock).check()

    assert report.ready
    worker_check = next(c for c in report.checks if c.name is CheckName.WORKER)
    assert worker_check.observed_at == NOW


def test_heartbeat_older_than_three_cycles_is_reported_stalled(
    session_factory: sessionmaker[Session],
) -> None:
    Worker(HeartbeatService(session_factory), FixedClock(NOW), INTERVAL_S, NoScenarios()).run_cycle(
        lag_ms=0
    )

    later = FixedClock(NOW + timedelta(seconds=16))
    report = readiness(session_factory, later).check()

    assert statuses(report)[CheckName.WORKER] is CheckStatus.FAILED


def test_stopped_worker_is_not_ready(session_factory: sessionmaker[Session]) -> None:
    clock = FixedClock(NOW)
    heartbeats = HeartbeatService(session_factory)
    Worker(heartbeats, clock, INTERVAL_S, NoScenarios()).run_cycle(lag_ms=0)
    stop = threading.Event()
    stop.set()

    Worker(heartbeats, clock, INTERVAL_S, NoScenarios()).run(stop, lambda: True)

    assert statuses(readiness(session_factory, clock).check())[CheckName.WORKER] is (
        CheckStatus.FAILED
    )


def test_unmigrated_database_fails_migration_check(empty_database_url: str) -> None:
    engine = create_db_engine(Settings(database_url=SecretStr(empty_database_url)))
    try:
        report = readiness(create_session_factory(engine), FixedClock(NOW)).check()
    finally:
        engine.dispose()

    assert statuses(report) == {
        CheckName.DATABASE: CheckStatus.OK,
        CheckName.MIGRATIONS: CheckStatus.FAILED,
        CheckName.WORKER: CheckStatus.FAILED,
        CheckName.AI_PROVIDER: CheckStatus.DISABLED,
    }


def test_unreachable_database_fails_every_storage_check() -> None:
    settings = Settings(database_url=SecretStr("postgresql+psycopg://x:y@127.0.0.1:1/none"))
    engine = create_db_engine(settings)
    try:
        report = readiness(create_session_factory(engine), FixedClock(NOW)).check()
    finally:
        engine.dispose()

    assert statuses(report) == {
        CheckName.DATABASE: CheckStatus.FAILED,
        CheckName.MIGRATIONS: CheckStatus.FAILED,
        CheckName.WORKER: CheckStatus.FAILED,
        CheckName.AI_PROVIDER: CheckStatus.DISABLED,
    }


def test_only_one_worker_holds_the_scheduler_lock(engine: Engine) -> None:
    with engine.connect() as first, engine.connect() as second:
        assert try_acquire_worker_lock(first)
        assert not try_acquire_worker_lock(second)
        release_worker_lock(first)
        assert try_acquire_worker_lock(second)


def test_lock_holder_is_detected_per_connection(engine: Engine) -> None:
    with engine.connect() as first, engine.connect() as second:
        assert not holds_worker_lock(first)
        try_acquire_worker_lock(first)

        assert holds_worker_lock(first)
        assert not holds_worker_lock(second)

        release_worker_lock(first)
        assert not holds_worker_lock(first)


def test_worker_stops_cycling_when_the_lock_is_lost(
    session_factory: sessionmaker[Session],
) -> None:
    clock = FixedClock(NOW)

    completed = Worker(HeartbeatService(session_factory), clock, INTERVAL_S, NoScenarios()).run(
        threading.Event(), lambda: False
    )

    assert not completed
    assert statuses(readiness(session_factory, clock).check())[CheckName.WORKER] is (
        CheckStatus.FAILED
    )
