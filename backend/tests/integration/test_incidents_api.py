from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.db import create_session_factory
from app.simulation.domain.catalog import ScenarioKey
from tests.api_client import client_for
from tests.fakes import FixedClock
from tests.health_runs import CONTEXT, Platform, manual_platform

pytestmark = pytest.mark.integration

BASE = "/api/v1/incidents"


@pytest.fixture
def platform(seeded_url: str) -> Iterator[Platform]:
    """collector_down for two minutes on a manual clock: stored states never go stale."""
    engine = create_engine(seeded_url)
    platform = manual_platform(
        create_session_factory(engine), engine, FixedClock(datetime.now(UTC))
    )
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(120)
    yield platform
    engine.dispose()


@pytest.fixture
def client(seeded_url: str, platform: Platform) -> Iterator[TestClient]:
    with client_for(seeded_url, dev_mutations=True) as test_client:
        yield test_client


def get(client: TestClient, path: str = "", **params: Any) -> Any:
    response = client.get(f"{BASE}{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def post(client: TestClient, path: str, body: Any = None, **headers: str) -> Any:
    return client.post(f"{BASE}{path}", json=body or {}, headers=headers)


def the_incident(client: TestClient) -> Any:
    (item,) = get(client, status="open")["items"]
    return item


def test_list_shows_the_open_incident_with_its_evidence_and_impact(client: TestClient) -> None:
    item = the_incident(client)

    assert (item["reference"], item["component"]["key"], item["failure_class"]) == (
        "INC-0001",
        "collector-01",
        "availability",
    )
    assert item["evidence_count"] > 0
    assert item["environment"] == "simulation"
    assert get(client, failure_class="latency")["items"] == []


@pytest.mark.parametrize(
    ("params", "code"),
    [
        ({"cursor": "bogus"}, "INVALID_CURSOR"),
        ({"from": "2026-01-01T00:00:00Z", "to": "2026-01-09T00:00:00Z"}, "INVALID_TIME_WINDOW"),
        ({"status": "closed"}, "VALIDATION_ERROR"),
    ],
)
def test_list_rejects_invalid_filters(
    client: TestClient, params: dict[str, str], code: str
) -> None:
    response = client.get(BASE, params=params)

    assert response.status_code == 422
    assert response.json()["code"] == code


def test_detail_links_condition_evidence_and_timeline(client: TestClient) -> None:
    detail = get(client, f"/{the_incident(client)['id']}")

    condition = {r["rule"]["key"]: r["alerting"] for r in detail["condition"]}
    assert condition == {"R-AVAIL-001": True, "R-CONN-001": True}
    assert detail["resolvable"] is False
    assert [e["label"] for e in detail["evidence"][:3]] == ["E1", "E2", "E3"]
    assert detail["evidence"][0]["kind"] == "evaluation"
    assert detail["evidence"][0]["evaluation"]["rule"]["key"] in condition
    assert {e["kind"] for e in detail["evidence"]} >= {"evaluation", "sample"}
    assert detail["events"][0]["type"] == "opened"
    assert detail["event_count"] == len(detail["events"])


def test_evidence_and_events_page_with_cursors(client: TestClient) -> None:
    incident_id = the_incident(client)["id"]
    first = get(client, f"/{incident_id}/evidence", limit=2)
    second = get(client, f"/{incident_id}/evidence", limit=2, cursor=first["next_cursor"])
    events = get(client, f"/{incident_id}/events", limit=1)

    assert [e["label"] for e in first["items"] + second["items"]] == ["E1", "E2", "E3", "E4"]
    assert events["items"][0]["type"] == "opened"
    assert events["next_cursor"] is not None


def test_acknowledgement_is_idempotent_and_audited(client: TestClient, platform: Platform) -> None:
    incident_id = the_incident(client)["id"]

    first = post(client, f"/{incident_id}/ack")
    second = post(client, f"/{incident_id}/ack")

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "acknowledged"
    assert second.json()["acknowledged_at"] == first.json()["acknowledged_at"]
    events = [e["type"] for e in get(client, f"/{incident_id}")["events"]]
    assert events.count("acknowledged") == 1
    audit = platform.rows(
        "SELECT outcome, details ->> 'changed' FROM audit_event WHERE action = 'incident.ack' "
        "ORDER BY occurred_at, id"
    )
    assert [tuple(r) for r in audit] == [("allowed", "true"), ("allowed", "false")]


def test_resolution_is_refused_while_the_condition_is_active(
    client: TestClient, platform: Platform
) -> None:
    incident_id = the_incident(client)["id"]

    response = post(client, f"/{incident_id}/resolve", {"comment": "Looks fine."})

    assert response.status_code == 409
    assert response.json()["code"] == "INCIDENT_CONDITION_ACTIVE"
    (audit,) = platform.rows(
        "SELECT outcome, details ->> 'error_code' FROM audit_event "
        "WHERE action = 'incident.resolve'"
    )
    assert tuple(audit) == ("failed", "INCIDENT_CONDITION_ACTIVE")


def test_manual_resolution_once_the_condition_is_no_longer_known(
    client: TestClient, platform: Platform
) -> None:
    incident_id = the_incident(client)["id"]
    (run,) = platform.rows("SELECT id FROM scenario_run WHERE scenario_key = 'collector_down'")
    platform.simulation.stop(run[0], CONTEXT)
    platform.start(ScenarioKey.TELEMETRY_BLACKOUT, "collector-01")
    # R-CONN-001 forgets the lost probes once they leave its 300 s window.
    platform.advance(330)

    resolved = post(client, f"/{incident_id}/resolve", {"comment": "Collector replaced."})
    again = post(client, f"/{incident_id}/resolve", {"comment": "Twice."})
    ack = post(client, f"/{incident_id}/ack")

    assert resolved.status_code == 200, resolved.text
    assert (resolved.json()["status"], resolved.json()["resolution"]) == ("resolved", "manual")
    assert again.json()["code"] == ack.json()["code"] == "INCIDENT_ILLEGAL_TRANSITION"
    timeline = get(client, f"/{incident_id}")["events"]
    assert timeline[-1]["payload"]["comment"] == "Collector replaced."


def test_resolution_comment_is_required(client: TestClient) -> None:
    response = post(client, f"/{the_incident(client)['id']}/resolve", {"comment": "   "})

    assert response.status_code == 422


def test_deterministic_diagnosis_cites_the_incident_evidence(client: TestClient) -> None:
    incident_id = the_incident(client)["id"]
    labels = {
        e["id"]: e["label"] for e in get(client, f"/{incident_id}/evidence", limit=200)["items"]
    }

    created = post(client, f"/{incident_id}/diagnose")
    repeated = post(client, f"/{incident_id}/diagnose")

    assert created.status_code == 201, created.text
    assert repeated.status_code == 200
    body = created.json()
    assert repeated.json()["id"] == body["id"]
    claims = body["observed_facts"] + body["hypotheses"] + body["recommended_checks"]
    cited = [c for claim in claims for c in claim["evidence"]]
    assert cited
    assert all(labels.get(c["evidence_id"]) == c["label"] for c in cited)
    assert "causation is not proven" in body["hypotheses"][0]["text"]
    assert body["validation"]["removed"] == []
    assert any("Simulated environment" in item for item in body["limitations"])
    timeline = [e["type"] for e in get(client, f"/{incident_id}")["events"]]
    assert timeline.count("diagnostic_added") == 1


def test_idempotency_key_returns_the_diagnosis_it_created(client: TestClient) -> None:
    incident_id = the_incident(client)["id"]

    first = post(client, f"/{incident_id}/diagnose", **{"Idempotency-Key": "demo-1"})
    second = post(client, f"/{incident_id}/diagnose", **{"Idempotency-Key": "demo-1"})
    listed = get(client, f"/{incident_id}/diagnostics")["items"]

    assert (first.status_code, second.status_code) == (201, 200)
    assert second.json()["id"] == first.json()["id"]
    assert [d["id"] for d in listed] == [first.json()["id"]]


def test_unknown_incident_is_not_found(client: TestClient) -> None:
    response = client.get(f"{BASE}/01a1d5d8-0000-7000-8000-000000000000")

    assert response.status_code == 404
    assert response.json()["code"] == "INCIDENT_NOT_FOUND"


def test_mutations_are_refused_and_audited_when_disabled(
    seeded_url: str, platform: Platform
) -> None:
    with client_for(seeded_url, dev_mutations=False) as client:
        response = post(client, f"/{the_incident(client)['id']}/ack")

    assert response.status_code == 403
    assert response.json()["code"] == "MUTATIONS_DISABLED"
    (audit,) = platform.rows("SELECT outcome FROM audit_event WHERE action = 'incident.ack'")
    assert audit[0] == "denied"
