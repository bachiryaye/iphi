from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.connectors.domain import CollectionRequest, CollectionResult
from app.connectors.simulation import SimulationConnector
from app.core.observation import ObservationSource
from app.simulation.domain.clock import first_tick_at_or_after, tick_of, tick_time
from app.simulation.domain.generator import MAX_TICKS_PER_BATCH, TickObservations, generate_range
from app.simulation.domain.platform import SIMULATED_PLATFORM
from tests.simulation_runs import FIRST_TICK, GOLDEN_START, baseline

LATE_TOLERANCE = timedelta(minutes=10)


@dataclass
class RecordingSource:
    """Generates from a fixed baseline and records the tick ranges requested."""

    started_at: datetime = GOLDEN_START
    calls: list[tuple[int, int]] = field(default_factory=list)

    def coverage_start(self) -> datetime:
        return self.started_at

    def observations(self, first_tick: int, last_tick: int) -> list[TickObservations]:
        self.calls.append((first_tick, last_tick))
        return generate_range(SIMULATED_PLATFORM, [baseline()], first_tick, last_tick)


def collect(
    source: RecordingSource, now: datetime, resume_after: datetime | None = None
) -> CollectionResult:
    request = CollectionRequest(now, resume_after, not_before=now - LATE_TOLERANCE)
    return SimulationConnector(source).collect(request)


def test_first_collection_starts_at_the_baseline_start() -> None:
    source = RecordingSource()

    result = collect(source, GOLDEN_START + timedelta(seconds=12))

    assert source.calls == [(FIRST_TICK, FIRST_TICK + 2)]
    assert result.watermark == tick_time(FIRST_TICK + 2)
    assert {s.observed_at for s in result.samples} == {tick_time(FIRST_TICK + i) for i in range(3)}


def test_collection_resumes_after_the_watermark() -> None:
    source = RecordingSource()
    now = GOLDEN_START + timedelta(seconds=60)

    collect(source, now, resume_after=tick_time(FIRST_TICK + 5))

    assert source.calls == [(FIRST_TICK + 6, tick_of(now))]


def test_no_new_tick_means_no_generation_and_unchanged_watermark() -> None:
    source = RecordingSource()
    watermark = tick_time(FIRST_TICK + 2)

    result = collect(source, watermark + timedelta(seconds=4), resume_after=watermark)

    assert source.calls == []
    assert result.samples == ()
    assert result.watermark == watermark


def test_catch_up_never_reaches_beyond_the_late_tolerance() -> None:
    source = RecordingSource()
    now = GOLDEN_START + timedelta(hours=2)

    collect(source, now, resume_after=GOLDEN_START)

    first, last = source.calls[0]
    assert tick_time(first) >= now - LATE_TOLERANCE
    assert last == tick_of(now)
    assert last - first + 1 <= MAX_TICKS_PER_BATCH


def test_slots_beyond_the_late_tolerance_are_reported_as_skipped() -> None:
    now = GOLDEN_START + timedelta(hours=2)

    result = collect(RecordingSource(), now, resume_after=GOLDEN_START)

    [issue] = result.issues
    assert issue.code == "SAMPLE_SLOTS_SKIPPED"
    skipped = first_tick_at_or_after(now - LATE_TOLERANCE) - (FIRST_TICK + 1)
    assert issue.message.startswith(f"{skipped} sample slot(s)")


def test_regular_collection_reports_no_issue() -> None:
    now = GOLDEN_START + timedelta(minutes=5)

    assert collect(RecordingSource(), now, resume_after=now - timedelta(seconds=5)).issues == ()


def test_ticks_before_the_active_baseline_are_never_replayed() -> None:
    # After a reset the watermark predates the new baseline: older slots belong to stopped runs.
    source = RecordingSource(started_at=GOLDEN_START + timedelta(seconds=32))
    now = GOLDEN_START + timedelta(seconds=50)

    collect(source, now, resume_after=GOLDEN_START)

    assert source.calls == [(FIRST_TICK + 7, tick_of(now))]


def test_samples_keep_metric_unit_and_scenario_run() -> None:
    result = collect(RecordingSource(), GOLDEN_START)

    assert result.samples
    assert all(s.scenario_run_id is not None for s in result.samples)
    assert {(s.metric_name, s.unit) for s in result.samples} >= {("up", "bool"), ("cpu_pct", "%")}
    assert SimulationConnector.source is ObservationSource.SIMULATION
