import socket
import subprocess
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.bootstrap import seed
from app.connectors.mqtt.adapter import MqttConfig
from app.connectors.mqtt.publisher import SimulatedPublisher
from app.core.observation import ObservationSource
from app.core.settings import Settings
from app.health.domain.states import HealthState
from app.main import create_app
from app.monitor.service import HeartbeatService
from app.simulation.domain.catalog import ScenarioKey
from app.simulation.domain.clock import ClockMode
from app.worker import Worker, build_cycle_steps
from tests.api_client import sign_in
from tests.fakes import CYCLE_INTERVAL_S, RETENTION, FixedClock
from tests.health_runs import CONTEXT, Platform
from tests.simulation_runs import GOLDEN_SEED, GOLDEN_START

pytestmark = pytest.mark.integration
BROKER_IMAGE = (
    "eclipse-mosquitto:2.0.22@"
    "sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279"
)


def docker(*arguments: str) -> str:
    return subprocess.run(  # noqa: S603 - fixed executable, fixture-owned container arguments
        ["docker", *arguments],  # noqa: S607 - Docker is a documented test prerequisite
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    ).stdout.strip()


@dataclass(frozen=True)
class Broker:
    container: str
    config: MqttConfig


@pytest.fixture(scope="module")
def broker() -> Iterator[Broker]:
    config_file = Path(__file__).resolve().parents[3] / "config/mosquitto/mosquitto.conf"
    container = f"iphi-test-mqtt-{uuid.uuid4().hex[:12]}"
    try:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
            docker(
                "create",
                "--name",
                container,
                "--label",
                "io.iphi.test=mqtt",
                "--read-only",
                "--user",
                "1883:1883",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--publish",
                f"127.0.0.1:{port}:1883",
                "--volume",
                f"{config_file}:/mosquitto/config/mosquitto.conf:ro",
                BROKER_IMAGE,
                "mosquitto",
                "-c",
                "/mosquitto/config/mosquitto.conf",
            )
        docker("start", container)
        # Network startup only: business time remains manual throughout these tests.
        for _ in range(100):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                threading.Event().wait(0.1)
        else:
            pytest.fail(f"Broker did not start: {docker('logs', container)}")
        yield Broker(container, MqttConfig("127.0.0.1", port, 10))
    finally:
        docker("rm", "--force", container)


@contextmanager
def publishing(platform: Platform, broker: Broker) -> Iterator[SimulatedPublisher]:
    publisher = SimulatedPublisher(platform.simulation, broker.config)
    stop = threading.Event()
    thread = threading.Thread(target=publisher.run, args=(stop,), daemon=True)
    thread.start()
    try:
        assert publisher.ready.wait(20), "Publisher subscription not ready"
        yield publisher
    finally:
        stop.set()
        thread.join(15)
        assert not thread.is_alive(), "Publisher did not stop"


def settings(database_url: str, broker: Broker, timeout_s: float = 10) -> Settings:
    return Settings(
        database_url=SecretStr(database_url),
        connector_source=ObservationSource.MQTT,
        mqtt_host="127.0.0.1",
        mqtt_port=broker.config.port,
        mqtt_timeout_s=timeout_s,
    )


@pytest.fixture
def platform(
    session_factory: sessionmaker[Session], engine: Engine, broker: Broker, database_url: str
) -> Platform:
    wall = FixedClock(GOLDEN_START + timedelta(minutes=30))
    simulation = seed(session_factory, wall, GOLDEN_SEED)
    simulation.set_clock_mode(ClockMode.MANUAL, 1, CONTEXT)
    worker = Worker(
        session_factory,
        HeartbeatService(session_factory),
        wall,
        CYCLE_INTERVAL_S,
        build_cycle_steps(session_factory, wall, RETENTION, settings(database_url, broker)),
    )
    return Platform(simulation, worker, engine)


def warmup(platform: Platform) -> None:
    platform.worker.run_cycle(0)
    platform.advance(60)
    assert set(platform.component_states().values()) == {HealthState.HEALTHY}


def test_collector_down_via_real_mqtt_has_one_evidenced_incident_and_unchanged_api(
    platform: Platform,
    broker: Broker,
    database_url: str,
) -> None:
    with publishing(platform, broker):
        warmup(platform)
        fault = platform.start(ScenarioKey.COLLECTOR_DOWN)
        platform.advance(120)

        assert platform.component_state("collector-01") is HealthState.CRITICAL
        assert platform.platform_state()[0] is HealthState.CRITICAL
        assert platform.active_incidents() == {("collector-01", "availability")}
        assert platform.rows("SELECT DISTINCT source FROM metric_sample") == [("mqtt",)]
        assert platform.rows("SELECT DISTINCT source FROM log_event") == [("mqtt",)]
        assert platform.rows("SELECT source, scenario_run_id FROM incident") == [("mqtt", fault.id)]
        assert (
            platform.rows(
                "SELECT count(*) FROM incident_evidence e "
                "JOIN metric_sample s ON s.id=e.metric_sample_id "
                "WHERE s.source='mqtt' AND s.metric_name='up' AND s.value=0"
            )[0][0]
            > 0
        )
        assert platform.rows("SELECT count(*) FROM collection_run WHERE status<>'ok'")[0][0] == 0

        app = create_app(settings(database_url, broker))
        with TestClient(app, base_url="http://127.0.0.1") as client:
            sign_in(client, database_url, "viewer")
            body = client.get("/api/v1/platforms").json()
            assert body["items"][0]["environment"] == "simulation"
            status = client.get("/api/v1/system/status").json()
            assert [c["connector_key"] for c in status["collection"]["connectors"]] == ["mqtt"]
            incidents = client.get("/api/v1/incidents").json()["items"]
            assert len(incidents) == 1
            assert incidents[0]["source"] == "mqtt"
        platform.stop(fault)
        platform.advance(360)
        assert not platform.active_incidents()
        assert platform.component_state("collector-01") is HealthState.HEALTHY


def test_lost_publisher_advances_absence_rules_then_recovery_is_visible(
    platform: Platform,
    session_factory: sessionmaker[Session],
    broker: Broker,
    database_url: str,
) -> None:
    with publishing(platform, broker):
        warmup(platform)
    wall = FixedClock(GOLDEN_START + timedelta(minutes=30))
    platform.worker = Worker(
        session_factory,
        HeartbeatService(session_factory),
        wall,
        CYCLE_INTERVAL_S,
        build_cycle_steps(session_factory, wall, RETENTION, settings(database_url, broker, 0.1)),
    )
    platform.advance(30)
    assert platform.component_state("collector-01") is HealthState.UNKNOWN
    assert {kind for _, kind in platform.active_incidents()} == {"telemetry_loss"}
    assert platform.rows(
        "SELECT status FROM collection_run ORDER BY started_at DESC, id DESC LIMIT 1"
    ) == [("failed",)]
    platform.worker = Worker(
        session_factory,
        HeartbeatService(session_factory),
        wall,
        CYCLE_INTERVAL_S,
        build_cycle_steps(session_factory, wall, RETENTION, settings(database_url, broker)),
    )
    with publishing(platform, broker):
        platform.advance(60)
    assert platform.component_state("collector-01") is HealthState.HEALTHY
    assert not platform.active_incidents()


def test_mqtt_reset_purges_both_transports_but_keeps_incident_evidence(
    platform: Platform,
    broker: Broker,
) -> None:
    with publishing(platform, broker):
        warmup(platform)
        platform.start(ScenarioKey.COLLECTOR_DOWN)
        platform.advance(120)
        old_baseline = platform.simulation.baseline().id
        platform.simulation.reset(GOLDEN_SEED, CONTEXT)
        assert platform.simulation.baseline().id != old_baseline
        assert platform.rows("SELECT count(*) FROM collection_cursor")[0][0] == 0
        assert (
            platform.rows(
                "SELECT count(*) FROM metric_sample s WHERE NOT EXISTS "
                "(SELECT 1 FROM incident_evidence e WHERE e.metric_sample_id=s.id)"
            )[0][0]
            == 0
        )
        assert platform.rows("SELECT count(*) FROM incident_evidence")[0][0] > 0
        platform.simulation.set_clock_mode(ClockMode.MANUAL, 1, CONTEXT)
        platform.advance(60)
        assert not platform.active_incidents()
        assert set(platform.component_states().values()) == {HealthState.HEALTHY}


def test_broker_restart_reconnects_publisher_and_connector(
    platform: Platform, broker: Broker
) -> None:
    with publishing(platform, broker) as publisher:
        warmup(platform)
        docker("restart", broker.container)
        assert publisher.ready.wait(20), "Publisher did not resubscribe after restart"
        platform.advance(30)
        assert platform.rows(
            "SELECT error_code FROM collection_run ORDER BY started_at DESC, id DESC LIMIT 1"
        ) == [(None,)]
        assert platform.component_state("collector-01") is HealthState.HEALTHY
