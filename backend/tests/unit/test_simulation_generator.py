import itertools
from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.core.settings import MAX_SEED
from app.simulation.domain.catalog import ScenarioKey
from app.simulation.domain.clock import first_tick_at_or_after
from app.simulation.domain.errors import SimulationNotInitializedError
from app.simulation.domain.generator import (
    GeneratedLog,
    GeneratedSample,
    TickObservations,
    fingerprint,
    generate_range,
    generate_tick,
)
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.domain.runs import ScenarioRun
from app.simulation.domain.signals import OBSERVATION_SOURCE, LogSeverity, Metric
from tests.simulation_runs import (
    FIRST_TICK,
    GOLDEN_COLLECTOR_DOWN,
    GOLDEN_START,
    GOLDEN_TICKS,
    baseline,
    make_run,
)

LAST_TICK = FIRST_TICK + GOLDEN_TICKS - 1


def generate(runs: Sequence[ScenarioRun], ticks: int = GOLDEN_TICKS) -> list[TickObservations]:
    return generate_range(SIMULATED_PLATFORM, runs, FIRST_TICK, FIRST_TICK + ticks - 1)


def series(ticks: Sequence[TickObservations], component: str, metric: Metric) -> list[float | None]:
    """One value per tick, None when the tick has no such sample."""
    values: list[float | None] = []
    for observations in ticks:
        found = [
            s.value
            for s in observations.samples
            if s.component_key == component and s.metric is metric
        ]
        values.append(found[0] if found else None)
    return values


def samples_of(ticks: Sequence[TickObservations], component: str) -> list[GeneratedSample]:
    return [s for t in ticks for s in t.samples if s.component_key == component]


def collector_down_runs() -> list[ScenarioRun]:
    return [baseline(), make_run(ScenarioKey.COLLECTOR_DOWN, "collector-01")]


def test_golden_seed_42_collector_down_120_ticks_fingerprint_is_stable() -> None:
    assert fingerprint(generate(collector_down_runs())) == GOLDEN_COLLECTOR_DOWN


def test_two_generations_with_fresh_run_ids_have_the_same_fingerprint() -> None:
    assert fingerprint(generate(collector_down_runs())) == fingerprint(
        generate(collector_down_runs())
    )


def test_tick_generation_order_does_not_change_observations() -> None:
    runs = collector_down_runs()
    ticks = list(range(FIRST_TICK, LAST_TICK + 1))
    ticks = ticks[1::2][::-1] + ticks[::2]

    shuffled = [generate_tick(SIMULATED_PLATFORM, runs, t) for t in ticks]

    assert fingerprint(shuffled) == fingerprint(generate(runs))


def test_another_seed_changes_the_fingerprint() -> None:
    other = [baseline(seed=43), make_run(ScenarioKey.COLLECTOR_DOWN, "collector-01", seed=43)]

    assert fingerprint(generate(other)) != fingerprint(generate(collector_down_runs()))


def test_every_observation_carries_simulation_source_and_its_run() -> None:
    runs = collector_down_runs()
    run_ids = {r.id for r in runs}
    ticks = generate(runs)
    observations: list[GeneratedSample | GeneratedLog] = [s for t in ticks for s in t.samples]
    observations += [log for t in ticks for log in t.logs]

    assert observations
    assert {o.source for o in observations} == {OBSERVATION_SOURCE}
    assert {o.scenario_run_id for o in observations} <= run_ids


def test_generation_without_a_baseline_run_is_refused() -> None:
    with pytest.raises(SimulationNotInitializedError):
        generate_tick(SIMULATED_PLATFORM, [], FIRST_TICK)


def window_sums(values: Sequence[float | None], size: int) -> list[float]:
    present = [v or 0.0 for v in values]
    return [sum(present[i : i + size]) for i in range(len(present) - size + 1)]


@settings(max_examples=25, deadline=None)
@given(seed=st.integers(min_value=0, max_value=MAX_SEED))
def test_baseline_stays_inside_default_clear_thresholds_for_any_seed(seed: int) -> None:
    ticks = generate([baseline(seed)], ticks=240)

    for component in SIMULATED_PLATFORM.components:
        key = component.key
        assert set(series(ticks, key, Metric.UP)) == {1.0}
        latency = series(ticks, key, Metric.PROBE_LATENCY_MS)
        assert max(v for v in latency if v is not None) < 200
        for metric in (Metric.CPU_PCT, Metric.MEM_PCT):
            assert max(v for v in series(ticks, key, metric) if v is not None) < 75
        if component.profile.queue_depth is not None:
            assert max(v or 0 for v in series(ticks, key, Metric.QUEUE_DEPTH)) < 500
        if component.profile.data_age_s is not None:
            assert max(v or 0 for v in series(ticks, key, Metric.DATA_AGE_S)) < 30
        # R-ERR-001 raises at 5 errors per 60 s (12 samples).
        assert max(window_sums(series(ticks, key, Metric.ERROR_COUNT), 12)) < 5


def test_collector_down_reports_only_the_failed_probe() -> None:
    ticks = generate(collector_down_runs())
    collector = samples_of(ticks, "collector-01")

    assert {s.metric for s in collector} == {Metric.UP}
    assert {s.value for s in collector} == {0.0}
    assert not [log for t in ticks for log in t.logs if log.component_key == "collector-01"]


def test_collector_down_ages_downstream_process_data() -> None:
    runs = collector_down_runs()
    ticks = generate(runs)

    for component in ("historian-01", "analytics-01"):
        ages = series(ticks, component, Metric.DATA_AGE_S)
        assert ages[-1] is not None
        assert ages[-1] > 590
        assert {s.scenario_run_id for s in samples_of(ticks, component)} == {runs[1].id}
    assert {s.scenario_run_id for s in samples_of(ticks, "timeseries-db-01")} == {runs[0].id}


def test_stopping_a_run_restores_nominal_behaviour_after_its_end() -> None:
    stopped = make_run(ScenarioKey.COLLECTOR_DOWN, "collector-01", stopped_after_s=300)
    ticks = generate([baseline(), stopped])
    up = series(ticks, "collector-01", Metric.UP)

    assert set(up[:60]) == {0.0}
    assert set(up[60:]) == {1.0}


def test_latency_rise_reaches_its_peak_at_the_end_of_the_ramp() -> None:
    run = make_run(ScenarioKey.LATENCY_RISE, "edge-gateway-01", parameters={"ramp_s": 300})
    latency = series(generate([baseline(), run]), "edge-gateway-01", Metric.PROBE_LATENCY_MS)

    assert latency[0] is not None
    assert latency[0] < 100
    assert all(1400 < (v or 0) < 1600 for v in latency[60:])


def test_stale_data_keeps_the_service_up_while_data_ages() -> None:
    ticks = generate([baseline(), make_run(ScenarioKey.STALE_DATA, "historian-01")])

    assert set(series(ticks, "historian-01", Metric.UP)) == {1.0}
    ages = series(ticks, "historian-01", Metric.DATA_AGE_S)
    assert ages[-1] is not None
    assert ages[-1] > 590
    assert max(v or 0 for v in series(ticks, "analytics-01", Metric.DATA_AGE_S)) < 30


def test_intermittent_loss_never_fails_two_consecutive_probes() -> None:
    run = make_run(ScenarioKey.INTERMITTENT_LOSS, "edge-gateway-01")
    up = series(generate([baseline(), run], ticks=720), "edge-gateway-01", Metric.UP)

    assert all(not (a == 0.0 and b == 0.0) for a, b in itertools.pairwise(up))
    assert 0.25 < up.count(0.0) / len(up) < 0.35


def test_error_burst_repeats_one_error_message() -> None:
    ticks = generate([baseline(), make_run(ScenarioKey.ERROR_BURST, "data-api-01")])
    errors = [
        log
        for t in ticks
        for log in t.logs
        if log.component_key == "data-api-01" and log.severity is LogSeverity.ERROR
    ]

    assert min(v or 0 for v in series(ticks, "data-api-01", Metric.ERROR_COUNT)) >= 1
    assert len(errors) >= GOLDEN_TICKS
    assert len({log.message for log in errors}) == 1


def test_resource_pressure_holds_cpu_and_memory_near_the_peak() -> None:
    ticks = generate([baseline(), make_run(ScenarioKey.RESOURCE_PRESSURE, "timeseries-db-01")])

    for metric in (Metric.CPU_PCT, Metric.MEM_PCT):
        values = series(ticks, "timeseries-db-01", metric)
        assert all(95 < (v or 0) <= 100 for v in values[36:])


def test_backlog_grows_steadily() -> None:
    queue = series(
        generate([baseline(), make_run(ScenarioKey.BACKLOG_GROWTH, "collector-01")]),
        "collector-01",
        Metric.QUEUE_DEPTH,
    )

    assert queue[-1] is not None
    assert queue[-1] > 11_000
    assert queue == sorted(queue, key=lambda v: v or 0)


def test_telemetry_blackout_yields_no_observation_for_the_target_only() -> None:
    ticks = generate([baseline(), make_run(ScenarioKey.TELEMETRY_BLACKOUT, "historian-01")])

    assert samples_of(ticks, "historian-01") == []
    assert set(series(ticks, "data-api-01", Metric.UP)) == {1.0}


def test_generation_from_an_unaligned_baseline_start_covers_every_tick() -> None:
    start = GOLDEN_START + timedelta(seconds=3)
    unaligned = replace(baseline(), started_at=start)
    first = first_tick_at_or_after(start)

    ticks = generate_range(SIMULATED_PLATFORM, [unaligned], first, first + 11)

    assert all(t.samples for t in ticks)
