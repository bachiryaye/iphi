"""Incidents with their evidence, timeline and diagnostics (architecture §04.1, ADR 0005)."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.api.health import ComponentRefOut, EvaluationOut, RuleRefOut, evaluation_out
from app.api.mutations import mutation
from app.api.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_CURSOR_CHARS,
    MAX_PAGE_SIZE,
    cursor_instant,
    cursor_integer,
    decode_cursor,
    encode_cursor,
    encode_instant,
)
from app.core.observation import LogSeverity, ObservationSource, Quality
from app.diagnostics.domain.model import (
    Citation,
    Claim,
    DiagnosticKind,
    DiagnosticStatus,
    StoredDiagnostic,
    Uncertainty,
)
from app.diagnostics.service import DiagnosticsService
from app.health.domain.rules import FailureClass
from app.health.domain.states import HealthState
from app.identity.domain import AuditAction, AuditContext
from app.incidents.domain.model import (
    MAX_COMMENT_CHARS,
    ActorType,
    EventType,
    EvidenceRole,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    PayloadValue,
    Resolution,
    StoredEvent,
)
from app.incidents.domain.records import (
    EventPosition,
    EvidenceItem,
    IncidentDetail,
    IncidentFilter,
    IncidentPosition,
    IncidentSummary,
)
from app.incidents.service import DETAIL_PAGE, IncidentCommands, IncidentQueries
from app.ingestion.domain.series import TimeWindow

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])

Simulation = Literal["simulation"]
IdempotencyKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")]
Comment = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_COMMENT_CHARS)
]


class ImpactOut(BaseModel):
    component: ComponentRefOut
    since: datetime


class IncidentOut(BaseModel):
    id: uuid.UUID
    number: int
    reference: str = Field(description="Human-readable identifier, INC-<number>.")
    title: str
    platform_id: uuid.UUID
    component: ComponentRefOut
    failure_class: FailureClass
    fingerprint: str = Field(description="sha256(platform|component|failure class).")
    status: IncidentStatus
    severity: IncidentSeverity = Field(description="Current severity of the condition.")
    peak_severity: IncidentSeverity
    opened_at: datetime
    last_seen_at: datetime = Field(description="Sample slot of the latest occurrence.")
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    resolution: Resolution | None
    occurrence_count: int = Field(description="Stored evaluations that confirmed the condition.")
    reopen_count: int
    evidence_count: int
    impacted: list[ImpactOut] = Field(
        description="Downstream components whose own alerts were suppressed into this incident."
    )
    scenario_run_id: uuid.UUID | None
    source: ObservationSource
    environment: Simulation = "simulation"


class IncidentPageOut(BaseModel):
    environment: Simulation = "simulation"
    items: list[IncidentOut]
    next_cursor: str | None


class SampleEvidenceOut(BaseModel):
    id: int
    metric_name: str
    value: float
    unit: str
    quality: Quality
    observed_at: datetime
    source: ObservationSource
    scenario_run_id: uuid.UUID | None


class LogEvidenceOut(BaseModel):
    id: int
    severity: LogSeverity
    message: str
    fingerprint: str
    observed_at: datetime
    source: ObservationSource
    scenario_run_id: uuid.UUID | None


class EvidenceOut(BaseModel):
    id: int
    label: str = Field(description="Stable label within the incident: E1, E2…")
    role: EvidenceRole
    kind: Literal["evaluation", "sample", "log"]
    added_at: datetime
    component: ComponentRefOut | None
    evaluation: EvaluationOut | None
    sample: SampleEvidenceOut | None
    log: LogEvidenceOut | None


class EvidencePageOut(BaseModel):
    environment: Simulation = "simulation"
    items: list[EvidenceOut]
    next_cursor: str | None


class EventOut(BaseModel):
    id: int
    type: EventType
    occurred_at: datetime = Field(description="Platform time.")
    actor_type: ActorType
    actor_label: str
    payload: dict[str, PayloadValue]


class EventPageOut(BaseModel):
    environment: Simulation = "simulation"
    items: list[EventOut]
    next_cursor: str | None


class CoveredRuleOut(BaseModel):
    rule: RuleRefOut
    failure_class: FailureClass
    state: HealthState = Field(description="Stored debounced state of the rule.")
    raw_state: HealthState
    evaluated_at: datetime
    alerting: bool = Field(description="Whether this rule still calls for the incident.")


class IncidentDetailOut(IncidentOut):
    condition: list[CoveredRuleOut] = Field(
        description="Rules the incident covers; it resolves itself once all are Healthy."
    )
    resolvable: bool = Field(description="Manual resolution is refused while a rule alerts.")
    evidence: list[EvidenceOut] = Field(description=f"First {DETAIL_PAGE} items, oldest first.")
    evidence_next_cursor: str | None
    events: list[EventOut] = Field(description=f"First {DETAIL_PAGE} events, oldest first.")
    event_count: int
    events_next_cursor: str | None


class IncidentListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_id: uuid.UUID | None = None
    status: list[IncidentStatus] = Field(default_factory=list, description="Any of; all if empty.")
    severity: IncidentSeverity | None = None
    component_id: uuid.UUID | None = None
    failure_class: FailureClass | None = None
    start: AwareDatetime | None = Field(
        default=None, alias="from", description="Opened at or after."
    )
    end: AwareDatetime | None = Field(default=None, alias="to", description="Opened before.")
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_CHARS)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class PageParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_CHARS)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


class ResolveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    comment: Comment = Field(description="Why the incident is closed; kept in its timeline.")


class CitationOut(BaseModel):
    evidence_id: int
    label: str


class ClaimOut(BaseModel):
    text: str
    evidence: list[CitationOut]


class HypothesisOut(ClaimOut):
    uncertainty: Uncertainty


class ValidationOut(BaseModel):
    checked_claims: int
    removed: list[str] = Field(description="Claims dropped: no citation in the evidence set.")
    dropped_citations: int


class DiagnosticOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    kind: DiagnosticKind
    provider: str
    model: str
    status: DiagnosticStatus
    observed_facts: list[ClaimOut]
    hypotheses: list[HypothesisOut] = Field(description="Correlations, never proven causes.")
    recommended_checks: list[ClaimOut]
    limitations: list[str]
    evidence_set_hash: str
    validation: ValidationOut
    created_by: str
    created_at: datetime = Field(description="Platform time.")
    environment: Simulation = "simulation"


class DiagnosticListOut(BaseModel):
    items: list[DiagnosticOut]


def incident_queries(request: Request) -> IncidentQueries:
    service: IncidentQueries = request.app.state.incident_queries
    return service


def incident_commands(request: Request) -> IncidentCommands:
    service: IncidentCommands = request.app.state.incident_commands
    return service


def diagnostics_service(request: Request) -> DiagnosticsService:
    service: DiagnosticsService = request.app.state.diagnostics
    return service


def component_keys(request: Request) -> dict[uuid.UUID, str]:
    keys: dict[uuid.UUID, str] = request.app.state.health.component_keys()
    return keys


Queries = Annotated[IncidentQueries, Depends(incident_queries)]
Commands = Annotated[IncidentCommands, Depends(incident_commands)]
Diagnostics = Annotated[DiagnosticsService, Depends(diagnostics_service)]
Keys = Annotated[dict[uuid.UUID, str], Depends(component_keys)]


@router.get("", summary="Incidents, newest opened first, filterable.")
def list_incidents(
    service: Queries, keys: Keys, params: Annotated[IncidentListParams, Query()]
) -> IncidentPageOut:
    if params.start is not None and params.end is not None:
        TimeWindow(params.start, params.end)
    query = IncidentFilter(
        platform_id=params.platform_id,
        statuses=frozenset(params.status),
        severity=params.severity,
        component_id=params.component_id,
        failure_class=params.failure_class,
        opened_from=params.start,
        opened_to=params.end,
        before=None if params.cursor is None else _decode_incident_cursor(params.cursor),
        limit=params.limit + 1,
    )
    found = service.page(query)
    page = found[: params.limit]
    last = page[-1].incident if page else None
    more = len(found) > params.limit and last is not None and last.number is not None
    return IncidentPageOut(
        items=[_incident_out(s, keys) for s in page],
        next_cursor=_encode_incident_cursor(last) if more and last is not None else None,
    )


@router.get("/{incident_id}", summary="Incident with its condition, evidence and timeline.")
def incident_detail(incident_id: uuid.UUID, service: Queries, keys: Keys) -> IncidentDetailOut:
    detail = service.detail(incident_id)
    return _detail_out(detail, keys)


@router.get("/{incident_id}/evidence", summary="Evidence of an incident, oldest first.")
def incident_evidence(
    incident_id: uuid.UUID, service: Queries, keys: Keys, params: Annotated[PageParams, Query()]
) -> EvidencePageOut:
    after = None if params.cursor is None else _decode_evidence_cursor(params.cursor)
    page = service.evidence(incident_id, after, params.limit)
    last = page.items[-1].stored.id if page.items else None
    return EvidencePageOut(
        items=[_evidence_out(i, keys) for i in page.items],
        next_cursor=encode_cursor("evidence", str(last)) if page.has_more and last else None,
    )


@router.get("/{incident_id}/events", summary="Timeline of an incident, oldest first.")
def incident_events(
    incident_id: uuid.UUID, service: Queries, params: Annotated[PageParams, Query()]
) -> EventPageOut:
    after = None if params.cursor is None else _decode_event_cursor(params.cursor)
    page = service.events(incident_id, after, params.limit)
    last = page.items[-1] if page.items else None
    return EventPageOut(
        items=[_event_out(e) for e in page.items],
        next_cursor=_encode_event_cursor(last) if page.has_more and last is not None else None,
    )


@dataclass(frozen=True, slots=True)
class IncidentViews:
    """Renders an incident after a command, as the list shows it."""

    queries: IncidentQueries
    keys: dict[uuid.UUID, str]

    def of(self, incident: Incident) -> IncidentOut:
        return _incident_out(self.queries.summary(incident.id), self.keys)


def incident_views(queries: Queries, keys: Keys) -> IncidentViews:
    return IncidentViews(queries, keys)


@dataclass(frozen=True, slots=True)
class DiagnoseOptions:
    mode: DiagnosticKind
    idempotency_key: str | None


def diagnose_options(
    mode: Annotated[
        Literal["deterministic"],
        Query(description="`llm` arrives with US-08; deterministic is always available."),
    ] = "deterministic",
    idempotency_key: Annotated[IdempotencyKey | None, Header(alias="Idempotency-Key")] = None,
) -> DiagnoseOptions:
    return DiagnoseOptions(DiagnosticKind(mode), idempotency_key)


Views = Annotated[IncidentViews, Depends(incident_views)]


@router.post("/{incident_id}/ack", summary="Acknowledge an incident; idempotent.")
def acknowledge_incident(
    incident_id: uuid.UUID,
    service: Commands,
    views: Views,
    context: Annotated[AuditContext, Depends(mutation(AuditAction.INCIDENT_ACK))],
) -> IncidentOut:
    return views.of(service.acknowledge(incident_id, context))


@router.post(
    "/{incident_id}/resolve",
    summary="Resolve an incident manually; refused while its condition is active.",
    responses={409: {"description": "INCIDENT_CONDITION_ACTIVE or INCIDENT_ILLEGAL_TRANSITION"}},
)
def resolve_incident(
    incident_id: uuid.UUID,
    body: ResolveIn,
    service: Commands,
    views: Views,
    context: Annotated[AuditContext, Depends(mutation(AuditAction.INCIDENT_RESOLVE))],
) -> IncidentOut:
    return views.of(service.resolve(incident_id, body.comment, context))


@router.post(
    "/{incident_id}/diagnose",
    status_code=status.HTTP_201_CREATED,
    summary="Diagnose an incident from its stored evidence.",
    responses={200: {"model": DiagnosticOut, "description": "Same key or unchanged evidence."}},
)
def diagnose_incident(
    incident_id: uuid.UUID,
    response: Response,
    service: Diagnostics,
    options: Annotated[DiagnoseOptions, Depends(diagnose_options)],
    context: Annotated[AuditContext, Depends(mutation(AuditAction.INCIDENT_DIAGNOSE))],
) -> DiagnosticOut:
    result = service.diagnose(incident_id, options.mode, options.idempotency_key, context)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _diagnostic_out(result.diagnostic)


@router.get("/{incident_id}/diagnostics", summary="Stored diagnostics, newest first.")
def list_diagnostics(incident_id: uuid.UUID, service: Diagnostics) -> DiagnosticListOut:
    return DiagnosticListOut(items=[_diagnostic_out(d) for d in service.of_incident(incident_id)])


def _ref(component_id: uuid.UUID, keys: dict[uuid.UUID, str]) -> ComponentRefOut:
    return ComponentRefOut(id=component_id, key=keys.get(component_id, "unknown"))


def _incident_out(summary: IncidentSummary, keys: dict[uuid.UUID, str]) -> IncidentOut:
    i = summary.incident
    return IncidentOut(
        id=i.id,
        number=i.number or 0,
        reference=i.reference,
        title=i.title,
        platform_id=i.platform_id,
        component=_ref(i.component_id, keys),
        failure_class=i.failure_class,
        fingerprint=i.fingerprint.value,
        status=i.status,
        severity=i.severity,
        peak_severity=i.peak_severity,
        opened_at=i.opened_at,
        last_seen_at=i.last_seen_at,
        acknowledged_at=i.acknowledged_at,
        acknowledged_by=i.acknowledged_by,
        resolved_at=i.resolved_at,
        resolved_by=i.resolved_by,
        resolution=i.resolution,
        occurrence_count=i.occurrence_count,
        reopen_count=i.reopen_count,
        evidence_count=summary.evidence_count,
        impacted=[
            ImpactOut(component=_ref(v.component_id, keys), since=v.since) for v in summary.impacts
        ],
        scenario_run_id=i.scenario_run_id,
        source=i.source,
    )


def _detail_out(detail: IncidentDetail, keys: dict[uuid.UUID, str]) -> IncidentDetailOut:
    evidence = list(detail.evidence)
    events = list(detail.events)
    last_evidence = evidence[-1].stored.id if evidence else None
    more_evidence = detail.summary.evidence_count > len(evidence) and last_evidence is not None
    more_events = detail.event_count > len(events) and bool(events)
    return IncidentDetailOut(
        **_incident_out(detail.summary, keys).model_dump(),
        condition=[
            CoveredRuleOut(
                rule=RuleRefOut(id=r.rule.id, key=r.rule.key, version=r.rule.version),
                failure_class=r.rule.definition.failure_class,
                state=r.state,
                raw_state=r.raw_state,
                evaluated_at=r.evaluated_at,
                alerting=r.alerting,
            )
            for r in detail.condition
        ],
        resolvable=detail.resolvable,
        evidence=[_evidence_out(i, keys) for i in evidence],
        evidence_next_cursor=encode_cursor("evidence", str(last_evidence))
        if more_evidence
        else None,
        events=[_event_out(e) for e in events],
        event_count=detail.event_count,
        events_next_cursor=_encode_event_cursor(events[-1]) if more_events else None,
    )


def _evidence_out(item: EvidenceItem, keys: dict[uuid.UUID, str]) -> EvidenceOut:
    e, s, lg = item.evaluation, item.sample, item.log
    component_id = e.component_id if e else s.component_id if s else lg.component_id if lg else None
    kind: Literal["evaluation", "sample", "log"] = "evaluation" if e else "sample" if s else "log"
    return EvidenceOut(
        id=item.stored.id,
        label=item.label,
        role=item.stored.role,
        kind=kind,
        added_at=item.stored.added_at,
        component=None if component_id is None else _ref(component_id, keys),
        evaluation=None if e is None else evaluation_out(e, keys.get(e.component_id, "unknown")),
        sample=None
        if s is None
        else SampleEvidenceOut(
            id=s.id,
            metric_name=s.metric_name,
            value=s.value,
            unit=s.unit,
            quality=s.quality,
            observed_at=s.observed_at,
            source=s.source,
            scenario_run_id=s.scenario_run_id,
        ),
        log=None
        if lg is None
        else LogEvidenceOut(
            id=lg.id,
            severity=lg.severity,
            message=lg.message,
            fingerprint=lg.fingerprint,
            observed_at=lg.observed_at,
            source=lg.source,
            scenario_run_id=lg.scenario_run_id,
        ),
    )


def _event_out(stored: StoredEvent) -> EventOut:
    e = stored.event
    return EventOut(
        id=stored.id,
        type=e.type,
        occurred_at=e.occurred_at,
        actor_type=e.actor.type,
        actor_label=e.actor.label,
        payload=dict(e.payload),
    )


def _citations(citations: tuple[Citation, ...]) -> list[CitationOut]:
    return [CitationOut(evidence_id=c.evidence_id, label=c.label) for c in citations]


def _claim_out(claim: Claim) -> ClaimOut:
    return ClaimOut(text=claim.text, evidence=_citations(claim.citations))


def _diagnostic_out(d: StoredDiagnostic) -> DiagnosticOut:
    diagnosis = d.diagnosis
    return DiagnosticOut(
        id=d.id,
        incident_id=d.incident_id,
        kind=d.kind,
        provider=d.provider,
        model=d.model,
        status=d.status,
        observed_facts=[_claim_out(c) for c in diagnosis.observed_facts],
        hypotheses=[
            HypothesisOut(text=h.text, evidence=_citations(h.citations), uncertainty=h.uncertainty)
            for h in diagnosis.hypotheses
        ],
        recommended_checks=[_claim_out(c) for c in diagnosis.recommended_checks],
        limitations=list(diagnosis.limitations),
        evidence_set_hash=d.evidence_set_hash,
        validation=ValidationOut(
            checked_claims=d.validation.checked_claims,
            removed=list(d.validation.removed),
            dropped_citations=d.validation.dropped_citations,
        ),
        created_by=d.created_by,
        created_at=d.created_at,
    )


def _encode_incident_cursor(incident: Incident) -> str:
    return encode_cursor("incident", encode_instant(incident.opened_at), str(incident.number))


def _decode_incident_cursor(cursor: str) -> IncidentPosition:
    at, number = decode_cursor("incident", cursor, 2)
    return IncidentPosition(cursor_instant(at), cursor_integer(number, minimum=1))


def _decode_evidence_cursor(cursor: str) -> int:
    (value,) = decode_cursor("evidence", cursor, 1)
    return cursor_integer(value, minimum=1)


def _encode_event_cursor(stored: StoredEvent) -> str:
    return encode_cursor("event", encode_instant(stored.event.occurred_at), str(stored.id))


def _decode_event_cursor(cursor: str) -> EventPosition:
    at, identifier = decode_cursor("event", cursor, 2)
    return EventPosition(cursor_instant(at), cursor_integer(identifier, minimum=1))
