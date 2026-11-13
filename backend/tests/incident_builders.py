"""Builders of health outcomes and incident plans for incident domain tests."""

import itertools
import uuid
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from app.core.observation import ObservationSource
from app.health.domain.evaluation import Evidence
from app.health.domain.records import EvaluationOutcome, RuleCondition
from app.health.domain.rules import (
    Aggregation,
    FailureClass,
    HealthRule,
    Level,
    Measure,
    Operator,
    RuleType,
)
from app.health.domain.states import HealthState
from app.incidents.domain.engine import IncidentPass, IncidentPlan, process
from app.incidents.domain.model import Incident
from app.topology.domain import (
    Component,
    ComponentType,
    Criticality,
    Dependency,
    DependencyKind,
    PlatformTopology,
)
from tests.health_rules import T0, absence_rule, availability_rule, latency_rule

H, W, C, U = HealthState.HEALTHY, HealthState.WARNING, HealthState.CRITICAL, HealthState.UNKNOWN
PLATFORM_ID = uuid.uuid4()
COLLECTOR = Component(
    uuid.uuid4(), "collector-01", "Collector", ComponentType.COLLECTOR, Criticality.HIGH
)
HISTORIAN = Component(
    uuid.uuid4(), "historian-01", "Historian", ComponentType.HISTORIAN, Criticality.HIGH
)
TOPOLOGY = PlatformTopology(
    PLATFORM_ID,
    "plant",
    "Plant",
    "simulation",
    (COLLECTOR, HISTORIAN),
    (Dependency(HISTORIAN.id, COLLECTOR.id, DependencyKind.DATA_FLOW),),
)
AVAIL = availability_rule()
LATENCY = latency_rule()
TELEMETRY = absence_rule()
_ratio = availability_rule().definition
CONN = HealthRule(
    uuid.uuid4(),
    "R-CONN-001",
    1,
    replace(
        _ratio,
        rule_type=RuleType.AVAILABILITY_RATIO,
        failure_class=FailureClass.CONNECTIVITY,
        measure=Measure("up", Aggregation.RATIO, Operator.LT, Level(0.95, 0.98), Level(0.8, 0.9)),
        window_seconds=300,
        raise_after=1,
    ),
    "ratio",
    T0,
)
FRESH = HealthRule(
    uuid.uuid4(),
    "R-FRESH-001",
    1,
    replace(LATENCY.definition, failure_class=FailureClass.FRESHNESS),
    "s",
    T0,
)
RULES = (AVAIL, CONN, LATENCY, FRESH, TELEMETRY)
_ids = itertools.count(1)


def outcome(
    component: Component,
    rule: HealthRule,
    at: datetime,
    state: HealthState,
    raw: HealthState | None = None,
) -> EvaluationOutcome:
    sample = next(_ids)
    return EvaluationOutcome(
        id=next(_ids),
        component_id=component.id,
        rule=rule,
        evaluated_at=at,
        state=state,
        raw_state=state if raw is None else raw,
        sets_state=True,
        evidence=Evidence(sample_ids=(sample,)),
    )


def periodic(o: EvaluationOutcome) -> EvaluationOutcome:
    """The once-a-minute evaluation of an unchanged state."""
    return replace(o, sets_state=False)


def run(
    outcomes: Sequence[EvaluationOutcome],
    active: Sequence[Incident] = (),
    reopenable: Sequence[Incident] = (),
    before: dict[tuple[uuid.UUID, str], RuleCondition] | None = None,
) -> IncidentPass:
    return process(
        IncidentPlan(
            topology=TOPOLOGY,
            rules=RULES,
            before=before or {},
            outcomes=outcomes,
            active=active,
            reopenable=reopenable,
            impacted={},
            source=ObservationSource.SIMULATION,
            new_id=uuid.uuid7,
        )
    )


def final(result: IncidentPass) -> list[Incident]:
    return [*result.opened, *result.changed]
