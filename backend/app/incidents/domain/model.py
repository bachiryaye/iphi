"""Incident vocabulary and value objects (architecture §03.1, §05.5; ADR 0005)."""

import hashlib
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus

from app.core.exceptions import IphiError
from app.core.observation import ObservationSource
from app.health.domain.rules import FailureClass

MAX_COMMENT_CHARS = 4000
_FINGERPRINT = re.compile(r"[0-9a-f]{64}")


class IncidentStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

    @property
    def active(self) -> bool:
        return self is not IncidentStatus.RESOLVED


class IncidentSeverity(StrEnum):
    """Declared from least to most severe."""

    WARNING = "warning"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_ORDER.index(self)


_SEVERITY_ORDER = tuple(IncidentSeverity)


class Resolution(StrEnum):
    AUTO_RECOVERED = "auto_recovered"
    MANUAL = "manual"
    # The simulation reset wipes the history the incident stood on; such incidents never reopen.
    RESET = "reset"


class EvidenceRole(StrEnum):
    TRIGGER = "trigger"
    SUPPORTING = "supporting"
    IMPACT = "impact"
    RECOVERY = "recovery"


class EventType(StrEnum):
    OPENED = "opened"
    OCCURRENCE = "occurrence"
    SEVERITY_CHANGED = "severity_changed"
    ACKNOWLEDGED = "acknowledged"
    COMMENTED = "commented"
    RESOLVED = "resolved"
    REOPENED = "reopened"
    RECLASSIFIED = "reclassified"
    DOWNSTREAM_SUPPRESSED = "downstream_suppressed"
    DIAGNOSTIC_ADDED = "diagnostic_added"


class ActorType(StrEnum):
    SYSTEM = "system"
    USER = "user"


@dataclass(frozen=True, slots=True)
class Actor:
    """`id` is set once users exist (US-11); `label` names the actor meanwhile."""

    type: ActorType
    label: str
    id: uuid.UUID | None = None


SYSTEM_ACTOR = Actor(ActorType.SYSTEM, "system")


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """sha256(platform_id|component_id|failure_class): at most one active incident each (D-10)."""

    value: str

    def __post_init__(self) -> None:
        if not _FINGERPRINT.fullmatch(self.value):
            raise ValueError("a fingerprint is 64 lowercase hexadecimal characters")

    @classmethod
    def of(
        cls, platform_id: uuid.UUID, component_id: uuid.UUID, failure_class: FailureClass
    ) -> Fingerprint:
        material = f"{platform_id}|{component_id}|{failure_class.value}"
        return cls(hashlib.sha256(material.encode()).hexdigest())


_TITLES: Mapping[FailureClass, str] = {
    FailureClass.AVAILABILITY: "{} unreachable",
    FailureClass.LATENCY: "{} probe latency high",
    FailureClass.FRESHNESS: "{} process data stale",
    FailureClass.ERRORS: "{} errors elevated",
    FailureClass.RESOURCES: "{} resource pressure",
    FailureClass.BACKLOG: "{} backlog growing",
    FailureClass.CONNECTIVITY: "{} connectivity degraded",
    FailureClass.TELEMETRY_LOSS: "{} telemetry lost",
}


def incident_title(component_key: str, failure_class: FailureClass) -> str:
    return _TITLES[failure_class].format(component_key)


@dataclass(frozen=True, slots=True)
class Incident:
    """Times are platform times (D-13). `number` is assigned by the database at insert;
    `updated_at` is the platform time of the latest change, never earlier than any event."""

    id: uuid.UUID
    number: int | None
    platform_id: uuid.UUID
    component_id: uuid.UUID
    failure_class: FailureClass
    fingerprint: Fingerprint
    title: str
    status: IncidentStatus
    severity: IncidentSeverity
    peak_severity: IncidentSeverity
    opened_at: datetime
    last_seen_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    resolution: Resolution | None
    occurrence_count: int
    reopen_count: int
    scenario_run_id: uuid.UUID | None
    source: ObservationSource

    @property
    def reference(self) -> str:
        return "INC-pending" if self.number is None else f"INC-{self.number:04d}"


type PayloadValue = str | int | float | bool | None
type Payload = Mapping[str, PayloadValue]


@dataclass(frozen=True, slots=True)
class IncidentEvent:
    incident_id: uuid.UUID
    type: EventType
    actor: Actor
    occurred_at: datetime
    payload: Payload


@dataclass(frozen=True, slots=True)
class StoredEvent:
    id: int
    event: IncidentEvent


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """Exactly one stored observation or rule evaluation (real foreign keys, no polymorphism)."""

    evaluation_id: int | None = None
    sample_id: int | None = None
    log_id: int | None = None

    def __post_init__(self) -> None:
        set_ids = [i for i in (self.evaluation_id, self.sample_id, self.log_id) if i is not None]
        if len(set_ids) != 1 or set_ids[0] < 1:
            raise ValueError("evidence references exactly one stored row")


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    incident_id: uuid.UUID
    ref: EvidenceRef
    role: EvidenceRole
    added_at: datetime


@dataclass(frozen=True, slots=True)
class Impact:
    """A downstream component whose own alert was suppressed into the incident (ADR 0005)."""

    incident_id: uuid.UUID
    component_id: uuid.UUID
    since: datetime


class IncidentNotFoundError(IphiError):
    status = HTTPStatus.NOT_FOUND
    code = "INCIDENT_NOT_FOUND"


class IllegalTransitionError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "INCIDENT_ILLEGAL_TRANSITION"


class ConditionActiveError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "INCIDENT_CONDITION_ACTIVE"
