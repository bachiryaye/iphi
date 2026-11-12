"""Collection runs: one per connector and cycle, the monitor's evidence that data arrives."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.observation import ObservationSource

MAX_ERROR_MESSAGE_CHARS = 500


class CollectionStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CollectionRun:
    id: uuid.UUID
    connector_key: str
    source: ObservationSource
    started_at: datetime
    finished_at: datetime
    status: CollectionStatus
    sample_count: int
    log_count: int
    rejected_count: int
    duplicate_count: int
    rejections: Mapping[str, int]
    watermark: datetime | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    """What a connector delivered in one cycle, before it is recorded as a run."""

    sample_count: int = 0
    log_count: int = 0
    duplicate_count: int = 0
    rejections: Mapping[str, int] | None = None
    watermark: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def rejected_count(self) -> int:
        return sum((self.rejections or {}).values())

    @property
    def status(self) -> CollectionStatus:
        """Duplicates are expected on re-delivery and keep a run `ok`; rejections do not.

        A run that stored nothing and delivered nothing already known failed, whether the
        connector reported an error or every observation was rejected.
        """
        nothing_usable = self.sample_count + self.log_count + self.duplicate_count == 0
        if nothing_usable and (self.error_code is not None or self.rejected_count):
            return CollectionStatus.FAILED
        if self.error_code is not None or self.rejected_count:
            return CollectionStatus.PARTIAL
        return CollectionStatus.OK

    @classmethod
    def failed(cls, code: str, message: str) -> CollectionOutcome:
        return cls(error_code=code, error_message=message)
