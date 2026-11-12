import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.simulation.domain.catalog import (
    CATALOG,
    SCENARIOS,
    ScenarioDefinition,
    ScenarioKey,
    ScenarioKind,
)
from app.simulation.domain.errors import (
    ScenarioNotStartableError,
    ScenarioParameterError,
    ScenarioTargetError,
)
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.domain.runs import RunPlan, StartRequest, plan_run
from app.topology.domain import Component, ComponentType, Criticality

NOW = datetime(2026, 11, 12, 10, 0, tzinfo=UTC)


def component(kind: ComponentType, key: str = "target-01") -> Component:
    return Component(uuid.uuid4(), key, key, kind, Criticality.HIGH)


def plan(
    scenario: ScenarioKey,
    target: Component | None,
    parameters: dict[str, float] | None = None,
    duration_s: int | None = None,
) -> RunPlan:
    request = StartRequest(SCENARIOS[scenario], target, parameters or {}, duration_s)
    return plan_run(request, NOW, 42, "dev-local")


def test_catalog_covers_the_nine_documented_scenarios() -> None:
    assert [d.key for d in CATALOG] == list(ScenarioKey)
    assert [d.key for d in CATALOG if d.kind is ScenarioKind.BASELINE] == [ScenarioKey.BASELINE]


@pytest.mark.parametrize("definition", [d for d in CATALOG if d.kind is ScenarioKind.FAULT])
def test_default_target_exists_and_is_eligible(definition: ScenarioDefinition) -> None:
    assert definition.default_target is not None
    simulated = SIMULATED_PLATFORM.component(definition.default_target)
    assert simulated is not None
    assert simulated.spec.type in definition.eligible_types


def test_parameter_defaults_are_inside_their_bounds() -> None:
    for definition in CATALOG:
        for p in definition.parameters:
            assert p.minimum <= p.default <= p.maximum, (definition.key, p.name)


def test_baseline_cannot_be_started() -> None:
    with pytest.raises(ScenarioNotStartableError):
        plan(ScenarioKey.BASELINE, None)


def test_ineligible_target_type_is_rejected() -> None:
    with pytest.raises(ScenarioTargetError, match="collector"):
        plan(ScenarioKey.COLLECTOR_DOWN, component(ComponentType.DATABASE))


def test_unknown_parameter_is_rejected() -> None:
    with pytest.raises(ScenarioParameterError, match="peak"):
        plan(ScenarioKey.STALE_DATA, component(ComponentType.HISTORIAN), {"peak_ms": 2.0})


def test_out_of_range_parameter_is_rejected() -> None:
    with pytest.raises(ScenarioParameterError, match="loss_ratio"):
        plan(ScenarioKey.INTERMITTENT_LOSS, component(ComponentType.GATEWAY), {"loss_ratio": 0.9})


@pytest.mark.parametrize("duration_s", [5, 8 * 24 * 3600])
def test_out_of_range_duration_is_rejected(duration_s: int) -> None:
    with pytest.raises(ScenarioParameterError, match="duration_s"):
        plan(ScenarioKey.STALE_DATA, component(ComponentType.HISTORIAN), duration_s=duration_s)


def test_plan_resolves_defaults_and_planned_end() -> None:
    target = component(ComponentType.GATEWAY)
    request = StartRequest(SCENARIOS[ScenarioKey.LATENCY_RISE], target, {"peak_ms": 2000}, 600)

    planned = plan_run(request, NOW, 42, "dev-local")

    assert dict(planned.parameters) == {"peak_ms": 2000.0, "ramp_s": 300.0}
    assert planned.ends_at == NOW + timedelta(seconds=600)
    assert planned.target == target
    assert planned.seed == 42
