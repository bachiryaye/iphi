"""Bounded time-series reads (ADR 0008): window limits, server-side downsampling, explicit gaps."""

import math
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from http import HTTPStatus

from app.core.exceptions import IphiError
from app.core.observation import ObservationSource, Quality

MAX_WINDOW = timedelta(days=7)
MAX_POINTS = 2000
# One missing point is tolerated (jitter, a single lost probe); two in a row make a gap.
TOLERATED_MISSING_POINTS = 1


class InvalidTimeWindowError(IphiError):
    status = HTTPStatus.UNPROCESSABLE_CONTENT
    code = "INVALID_TIME_WINDOW"


class SeriesMode(StrEnum):
    RAW = "raw"
    AGGREGATED = "aggregated"


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise InvalidTimeWindowError("Time bounds must carry a UTC offset.")
        if self.start >= self.end:
            raise InvalidTimeWindowError("'from' must be before 'to'.")
        if self.end - self.start > MAX_WINDOW:
            raise InvalidTimeWindowError(f"A window spans at most {MAX_WINDOW.days} days.")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


@dataclass(frozen=True, slots=True)
class SeriesQuery:
    component_id: uuid.UUID
    metric_name: str
    window: TimeWindow
    max_points: int

    def __post_init__(self) -> None:
        if not 1 <= self.max_points <= MAX_POINTS:
            raise InvalidTimeWindowError(f"max_points must be between 1 and {MAX_POINTS}.")

    def bucket_seconds(self) -> int:
        """Smallest whole-second bucket that keeps the window within max_points buckets."""
        return max(1, math.ceil(self.window.duration.total_seconds() / self.max_points))


@dataclass(frozen=True, slots=True)
class RawPoint:
    sample_id: int
    observed_at: datetime
    value: float
    quality: Quality
    source: ObservationSource
    scenario_run_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class BucketPoint:
    """Aggregate of the samples of one source within [bucket_start, bucket_start + bucket_s)."""

    bucket_start: datetime
    minimum: float
    average: float
    maximum: float
    count: int
    worst_quality: Quality
    source: ObservationSource


@dataclass(frozen=True, slots=True)
class Gap:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class Series:
    query: SeriesQuery
    component_key: str
    unit: str
    bucket_s: int | None
    raw: tuple[RawPoint, ...]
    buckets: tuple[BucketPoint, ...]
    gaps: tuple[Gap, ...]

    @property
    def mode(self) -> SeriesMode:
        return SeriesMode.RAW if self.bucket_s is None else SeriesMode.AGGREGATED


def find_gaps(
    times: Sequence[datetime], window: TimeWindow, resolution_s: float, now: datetime
) -> tuple[Gap, ...]:
    """Stretches of more than TOLERATED_MISSING_POINTS missing points in [start, min(end, now)].

    `times` are point start times in ascending order; each point covers `resolution_s`. The part
    of the window after `now` cannot hold data yet, so it is never reported as a gap.
    """
    horizon = min(window.end, now)
    if horizon <= window.start:
        return ()
    resolution = timedelta(seconds=resolution_s)
    tolerance = resolution * TOLERATED_MISSING_POINTS
    gaps: list[Gap] = []
    covered_until = window.start
    for at in times:
        if at - covered_until > tolerance:
            gaps.append(Gap(covered_until, at))
        covered_until = max(covered_until, at + resolution)
    if horizon - covered_until > tolerance:
        gaps.append(Gap(covered_until, horizon))
    return tuple(gaps)
