"""What one rule concludes from one window of observations, before hysteresis (rules.md P-07).

Windows are (evaluated_at - window, evaluated_at]: a rule evaluated at a sample slot sees the
sample of that slot, and window / 5 s samples in all.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from app.core.observation import Quality
from app.health.domain.rules import Aggregation, HealthRule, Measure
from app.health.domain.states import HealthState
from app.ingestion.domain.observations import ObservationMark, StoredSample

# rule_evaluation.evidence holds at most this many observation IDs (architecture §03.1).
MAX_EVIDENCE = 50
P95 = 0.95
_UNITLESS = frozenset({"bool", "count"})


@dataclass(frozen=True, slots=True)
class Evidence:
    sample_ids: tuple[int, ...] = ()
    log_ids: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class Measurement:
    raw_state: HealthState
    observed_value: float | None
    sample_count: int
    evidence: Evidence
    explanation: str


def measure(
    rule: HealthRule, measure_spec: Measure, samples: Sequence[StoredSample]
) -> Measurement:
    """Raw state of a measured rule over the window's samples, in observed_at order."""
    definition = rule.definition
    # D-16: a bad-quality sample proves nothing, healthy or not.
    usable = [s for s in samples if s.quality is not Quality.BAD]
    ignored = len(samples) - len(usable)
    if len(usable) < definition.min_samples:
        explanation = (
            f"{len(usable)} usable {measure_spec.metric_name} samples in the last "
            f"{definition.window_seconds} s, {definition.min_samples} required{_ignored(ignored)}."
        )
        return Measurement(HealthState.UNKNOWN, None, len(usable), Evidence(), explanation)
    value = aggregate(measure_spec.aggregation, [s.value for s in usable])
    raw = raw_level(measure_spec, value)
    return Measurement(
        raw,
        value,
        len(usable),
        Evidence(sample_ids=_evidence(measure_spec, usable)),
        _described(rule, measure_spec, value, len(usable), raw) + f"{_ignored(ignored)}.",
    )


def measure_absence(
    rule: HealthRule, marks: Sequence[ObservationMark], evaluated_at: datetime
) -> Measurement:
    """Healthy while the component was observed in the window, Unknown otherwise (ADR 0003).

    The observed value is the age of the newest observation, in seconds.
    """
    window = rule.definition.window_seconds
    if not marks:
        return Measurement(
            HealthState.UNKNOWN, None, 0, Evidence(), f"No observation in the last {window} s."
        )
    newest = marks[-1]
    age = (evaluated_at - newest.observed_at).total_seconds()
    evidence = Evidence(
        sample_ids=() if newest.sample_id is None else (newest.sample_id,),
        log_ids=() if newest.log_id is None else (newest.log_id,),
    )
    explanation = f"Last observation {_number(age)} s before evaluation, within {window} s."
    return Measurement(HealthState.HEALTHY, age, len(marks), evidence, explanation)


def aggregate(aggregation: Aggregation, values: Sequence[float]) -> float:
    """Values in observed_at order; never empty."""
    if aggregation is Aggregation.LAST:
        return values[-1]
    if aggregation is Aggregation.MAX:
        return max(values)
    if aggregation is Aggregation.SUM:
        return math.fsum(values)
    if aggregation is Aggregation.P95:
        # Nearest-rank percentile: always an observed value, never an interpolation.
        ordered = sorted(values)
        return ordered[math.ceil(P95 * len(ordered)) - 1]
    # AVG, and RATIO: the mean of 0/1 probe results is the share of answered probes.
    return math.fsum(values) / len(values)


def raw_level(measure_spec: Measure, value: float) -> HealthState:
    """State the value alone reaches against the raise thresholds."""
    breaches = measure_spec.operator.breaches
    if measure_spec.critical and breaches(value, measure_spec.critical.threshold):
        return HealthState.CRITICAL
    if measure_spec.warning and breaches(value, measure_spec.warning.threshold):
        return HealthState.WARNING
    return HealthState.HEALTHY


def held_level(measure_spec: Measure, value: float) -> HealthState:
    """Lowest state the value still holds against the clear thresholds."""
    breaches = measure_spec.operator.breaches
    if measure_spec.critical and breaches(value, measure_spec.critical.clear):
        return HealthState.CRITICAL
    if measure_spec.warning and breaches(value, measure_spec.warning.clear):
        return HealthState.WARNING
    return HealthState.HEALTHY


def _evidence(measure_spec: Measure, usable: Sequence[StoredSample]) -> tuple[int, ...]:
    """The samples that drive the value: the last one, or the worst first, up to MAX_EVIDENCE."""
    if measure_spec.aggregation is Aggregation.LAST:
        return (usable[-1].id,)
    sign = -1 if measure_spec.operator.upward else 1
    ranked = sorted(usable, key=lambda s: (sign * s.value, -s.observed_at.timestamp()))
    return tuple(sorted(s.id for s in ranked[:MAX_EVIDENCE]))


def _described(
    rule: HealthRule, measure_spec: Measure, value: float, count: int, raw: HealthState
) -> str:
    unit, symbol = rule.unit, measure_spec.operator.symbol
    measured = (
        f"{measure_spec.aggregation} of {measure_spec.metric_name} over "
        f"{rule.definition.window_seconds} s = {_quantity(value, unit)} from {count} samples"
    )
    breached = {
        HealthState.CRITICAL: measure_spec.critical,
        HealthState.WARNING: measure_spec.warning,
    }.get(raw)
    if breached is None:
        limit = _quantity(measure_spec.lowest.threshold, unit)
        return f"{measured}: no threshold breached ({symbol} {limit})"
    return f"{measured}: {raw} threshold breached ({symbol} {_quantity(breached.threshold, unit)})"


def _ignored(ignored: int) -> str:
    return f"; {ignored} bad-quality samples ignored" if ignored else ""


def _quantity(value: float, unit: str | None) -> str:
    return _number(value) if unit is None or unit in _UNITLESS else f"{_number(value)} {unit}"


def _number(value: float) -> str:
    return f"{round(value, 3):g}"
