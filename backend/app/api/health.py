"""Health states with their justification (architecture §04.1, rules.md D-07)."""

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

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
from app.api.simulations import simulation_service
from app.api.windows import WindowParams, window_of
from app.health.domain.evaluation import Evidence, Measurement
from app.health.domain.freshness import HealthView, ReadContext, evaluation_max_age
from app.health.domain.records import EvaluationFilter, EvaluationPosition, StoredEvaluation
from app.health.domain.rules import (
    RULE_KEY_PATTERN,
    Aggregation,
    FailureClass,
    HealthRule,
    Level,
    Operator,
    RuleType,
)
from app.health.domain.states import HealthState
from app.health.service import (
    ComponentHealthView,
    ComponentRef,
    HealthQueries,
    PlatformHealthView,
    RuleStatusView,
)
from app.ingestion.domain.series import TimeWindow
from app.simulation.domain.clock import ClockMode
from app.simulation.service import SimulationService
from app.topology.domain import ComponentType, Criticality, DependencyKind, PlatformTopology

router = APIRouter(prefix="/api/v1", tags=["health"])

Simulation = Literal["simulation"]


class ComponentRefOut(BaseModel):
    id: uuid.UUID
    key: str

    @classmethod
    def of(cls, ref: ComponentRef) -> ComponentRefOut:
        return cls(id=ref.id, key=ref.key)


class HealthOut(BaseModel):
    state: HealthState = Field(
        description="State to act on: Unknown when the stored evaluation is stale (D-02)."
    )
    evaluated_state: HealthState | None = Field(description="Last computed state, stale or not.")
    since: datetime | None
    evaluated_at: datetime | None = Field(description="Sample slot of the last evaluation.")
    stale: bool
    stale_reason: str | None

    @classmethod
    def of(cls, view: HealthView) -> HealthOut:
        return cls(
            state=view.state,
            evaluated_state=view.evaluated_state,
            since=view.since,
            evaluated_at=view.evaluated_at,
            stale=view.stale,
            stale_reason=view.stale_reason,
        )


class StateCountsOut(BaseModel):
    healthy: int
    warning: int
    unknown: int
    critical: int


class PlatformHealthOut(HealthOut):
    counts: StateCountsOut = Field(description="Components per evaluated state.")
    priority: int | None = Field(description="Line of the ADR 0004 aggregation table applied.")
    rationale: str
    decided_by: list[ComponentRefOut] = Field(description="Components behind the state.")


class PlatformOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    environment: Simulation = "simulation"
    health: PlatformHealthOut


class PlatformListOut(BaseModel):
    items: list[PlatformOut]


class EvidenceOut(BaseModel):
    sample_ids: list[int] = Field(description="Stored metric samples (GET /metrics points).")
    log_ids: list[int] = Field(description="Stored log events (GET /logs items).")

    @classmethod
    def of(cls, evidence: Evidence) -> EvidenceOut:
        return cls(sample_ids=list(evidence.sample_ids), log_ids=list(evidence.log_ids))


class RuleRefOut(BaseModel):
    id: uuid.UUID
    key: str
    version: int


class EvaluationOut(BaseModel):
    id: int
    rule: RuleRefOut
    component: ComponentRefOut
    evaluated_at: datetime
    window_start: datetime = Field(description="Exclusive start; the window ends at evaluated_at.")
    observed_value: float | None
    unit: str | None
    sample_count: int
    raw_state: HealthState = Field(description="State of the value alone, before hysteresis.")
    state: HealthState = Field(description="Debounced rule state after this evaluation.")
    explanation: str
    evidence: EvidenceOut


class ComponentOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    type: ComponentType
    criticality: Criticality
    platform_id: uuid.UUID
    environment: Simulation = "simulation"
    health: HealthOut
    reason: EvaluationOut | None = Field(
        description="Evaluation that set the worst rule state (earliest first); none if Healthy."
    )
    impacted_by: list[ComponentRefOut] = Field(
        description="Upstream components Critical or Unknown; an annotation, not a state (D-06)."
    )


class ComponentListOut(BaseModel):
    items: list[ComponentOut]


class DependencyOut(BaseModel):
    component: ComponentRefOut
    kind: DependencyKind


class ComponentDetailOut(ComponentOut):
    upstream: list[DependencyOut] = Field(description="Direct dependencies: data comes from them.")
    downstream: list[DependencyOut] = Field(description="Direct dependents: data goes to them.")


class TopologyNodeOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    type: ComponentType
    criticality: Criticality
    health: HealthOut
    impacted_by: list[uuid.UUID]


class TopologyEdgeOut(BaseModel):
    dependent_id: uuid.UUID = Field(description="Depends on dependency_id.")
    dependency_id: uuid.UUID = Field(description="Data flows from it to dependent_id.")
    kind: DependencyKind


class TopologyOut(BaseModel):
    environment: Simulation = "simulation"
    platform_id: uuid.UUID
    health: PlatformHealthOut
    nodes: list[TopologyNodeOut]
    edges: list[TopologyEdgeOut]


class LevelOut(BaseModel):
    threshold: float = Field(description="Raises when `value <operator> threshold` holds.")
    clear: float = Field(description="Clears once `value <operator> clear` no longer holds.")


class HealthRuleOut(BaseModel):
    id: uuid.UUID
    key: str
    version: int
    rule_type: RuleType
    failure_class: FailureClass
    metric_name: str | None = Field(description="None for absence rules: any observation counts.")
    unit: str | None
    aggregation: Aggregation | None
    operator: Operator | None
    warning: LevelOut | None
    critical: LevelOut | None
    window_seconds: int
    raise_after: int = Field(description="Consecutive evaluations to enter a worse state.")
    clear_after: int = Field(description="Consecutive evaluations to return to a better state.")
    min_samples: int
    target_types: list[ComponentType] = Field(description="Empty with target_components: all.")
    target_components: list[str]
    rationale: str
    recommendation: str
    enabled: bool
    created_at: datetime


class HealthRuleListOut(BaseModel):
    items: list[HealthRuleOut]


class DebounceOut(BaseModel):
    pending_state: HealthState
    streak: int
    required: int


class RuleStatusOut(BaseModel):
    rule: HealthRuleOut
    health: HealthOut = Field(description="Debounced rule state; Unknown once stale.")
    debounce: DebounceOut | None = Field(description="Transition in progress, if any.")
    evaluated_at: datetime
    window_start: datetime
    raw_state: HealthState
    observed_value: float | None
    sample_count: int
    explanation: str
    evidence: EvidenceOut
    last_evaluation_id: int = Field(description="Latest stored evaluation of this rule.")
    state_evaluation_id: int = Field(description="Stored evaluation that set the current state.")


class ComponentRulesOut(BaseModel):
    environment: Simulation = "simulation"
    component: ComponentRefOut
    health: HealthOut
    rules: list[RuleStatusOut]


class EvaluationPageOut(BaseModel):
    environment: Simulation = "simulation"
    items: list[EvaluationOut]
    next_cursor: str | None


class ComponentFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform_id: uuid.UUID | None = None
    state: HealthState | None = Field(default=None, description="Matches the state to act on.")
    type: ComponentType | None = None
    criticality: Criticality | None = None


class RuleListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    all_versions: bool = Field(default=False, description="Every stored version, disabled too.")


class EvaluationParams(WindowParams):
    component_id: uuid.UUID | None = None
    rule_key: str | None = Field(default=None, pattern=RULE_KEY_PATTERN)
    state: HealthState | None = None
    cursor: str | None = Field(
        default=None,
        max_length=MAX_CURSOR_CHARS,
        description="From next_cursor; it keeps the first page's window, `from`/`to` are ignored.",
    )
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


def health_queries(request: Request) -> HealthQueries:
    service: HealthQueries = request.app.state.health
    return service


def read_context(
    request: Request, simulation: Annotated[SimulationService, Depends(simulation_service)]
) -> ReadContext:
    clock = simulation.clock()
    cycle_interval_s: float = request.app.state.cycle_interval_s
    manual = clock.state.mode is ClockMode.MANUAL
    return ReadContext(
        clock.platform_time, evaluation_max_age(manual, clock.state.speed, cycle_interval_s)
    )


Queries = Annotated[HealthQueries, Depends(health_queries)]
Context = Annotated[ReadContext, Depends(read_context)]


@router.get("/platforms", summary="Platforms with their aggregated state and its rationale.")
def list_platforms(service: Queries, context: Context) -> PlatformListOut:
    return PlatformListOut(items=[_platform_out(v) for v in service.platforms(context)])


@router.get(
    "/platforms/{platform_id}/topology",
    summary="Components with state and impact, and dependency edges with explicit direction.",
)
def platform_topology(platform_id: uuid.UUID, service: Queries, context: Context) -> TopologyOut:
    view = service.topology(platform_id, context)
    return TopologyOut(
        platform_id=platform_id,
        health=_platform_health_out(view.platform),
        nodes=[
            TopologyNodeOut(
                id=v.component.id,
                key=v.component.key,
                name=v.component.name,
                type=v.component.type,
                criticality=v.component.criticality,
                health=HealthOut.of(v.health),
                impacted_by=[r.id for r in v.impacted_by],
            )
            for v in view.components
        ],
        edges=[
            TopologyEdgeOut(dependent_id=d.dependent_id, dependency_id=d.dependency_id, kind=d.kind)
            for d in view.platform.topology.dependencies
        ],
    )


@router.get("/components", summary="Components with their current state, filterable.")
def list_components(
    service: Queries, context: Context, params: Annotated[ComponentFilter, Query()]
) -> ComponentListOut:
    views = service.components(params.platform_id, context)
    return ComponentListOut(
        items=[
            _component_out(v)
            for v in views
            if (params.state is None or v.health.state is params.state)
            and (params.type is None or v.component.type is params.type)
            and (params.criticality is None or v.component.criticality is params.criticality)
        ]
    )


@router.get(
    "/components/{component_id}",
    summary="Component details, direct dependencies both ways, current state and impact.",
)
def component_detail(
    component_id: uuid.UUID, service: Queries, context: Context
) -> ComponentDetailOut:
    view, topology = service.component(component_id, context)
    base = _component_out(view)
    keys = topology.keys_by_id()
    return ComponentDetailOut(
        **base.model_dump(),
        upstream=[
            DependencyOut(component=_ref(d.dependency_id, keys), kind=d.kind)
            for d in topology.dependencies
            if d.dependent_id == component_id
        ],
        downstream=[
            DependencyOut(component=_ref(d.dependent_id, keys), kind=d.kind)
            for d in topology.dependencies
            if d.dependency_id == component_id
        ],
    )


@router.get(
    "/components/{component_id}/health",
    summary="Latest evaluation of every applicable rule, with threshold, value and evidence.",
)
def component_health(
    component_id: uuid.UUID, service: Queries, context: Context
) -> ComponentRulesOut:
    view, statuses = service.component_rules(component_id, context)
    return ComponentRulesOut(
        component=ComponentRefOut(id=view.component.id, key=view.component.key),
        health=HealthOut.of(view.health),
        rules=[_rule_status_out(s) for s in statuses],
    )


@router.get("/health-rules", summary="Health rules, read-only: active versions by default.")
def list_health_rules(
    service: Queries, params: Annotated[RuleListParams, Query()]
) -> HealthRuleListOut:
    return HealthRuleListOut(items=[_rule_out(r) for r in service.rules(params.all_versions)])


@router.get("/rule-evaluations", summary="Stored rule evaluations, newest first.")
def list_rule_evaluations(
    service: Queries, context: Context, params: Annotated[EvaluationParams, Query()]
) -> EvaluationPageOut:
    if params.cursor is None:
        window, before = window_of(params, context.platform_now), None
    else:
        window, before = _decode_cursor(params.cursor)
    query = EvaluationFilter(
        start=window.start,
        end=window.end,
        component_id=params.component_id,
        rule_key=params.rule_key,
        state=params.state,
        before=before,
        limit=params.limit + 1,
    )
    found = service.evaluations(query)
    page, more = found[: params.limit], len(found) > params.limit
    keys = service.component_keys()
    return EvaluationPageOut(
        items=[_evaluation_out(e, keys[e.component_id]) for e in page],
        next_cursor=_encode_cursor(page[-1], window) if more else None,
    )


def _platform_health_out(view: PlatformHealthView) -> PlatformHealthOut:
    return PlatformHealthOut(
        **HealthOut.of(view.health).model_dump(),
        counts=StateCountsOut(**{s.value: n for s, n in view.counts.items()}),
        priority=view.priority,
        rationale=view.rationale,
        decided_by=[ComponentRefOut.of(r) for r in view.decided_by],
    )


def _platform_out(view: PlatformHealthView) -> PlatformOut:
    topology: PlatformTopology = view.topology
    return PlatformOut(
        id=topology.platform_id,
        key=topology.key,
        name=topology.name,
        health=_platform_health_out(view),
    )


def _component_out(view: ComponentHealthView) -> ComponentOut:
    c = view.component
    reason = view.reason
    return ComponentOut(
        id=c.id,
        key=c.key,
        name=c.name,
        type=c.type,
        criticality=c.criticality,
        platform_id=view.platform_id,
        health=HealthOut.of(view.health),
        reason=None if reason is None else _evaluation_out(reason, c.key),
        impacted_by=[ComponentRefOut.of(r) for r in view.impacted_by],
    )


def _ref(component_id: uuid.UUID, keys: dict[uuid.UUID, str]) -> ComponentRefOut:
    return ComponentRefOut(id=component_id, key=keys[component_id])


def _level_out(level: Level | None) -> LevelOut | None:
    return None if level is None else LevelOut(threshold=level.threshold, clear=level.clear)


def _rule_out(rule: HealthRule) -> HealthRuleOut:
    d, m = rule.definition, rule.definition.measure
    return HealthRuleOut(
        id=rule.id,
        key=rule.key,
        version=rule.version,
        rule_type=d.rule_type,
        failure_class=d.failure_class,
        metric_name=None if m is None else m.metric_name,
        unit=rule.unit,
        aggregation=None if m is None else m.aggregation,
        operator=None if m is None else m.operator,
        warning=None if m is None else _level_out(m.warning),
        critical=None if m is None else _level_out(m.critical),
        window_seconds=d.window_seconds,
        raise_after=d.raise_after,
        clear_after=d.clear_after,
        min_samples=d.min_samples,
        target_types=sorted(d.targets.component_types),
        target_components=sorted(d.targets.component_keys),
        rationale=d.rationale,
        recommendation=d.recommendation,
        enabled=d.enabled,
        created_at=rule.created_at,
    )


def _rule_status_out(view: RuleStatusView) -> RuleStatusOut:
    s = view.state
    progress, m = s.progress, s.measurement
    debounce = None
    if progress.pending is not None and view.required_streak is not None:
        debounce = DebounceOut(
            pending_state=progress.pending, streak=progress.streak, required=view.required_streak
        )
    return RuleStatusOut(
        rule=_rule_out(s.rule),
        health=HealthOut.of(view.health),
        debounce=debounce,
        evaluated_at=s.evaluated_at,
        window_start=s.evaluated_at - timedelta(seconds=s.rule.definition.window_seconds),
        **_measurement_fields(m),
        last_evaluation_id=s.last_evaluation_id,
        state_evaluation_id=s.state_evaluation_id,
    )


def _measurement_fields(m: Measurement) -> dict[str, object]:
    return {
        "raw_state": m.raw_state,
        "observed_value": m.observed_value,
        "sample_count": m.sample_count,
        "explanation": m.explanation,
        "evidence": EvidenceOut.of(m.evidence),
    }


def _evaluation_out(e: StoredEvaluation, component_key: str) -> EvaluationOut:
    return EvaluationOut(
        id=e.id,
        rule=RuleRefOut(id=e.rule.id, key=e.rule.key, version=e.rule.version),
        component=ComponentRefOut(id=e.component_id, key=component_key),
        evaluated_at=e.evaluated_at,
        window_start=e.window_start,
        unit=e.rule.unit,
        state=e.state,
        **_measurement_fields(e.measurement),
    )


def _encode_cursor(e: StoredEvaluation, window: TimeWindow) -> str:
    return encode_cursor(
        "evaluation",
        encode_instant(e.evaluated_at),
        str(e.id),
        encode_instant(window.start),
        encode_instant(window.end),
    )


def _decode_cursor(cursor: str) -> tuple[TimeWindow, EvaluationPosition]:
    at, identifier, start, end = decode_cursor("evaluation", cursor, 4)
    position = EvaluationPosition(cursor_instant(at), cursor_integer(identifier, minimum=1))
    return TimeWindow(cursor_instant(start), cursor_instant(end)), position
