from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import seed
from app.core.db import create_session_factory
from app.core.observation import tick_of
from app.identity.domain import AuditContext
from app.simulation.domain.catalog import ScenarioKey
from app.simulation.domain.clock import ClockMode
from app.simulation.domain.errors import (
    BaselineRunPermanentError,
    ScenarioRunNotActiveError,
    ScenarioTargetBusyError,
    SimulationNotInitializedError,
)
from app.simulation.domain.generator import fingerprint
from app.simulation.domain.runs import RunStatus
from app.simulation.repository import ACTIVE_TARGET_INDEX, MAX_OVERLAPPING_RUNS
from app.simulation.service import SimulationService, StartCommand, build_simulation
from tests.fakes import FixedClock, cycling_worker
from tests.simulation_runs import (
    FIRST_TICK,
    GOLDEN_COLLECTOR_DOWN,
    GOLDEN_SEED,
    GOLDEN_START,
    GOLDEN_TICKS,
)

pytestmark = pytest.mark.integration

CONTEXT = AuditContext("dev-local", "corr-simulation-test")


def simulation(factory: sessionmaker[Session], wall: FixedClock) -> SimulationService:
    return build_simulation(factory, wall)


@pytest.fixture
def wall() -> FixedClock:
    return FixedClock(GOLDEN_START)


@pytest.fixture
def service(session_factory: sessionmaker[Session], wall: FixedClock) -> SimulationService:
    return seed(session_factory, wall, GOLDEN_SEED)


def command(
    scenario: ScenarioKey, target: str | None = None, *, duration_s: int | None = None
) -> StartCommand:
    return StartCommand(scenario, target, {}, duration_s)


def audit_rows(engine: Engine) -> list[tuple[str, str, dict[str, Any]]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT action, outcome, details FROM audit_event ORDER BY occurred_at, id")
        )
        return [(r.action, r.outcome, r.details) for r in rows]


def count(engine: Engine, sql: str) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text(sql)).scalar_one())


def test_seed_is_idempotent(
    session_factory: sessionmaker[Session], wall: FixedClock, engine: Engine
) -> None:
    for _ in range(2):
        seed(session_factory, wall, GOLDEN_SEED)

    assert count(engine, "SELECT count(*) FROM platform") == 1
    assert count(engine, "SELECT count(*) FROM component") == 7
    assert count(engine, "SELECT count(*) FROM dependency") == 6
    assert count(engine, "SELECT count(*) FROM sim_clock") == 1
    assert count(engine, "SELECT count(*) FROM scenario_run WHERE status = 'active'") == 1


def test_unseeded_simulation_reports_it_is_not_initialized(
    session_factory: sessionmaker[Session], wall: FixedClock
) -> None:
    with pytest.raises(SimulationNotInitializedError):
        simulation(session_factory, wall).clock()


def test_golden_fingerprint_holds_through_persistence_and_restart(
    service: SimulationService, database_url: str, wall: FixedClock
) -> None:
    run = service.start(command(ScenarioKey.COLLECTOR_DOWN), CONTEXT)
    last_tick = FIRST_TICK + GOLDEN_TICKS - 1

    first = service.observations(FIRST_TICK, last_tick)

    restarted_engine = create_engine(database_url)
    try:
        restarted = simulation(create_session_factory(restarted_engine), wall)
        second = restarted.observations(FIRST_TICK, last_tick)
    finally:
        restarted_engine.dispose()
    assert fingerprint(first) == fingerprint(second) == GOLDEN_COLLECTOR_DOWN
    run_ids = {s.scenario_run_id for t in first for s in t.samples}
    assert run.id in run_ids
    assert len(run_ids) == 2
    assert {s.source for t in first for s in t.samples} == {"simulation"}


def test_second_run_on_a_busy_target_is_refused_and_audited(
    service: SimulationService, engine: Engine
) -> None:
    service.start(command(ScenarioKey.LATENCY_RISE), CONTEXT)

    with pytest.raises(ScenarioTargetBusyError, match="edge-gateway-01"):
        service.start(command(ScenarioKey.INTERMITTENT_LOSS), CONTEXT)

    assert [(action, outcome) for action, outcome, _ in audit_rows(engine)] == [
        ("scenario.start", "allowed"),
        ("scenario.start", "failed"),
    ]
    assert audit_rows(engine)[1][2]["error_code"] == "SCENARIO_TARGET_BUSY"


def test_database_allows_one_active_run_per_target(
    service: SimulationService, engine: Engine
) -> None:
    service.start(command(ScenarioKey.BACKLOG_GROWTH), CONTEXT)

    with pytest.raises(IntegrityError, match=ACTIVE_TARGET_INDEX), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO scenario_run (id, platform_id, scenario_key, target_component_id, "
                "seed, started_at, status, started_by) "
                "SELECT gen_random_uuid(), platform_id, 'collector_down', target_component_id, "
                "seed, started_at, 'active', 'test' FROM scenario_run "
                "WHERE scenario_key = 'backlog_growth'"
            )
        )


def test_planned_end_completes_the_run_in_manual_time(service: SimulationService) -> None:
    service.set_clock_mode(ClockMode.MANUAL, 1.0, CONTEXT)
    run = service.start(command(ScenarioKey.STALE_DATA, duration_s=30), CONTEXT)

    service.advance_clock(60, CONTEXT)

    [completed] = service.list_runs(RunStatus.COMPLETED, None, 10).items
    assert completed.id == run.id
    assert completed.stopped_at == run.started_at + timedelta(seconds=30)


def test_worker_cycle_completes_expired_runs(
    service: SimulationService, session_factory: sessionmaker[Session], wall: FixedClock
) -> None:
    run = service.start(command(ScenarioKey.ERROR_BURST, duration_s=20), CONTEXT)
    wall.current += timedelta(seconds=25)

    cycling_worker(session_factory, wall).run_cycle(0)

    [completed] = service.list_runs(RunStatus.COMPLETED, None, 10).items
    assert completed.id == run.id


def test_stop_rules(service: SimulationService) -> None:
    run = service.start(command(ScenarioKey.RESOURCE_PRESSURE), CONTEXT)
    [baseline] = service.list_runs(RunStatus.ACTIVE, None, 10).items[1:]

    stopped = service.stop(run.id, CONTEXT)

    assert stopped.status is RunStatus.STOPPED
    with pytest.raises(ScenarioRunNotActiveError):
        service.stop(run.id, CONTEXT)
    with pytest.raises(BaselineRunPermanentError):
        service.stop(baseline.id, CONTEXT)


def test_reset_stops_runs_and_keeps_platform_time_monotonic(
    service: SimulationService, wall: FixedClock
) -> None:
    service.set_clock_mode(ClockMode.ACCELERATED, 60.0, CONTEXT)
    service.start(command(ScenarioKey.LATENCY_RISE), CONTEXT)
    wall.current += timedelta(seconds=60)
    before = service.clock().platform_time

    outcome = service.reset(7, CONTEXT)

    assert outcome.stopped_runs == 2
    assert outcome.clock.state.mode is ClockMode.REALTIME
    assert outcome.clock.state.seed == 7
    assert outcome.clock.platform_time == before
    active = service.list_runs(RunStatus.ACTIVE, None, 10).items
    assert [r.id for r in active] == [outcome.baseline.id]
    assert outcome.baseline.seed == 7


def test_runs_page_by_number_newest_first(service: SimulationService) -> None:
    for scenario in (ScenarioKey.LATENCY_RISE, ScenarioKey.ERROR_BURST):
        service.start(command(scenario), CONTEXT)

    first = service.list_runs(None, None, 2)
    second = service.list_runs(None, first.next_before, 2)

    numbers = [r.number for r in first.items + second.items]
    assert numbers == sorted(numbers, reverse=True)
    assert len(numbers) == 3
    assert second.next_before is None


def test_reset_after_a_clock_behind_wall_time_leaves_no_tick_without_baseline(
    service: SimulationService, wall: FixedClock
) -> None:
    service.set_clock_mode(ClockMode.MANUAL, 1.0, CONTEXT)
    service.start(command(ScenarioKey.LATENCY_RISE), CONTEXT)
    wall.current += timedelta(seconds=600)

    outcome = service.reset(GOLDEN_SEED, CONTEXT)

    last_tick = tick_of(outcome.clock.platform_time) + 1
    ticks = service.observations(FIRST_TICK, last_tick)
    assert len(ticks) == last_tick - FIRST_TICK + 1
    assert all(t.samples for t in ticks)


def test_mutation_on_an_unseeded_platform_is_audited_as_failed(
    session_factory: sessionmaker[Session], wall: FixedClock, engine: Engine
) -> None:
    with pytest.raises(SimulationNotInitializedError):
        simulation(session_factory, wall).start(command(ScenarioKey.COLLECTOR_DOWN), CONTEXT)

    assert audit_rows(engine) == [
        ("scenario.start", "failed", {"error_code": "SIMULATION_NOT_INITIALIZED"})
    ]


def test_generation_refuses_to_truncate_overlapping_runs(
    service: SimulationService, engine: Engine
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO scenario_run (id, platform_id, scenario_key, target_component_id, "
                "seed, started_at, stopped_at, status, started_by) "
                "SELECT gen_random_uuid(), r.platform_id, 'latency_rise', c.id, 42, "
                "r.started_at, r.started_at + interval '1 hour', 'stopped', 'test' "
                "FROM scenario_run r, component c, generate_series(1, :n) "
                "WHERE r.scenario_key = 'baseline' AND c.key = 'edge-gateway-01'"
            ),
            {"n": MAX_OVERLAPPING_RUNS},
        )

    with pytest.raises(RuntimeError, match="overlap"):
        service.observations(FIRST_TICK, FIRST_TICK + 1)
