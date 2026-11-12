"""Connector port (architecture §04.4).

A connector turns one source into normalized observations. It reports failures in the result
instead of raising, and never knows about rules, incidents or storage.
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.observation import LogSeverity, ObservationSource, Quality


@dataclass(frozen=True, slots=True)
class ObservedSample:
    component_key: str
    metric_name: str
    value: float
    unit: str
    quality: Quality
    observed_at: datetime
    scenario_run_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ObservedLog:
    component_key: str
    severity: LogSeverity
    message: str
    attributes: Mapping[str, str | int | float | bool]
    observed_at: datetime
    scenario_run_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ConnectorIssue:
    """A problem the connector met while collecting; its data may still be partially usable."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class CollectionRequest:
    """`now` is platform time. `resume_after` is the event-time watermark of the connector's
    last persisted collection, or None on its first one. Observations before `not_before`
    would be rejected as too late, so a connector need not produce them."""

    now: datetime
    resume_after: datetime | None
    not_before: datetime


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """`watermark`: event time up to which the source has been fully read, if it has one."""

    samples: tuple[ObservedSample, ...] = ()
    logs: tuple[ObservedLog, ...] = ()
    issues: tuple[ConnectorIssue, ...] = ()
    watermark: datetime | None = None


class Connector(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def source(self) -> ObservationSource: ...

    def collect(self, request: CollectionRequest) -> CollectionResult: ...
