from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from app.monitor.service import HeartbeatService
from app.worker import CycleSteps, Worker, build_cycle_steps

RETENTION = timedelta(days=7)
CYCLE_INTERVAL_S = 5.0


@dataclass
class FixedClock:
    current: datetime

    def now(self) -> datetime:
        return self.current


@dataclass
class WallPlatformTime:
    """Platform time that follows a wall clock, for worker tests without a seeded simulation."""

    wall: FixedClock

    def begin_cycle(self, _session: Session) -> datetime:
        return self.wall.now()


class NoCollection:
    def collect(self, _session: Session, _platform_now: datetime) -> Sequence[object]:
        return []


class NoRetention:
    def purge_if_due(self, _factory: sessionmaker[Session], _platform_now: datetime) -> int:
        return 0


def idle_steps(wall: FixedClock) -> CycleSteps:
    """Cycle steps that touch nothing but the clock: the worker writes only its heartbeat."""
    return CycleSteps(WallPlatformTime(wall), NoCollection(), NoRetention())


def cycling_worker(session_factory: sessionmaker[Session], wall: FixedClock) -> Worker:
    """The production cycle (simulation, collection, retention) driven by a test clock."""
    steps = build_cycle_steps(session_factory, wall, RETENTION)
    return Worker(session_factory, HeartbeatService(session_factory), wall, CYCLE_INTERVAL_S, steps)
