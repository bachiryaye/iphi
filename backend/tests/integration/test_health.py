from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from functools import partial

import pytest
import structlog
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.connectors.domain import CollectionRequest, CollectionResult
from app.connectors.simulation import SimulationConnector
from app.core.db import create_session_factory
from app.core.migrations import alembic_config
from app.core.retention import EvidenceHolds, RetentionJob
from app.health.config import DEFAULT_RULES_PATH, load_rules
from app.health.domain.states import HealthState
from app.health.service import HealthEvaluation, HealthRuleCatalog, purge_evaluations
from app.ingestion.domain.catalog import METRIC_CATALOG
from app.monitor.service import HeartbeatService
from app.simulation.domain.catalog import SCENARIOS, ScenarioKey
from app.simulation.domain.platform import SIMULATED_PLATFORM
from app.topology.domain import ComponentSpec, ComponentType, Criticality, TopologySpec
from app.topology.service import TopologyService
from app.worker import Worker
from tests.fakes import FixedClock, NoHistoryOrigin, idle_steps
from tests.health_runs import CONTEXT, Platform, manual_platform
from tests.simulation_runs import GOLDEN_SEED, GOLDEN_START

pytestmark = pytest.mark.integration

H, W, C, U = HealthState.HEALTHY, HealthState.WARNING, HealthState.CRITICAL, HealthState.UNKNOWN
NOW = GOLDEN_START + timedelta(minutes=30)
FAULT_S = 420
RECOVERY_S = 360


@pytest.fixture
def wall() -> FixedClock:
    return FixedClock(NOW)


@pytest.fixture
def platform(session_factory: sessionmaker[Session], engine: Engine, wall: FixedClock) -> Platform:
    return manual_platform(session_factory, engine, wall)


@dataclass(frozen=True)
class Expected:
    """Catalog outcome (architecture §05.6) on the default target, after FAULT_S seconds."""

    scenario: ScenarioKey
    rules: tuple[str, ...]
    sequence: tuple[HealthState, ...]
    platform: HealthState
    steady: tuple[str, ...] = ()

    @property
    def target(self) -> str:
        target = SCENARIOS[self.scenario].default_target
        assert target is not None
        return target


CATALOG = [
    Expected(ScenarioKey.COLLECTOR_DOWN, ("R-AVAIL-001",), (H, C), C),
    Expected(ScenarioKey.LATENCY_RISE, ("R-LAT-001",), (H, W, C), C),
    Expected(ScenarioKey.STALE_DATA, ("R-FRESH-001",), (H, W, C), C, ("R-AVAIL-001", "R-CONN-001")),
    Expected(ScenarioKey.INTERMITTENT_LOSS, ("R-CONN-001",), (H, W, C), C, ("R-AVAIL-001",)),
    Expected(ScenarioKey.ERROR_BURST, ("R-ERR-001",), (H, W, C), C),
    Expected(ScenarioKey.RESOURCE_PRESSURE, ("R-RES-001", "R-RES-002"), (H, W, C), C),
    Expected(ScenarioKey.BACKLOG_GROWTH, ("R-QUEUE-001",), (H, W, C), C),
    Expected(ScenarioKey.TELEMETRY_BLACKOUT, ("R-TEL-001",), (H, U), U),
]


@pytest.mark.parametrize("expected", CATALOG, ids=lambda e: e.scenario.value)
def test_catalog_scenario_reaches_its_expected_states_then_recovers_without_oscillation(
    platform: Platform, expected: Expected
) -> None:
    run = platform.start(expected.scenario)
    platform.advance(FAULT_S)

    for rule in expected.rules:
        assert platform.rule_states(expected.target, rule) == [U, *expected.sequence]
    for rule in expected.steady:
        assert platform.rule_states(expected.target, rule) == [U, H]
    assert platform.component_state(expected.target) is expected.sequence[-1]
    assert platform.platform_state()[0] is expected.platform

    platform.stop(run)
    platform.advance(RECOVERY_S)

    for rule in expected.rules:
        recovery = platform.rule_states(expected.target, rule)[len(expected.sequence) :]
        severities = [s.severity for s in recovery]
        assert recovery[-1] is H
        assert severities == sorted(severities, reverse=True), recovery
    assert set(platform.component_states().values()) == {H}
    assert platform.platform_state() == (H, 4)


def test_baseline_keeps_every_component_healthy(platform: Platform) -> None:
    platform.advance(FAULT_S)

    assert set(platform.component_states().values()) == {H}
    assert len(platform.component_states()) == 7
    assert platform.platform_state() == (H, 4)
    with platform.engine.connect() as connection:
        changes = connection.execute(
            text("SELECT count(*) FROM rule_evaluation WHERE state NOT IN ('healthy', 'unknown')")
        ).scalar_one()
    assert changes == 0


def test_collector_down_is_critical_within_three_cycles_and_impacts_downstream(
    platform: Platform,
) -> None:
    run = platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(15, step=5)

    assert platform.component_state("collector-01") is C
    assert platform.platform_state() == (C, 1)
    platform.advance(30)
    for downstream in ("historian-01", "data-api-01", "analytics-01"):
        assert "collector-01" in platform.impacted(downstream)
    assert platform.impacted("timeseries-db-01") == set()
    assert run.target_key == "collector-01"


def test_telemetry_blackout_is_never_reported_healthy(platform: Platform) -> None:
    platform.start(ScenarioKey.TELEMETRY_BLACKOUT, "historian-01")
    seen = []
    for _ in range(24):
        platform.advance(15, step=15)
        seen.append(platform.component_state("historian-01"))

    assert seen[0] is U
    assert set(seen) == {U}
    assert platform.impacted("data-api-01") == {"historian-01"}
    assert platform.platform_state() == (U, 2)


def test_every_state_is_traceable_to_stored_evaluations_and_samples(platform: Platform) -> None:
    platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(300)

    with platform.engine.connect() as connection:
        dangling = connection.execute(
            text(
                "SELECT count(*) FROM rule_evaluation e, "
                "jsonb_array_elements_text(e.evidence -> 'samples') AS s(id) "
                "WHERE NOT EXISTS (SELECT 1 FROM metric_sample m WHERE m.id = s.id::bigint)"
            )
        ).scalar_one()
        reasons = connection.execute(
            text(
                "SELECT r.key, e.state FROM component_health h "
                "JOIN rule_evaluation e ON e.id = h.reason_evaluation_id "
                "JOIN health_rule r ON r.id = e.rule_id WHERE h.state <> 'healthy'"
            )
        ).all()
    assert dangling == 0
    assert reasons == [("R-LAT-001", "critical")]


def test_same_seed_and_clock_give_the_same_state_history_whatever_the_cadence(
    database_factory: Callable[[], str],
) -> None:
    histories = []
    for step in (5, 60):
        url = database_factory()
        command.upgrade(alembic_config(url), "head")
        engine = create_engine(url)
        platform = manual_platform(create_session_factory(engine), engine, FixedClock(NOW))
        platform.start(ScenarioKey.LATENCY_RISE)
        platform.advance(360, step=step)
        histories.append(
            platform.rows(
                "SELECT c.key, r.key, r.version, e.evaluated_at, e.raw_state, e.state, "
                "e.observed_value FROM rule_evaluation e JOIN health_rule r ON r.id = e.rule_id "
                "JOIN component c ON c.id = e.component_id ORDER BY 1, 2, 4"
            )
        )
        engine.dispose()

    assert histories[0] == histories[1]
    assert len(histories[0]) > 100


def test_reset_restarts_health_from_unknown(platform: Platform) -> None:
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(60)

    platform.simulation.reset(GOLDEN_SEED, CONTEXT)

    (counts,) = platform.rows(
        "SELECT (SELECT count(*) FROM rule_evaluation e WHERE NOT EXISTS (SELECT 1 FROM "
        "incident_evidence i WHERE i.rule_evaluation_id = e.id)), "
        "(SELECT count(*) FROM rule_state), (SELECT count(*) FROM component_health), "
        "(SELECT count(*) FROM platform_health)"
    )
    assert tuple(counts) == (0, 0, 0, 0)


def test_retention_keeps_the_evaluations_current_states_cite(platform: Platform) -> None:
    platform.advance(300)
    with platform.engine.connect() as connection:
        total, newest = connection.execute(
            text("SELECT count(*), max(evaluated_at) FROM rule_evaluation")
        ).one()
    job = RetentionJob(timedelta(0), [partial(purge_evaluations, holds=EvidenceHolds())])
    session_factory = create_session_factory(platform.engine)

    deleted = job.purge_if_due(session_factory, newest + timedelta(seconds=1))

    with platform.engine.connect() as connection:
        left = connection.execute(text("SELECT count(*) FROM rule_evaluation")).scalar_one()
        cited = connection.execute(
            text(
                "SELECT count(*) FROM rule_state s WHERE NOT EXISTS "
                "(SELECT 1 FROM rule_evaluation e WHERE e.id = s.state_evaluation_id)"
            )
        ).scalar_one()
    assert deleted == total - left > 0
    assert cited == 0


def test_rule_catalog_versions_changes_and_disables_removed_rules(
    session_factory: sessionmaker[Session], wall: FixedClock, engine: Engine
) -> None:
    manual_platform(session_factory, engine, wall)
    keys = [c.key for c in SIMULATED_PLATFORM.components]
    specs = load_rules(DEFAULT_RULES_PATH, METRIC_CATALOG, keys)
    catalog = HealthRuleCatalog(session_factory)
    assert catalog.ensure(specs) == []

    latency = next(s for s in specs if s.key == "R-LAT-001")
    retuned = replace(latency, definition=replace(latency.definition, raise_after=4))
    others = [s for s in specs if s.key not in ("R-LAT-001", "R-QUEUE-001")]
    created = catalog.ensure([*others, retuned])

    assert sorted((r.key, r.version, r.definition.enabled) for r in created) == [
        ("R-LAT-001", 2, True),
        ("R-QUEUE-001", 2, False),
    ]


def test_rule_versions_cannot_be_updated_in_place(
    session_factory: sessionmaker[Session], wall: FixedClock, engine: Engine
) -> None:
    manual_platform(session_factory, engine, wall)

    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(
            text("UPDATE health_rule SET critical_threshold = 1 WHERE key = 'R-LAT-001'")
        )


def test_failing_evaluation_never_rolls_back_the_collection(
    platform: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    (before,) = platform.rows("SELECT count(*), max(last_evaluated_at) FROM rule_state")

    def broken(*_args: object) -> None:
        raise RuntimeError("evaluation bug")

    monkeypatch.setattr(HealthEvaluation, "_evaluate", broken)
    platform.advance(30)

    (after,) = platform.rows("SELECT count(*), max(last_evaluated_at) FROM rule_state")
    (heartbeat,) = platform.rows("SELECT last_cycle_at FROM monitor_heartbeat")
    newest = platform.rows("SELECT max(observed_at) FROM metric_sample")[0][0]
    assert tuple(after) == tuple(before)
    assert newest > before[1]
    assert heartbeat[0] is not None


def test_slots_are_evaluated_only_once_collected(
    platform: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = SimulationConnector.collect
    calls = iter([True])

    def fails_once(self: SimulationConnector, request: CollectionRequest) -> CollectionResult:
        if next(calls, False):
            raise ConnectionError("source unreachable")
        return original(self, request)

    monkeypatch.setattr(SimulationConnector, "collect", fails_once)
    (evaluated,) = platform.rows("SELECT max(last_evaluated_at) FROM rule_state")
    platform.advance(30)
    (held,) = platform.rows("SELECT max(last_evaluated_at) FROM rule_state")
    platform.advance(30)

    assert held == evaluated
    for key in ("collector-01", "historian-01"):
        assert platform.rule_states(key, "R-TEL-001") == [U, H]
        assert platform.rule_states(key, "R-AVAIL-001") == [U, H]


def test_evaluating_one_platform_keeps_the_rule_states_of_another(
    platform: Platform, session_factory: sessionmaker[Session]
) -> None:
    other = TopologySpec(
        "other-plant",
        "Other plant",
        (ComponentSpec("probe-01", "Probe 01", ComponentType.SOURCE, Criticality.LOW),),
        (),
    )
    TopologyService(session_factory).ensure(other)
    lookback = timedelta(minutes=10)
    with session_factory.begin() as session:
        HealthEvaluation(
            TopologyService(session_factory), "other-plant", lookback, NoHistoryOrigin()
        ).evaluate(session, platform.simulation.clock().platform_time)

    platform.advance(30)

    (kept,) = platform.rows(
        "SELECT count(*) FROM rule_state s JOIN component c ON c.id = s.component_id "
        "WHERE c.key = 'probe-01'"
    )
    assert kept[0] > 0


def test_every_log_event_of_a_cycle_shares_one_correlation_id(
    session_factory: sessionmaker[Session], wall: FixedClock
) -> None:
    seen: list[dict[str, object]] = []

    class Recording:
        def evaluate(self, _session: Session, _now: datetime) -> None:
            seen.append(structlog.contextvars.get_contextvars())

    steps = replace(idle_steps(wall), health=Recording())
    worker = Worker(session_factory, HeartbeatService(session_factory), wall, 5.0, steps)

    worker.run_cycle(0)
    worker.run_cycle(0)

    ids = [str(s["correlation_id"]) for s in seen]
    assert len(set(ids)) == 2
    assert all(i.startswith("cycle-") for i in ids)
    assert structlog.contextvars.get_contextvars() == {}
