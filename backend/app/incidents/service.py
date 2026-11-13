import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

import structlog
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.observation import ObservationSource
from app.core.retention import EvidenceHolds
from app.health.domain.records import HealthPass, RuleCondition
from app.health.service import HealthReader
from app.identity.domain import AuditAction, AuditContext
from app.identity.service import AuditDraft, AuditedMutations
from app.incidents import repository
from app.incidents.domain.conditions import alert_severity, covered_classes
from app.incidents.domain.engine import (
    IncidentPass,
    IncidentPlan,
    process,
    reopenable_since,
)
from app.incidents.domain.lifecycle import (
    Change,
    Closure,
    acknowledge,
    record_diagnostic,
    resolve,
)
from app.incidents.domain.model import (
    Actor,
    ActorType,
    ConditionActiveError,
    EventType,
    Incident,
    IncidentNotFoundError,
    Resolution,
    StoredEvent,
)
from app.incidents.domain.records import (
    PACKED_OBSERVATIONS,
    CoveredRule,
    EventPosition,
    EvidenceItem,
    ImpactView,
    IncidentDetail,
    IncidentFilter,
    IncidentSummary,
    StoredEvidence,
)
from app.incidents.repository import IncidentRepository
from app.ingestion.service import ObservationReader
from app.topology.domain import PlatformNotFoundError, PlatformTopology
from app.topology.service import TopologyService

# Evidence and events embedded in an incident detail; further pages through their own routes.
DETAIL_PAGE = 200

log = structlog.get_logger(__name__)


def evidence_holds() -> EvidenceHolds:
    """Observations and evaluations that retention and reset must keep (ADR 0008)."""
    return repository.evidence_holds()


class ScenarioAttribution(Protocol):
    def run_on(
        self, session: Session, component_id: uuid.UUID, at: datetime
    ) -> uuid.UUID | None: ...


class IncidentProcessing:
    """Cycle step 6 (architecture §02.2), inside the caller's unit of work."""

    def __init__(
        self,
        topology: TopologyService,
        platform_key: str,
        attribution: ScenarioAttribution,
        source: ObservationSource,
    ) -> None:
        self._topology_service = topology
        self._platform_key = platform_key
        self._attribution = attribution
        self._source = source
        self._topology: PlatformTopology | None = None

    def process(
        self, session: Session, platform_now: datetime, health: HealthPass | None
    ) -> IncidentPass | None:
        """Applies the evaluations the health step stored in this cycle; None when there were
        none or when processing failed.

        Writes sit in a savepoint: a failure never rolls back the health states of the cycle.
        Firing and recovered rules are evaluated again within a minute, so incidents catch up.
        """
        if health is None or not health.outcomes:
            return None
        try:
            with session.begin_nested():
                return self._process(session, health)
        except Exception:
            # Incident boundary (C-14), like the health step: logged, the cycle goes on.
            log.exception("incidents.processing_failed", platform_time=platform_now)
            return None

    def _process(self, session: Session, health: HealthPass) -> IncidentPass:
        topology = self._platform()
        incidents = IncidentRepository(session)
        # Locked until the cycle commits: an acknowledgement or a manual resolution waits.
        active = incidents.active(topology.platform_id, for_update=True)
        since = reopenable_since(health.outcomes[0].evaluated_at, health.history_start)
        impacts = incidents.impacts([i.id for i in active])
        plan = IncidentPlan(
            topology=topology,
            rules=health.rules,
            before=health.before,
            outcomes=health.outcomes,
            active=active,
            reopenable=incidents.latest_resolved(topology.platform_id, since),
            impacted={k: frozenset(v.component_id for v in views) for k, views in impacts.items()},
            source=self._source,
            new_id=uuid.uuid7,
        )
        result = process(plan)
        opened = [
            replace(
                i, scenario_run_id=self._attribution.run_on(session, i.component_id, i.opened_at)
            )
            for i in result.opened
        ]
        # Updates first: a reclassified incident frees its former fingerprint for a new one.
        incidents.update(result.changed)
        numbers = incidents.insert(opened)
        incidents.add_impacts(result.impacts)
        incidents.add_events(result.events)
        incidents.add_evidence(result.evidence)
        _log_events(result, {**{i.id: i.number for i in result.changed}, **numbers})
        return result

    def _platform(self) -> PlatformTopology:
        # Components and dependencies only change at seed time, before the worker starts.
        if self._topology is None:
            topology = self._topology_service.platform(self._platform_key)
            if topology is None:
                raise PlatformNotFoundError(f"Platform {self._platform_key} is not seeded.")
            self._topology = topology
        return self._topology


_LOGGED = {
    EventType.OPENED: "incident.opened",
    EventType.SEVERITY_CHANGED: "incident.severity_changed",
    EventType.RESOLVED: "incident.resolved",
    EventType.REOPENED: "incident.reopened",
    EventType.RECLASSIFIED: "incident.reclassified",
    EventType.DOWNSTREAM_SUPPRESSED: "incident.downstream_suppressed",
}


def _log_events(result: IncidentPass, numbers: dict[uuid.UUID, int | None]) -> None:
    for event in result.events:
        name = _LOGGED.get(event.type)
        if name is not None:
            log.info(
                name,
                incident_id=event.incident_id,
                number=numbers.get(event.incident_id),
                platform_time=event.occurred_at,
                **event.payload,
            )


def actor_of(context: AuditContext) -> Actor:
    return Actor(ActorType.USER, context.actor_label, context.actor_id)


class IncidentCommands:
    """Human actions on incidents; each is audited, refused ones included (X-14)."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        wall: Clock,
        platform_now: Callable[[], datetime],
    ) -> None:
        self._audited = AuditedMutations(session_factory, wall)
        self._platform_now = platform_now

    def acknowledge(self, incident_id: uuid.UUID, context: AuditContext) -> Incident:
        """Idempotent: acknowledging an acknowledged incident returns it unchanged."""
        with self._audited.run(context, AuditAction.INCIDENT_ACK) as work:
            history, incident, at = self._begin(work.session, incident_id, work.audit)
            change = acknowledge(incident, actor_of(context), at)
            work.audit.details["changed"] = bool(change.events)
            return history.apply(change)

    def resolve(self, incident_id: uuid.UUID, comment: str, context: AuditContext) -> Incident:
        """Refused with INCIDENT_CONDITION_ACTIVE while a covered rule still alerts (ADR 0005)."""
        with self._audited.run(context, AuditAction.INCIDENT_RESOLVE) as work:
            history, incident, at = self._begin(work.session, incident_id, work.audit)
            if incident.status.active:
                alerting = [r for r in history.condition(incident) if r.alerting]
                if alerting:
                    states = ", ".join(f"{r.rule.key} {r.state}" for r in alerting)
                    raise ConditionActiveError(
                        f"{incident.reference} cannot be resolved while its condition is "
                        f"active ({states}); it resolves itself once the rules recover."
                    )
            closure = Closure(Resolution.MANUAL, actor_of(context), at, {"comment": comment})
            return history.apply(resolve(incident, closure))

    def _begin(
        self, session: Session, incident_id: uuid.UUID, audit: AuditDraft
    ) -> tuple[IncidentHistory, Incident, datetime]:
        audit.target_type, audit.target_id = "incident", str(incident_id)
        history = IncidentHistory(session)
        incident = history.lock(incident_id)
        audit.platform_time = at = self._platform_now()
        return history, incident, at


class IncidentHistory:
    """Incident reads and writes in the caller's unit of work, for other modules' use cases."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._incidents = IncidentRepository(session)

    def find(self, incident_id: uuid.UUID) -> Incident:
        incident = self._incidents.get(incident_id, for_update=False)
        if incident is None:
            raise IncidentNotFoundError(f"No incident {incident_id}.")
        return incident

    def lock(self, incident_id: uuid.UUID) -> Incident:
        incident = self._incidents.get(incident_id, for_update=True)
        if incident is None:
            raise IncidentNotFoundError(f"No incident {incident_id}.")
        return incident

    def apply(self, change: Change) -> Incident:
        if change.events:
            self._incidents.update([change.incident])
            self._incidents.add_events(change.events)
        return change.incident

    def close_all(self, actor: Actor, at: datetime) -> int:
        """Resolves every active incident as `reset`; returns how many were closed."""
        active = self._incidents.active(None, for_update=True)
        for incident in active:
            self.apply(resolve(incident, Closure(Resolution.RESET, actor, at, {})))
        return len(active)

    def record_diagnostic(
        self, incident: Incident, diagnostic: tuple[uuid.UUID, str], actor: Actor, at: datetime
    ) -> None:
        self.apply(record_diagnostic(incident, diagnostic, actor, at))

    def condition(self, incident: Incident) -> list[CoveredRule]:
        """Rules the incident covers on its component, in their current stored state."""
        classes = covered_classes(incident.failure_class)
        return [
            CoveredRule(
                rule=s.rule,
                state=s.progress.state,
                raw_state=s.measurement.raw_state,
                evaluated_at=s.evaluated_at,
                alerting=alert_severity(
                    s.rule, RuleCondition(s.progress.state, s.measurement.raw_state)
                )
                is not None,
            )
            for s in HealthReader(self._session).rule_states(incident.component_id)
            if s.rule.definition.failure_class in classes
        ]

    def impacts(self, incident_id: uuid.UUID) -> list[ImpactView]:
        return self._incidents.impacts([incident_id]).get(incident_id, [])

    def related(
        self, component_ids: set[uuid.UUID], start: datetime, end: datetime, limit: int
    ) -> list[Incident]:
        """Incidents of these components active at some point of [start, end]."""
        return self._incidents.overlapping(component_ids, start, end, limit)

    def key_evidence(self, incident_id: uuid.UUID, limit: int) -> list[EvidenceItem]:
        """Evaluations that opened, impacted or recovered the incident, the latest supporting
        ones, and the first observations each cites: at most 2 x limit x (1 + PACKED) items."""
        evaluations = self._incidents.key_evaluations(incident_id, limit)
        evaluations += self._incidents.latest_supporting_evaluations(incident_id, limit)
        items = resolve_evidence(self._session, evaluations)
        cited = [i.evaluation.measurement.evidence for i in items if i.evaluation is not None]
        observations = self._incidents.observation_evidence(
            incident_id,
            sorted({s for e in cited for s in e.sample_ids[:PACKED_OBSERVATIONS]}),
            sorted({lg for e in cited for lg in e.log_ids[:PACKED_OBSERVATIONS]}),
        )
        return items + resolve_evidence(self._session, observations)

    def has_log_evidence(self, incident_id: uuid.UUID) -> bool:
        return self._incidents.has_log_evidence(incident_id)


def resolve_evidence(session: Session, stored: Sequence[StoredEvidence]) -> list[EvidenceItem]:
    """Evidence rows with the evaluation, sample or log each references (foreign keys)."""
    evaluations = HealthReader(session).evaluations(
        [s.evaluation_id for s in stored if s.evaluation_id is not None]
    )
    observations = ObservationReader(session)
    samples = observations.samples_by_ids([s.sample_id for s in stored if s.sample_id])
    logs = observations.logs_by_ids([s.log_id for s in stored if s.log_id is not None])
    return [
        EvidenceItem(
            stored=s,
            evaluation=None if s.evaluation_id is None else evaluations.get(s.evaluation_id),
            sample=None if s.sample_id is None else samples.get(s.sample_id),
            log=None if s.log_id is None else logs.get(s.log_id),
        )
        for s in stored
    ]


@dataclass(frozen=True, slots=True)
class EvidencePage:
    items: list[EvidenceItem]
    has_more: bool


@dataclass(frozen=True, slots=True)
class EventPage:
    items: list[StoredEvent]
    has_more: bool


class IncidentQueries:
    """Read side for the API; each answer reads in one session."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def summary(self, incident_id: uuid.UUID) -> IncidentSummary:
        with self._session_factory() as session:
            incidents = IncidentRepository(session)
            incident = incidents.get(incident_id, for_update=False)
            if incident is None:
                raise IncidentNotFoundError(f"No incident {incident_id}.")
            (summary,) = _summaries(incidents, [incident])
            return summary

    def page(self, query: IncidentFilter) -> list[IncidentSummary]:
        with self._session_factory() as session:
            incidents = IncidentRepository(session)
            found = incidents.page(query)
            return _summaries(incidents, found)

    def detail(self, incident_id: uuid.UUID) -> IncidentDetail:
        with self._session_factory() as session:
            incidents = IncidentRepository(session)
            incident = incidents.get(incident_id, for_update=False)
            if incident is None:
                raise IncidentNotFoundError(f"No incident {incident_id}.")
            (summary,) = _summaries(incidents, [incident])
            return IncidentDetail(
                summary=summary,
                condition=tuple(IncidentHistory(session).condition(incident)),
                evidence=tuple(
                    resolve_evidence(session, incidents.evidence(incident_id, None, DETAIL_PAGE))
                ),
                events=tuple(incidents.events(incident_id, None, DETAIL_PAGE)),
                event_count=incidents.event_count(incident_id),
            )

    def evidence(self, incident_id: uuid.UUID, after: int | None, limit: int) -> EvidencePage:
        with self._session_factory() as session:
            incidents = self._existing(session, incident_id)
            stored = incidents.evidence(incident_id, after, limit + 1)
            items = resolve_evidence(session, stored[:limit])
        return EvidencePage(items, len(stored) > limit)

    def events(self, incident_id: uuid.UUID, after: EventPosition | None, limit: int) -> EventPage:
        with self._session_factory() as session:
            found = self._existing(session, incident_id).events(incident_id, after, limit + 1)
        return EventPage(found[:limit], len(found) > limit)

    @staticmethod
    def _existing(session: Session, incident_id: uuid.UUID) -> IncidentRepository:
        incidents = IncidentRepository(session)
        if incidents.get(incident_id, for_update=False) is None:
            raise IncidentNotFoundError(f"No incident {incident_id}.")
        return incidents


def _summaries(incidents: IncidentRepository, found: Sequence[Incident]) -> list[IncidentSummary]:
    ids = [i.id for i in found]
    counts = incidents.evidence_counts(ids)
    impacts = incidents.impacts(ids)
    return [IncidentSummary(i, counts.get(i.id, 0), tuple(impacts.get(i.id, []))) for i in found]
