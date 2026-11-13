import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import seed
from app.connectors.domain import (
    CollectionRequest,
    CollectionResult,
    ConnectorIssue,
    ObservedLog,
    ObservedSample,
)
from app.core.observation import LogSeverity, ObservationSource, Quality
from app.core.retention import RetentionJob
from app.identity.domain import AuditContext
from app.ingestion.domain.collection import (
    MAX_ERROR_MESSAGE_CHARS,
    CollectionRun,
    CollectionStatus,
)
from app.ingestion.domain.validation import IngestionPolicy
from app.ingestion.repository import (
    MetricSampleRecord,
)
from app.ingestion.service import CollectionService, purge_observations
from app.simulation.domain.catalog import ScenarioKey
from app.simulation.domain.clock import ClockMode
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.simulation.service import SimulationService, StartCommand
from app.topology.service import TopologyService
from tests.fakes import FixedClock, cycling_worker
from tests.observations import component_id, insert_samples
from tests.simulation_runs import GOLDEN_SEED, GOLDEN_START

pytestmark = pytest.mark.integration

NOW = GOLDEN_START + timedelta(minutes=30)
CONTEXT = AuditContext("dev-local", "corr-ingestion-test")
COMPONENTS = len(SIMULATED_PLATFORM.components)


@dataclass
class ScriptedConnector:
    """Returns the scripted result, or raises it, and records every request."""

    key: str = "scripted"
    source: ObservationSource = ObservationSource.SIMULATION
    result: CollectionResult | Exception = field(default_factory=CollectionResult)
    requests: list[CollectionRequest] = field(default_factory=list)

    def collect(self, request: CollectionRequest) -> CollectionResult:
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def sample(**changes: Any) -> ObservedSample:
    base = ObservedSample("collector-01", "probe_latency_ms", 35.0, "ms", Quality.GOOD, NOW)
    return replace(base, **changes)


def error_log(request_id: str) -> ObservedLog:
    return ObservedLog(
        "collector-01", LogSeverity.ERROR, "Read timeout", {"request_id": request_id}, NOW
    )


@pytest.fixture
def wall() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def simulation(session_factory: sessionmaker[Session], wall: FixedClock) -> SimulationService:
    return seed(session_factory, wall, GOLDEN_SEED)


def collection(
    session_factory: sessionmaker[Session], wall: FixedClock, *connectors: ScriptedConnector
) -> CollectionService:
    return CollectionService(
        connectors,
        TopologyService(session_factory),
        SIMULATED_PLATFORM.key,
        IngestionPolicy(),
        wall,
    )


Collect = Callable[..., list[CollectionRun]]


@pytest.fixture
def collect(
    session_factory: sessionmaker[Session], wall: FixedClock, simulation: SimulationService
) -> Collect:
    def run(*connectors: ScriptedConnector, now: datetime = NOW) -> list[CollectionRun]:
        service = collection(session_factory, wall, *connectors)
        with session_factory.begin() as session:
            return service.collect(session, now)

    return run


def count(engine: Engine, table: str, where: str = "true") -> int:
    with engine.connect() as connection:
        # Test-only helper; table and condition are literals of this module.
        statement = text(f"SELECT count(*) FROM {table} WHERE {where}")  # noqa: S608
        return int(connection.execute(statement).scalar_one())


def test_valid_observations_are_stored_with_reception_time_and_run(
    collect: Collect, engine: Engine
) -> None:
    connector = ScriptedConnector(
        result=CollectionResult(
            samples=(sample(), sample(metric_name="cpu_pct", unit="%", value=30.0)),
            logs=(error_log("a1"),),
            watermark=NOW,
        )
    )

    [run] = collect(connector)

    assert (run.status, run.sample_count, run.log_count) == (CollectionStatus.OK, 2, 1)
    assert run.watermark == NOW
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT observed_at, received_at, source, collection_run_id FROM metric_sample")
        ).all()
    assert {(r.observed_at, r.received_at, r.source, r.collection_run_id) for r in rows} == {
        (NOW, NOW, "simulation", run.id)
    }


@pytest.mark.parametrize(
    ("invalid", "code"),
    [
        (sample(component_key="ghost-01"), "UNKNOWN_COMPONENT"),
        (sample(metric_name="temperature_c"), "UNKNOWN_METRIC"),
        (sample(unit="s"), "UNIT_MISMATCH"),
        (sample(value=float("nan")), "VALUE_NOT_FINITE"),
        (sample(value=-1.0), "METRIC_OUT_OF_RANGE"),
        (sample(observed_at=NOW + timedelta(seconds=31)), "OBSERVATION_IN_FUTURE"),
        (sample(observed_at=NOW - timedelta(minutes=11)), "OBSERVATION_TOO_LATE"),
    ],
)
def test_invalid_sample_is_rejected_counted_and_not_stored(
    collect: Collect, engine: Engine, invalid: ObservedSample, code: str
) -> None:
    connector = ScriptedConnector(result=CollectionResult(samples=(sample(), invalid)))

    [run] = collect(connector)

    assert run.status is CollectionStatus.PARTIAL
    assert (run.sample_count, run.rejected_count) == (1, 1)
    assert dict(run.rejections) == {code: 1}
    assert count(engine, "metric_sample") == 1


def test_late_observation_within_tolerance_is_accepted(collect: Collect, engine: Engine) -> None:
    late = sample(observed_at=NOW - timedelta(minutes=9, seconds=55))

    [run] = collect(ScriptedConnector(result=CollectionResult(samples=(late,))))

    assert (run.status, run.sample_count) == (CollectionStatus.OK, 1)
    assert count(engine, "metric_sample", "received_at - observed_at > interval '9 minutes'") == 1


def test_redelivered_observations_are_ignored_and_counted(collect: Collect, engine: Engine) -> None:
    result = CollectionResult(samples=(sample(), sample()), logs=(error_log("a1"), error_log("a1")))
    connector = ScriptedConnector(result=result)

    first, second = collect(connector)[0], collect(connector)[0]

    assert (first.sample_count, first.log_count, first.duplicate_count) == (1, 1, 2)
    assert (second.sample_count, second.log_count, second.duplicate_count) == (0, 0, 4)
    assert second.status is CollectionStatus.OK
    assert count(engine, "metric_sample") == 1
    assert count(engine, "log_event") == 1


def test_logs_with_distinct_attributes_are_kept_apart(collect: Collect, engine: Engine) -> None:
    result = CollectionResult(logs=(error_log("a1"), error_log("b2"), error_log("c3")))

    collect(ScriptedConnector(result=result))

    assert count(engine, "log_event") == 3
    with engine.connect() as connection:
        fingerprints = connection.execute(text("SELECT DISTINCT fingerprint FROM log_event")).all()
    assert len(fingerprints) == 1


def test_failing_connector_is_recorded_without_stopping_the_others(
    collect: Collect, engine: Engine
) -> None:
    broken = ScriptedConnector(key="broken", result=ConnectionError("broker unreachable"))
    healthy = ScriptedConnector(key="healthy", result=CollectionResult(samples=(sample(),)))

    failed, ok = collect(broken, healthy)

    assert (failed.status, failed.error_code) == (CollectionStatus.FAILED, "CONNECTOR_ERROR")
    assert failed.error_message is not None
    assert "ConnectionError" in failed.error_message
    assert "broker unreachable" not in failed.error_message
    assert (ok.status, ok.sample_count) == (CollectionStatus.OK, 1)
    assert count(engine, "metric_sample") == 1


def test_storage_failure_of_one_connector_is_rolled_back_alone(
    collect: Collect, engine: Engine
) -> None:
    orphan = sample(scenario_run_id=uuid.uuid4())
    rejected_by_db = ScriptedConnector(key="orphan", result=CollectionResult(samples=(orphan,)))
    healthy = ScriptedConnector(key="healthy", result=CollectionResult(samples=(sample(),)))

    failed, ok = collect(rejected_by_db, healthy)

    assert (failed.status, failed.error_code) == (CollectionStatus.FAILED, "PERSISTENCE_ERROR")
    assert (failed.sample_count, ok.sample_count) == (0, 1)
    assert count(engine, "collection_run") == 2
    assert count(engine, "metric_sample") == 1


def test_output_breaking_the_connector_contract_fails_that_connector_only(
    collect: Collect, engine: Engine
) -> None:
    malformed = sample(value="12")
    broken = ScriptedConnector(key="malformed", result=CollectionResult(samples=(malformed,)))
    healthy = ScriptedConnector(key="healthy", result=CollectionResult(samples=(sample(),)))

    failed, ok = collect(broken, healthy)

    assert (failed.status, failed.error_code) == (
        CollectionStatus.FAILED,
        "INVALID_CONNECTOR_OUTPUT",
    )
    assert (ok.status, ok.sample_count) == (CollectionStatus.OK, 1)
    assert count(engine, "metric_sample") == 1


def test_connector_issue_marks_the_run_partial(collect: Collect) -> None:
    result = CollectionResult(
        samples=(sample(),), issues=(ConnectorIssue("TOPIC_LAGGING", "Topic 3 s behind"),)
    )

    [run] = collect(ScriptedConnector(result=result))

    assert (run.status, run.error_code, run.error_message) == (
        CollectionStatus.PARTIAL,
        "TOPIC_LAGGING",
        "Topic 3 s behind",
    )


def test_long_connector_message_is_stored_bounded(collect: Collect) -> None:
    result = CollectionResult(samples=(sample(),), issues=(ConnectorIssue("SLOW", "x" * 2000),))

    [run] = collect(ScriptedConnector(result=result))

    assert run.error_message is not None
    assert len(run.error_message) == MAX_ERROR_MESSAGE_CHARS


def test_next_collection_resumes_from_the_last_watermark(collect: Collect) -> None:
    connector = ScriptedConnector(result=CollectionResult(watermark=NOW - timedelta(seconds=5)))
    collect(connector)
    connector.result = ConnectionError("down")
    collect(connector)

    collect(connector)

    assert [r.resume_after for r in connector.requests] == [
        None,
        NOW - timedelta(seconds=5),
        NOW - timedelta(seconds=5),
    ]


def samples_per_tick(engine: Engine) -> dict[datetime, int]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT observed_at, count(*) FROM metric_sample GROUP BY observed_at")
        ).all()
    return {r[0]: r[1] for r in rows}


def test_worker_cycle_collects_every_elapsed_tick_once(
    simulation: SimulationService,
    session_factory: sessionmaker[Session],
    wall: FixedClock,
    engine: Engine,
) -> None:
    cycle = cycling_worker(session_factory, wall)
    simulation.set_clock_mode(ClockMode.MANUAL, 1.0, CONTEXT)
    start = simulation.clock().platform_time

    cycle.run_cycle(0)
    simulation.advance_clock(60, CONTEXT)
    cycle.run_cycle(0)
    cycle.run_cycle(0)

    per_tick = samples_per_tick(engine)
    assert sorted(per_tick) == [start + timedelta(seconds=5 * i) for i in range(13)]
    assert len(set(per_tick.values())) == 1
    assert count(engine, "metric_sample", "source <> 'simulation' OR scenario_run_id IS NULL") == 0
    assert count(engine, "collection_run", "duplicate_count > 0") == 0


def test_down_collector_still_reports_its_failed_probe(
    simulation: SimulationService,
    session_factory: sessionmaker[Session],
    wall: FixedClock,
    engine: Engine,
) -> None:
    simulation.set_clock_mode(ClockMode.MANUAL, 1.0, CONTEXT)
    simulation.start(StartCommand(ScenarioKey.COLLECTOR_DOWN, None, {}, None), CONTEXT)
    simulation.advance_clock(30, CONTEXT)

    cycling_worker(session_factory, wall).run_cycle(0)

    with Session(engine) as session:
        probes = session.scalars(
            select(MetricSampleRecord.value)
            .where(MetricSampleRecord.metric_name == "up")
            .where(MetricSampleRecord.scenario_run_id.is_not(None))
            .where(MetricSampleRecord.value == 0)
        ).all()
    assert probes
    assert count(engine, "collection_run", "status = 'ok'") == 1


def test_reset_purges_simulated_history_and_never_replays_stopped_runs(
    simulation: SimulationService,
    session_factory: sessionmaker[Session],
    wall: FixedClock,
    engine: Engine,
) -> None:
    cycle = cycling_worker(session_factory, wall)
    simulation.start(StartCommand(ScenarioKey.ERROR_BURST, None, {}, None), CONTEXT)
    wall.current += timedelta(seconds=30)
    cycle.run_cycle(0)
    assert count(engine, "metric_sample") > 0

    reset = simulation.reset(GOLDEN_SEED, CONTEXT)
    wall.current += timedelta(seconds=12)
    cycle.run_cycle(0)

    reset_at = reset.baseline.started_at.isoformat()
    assert count(engine, "metric_sample", f"observed_at < '{reset_at}'") == 0
    assert count(engine, "log_event", "attributes ? 'request_id'") == 0
    assert count(engine, "metric_sample") > 0
    with engine.connect() as connection:
        runs = connection.execute(text("SELECT DISTINCT scenario_run_id FROM metric_sample")).all()
    assert [r[0] for r in runs] == [reset.baseline.id]
    assert reset.baseline.started_at in samples_per_tick(engine)


def test_cycle_in_progress_holds_off_simulation_mutations(
    simulation: SimulationService, session_factory: sessionmaker[Session], engine: Engine
) -> None:
    with session_factory.begin() as cycle:
        simulation.begin_cycle(cycle)

        with engine.begin() as other:
            other.execute(text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(OperationalError, match="lock timeout"):
                other.execute(text("SELECT 1 FROM sim_clock FOR UPDATE"))


@pytest.mark.usefixtures("simulation")
def test_retention_purges_old_observations_in_bounded_batches(
    session_factory: sessionmaker[Session], engine: Engine
) -> None:
    recent = NOW - timedelta(days=1)
    old = NOW - timedelta(days=8)
    times = [old - timedelta(seconds=5 * i) for i in range(30)] + [recent]
    collector = component_id(session_factory, "collector-01")
    insert_samples(session_factory, collector, [(t, 1.0) for t in times])
    job = RetentionJob(timedelta(days=7), [purge_observations])

    deleted = job.purge_if_due(session_factory, NOW)
    again = job.purge_if_due(session_factory, NOW + timedelta(minutes=5))

    assert (deleted, again) == (30, 0)
    assert count(engine, "metric_sample") == 1
