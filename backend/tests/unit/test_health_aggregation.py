import uuid
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.health.domain.aggregation import (
    RuleStanding,
    component_verdict,
    impacted_by,
    platform_verdict,
)
from app.health.domain.engine import Standing
from app.health.domain.freshness import ReadContext, evaluation_max_age, health_view
from app.health.domain.states import HealthState
from app.topology.domain import Component, ComponentType, Criticality, Dependency, DependencyKind
from tests.health_rules import T0

H, W, C, U = HealthState.HEALTHY, HealthState.WARNING, HealthState.CRITICAL, HealthState.UNKNOWN
HIGH, MEDIUM, LOW = Criticality.HIGH, Criticality.MEDIUM, Criticality.LOW


def component(key: str, criticality: Criticality = HIGH) -> Component:
    return Component(uuid.uuid4(), key, key, ComponentType.COLLECTOR, criticality)


def test_severity_order_puts_unknown_between_warning_and_critical() -> None:
    assert sorted(HealthState, key=lambda s: s.severity) == [H, W, U, C]


def test_component_is_its_worst_rule_named_by_the_first_to_enter_it() -> None:
    standings = [
        RuleStanding("R-LAT-001", C, T0 + timedelta(seconds=30)),
        RuleStanding("R-AVAIL-001", C, T0 + timedelta(seconds=10)),
        RuleStanding("R-TEL-001", U, T0),
    ]

    verdict = component_verdict(standings)

    assert (verdict.state, verdict.deciding_rule) == (C, "R-AVAIL-001")


def test_component_without_rules_is_unknown_and_healthy_has_no_deciding_rule() -> None:
    assert component_verdict([]).state is U
    healthy = component_verdict([RuleStanding("R-TEL-001", H, T0)])
    assert (healthy.state, healthy.deciding_rule) == (H, None)


@pytest.mark.parametrize(
    ("states", "expected", "priority"),
    [
        ([(HIGH, C), (LOW, H)], C, 1),
        ([(MEDIUM, C), (HIGH, U)], C, 1),
        ([(HIGH, U), (LOW, C)], U, 2),
        ([(LOW, C), (HIGH, H)], W, 3),
        ([(MEDIUM, U), (HIGH, H)], W, 3),
        ([(LOW, U), (HIGH, H)], W, 3),
        ([(HIGH, W), (HIGH, H)], W, 3),
        ([(HIGH, H), (LOW, H)], H, 4),
    ],
)
def test_platform_follows_the_adr_0004_priority_table(
    states: list[tuple[Criticality, HealthState]], expected: HealthState, priority: int
) -> None:
    components = [component(f"c-{i}", crit) for i, (crit, _) in enumerate(states)]

    verdict = platform_verdict(
        components, {c.id: s for c, (_, s) in zip(components, states, strict=True)}
    )

    assert (verdict.state, verdict.priority) == (expected, priority)
    assert verdict.rationale.startswith(f"Priority {priority}: ")


def test_platform_counts_components_without_state_as_unknown() -> None:
    a, b = component("a"), component("b", LOW)

    verdict = platform_verdict([a, b], {b.id: H})

    assert (verdict.state, verdict.counts[U], verdict.decided_by) == (U, 1, (a.id,))


STATES = st.sampled_from(list(HealthState))
CRITICALITIES = st.sampled_from(list(Criticality))


@given(st.lists(st.tuples(CRITICALITIES, STATES), min_size=1, max_size=12))
def test_platform_is_never_milder_than_a_major_component_failure(
    states: list[tuple[Criticality, HealthState]],
) -> None:
    components = [component(f"c-{i}", crit) for i, (crit, _) in enumerate(states)]
    verdict = platform_verdict(
        components, {c.id: s for c, (_, s) in zip(components, states, strict=True)}
    )

    if any(s is C and crit is not LOW for crit, s in states):
        assert verdict.state is C
    if verdict.state is H:
        assert all(s is H for _, s in states)
    assert sum(verdict.counts.values()) == len(states)


def test_impact_is_the_transitive_upstream_failure_and_never_a_state() -> None:
    source, gateway, collector, api = (component(k) for k in ("source", "gw", "col", "api"))
    edges = [
        Dependency(gateway.id, source.id, DependencyKind.DATA_FLOW),
        Dependency(collector.id, gateway.id, DependencyKind.DATA_FLOW),
        Dependency(api.id, collector.id, DependencyKind.DATA_FLOW),
    ]
    states = {source.id: H, gateway.id: C, collector.id: U, api.id: H}

    impact = impacted_by(states, edges)

    assert impact[api.id] == tuple(sorted((gateway.id, collector.id)))
    assert impact[collector.id] == (gateway.id,)
    assert impact[gateway.id] == ()
    assert states[api.id] is H


def test_stored_state_is_reported_unknown_once_evaluations_stop() -> None:
    standing = Standing(H, T0)
    max_age = evaluation_max_age(manual=False, speed=1.0, cycle_interval_s=5.0)
    assert max_age == timedelta(seconds=20)

    fresh = health_view(standing, T0, ReadContext(T0 + timedelta(seconds=20), max_age))
    stale = health_view(standing, T0, ReadContext(T0 + timedelta(seconds=21), max_age))
    never = health_view(None, None, ReadContext(T0, max_age))

    assert (fresh.state, fresh.stale) == (H, False)
    assert (stale.state, stale.evaluated_state, stale.stale) == (U, H, True)
    assert (never.state, never.stale) == (U, True)


def test_staleness_scales_with_clock_speed_and_is_off_in_manual_mode() -> None:
    assert evaluation_max_age(manual=False, speed=60.0, cycle_interval_s=5.0) == timedelta(
        seconds=905
    )
    assert evaluation_max_age(manual=True, speed=1.0, cycle_interval_s=5.0) is None
