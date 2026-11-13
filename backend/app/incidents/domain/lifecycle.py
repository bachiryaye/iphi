"""Incident lifecycle: the single state machine of incidents (rules.md P-03, D-11; ADR 0005).

Every function returns the changed incident with the events recording the change; callers
persist both in one transaction. A status transition is never dated before the incident's
latest change: when the worker processes a sample slot older than a human action, the timeline
read in time order still ends in the incident's current status.
"""

import uuid
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from app.core.observation import ObservationSource
from app.health.domain.rules import FailureClass
from app.incidents.domain.model import (
    SYSTEM_ACTOR,
    Actor,
    EventType,
    Fingerprint,
    IllegalTransitionError,
    Incident,
    IncidentEvent,
    IncidentSeverity,
    IncidentStatus,
    Payload,
    PayloadValue,
    Resolution,
    incident_title,
)


class Action(StrEnum):
    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"
    REOPEN = "reopen"


TRANSITIONS = MappingProxyType(
    {
        (IncidentStatus.OPEN, Action.ACKNOWLEDGE): IncidentStatus.ACKNOWLEDGED,
        (IncidentStatus.OPEN, Action.RESOLVE): IncidentStatus.RESOLVED,
        (IncidentStatus.ACKNOWLEDGED, Action.RESOLVE): IncidentStatus.RESOLVED,
        (IncidentStatus.RESOLVED, Action.REOPEN): IncidentStatus.OPEN,
    }
)

_PAST = {Action.ACKNOWLEDGE: "acknowledged", Action.RESOLVE: "resolved", Action.REOPEN: "reopened"}


def next_status(incident: Incident, action: Action) -> IncidentStatus:
    """Raises IllegalTransitionError for a transition the table does not list."""
    status = TRANSITIONS.get((incident.status, action))
    if status is None:
        raise IllegalTransitionError(
            f"{incident.reference} is {incident.status}; it cannot be {_PAST[action]}."
        )
    return status


@dataclass(frozen=True, slots=True)
class Change:
    incident: Incident
    events: tuple[IncidentEvent, ...]


@dataclass(frozen=True, slots=True)
class Detection:
    """A stored rule evaluation that changes an incident, at its sample slot."""

    evaluation_id: int
    rule_key: str
    rule_version: int
    at: datetime

    def payload(self) -> dict[str, PayloadValue]:
        return {
            "evaluation_id": self.evaluation_id,
            "rule_key": self.rule_key,
            "rule_version": self.rule_version,
        }


@dataclass(frozen=True, slots=True)
class Opening:
    id: uuid.UUID
    platform_id: uuid.UUID
    component_id: uuid.UUID
    component_key: str
    failure_class: FailureClass
    severity: IncidentSeverity
    source: ObservationSource


@dataclass(frozen=True, slots=True)
class Closure:
    resolution: Resolution
    actor: Actor
    at: datetime
    details: Payload


def open_incident(opening: Opening, detection: Detection) -> Change:
    at = detection.at
    incident = Incident(
        id=opening.id,
        number=None,
        platform_id=opening.platform_id,
        component_id=opening.component_id,
        failure_class=opening.failure_class,
        fingerprint=Fingerprint.of(
            opening.platform_id, opening.component_id, opening.failure_class
        ),
        title=incident_title(opening.component_key, opening.failure_class),
        status=IncidentStatus.OPEN,
        severity=opening.severity,
        peak_severity=opening.severity,
        opened_at=at,
        last_seen_at=at,
        updated_at=at,
        acknowledged_at=None,
        acknowledged_by=None,
        resolved_at=None,
        resolved_by=None,
        resolution=None,
        occurrence_count=1,
        reopen_count=0,
        scenario_run_id=None,
        source=opening.source,
    )
    payload = {"severity": opening.severity.value, **detection.payload()}
    return Change(incident, (_event(incident, EventType.OPENED, SYSTEM_ACTOR, at, payload),))


def record_occurrence(incident: Incident, detection: Detection) -> Change:
    """Another stored evaluation confirming the condition of an active incident."""
    at = detection.at
    changed = replace(
        incident,
        occurrence_count=incident.occurrence_count + 1,
        last_seen_at=max(incident.last_seen_at, at),
        updated_at=max(incident.updated_at, at),
    )
    event = _event(changed, EventType.OCCURRENCE, SYSTEM_ACTOR, at, detection.payload())
    return Change(changed, (event,))


def change_severity(incident: Incident, severity: IncidentSeverity, detection: Detection) -> Change:
    if severity is incident.severity:
        return Change(incident, ())
    at = _not_before(incident, detection.at)
    changed = replace(
        incident,
        severity=severity,
        peak_severity=max(incident.peak_severity, severity, key=_rank),
        updated_at=at,
    )
    payload = {"from": incident.severity.value, "to": severity.value, **detection.payload()}
    event = _event(changed, EventType.SEVERITY_CHANGED, SYSTEM_ACTOR, at, payload)
    return Change(changed, (event,))


def acknowledge(incident: Incident, actor: Actor, at: datetime) -> Change:
    """Idempotent: an acknowledged incident is returned unchanged, without event."""
    if incident.status is IncidentStatus.ACKNOWLEDGED:
        return Change(incident, ())
    status = next_status(incident, Action.ACKNOWLEDGE)
    at = _not_before(incident, at)
    changed = replace(
        incident, status=status, acknowledged_at=at, acknowledged_by=actor.label, updated_at=at
    )
    return Change(changed, (_event(changed, EventType.ACKNOWLEDGED, actor, at, {}),))


def resolve(incident: Incident, closure: Closure) -> Change:
    if closure.resolution is Resolution.MANUAL and not closure.details.get("comment"):
        raise ValueError("a manual resolution needs a comment")
    status = next_status(incident, Action.RESOLVE)
    at = _not_before(incident, closure.at)
    changed = replace(
        incident,
        status=status,
        resolved_at=at,
        resolved_by=closure.actor.label,
        resolution=closure.resolution,
        updated_at=at,
    )
    payload = {"resolution": closure.resolution.value, **closure.details}
    return Change(changed, (_event(changed, EventType.RESOLVED, closure.actor, at, payload),))


def reopen(incident: Incident, severity: IncidentSeverity, detection: Detection) -> Change:
    status = next_status(incident, Action.REOPEN)
    at = _not_before(incident, detection.at)
    changed = replace(
        incident,
        status=status,
        severity=severity,
        peak_severity=max(incident.peak_severity, severity, key=_rank),
        acknowledged_at=None,
        acknowledged_by=None,
        resolved_at=None,
        resolved_by=None,
        resolution=None,
        occurrence_count=incident.occurrence_count + 1,
        reopen_count=incident.reopen_count + 1,
        last_seen_at=max(incident.last_seen_at, detection.at),
        updated_at=at,
    )
    payload = {
        "severity": severity.value,
        "reopen_count": changed.reopen_count,
        **detection.payload(),
    }
    return Change(changed, (_event(changed, EventType.REOPENED, SYSTEM_ACTOR, at, payload),))


def reclassify_as_unreachable(
    incident: Incident, component_key: str, detection: Detection
) -> Change:
    """A connectivity incident whose component stops answering becomes an availability one:
    the same failure, better named (ADR 0017). Its fingerprint follows the new class."""
    if incident.failure_class is not FailureClass.CONNECTIVITY or not incident.status.active:
        raise ValueError("only an active connectivity incident is reclassified as unreachable")
    target = FailureClass.AVAILABILITY
    at = _not_before(incident, detection.at)
    changed = replace(
        incident,
        failure_class=target,
        fingerprint=Fingerprint.of(incident.platform_id, incident.component_id, target),
        title=incident_title(component_key, target),
        updated_at=at,
    )
    payload = {"from": incident.failure_class.value, "to": target.value, **detection.payload()}
    return Change(changed, (_event(changed, EventType.RECLASSIFIED, SYSTEM_ACTOR, at, payload),))


def suppress_downstream(
    incident: Incident,
    component: tuple[uuid.UUID, str],
    failure_class: FailureClass,
    detection: Detection,
) -> Change:
    """A downstream component's alert attached to this incident instead of opening its own."""
    component_id, component_key = component
    at = detection.at
    changed = replace(incident, updated_at=max(incident.updated_at, at))
    payload = {
        "component_id": str(component_id),
        "component_key": component_key,
        "failure_class": failure_class.value,
        **detection.payload(),
    }
    event = _event(changed, EventType.DOWNSTREAM_SUPPRESSED, SYSTEM_ACTOR, at, payload)
    return Change(changed, (event,))


def record_diagnostic(
    incident: Incident, diagnostic: tuple[uuid.UUID, str], actor: Actor, at: datetime
) -> Change:
    diagnostic_id, kind = diagnostic
    at = _not_before(incident, at)
    changed = replace(incident, updated_at=at)
    payload = {"diagnostic_id": str(diagnostic_id), "kind": kind}
    return Change(changed, (_event(changed, EventType.DIAGNOSTIC_ADDED, actor, at, payload),))


def _not_before(incident: Incident, at: datetime) -> datetime:
    return max(at, incident.updated_at)


def _rank(severity: IncidentSeverity) -> int:
    return severity.rank


def _event(
    incident: Incident, event_type: EventType, actor: Actor, at: datetime, payload: Payload
) -> IncidentEvent:
    return IncidentEvent(incident.id, event_type, actor, at, MappingProxyType(dict(payload)))
