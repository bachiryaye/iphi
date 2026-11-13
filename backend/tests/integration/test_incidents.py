import threading
import uuid
from datetime import timedelta
from functools import partial

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.observation import ObservationSource
from app.core.retention import RetentionJob
from app.health.domain.rules import FailureClass
from app.health.service import purge_evaluations
from app.incidents.domain.lifecycle import Detection, Opening, open_incident
from app.incidents.domain.model import Incident, IncidentSeverity
from app.incidents.repository import IncidentRepository
from app.incidents.service import IncidentProcessing, evidence_holds
from app.ingestion.service import purge_observations
from app.simulation.domain.catalog import SCENARIOS, ScenarioKey
from app.simulation.domain.clock import ClockMode
from tests.fakes import FixedClock
from tests.health_runs import CONTEXT, Platform, manual_platform
from tests.simulation_runs import GOLDEN_SEED, GOLDEN_START

pytestmark = pytest.mark.integration

NOW = GOLDEN_START + timedelta(minutes=30)
FAULT_S = 420
RECOVERY_S = 360

CATALOG = [
    (ScenarioKey.COLLECTOR_DOWN, "availability"),
    (ScenarioKey.LATENCY_RISE, "latency"),
    (ScenarioKey.STALE_DATA, "freshness"),
    (ScenarioKey.INTERMITTENT_LOSS, "connectivity"),
    (ScenarioKey.ERROR_BURST, "errors"),
    (ScenarioKey.RESOURCE_PRESSURE, "resources"),
    (ScenarioKey.BACKLOG_GROWTH, "backlog"),
    (ScenarioKey.TELEMETRY_BLACKOUT, "telemetry_loss"),
]


@pytest.fixture
def platform(session_factory: sessionmaker[Session], engine: Engine) -> Platform:
    return manual_platform(session_factory, engine, FixedClock(NOW))


@pytest.mark.parametrize(("scenario", "failure_class"), CATALOG, ids=str)
def test_catalog_scenario_opens_one_incident_then_resolves_it_on_recovery(
    platform: Platform, scenario: ScenarioKey, failure_class: str
) -> None:
    target = SCENARIOS[scenario].default_target
    run = platform.start(scenario)
    platform.advance(FAULT_S)

    assert platform.active_incidents() == {(target, failure_class)}

    platform.stop(run)
    platform.advance(RECOVERY_S)

    assert [(r[0], r[1], r[2], r[5]) for r in platform.incidents()] == [
        (target, failure_class, "resolved", "auto_recovered")
    ]


def test_collector_down_attaches_downstream_freshness_as_impact(platform: Platform) -> None:
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(FAULT_S)

    impacted = platform.rows(
        "SELECT c.key FROM incident_impact m JOIN component c ON c.id = m.component_id"
    )
    events = platform.events("collector-01", "availability")
    assert {r[0] for r in impacted} == {"historian-01", "analytics-01"}
    assert events.count("downstream_suppressed") == 2
    assert events[0] == "opened"
    roles = platform.rows("SELECT DISTINCT role FROM incident_evidence ORDER BY role")
    assert [r[0] for r in roles] == ["impact", "supporting", "trigger"]


def test_connectivity_incident_becomes_the_availability_one_when_unreachable(
    platform: Platform,
) -> None:
    lossy = platform.start(ScenarioKey.INTERMITTENT_LOSS, "collector-01")
    platform.advance(120)
    assert platform.active_incidents() == {("collector-01", "connectivity")}
    platform.stop(lossy)

    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(60)

    (incident,) = platform.incidents()
    assert incident[:3] == ("collector-01", "availability", "open")
    assert "reclassified" in platform.events("collector-01", "availability")


def test_error_burst_updates_one_incident_with_growing_occurrences(platform: Platform) -> None:
    platform.start(ScenarioKey.ERROR_BURST)
    platform.advance(600)

    (incident,) = platform.incidents()
    assert incident[:3] == ("data-api-01", "errors", "open")
    assert incident[4] > 5
    assert platform.events("data-api-01", "errors").count("occurrence") == incident[4] - 1


def test_latency_rise_raises_severity_then_recovers_automatically(platform: Platform) -> None:
    run = platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(FAULT_S)
    platform.stop(run)
    platform.advance(RECOVERY_S)

    lifecycle = [e for e in platform.events("edge-gateway-01", "latency") if e != "occurrence"]
    (row,) = platform.rows("SELECT severity, peak_severity, resolution FROM incident")
    assert lifecycle == ["opened", "severity_changed", "resolved"]
    assert tuple(row) == ("critical", "critical", "auto_recovered")


def test_same_failure_within_fifteen_minutes_reopens_its_incident(platform: Platform) -> None:
    run = platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(FAULT_S)
    platform.stop(run)
    platform.advance(RECOVERY_S)

    platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(180)

    (row,) = platform.rows("SELECT number, status, reopen_count, acknowledged_at FROM incident")
    assert tuple(row) == (1, "open", 1, None)
    assert "reopened" in platform.events("edge-gateway-01", "latency")


def test_same_failure_after_fifteen_minutes_opens_a_new_incident(platform: Platform) -> None:
    run = platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(FAULT_S)
    platform.stop(run)
    platform.advance(RECOVERY_S + 16 * 60)

    platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(180)

    rows = platform.rows("SELECT number, status, reopen_count FROM incident ORDER BY number")
    assert [tuple(r) for r in rows] == [(1, "resolved", 0), (2, "open", 0)]


def test_database_refuses_a_second_active_incident_with_the_same_fingerprint(
    platform: Platform, session_factory: sessionmaker[Session]
) -> None:
    topology = platform.simulation._topology()
    collector = topology.component("collector-01")
    assert collector is not None

    def opening() -> list[Incident]:
        change = open_incident(
            Opening(
                uuid.uuid7(),
                topology.platform_id,
                collector.id,
                collector.key,
                FailureClass.BACKLOG,
                IncidentSeverity.WARNING,
                ObservationSource.SIMULATION,
            ),
            Detection(1, "R-QUEUE-001", 1, NOW),
        )
        return [change.incident]

    first = session_factory()
    IncidentRepository(first).insert(opening())
    errors: list[BaseException] = []

    def second() -> None:
        with session_factory() as session:
            try:
                IncidentRepository(session).insert(opening())
                session.commit()
            except DBAPIError as exc:
                session.rollback()
                errors.append(exc)

    racer = threading.Thread(target=second)
    racer.start()
    racer.join(timeout=1)
    assert racer.is_alive()
    first.commit()
    first.close()
    racer.join(timeout=10)

    assert len(errors) == 1
    assert isinstance(errors[0], IntegrityError)
    assert "uq_incident_fingerprint_active" in str(errors[0])
    (count,) = platform.rows("SELECT count(*) FROM incident WHERE failure_class = 'backlog'")
    assert count[0] == 1


def test_reset_closes_incidents_and_keeps_their_evidence(platform: Platform) -> None:
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(120)
    (evidence_before,) = platform.rows("SELECT count(*) FROM incident_evidence")

    platform.simulation.reset(GOLDEN_SEED, CONTEXT)
    platform.simulation.set_clock_mode(ClockMode.MANUAL, 1.0, CONTEXT)
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(60)

    rows = platform.rows("SELECT number, status, resolution FROM incident ORDER BY number")
    (evidence_after,) = platform.rows(
        "SELECT count(*) FROM incident_evidence WHERE incident_id = "
        "(SELECT id FROM incident WHERE number = 1)"
    )
    assert [tuple(r) for r in rows] == [(1, "resolved", "reset"), (2, "open", None)]
    assert evidence_after[0] == evidence_before[0] > 0


def test_history_after_a_reset_ignores_the_evidence_kept_from_before(platform: Platform) -> None:
    run = platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(FAULT_S)
    platform.stop(run)
    platform.advance(RECOVERY_S)
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(120)

    platform.simulation.reset(GOLDEN_SEED, CONTEXT)
    platform.simulation.set_clock_mode(ClockMode.MANUAL, 1.0, CONTEXT)
    platform.advance(330)
    platform.start(ScenarioKey.LATENCY_RISE)
    platform.advance(180)

    rows = platform.rows(
        "SELECT number, failure_class, status, resolution, reopen_count FROM incident "
        "ORDER BY number"
    )
    assert [tuple(r) for r in rows] == [
        (1, "latency", "resolved", "auto_recovered", 0),
        (2, "availability", "resolved", "reset", 0),
        (3, "latency", "open", None, 0),
    ]


def test_retention_keeps_observations_and_evaluations_cited_as_evidence(
    platform: Platform, session_factory: sessionmaker[Session]
) -> None:
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(120)
    (newest,) = platform.rows("SELECT max(observed_at) FROM metric_sample")
    holds = evidence_holds()
    job = RetentionJob(
        timedelta(0),
        [partial(purge_observations, holds=holds), partial(purge_evaluations, holds=holds)],
    )

    deleted = job.purge_if_due(session_factory, newest[0] + timedelta(seconds=1))

    (left,) = platform.rows(
        "SELECT (SELECT count(*) FROM metric_sample), (SELECT count(*) FROM incident_evidence "
        "WHERE metric_sample_id IS NOT NULL), (SELECT count(*) FROM rule_evaluation e WHERE "
        "EXISTS (SELECT 1 FROM incident_evidence i WHERE i.rule_evaluation_id = e.id))"
    )
    (cited,) = platform.rows(
        "SELECT count(*) FROM incident_evidence WHERE rule_evaluation_id IS NOT NULL"
    )
    assert deleted > 0
    assert left[0] == left[1] > 0
    assert left[2] == cited[0]


def test_failing_incident_step_keeps_health_and_catches_up(
    platform: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    platform.start(ScenarioKey.COLLECTOR_DOWN)

    def broken(*_args: object) -> None:
        raise RuntimeError("incident bug")

    with monkeypatch.context() as patch:
        patch.setattr(IncidentProcessing, "_process", broken)
        platform.advance(60)
        assert platform.component_state("collector-01").value == "critical"
        assert platform.incidents() == []

    platform.advance(90)

    # Catch-up rides on the once-a-minute evaluations, upstream order is not guaranteed then.
    assert ("collector-01", "availability") in platform.active_incidents()


def test_incident_evidence_and_events_are_append_only(platform: Platform) -> None:
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(60)

    for statement in (
        "UPDATE incident_evidence SET role = 'impact'",
        "DELETE FROM incident_event",
        "DELETE FROM incident_impact",
    ):
        with pytest.raises(DBAPIError, match="append-only"), platform.engine.begin() as c:
            c.execute(text(statement))


def test_baseline_opens_no_incident_even_right_after_an_unaligned_boot(
    session_factory: sessionmaker[Session], engine: Engine
) -> None:
    # Booting between two sample slots evaluates a slot no observation covers yet.
    wall = FixedClock(NOW + timedelta(seconds=2, milliseconds=500))
    platform = manual_platform(session_factory, engine, wall)

    platform.advance(FAULT_S)

    assert platform.incidents() == []
