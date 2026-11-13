from datetime import timedelta

import pytest

from app.core.observation import Quality
from app.health.domain.evaluation import (
    MAX_EVIDENCE,
    aggregate,
    held_level,
    measure,
    measure_absence,
    raw_level,
)
from app.health.domain.rules import Aggregation, Level, Measure, Operator
from app.health.domain.states import HealthState
from app.ingestion.domain.observations import ObservationMark
from tests.health_rules import SLOT, T0, absence_rule, latency_rule, sample

H, W, C, U = HealthState.HEALTHY, HealthState.WARNING, HealthState.CRITICAL, HealthState.UNKNOWN
LATENCY = Measure(
    "probe_latency_ms", Aggregation.P95, Operator.GT, Level(250, 200), Level(1000, 800)
)
RATIO = Measure("up", Aggregation.RATIO, Operator.LT, Level(0.95, 0.98), Level(0.80, 0.90))
ERRORS = Measure("error_count", Aggregation.SUM, Operator.GE, Level(5, 2), Level(20, 5))


@pytest.mark.parametrize(
    ("aggregation", "values", "expected"),
    [
        (Aggregation.LAST, [3, 1, 2], 2),
        (Aggregation.AVG, [1, 2, 6], 3),
        (Aggregation.MAX, [3, 9, 2], 9),
        (Aggregation.SUM, [1, 2, 3], 6),
        (Aggregation.RATIO, [1, 0, 1, 1], 0.75),
        # Nearest rank: the 95th percentile of 20 values is the 19th smallest, never interpolated.
        (Aggregation.P95, list(range(1, 21)), 19),
        (Aggregation.P95, [10, 2000, 30], 2000),
        (Aggregation.P95, [7], 7),
    ],
)
def test_aggregations_reduce_the_window_values(
    aggregation: Aggregation, values: list[float], expected: float
) -> None:
    assert aggregate(aggregation, values) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("spec", "value", "raw", "held"),
    [
        (LATENCY, 100, H, H),
        (LATENCY, 220, H, W),  # inside the warning deadband
        (LATENCY, 251, W, W),
        (LATENCY, 900, W, C),  # inside the critical deadband
        (LATENCY, 1001, C, C),
        (LATENCY, 250, H, W),  # strictly greater raises
        (RATIO, 0.99, H, H),
        (RATIO, 0.96, H, W),
        (RATIO, 0.94, W, W),
        (RATIO, 0.85, W, C),
        (RATIO, 0.79, C, C),
        (ERRORS, 5, W, C),  # ge: the threshold raises, and critical clears below 5 only
        (ERRORS, 4, H, W),
        (ERRORS, 1, H, H),
        (ERRORS, 20, C, C),
    ],
)
def test_raise_and_clear_thresholds_per_operator(
    spec: Measure, value: float, raw: HealthState, held: HealthState
) -> None:
    assert (raw_level(spec, value), held_level(spec, value)) == (raw, held)


def test_measurement_explains_value_threshold_and_cites_samples() -> None:
    rule = latency_rule()
    samples = [sample(v, T0 + i * SLOT) for i, v in enumerate([40, 1200, 60])]

    result = measure(rule, LATENCY, samples)

    assert (result.raw_state, result.observed_value, result.sample_count) == (C, 1200, 3)
    assert set(result.evidence.sample_ids) == {s.id for s in samples}
    assert result.explanation == (
        "p95 of probe_latency_ms over 60 s = 1200 ms from 3 samples: "
        "critical threshold breached (> 1000 ms)."
    )


def test_bad_quality_samples_never_count_as_evidence() -> None:
    rule = latency_rule()
    samples = [sample(40, quality=Quality.BAD), sample(45, quality=Quality.BAD)]

    result = measure(rule, LATENCY, samples)

    assert (result.raw_state, result.observed_value, result.evidence.sample_ids) == (U, None, ())
    assert "2 bad-quality samples ignored" in result.explanation


def test_window_below_min_samples_is_unknown() -> None:
    result = measure(latency_rule(min_samples=3), LATENCY, [sample(40), sample(41)])

    assert result.raw_state is U
    assert result.explanation.startswith("2 usable probe_latency_ms samples in the last 60 s")


def test_evidence_is_capped_and_keeps_the_worst_samples() -> None:
    samples = [sample(float(i), T0 + i * SLOT) for i in range(80)]

    result = measure(latency_rule(), LATENCY, samples)

    assert len(result.evidence.sample_ids) == MAX_EVIDENCE
    assert set(result.evidence.sample_ids) == {s.id for s in samples[-MAX_EVIDENCE:]}


def test_last_aggregation_cites_only_the_last_sample() -> None:
    samples = [sample(1, T0), sample(0, T0 + SLOT)]
    spec = Measure("up", Aggregation.LAST, Operator.LT, None, Level(1, 1))

    result = measure(latency_rule(), spec, samples)

    assert result.evidence.sample_ids == (samples[-1].id,)


def test_absence_rule_is_healthy_with_an_observation_and_unknown_without() -> None:
    rule = absence_rule()
    at = T0 + timedelta(seconds=15)
    mark = ObservationMark(sample(1).component_id, T0 + timedelta(seconds=10), 42, None)

    seen = measure_absence(rule, [mark], at)
    blind = measure_absence(rule, [], at)

    assert (seen.raw_state, seen.observed_value, seen.evidence.sample_ids) == (H, 5, (42,))
    assert (blind.raw_state, blind.observed_value) == (U, None)
    assert blind.explanation == "No observation in the last 15 s."
