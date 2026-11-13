"""Stored incidents as services and the API read them."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.health.domain.records import StoredEvaluation
from app.health.domain.rules import FailureClass, HealthRule
from app.health.domain.states import HealthState
from app.incidents.domain.model import (
    EvidenceRole,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    StoredEvent,
)
from app.ingestion.domain.logs import StoredLog
from app.ingestion.domain.observations import SampleDetail

# Observations of each evaluation carried into an evidence pack (§06.2: a bounded pack).
PACKED_OBSERVATIONS = 1


@dataclass(frozen=True, slots=True)
class IncidentPosition:
    """Keyset position: the last incident of the previous page."""

    opened_at: datetime
    number: int


@dataclass(frozen=True, slots=True)
class IncidentFilter:
    """Incidents newest opened first; `opened_from` inclusive, `opened_to` exclusive."""

    platform_id: uuid.UUID | None
    statuses: frozenset[IncidentStatus]
    severity: IncidentSeverity | None
    component_id: uuid.UUID | None
    failure_class: FailureClass | None
    opened_from: datetime | None
    opened_to: datetime | None
    before: IncidentPosition | None
    limit: int


@dataclass(frozen=True, slots=True)
class ImpactView:
    component_id: uuid.UUID
    since: datetime


@dataclass(frozen=True, slots=True)
class IncidentSummary:
    incident: Incident
    evidence_count: int
    impacts: tuple[ImpactView, ...]


@dataclass(frozen=True, slots=True)
class StoredEvidence:
    """An evidence row; `ordinal` numbers the incident's evidence from 1, in insertion order,
    which append-only storage keeps stable (the `E<n>` labels)."""

    id: int
    ordinal: int
    role: EvidenceRole
    added_at: datetime
    evaluation_id: int | None
    sample_id: int | None
    log_id: int | None


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """An evidence row with the stored evaluation, sample or log it references."""

    stored: StoredEvidence
    evaluation: StoredEvaluation | None
    sample: SampleDetail | None
    log: StoredLog | None

    @property
    def label(self) -> str:
        return f"E{self.stored.ordinal}"


@dataclass(frozen=True, slots=True)
class EventPosition:
    occurred_at: datetime
    id: int


@dataclass(frozen=True, slots=True)
class CoveredRule:
    """A rule the incident's condition covers, in its current stored state."""

    rule: HealthRule
    state: HealthState
    raw_state: HealthState
    evaluated_at: datetime
    alerting: bool


@dataclass(frozen=True, slots=True)
class IncidentDetail:
    summary: IncidentSummary
    condition: tuple[CoveredRule, ...]
    evidence: tuple[EvidenceItem, ...]
    events: tuple[StoredEvent, ...]
    event_count: int

    @property
    def resolvable(self) -> bool:
        """Manual resolution is refused while a covered rule still alerts (ADR 0005)."""
        incident = self.summary.incident
        return incident.status.active and not any(r.alerting for r in self.condition)
