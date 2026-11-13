"""Stored observations as other modules read them (health rule windows)."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.core.observation import Quality


@dataclass(frozen=True, slots=True)
class StoredSample:
    id: int
    component_id: uuid.UUID
    metric_name: str
    value: float
    quality: Quality
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ObservationMark:
    """That a component was observed at an instant, by a sample or a log, whatever its quality.

    Carries one stored observation of that instant so the mark itself can be cited as evidence.
    """

    component_id: uuid.UUID
    observed_at: datetime
    sample_id: int | None
    log_id: int | None
