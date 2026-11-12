import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from app.core.observation import LogSeverity, ObservationSource
from app.ingestion.domain.series import TimeWindow


@dataclass(frozen=True, slots=True)
class LogPosition:
    """Keyset position: the last log of the previous page."""

    observed_at: datetime
    id: int


@dataclass(frozen=True, slots=True)
class LogQuery:
    window: TimeWindow
    component_id: uuid.UUID | None
    min_severity: LogSeverity | None
    before: LogPosition | None
    limit: int


@dataclass(frozen=True, slots=True)
class StoredLog:
    id: int
    component_id: uuid.UUID
    severity: LogSeverity
    message: str
    fingerprint: str
    attributes: Mapping[str, object]
    observed_at: datetime
    received_at: datetime
    source: ObservationSource
    scenario_run_id: uuid.UUID | None

    @property
    def position(self) -> LogPosition:
        return LogPosition(self.observed_at, self.id)
