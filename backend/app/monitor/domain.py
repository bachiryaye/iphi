from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.ingestion.domain.collection import CollectionRun, CollectionStatus

# Same tolerance as R-TEL-001: three missed cycles before the worker is considered stalled.
STALE_AFTER_CYCLES = 3


class ProcessStatus(StrEnum):
    RUNNING = "running"
    STOPPED = "stopped"


class CheckStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    DISABLED = "disabled"


class CheckName(StrEnum):
    DATABASE = "database"
    MIGRATIONS = "migrations"
    WORKER = "worker"
    AI_PROVIDER = "ai_provider"


@dataclass(frozen=True, slots=True)
class Heartbeat:
    process: str
    last_cycle_at: datetime
    last_cycle_duration_ms: int
    cycle_lag_ms: int
    status: ProcessStatus

    def __post_init__(self) -> None:
        if self.last_cycle_at.tzinfo is None:
            raise ValueError("last_cycle_at must be timezone-aware")
        if self.last_cycle_duration_ms < 0 or self.cycle_lag_ms < 0:
            raise ValueError("cycle duration and lag are non-negative")


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    name: CheckName
    status: CheckStatus
    detail: str
    observed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    checked_at: datetime
    cycle_interval_s: float
    checks: tuple[ReadinessCheck, ...]

    @property
    def ready(self) -> bool:
        return all(check.status is not CheckStatus.FAILED for check in self.checks)


def assess_worker(
    heartbeat: Heartbeat | None, now: datetime, cycle_interval_s: float
) -> ReadinessCheck:
    """A missing, stopped or late heartbeat fails readiness: the monitor never looks green blind."""
    if heartbeat is None:
        return ReadinessCheck(CheckName.WORKER, CheckStatus.FAILED, "No worker cycle recorded yet.")
    at = heartbeat.last_cycle_at
    if heartbeat.status is ProcessStatus.STOPPED:
        return ReadinessCheck(CheckName.WORKER, CheckStatus.FAILED, "Worker stopped.", at)
    age = now - at
    if age > timedelta(seconds=STALE_AFTER_CYCLES * cycle_interval_s):
        return ReadinessCheck(
            CheckName.WORKER,
            CheckStatus.FAILED,
            f"Worker stalled: last cycle {age.total_seconds():.0f} s ago, "
            f"expected every {cycle_interval_s:g} s.",
            at,
        )
    return ReadinessCheck(
        CheckName.WORKER,
        CheckStatus.OK,
        f"Last cycle took {heartbeat.last_cycle_duration_ms} ms.",
        at,
    )


def assess_migrations(current: str | None, expected: str) -> ReadinessCheck:
    if current == expected:
        return ReadinessCheck(CheckName.MIGRATIONS, CheckStatus.OK, f"At revision {expected}.")
    found = current or "none"
    return ReadinessCheck(
        CheckName.MIGRATIONS,
        CheckStatus.FAILED,
        f"Database at revision {found}, code expects {expected}.",
    )


class CollectionState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"
    STALLED = "stalled"
    NOT_STARTED = "not_started"


# Worst first: the overall collection state is the worst state of any enabled connector.
_COLLECTION_SEVERITY = (
    CollectionState.FAILED,
    CollectionState.STALLED,
    CollectionState.NOT_STARTED,
    CollectionState.DEGRADED,
    CollectionState.OK,
)


@dataclass(frozen=True, slots=True)
class CollectionAssessment:
    state: CollectionState
    detail: str


def assess_collection(
    last: CollectionRun | None, now: datetime, cycle_interval_s: float
) -> CollectionAssessment:
    """Silence is reported as such: a connector that stopped running never looks healthy."""
    if last is None:
        return CollectionAssessment(CollectionState.NOT_STARTED, "No collection recorded yet.")
    age = now - last.started_at
    if age > timedelta(seconds=STALE_AFTER_CYCLES * cycle_interval_s):
        return CollectionAssessment(
            CollectionState.STALLED,
            f"Last collection {age.total_seconds():.0f} s ago, "
            f"expected every {cycle_interval_s:g} s.",
        )
    if last.status is CollectionStatus.FAILED:
        return CollectionAssessment(
            CollectionState.FAILED, f"Last collection failed ({last.error_code})."
        )
    if last.status is CollectionStatus.PARTIAL:
        return CollectionAssessment(
            CollectionState.DEGRADED,
            f"Last collection partial: {last.rejected_count} observation(s) rejected"
            + (f", {last.error_code}." if last.error_code else "."),
        )
    return CollectionAssessment(CollectionState.OK, "Last collection complete.")


def worst_collection_state(states: list[CollectionState]) -> CollectionState:
    if not states:
        return CollectionState.NOT_STARTED
    return min(states, key=_COLLECTION_SEVERITY.index)
