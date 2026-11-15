import uuid
from datetime import timedelta

import pytest

from app.health.domain.engine import Standing
from app.health.domain.evaluation import Evidence, Measurement
from app.health.domain.freshness import HealthView, ReadContext, health_view
from app.health.domain.hysteresis import RuleProgress
from app.health.domain.key_metric import (
    KeyMetricKind,
    MetricRange,
    choose_key_rule,
    key_metric,
)
from app.health.domain.records import StoredRuleState
from app.health.domain.rules import HealthRule
from app.health.domain.states import HealthState
from app.topology.domain import ComponentType
from tests.health_rules import T0, absence_rule, availability_rule, latency_rule

COMPONENT = uuid.uuid4()


def state(rule: HealthRule, value: float | None, current: HealthState) -> StoredRuleState:
    return StoredRuleState(
        component_id=COMPONENT,
        rule=rule,
        progress=RuleProgress(current, T0),
        measurement=Measurement(current, value, 0 if value is None else 12, Evidence(), "x"),
        evaluated_at=T0 + timedelta(seconds=30),
        last_evaluation_id=7,
        state_evaluation_id=3,
    )


def fresh(s: StoredRuleState) -> HealthView:
    context = ReadContext(s.evaluated_at, timedelta(seconds=15))
    return health_view(Standing(s.progress.state, s.progress.since), s.evaluated_at, context)


def test_reason_rule_wins_over_the_type_default() -> None:
    latency = state(latency_rule(), 42, HealthState.HEALTHY)
    down = state(availability_rule(), 0, HealthState.CRITICAL)

    chosen = choose_key_rule([latency, down], "R-AVAIL-001", ComponentType.COLLECTOR)

    assert chosen is down


def test_type_default_applies_without_a_reason() -> None:
    latency = state(latency_rule(), 42, HealthState.HEALTHY)
    down = state(availability_rule(), 1, HealthState.HEALTHY)

    assert choose_key_rule([down, latency], None, ComponentType.GATEWAY) is latency


def test_absence_reason_falls_back_to_the_type_default() -> None:
    blind = state(absence_rule(), None, HealthState.UNKNOWN)
    latency = state(latency_rule(), None, HealthState.UNKNOWN)

    assert choose_key_rule([blind, latency], "R-TEL-001", ComponentType.API) is latency


def test_no_measured_rule_means_no_key_metric() -> None:
    blind = state(absence_rule(), None, HealthState.UNKNOWN)

    assert choose_key_rule([blind], None, ComponentType.API) is None
    assert choose_key_rule([], None, ComponentType.API) is None


def test_meter_range_reaches_past_the_critical_threshold() -> None:
    latency = state(latency_rule(), 1200, HealthState.CRITICAL)

    metric = key_metric(latency, fresh(latency), MetricRange(0, 600_000))

    assert metric.kind is KeyMetricKind.METER
    assert (metric.display_min, metric.display_max) == (0, 1250)
    assert metric.health.state is HealthState.CRITICAL


def test_display_max_stays_within_the_metric_range() -> None:
    latency = state(latency_rule(), 90, HealthState.HEALTHY)

    metric = key_metric(latency, fresh(latency), MetricRange(0, 1100))

    assert metric.display_max == 1100


def test_probe_result_is_never_a_meter() -> None:
    down = state(availability_rule(), 0, HealthState.CRITICAL)

    assert key_metric(down, fresh(down), MetricRange(0, 1)).kind is KeyMetricKind.AVAILABILITY


def test_stale_rule_state_is_unknown() -> None:
    latency = state(latency_rule(), 42, HealthState.HEALTHY)
    late = ReadContext(latency.evaluated_at + timedelta(minutes=5), timedelta(seconds=15))
    view = health_view(Standing(HealthState.HEALTHY, T0), latency.evaluated_at, late)

    assert key_metric(latency, view, None).health.state is HealthState.UNKNOWN


def test_absence_rule_has_no_key_metric() -> None:
    blind = state(absence_rule(), None, HealthState.UNKNOWN)

    with pytest.raises(ValueError, match="measures no metric"):
        key_metric(blind, fresh(blind), None)
