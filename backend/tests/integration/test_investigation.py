import uuid
from datetime import timedelta

import pytest

from tests.api_client import client_for
from tests.health_runs import Platform

pytestmark = pytest.mark.integration


def test_recorded_history_has_proof_and_gaps_and_validates_bounds(
    seeded_url: str, platform: Platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    with client_for(seeded_url, role="viewer") as client:
        component = next(
            c
            for c in client.get("/api/v1/components").json()["items"]
            if c["key"] == "collector-01"
        )
        end = platform.simulation.clock().platform_time
        params: dict[str, str | int] = {
            "from": (end - timedelta(minutes=5)).isoformat(),
            "to": end.isoformat(),
            "max_segments": 20,
        }
        response = client.get(f"/api/v1/components/{component['id']}/state-history", params=params)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["environment"] == "simulation"
        assert data["source"] == "rule_evaluations"
        assert len(data["rules"]) == 8
        segments = data["component_lane"]["segments"]
        assert segments[0]["state"] == "unknown"
        assert any(s["state"] == "critical" and s["evaluation_ids"] for s in segments)
        ids = {i for lane in data["rules"] for s in lane["segments"] for i in s["evaluation_ids"]}
        stored = {
            row[0]
            for row in platform.rows(
                "SELECT id FROM rule_evaluation WHERE component_id = :id", id=component["id"]
            )
        }
        assert ids <= stored
        assert client.get(f"/api/v1/components/{uuid.uuid4()}/state-history").status_code == 404
        for bad in (
            {"max_segments": 2001},
            {"from": end.isoformat(), "to": (end - timedelta(seconds=1)).isoformat()},
            {"from": (end - timedelta(days=8)).isoformat(), "to": end.isoformat()},
        ):
            assert (
                client.get(
                    f"/api/v1/components/{component['id']}/state-history", params=bad
                ).status_code
                == 422
            )
        monkeypatch.setattr("app.health.history_repository.MAX_HISTORY_ROWS", 1)
        refused = client.get(f"/api/v1/components/{component['id']}/state-history", params=params)
        assert refused.status_code == 413
        assert refused.json()["code"] == "HISTORY_TOO_DENSE"


def test_comment_is_audited_escaped_and_does_not_change_status(
    seeded_url: str, platform: Platform
) -> None:
    with client_for(seeded_url, role="admin") as client:
        incident = client.get("/api/v1/incidents").json()["items"][0]
        path = f"/api/v1/incidents/{incident['id']}"
        note = "<script>alert('untrusted')</script> investigate collector"
        response = client.post(f"{path}/comments", json={"comment": note})
        assert response.status_code == 201, response.text
        assert response.json()["status"] == incident["status"]
        events = client.get(f"{path}/events").json()["items"]
        comment = next(e for e in events if e["type"] == "commented")
        assert comment["payload"] == {"comment": note}
        assert comment["actor_label"] == "admin"
        for bad in ("", "   ", "a" * 4001):
            assert client.post(f"{path}/comments", json={"comment": bad}).status_code == 422
        (audit,) = platform.rows(
            "SELECT outcome FROM audit_event WHERE action = 'incident.comment'"
        )
        assert audit[0] == "allowed"
        assert client.post("/api/v1/simulations/reset", json={}).status_code == 200
        closed = client.post(f"{path}/comments", json={"comment": "Post-resolution investigation."})
        assert closed.status_code == 201
        assert closed.json()["status"] == "resolved"
    with client_for(seeded_url, role="viewer") as client:
        assert client.post(f"{path}/comments", json={"comment": "forbidden"}).status_code == 403
    assert platform.rows(
        "SELECT outcome FROM audit_event WHERE action = 'incident.comment' ORDER BY occurred_at"
    ) == [("allowed",), ("allowed",), ("denied",)]
