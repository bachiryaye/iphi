"""Scheduled purge of history older than the retention period (ADR 0008)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import ColumnElement, false
from sqlalchemy.orm import Session, sessionmaker

RETENTION_BATCH = 50_000
RETENTION_INTERVAL = timedelta(hours=1)

type Purge = Callable[[Session, datetime, int], int]
"""Deletes at most `batch` rows per table observed before `cutoff`; returns the count."""

type RowHold = Callable[[ColumnElement[int]], ColumnElement[bool]]
"""SQL predicate on a row ID column, true for the rows a purge must keep."""


def no_hold(_row_id: ColumnElement[int]) -> ColumnElement[bool]:
    return false()


@dataclass(frozen=True, slots=True)
class EvidenceHolds:
    """Rows cited as incident evidence, which neither retention nor reset may delete (ADR 0008).

    The incidents module provides them; ingestion and health apply them without depending on it.
    """

    samples: RowHold = no_hold
    logs: RowHold = no_hold
    evaluations: RowHold = no_hold


log = structlog.get_logger(__name__)


class RetentionJob:
    """Runs every purge at most once per platform hour, except while a full batch shows that a
    backlog remains."""

    def __init__(self, retention: timedelta, purges: Sequence[Purge]) -> None:
        self._retention = retention
        self._purges = tuple(purges)
        self._last_run: datetime | None = None
        self._backlog = False

    def purge_if_due(self, session_factory: sessionmaker[Session], platform_now: datetime) -> int:
        """Own short transaction, after the cycle has committed: large deletes neither lengthen
        the cycle's lock on sim_clock nor roll back with it. The schedule advances only once
        the purge is committed."""
        due = (
            self._backlog
            or self._last_run is None
            or platform_now - self._last_run >= RETENTION_INTERVAL
        )
        if not due:
            return 0
        cutoff = platform_now - self._retention
        with session_factory.begin() as session:
            deleted = [purge(session, cutoff, RETENTION_BATCH) for purge in self._purges]
        self._last_run = platform_now
        self._backlog = any(count >= RETENTION_BATCH for count in deleted)
        if any(deleted):
            log.info("retention.purged", deleted=sum(deleted), backlog=self._backlog)
        return sum(deleted)
