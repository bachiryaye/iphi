"""Key metric of a component, chosen by the server for the Overview range meter (design
system §6.1): the frontend never decides which measurement represents a component."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.health.domain.freshness import HealthView
from app.health.domain.records import StoredRuleState
from app.health.domain.rules import Measure
from app.topology.domain import ComponentType

AVAILABILITY_METRIC = "up"

DEFAULT_METRIC: Mapping[ComponentType, str] = {
    ComponentType.SOURCE: "probe_latency_ms",
    ComponentType.GATEWAY: "probe_latency_ms",
    ComponentType.API: "probe_latency_ms",
    ComponentType.COLLECTOR: "queue_depth",
    ComponentType.HISTORIAN: "data_age_s",
    ComponentType.ANALYTICS: "data_age_s",
    ComponentType.DATABASE: "cpu_pct",
}

# Room above the critical threshold so an out-of-band value still reads as "past critical".
DISPLAY_HEADROOM = 1.25


class KeyMetricKind(StrEnum):
    METER = "meter"
    """Higher is worse and the thresholds frame a range: drawn as a range meter."""
    AVAILABILITY = "availability"
    """Probe result or answered ratio: shown as text (`DOWN since …`), never as a gauge."""
    VALUE = "value"
    """Lower is worse on a non-probe metric: shown as a number only."""


@dataclass(frozen=True, slots=True)
class MetricRange:
    """Bounds a metric can take (the ingestion catalog)."""

    minimum: float
    maximum: float


@dataclass(frozen=True, slots=True)
class KeyMetric:
    state: StoredRuleState
    health: HealthView
    measure: Measure
    kind: KeyMetricKind
    display_min: float
    display_max: float


def choose_key_rule(
    states: Sequence[StoredRuleState], reason_rule_key: str | None, component_type: ComponentType
) -> StoredRuleState | None:
    """The rule behind the component's worst state when it measures a metric; otherwise the
    rule on the type's default metric. Absence rules measure nothing and are skipped."""
    measured = [s for s in states if s.rule.definition.measure is not None]
    if reason_rule_key is not None:
        reason = next((s for s in measured if s.rule.key == reason_rule_key), None)
        if reason is not None:
            return reason
    default = DEFAULT_METRIC[component_type]
    return next((s for s in sorted(measured, key=_rule_key) if _metric(s) == default), None)


def key_metric(
    state: StoredRuleState, health: HealthView, metric_range: MetricRange | None
) -> KeyMetric:
    measure = state.rule.definition.measure
    if measure is None:
        raise ValueError(f"{state.rule.key} measures no metric")
    if measure.metric_name == AVAILABILITY_METRIC:
        kind = KeyMetricKind.AVAILABILITY
    elif measure.operator.upward:
        kind = KeyMetricKind.METER
    else:
        kind = KeyMetricKind.VALUE
    top = max(level.threshold for level in measure.levels)
    minimum = 0.0 if metric_range is None else metric_range.minimum
    maximum = top * DISPLAY_HEADROOM
    if metric_range is not None:
        maximum = min(maximum, metric_range.maximum)
    return KeyMetric(state, health, measure, kind, minimum, max(maximum, top))


def _metric(state: StoredRuleState) -> str | None:
    measure = state.rule.definition.measure
    return None if measure is None else measure.metric_name


def _rule_key(state: StoredRuleState) -> str:
    return state.rule.key
