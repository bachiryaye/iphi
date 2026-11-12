from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, text

from app.bootstrap import bootstrap
from app.core.settings import Settings
from app.main import create_app

pytestmark = pytest.mark.integration

BASE = "/api/v1/simulations"


def client_for(database_url: str, *, dev_mutations: bool) -> TestClient:
    settings = Settings(database_url=SecretStr(database_url), dev_mutations=dev_mutations)
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.fixture
def seeded_url(empty_database_url: str) -> str:
    bootstrap(Settings(database_url=SecretStr(empty_database_url)))
    return empty_database_url


@pytest.fixture
def client(seeded_url: str) -> Iterator[TestClient]:
    with client_for(seeded_url, dev_mutations=True) as test_client:
        yield test_client


def test_catalog_lists_every_scenario_with_its_expected_outcome(client: TestClient) -> None:
    response = client.get(f"{BASE}/scenarios")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "simulation"
    assert body["sample_interval_s"] == 5
    items = {item["key"]: item for item in body["items"]}
    assert len(items) == 9
    collector_down = items["collector_down"]
    assert collector_down["default_target_component_key"] == "collector-01"
    assert "availability" in collector_down["expected"]["incident"]
    assert {p["name"] for p in items["latency_rise"]["parameters"]} == {"peak_ms", "ramp_s"}


def test_started_run_is_listed_and_stoppable(client: TestClient) -> None:
    started = client.post(
        f"{BASE}/scenarios",
        json={"scenario_key": "latency_rise", "parameters": {"peak_ms": 2000}, "duration_s": 600},
    )

    assert started.status_code == 201
    run = started.json()
    assert run["target_component_key"] == "edge-gateway-01"
    assert run["parameters"] == {"peak_ms": 2000.0, "ramp_s": 300.0}
    assert run["source"] == "simulation"
    active = client.get(f"{BASE}/runs", params={"status": "active"}).json()["items"]
    assert [r["scenario_key"] for r in active] == ["latency_rise", "baseline"]

    stopped = client.post(f"{BASE}/runs/{run['id']}/stop")

    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"


def test_runs_are_paginated_with_an_opaque_cursor(client: TestClient) -> None:
    client.post(f"{BASE}/scenarios", json={"scenario_key": "error_burst"})

    first = client.get(f"{BASE}/runs", params={"limit": 1}).json()
    second = client.get(f"{BASE}/runs", params={"limit": 1, "cursor": first["next_cursor"]})

    assert first["items"][0]["scenario_key"] == "error_burst"
    assert second.json()["items"][0]["scenario_key"] == "baseline"
    assert second.json()["next_cursor"] is None


def test_malformed_cursor_is_a_problem_response(client: TestClient) -> None:
    response = client.get(f"{BASE}/runs", params={"cursor": "not-a-cursor"})

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "INVALID_CURSOR"


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            {"scenario_key": "latency_rise", "parameters": {"peak_ms": 1}},
            "SCENARIO_PARAMETER_INVALID",
        ),
        (
            {"scenario_key": "stale_data", "target_component_key": "plc-sim-01"},
            "SCENARIO_TARGET_INVALID",
        ),
        (
            {"scenario_key": "stale_data", "target_component_key": "ghost-01"},
            "SCENARIO_TARGET_INVALID",
        ),
        ({"scenario_key": "baseline"}, "SCENARIO_NOT_STARTABLE"),
        ({"scenario_key": "unknown"}, "VALIDATION_ERROR"),
        ({"scenario_key": "stale_data", "target_component_key": "Bad Key"}, "VALIDATION_ERROR"),
        ({"scenario_key": "stale_data", "extra": 1}, "VALIDATION_ERROR"),
    ],
)
def test_invalid_start_requests_are_rejected(
    client: TestClient, payload: dict[str, object], code: str
) -> None:
    response = client.post(f"{BASE}/scenarios", json=payload)

    assert response.status_code in {409, 422}
    assert response.json()["code"] == code


def test_clock_commands(client: TestClient) -> None:
    assert client.get(f"{BASE}/clock").json()["mode"] == "realtime"

    refused = client.post(f"{BASE}/clock", json={"action": "advance", "seconds": 30})
    assert refused.status_code == 409
    assert refused.json()["code"] == "CLOCK_NOT_MANUAL"

    manual = client.post(f"{BASE}/clock", json={"action": "set_mode", "mode": "manual"})
    before = manual.json()["platform_time"]
    advanced = client.post(f"{BASE}/clock", json={"action": "advance", "seconds": 30})

    assert advanced.status_code == 200
    assert advanced.json()["platform_time"] > before
    assert advanced.json()["environment"] == "simulation"


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "set_mode", "mode": "accelerated"},
        {"action": "set_mode", "mode": "realtime", "speed": 10},
        {"action": "set_mode", "mode": "accelerated", "speed": 120},
        {"action": "advance", "seconds": 0},
    ],
)
def test_invalid_clock_commands_are_rejected(
    client: TestClient, payload: dict[str, object]
) -> None:
    response = client.post(f"{BASE}/clock", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_reset_restarts_baseline_with_requested_seed(client: TestClient) -> None:
    client.post(f"{BASE}/scenarios", json={"scenario_key": "collector_down"})

    response = client.post(f"{BASE}/reset", json={"seed": 7})

    assert response.status_code == 200
    body = response.json()
    assert body["stopped_runs"] == 2
    assert body["clock"]["seed"] == 7
    assert body["baseline_run"]["scenario_key"] == "baseline"


def test_reset_without_body_uses_the_configured_seed(client: TestClient) -> None:
    response = client.post(f"{BASE}/reset")

    assert response.status_code == 200
    assert response.json()["clock"]["seed"] == 42


def test_mutations_without_dev_flag_are_denied_and_audited(seeded_url: str, engine: Engine) -> None:
    with client_for(seeded_url, dev_mutations=False) as denied_client:
        response = denied_client.post(
            f"{BASE}/scenarios",
            json={"scenario_key": "collector_down"},
            headers={"X-Correlation-ID": "corr-denied-0001"},
        )
        catalog = denied_client.get(f"{BASE}/scenarios")

    assert response.status_code == 403
    assert response.json()["code"] == "MUTATIONS_DISABLED"
    assert catalog.status_code == 200
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT action, outcome, actor_label, correlation_id FROM audit_event")
        ).one()
    assert tuple(row) == ("scenario.start", "denied", "dev-local", "corr-denied-0001")


def test_allowed_mutations_are_audited_with_platform_time(
    client: TestClient, engine: Engine
) -> None:
    client.post(f"{BASE}/scenarios", json={"scenario_key": "backlog_growth"})

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT action, outcome, target_type, platform_time IS NOT NULL FROM audit_event")
        ).one()
    assert tuple(row) == ("scenario.start", "allowed", "scenario_run", True)
