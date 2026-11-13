from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.core.db import create_session_factory
from app.simulation.domain.catalog import ScenarioKey
from app.simulation.domain.clock import ClockMode
from tests.api_client import client_for
from tests.fakes import FixedClock
from tests.health_runs import CONTEXT, Platform, manual_platform

pytestmark = pytest.mark.integration

COLLECTOR_RULES = {
    "R-AVAIL-001", "R-CONN-001", "R-ERR-001", "R-LAT-001",
    "R-QUEUE-001", "R-RES-001", "R-RES-002", "R-TEL-001",
}  # fmt: skip


def collector_down(url: str, wall: FixedClock) -> Platform:
    engine = create_engine(url)
    platform = manual_platform(create_session_factory(engine), engine, wall)
    platform.start(ScenarioKey.COLLECTOR_DOWN)
    platform.advance(60)
    return platform


@pytest.fixture
def client(seeded_url: str) -> Iterator[TestClient]:
    """collector_down for one minute on a manual clock: stored states never go stale."""
    platform = collector_down(seeded_url, FixedClock(datetime.now(UTC)))
    with client_for(seeded_url, dev_mutations=False) as test_client:
        yield test_client
    platform.engine.dispose()


def get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(f"/api/v1{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def component(client: TestClient, key: str) -> Any:
    return next(c for c in get(client, "/components")["items"] if c["key"] == key)


def test_platform_reports_state_counts_and_the_aggregation_line(client: TestClient) -> None:
    (platform,) = get(client, "/platforms")["items"]
    health = platform["health"]

    assert (platform["environment"], health["state"], health["priority"]) == (
        "simulation",
        "critical",
        1,
    )
    assert [c["key"] for c in health["decided_by"]] == ["collector-01"]
    assert sum(health["counts"].values()) == 7
    assert health["stale"] is False
    assert health["rationale"].startswith("Priority 1:")


def test_topology_gives_states_impact_and_edge_direction(client: TestClient) -> None:
    platform_id = get(client, "/platforms")["items"][0]["id"]
    topology = get(client, f"/platforms/{platform_id}/topology")
    ids = {n["key"]: n["id"] for n in topology["nodes"]}

    assert len(topology["nodes"]) == 7
    assert {"dependent_id": ids["historian-01"], "dependency_id": ids["collector-01"],
            "kind": "data_flow"} in topology["edges"]  # fmt: skip
    analytics = next(n for n in topology["nodes"] if n["key"] == "analytics-01")
    assert ids["collector-01"] in analytics["impacted_by"]


def test_components_filter_by_state_and_criticality(client: TestClient) -> None:
    critical = get(client, "/components", state="critical")["items"]
    low = get(client, "/components", criticality="low")["items"]

    assert [c["key"] for c in critical] == ["collector-01"]
    assert critical[0]["reason"]["rule"]["key"] == "R-AVAIL-001"
    assert [c["key"] for c in low] == ["analytics-01"]
    assert client.get("/api/v1/components", params={"colour": "red"}).status_code == 422


def test_component_detail_lists_dependencies_both_ways_and_impact(client: TestClient) -> None:
    historian = get(client, f"/components/{component(client, 'historian-01')['id']}")

    assert {d["component"]["key"] for d in historian["upstream"]} == {
        "collector-01",
        "timeseries-db-01",
    }
    assert [d["component"]["key"] for d in historian["downstream"]] == ["data-api-01"]
    assert [c["key"] for c in historian["impacted_by"]] == ["collector-01"]


def test_component_health_justifies_every_rule_with_threshold_value_and_evidence(
    client: TestClient,
) -> None:
    collector = component(client, "collector-01")
    health = get(client, f"/components/{collector['id']}/health")
    rules = {r["rule"]["key"]: r for r in health["rules"]}

    assert set(rules) == COLLECTOR_RULES
    availability = rules["R-AVAIL-001"]
    assert (availability["health"]["state"], availability["observed_value"]) == ("critical", 0)
    assert availability["rule"]["critical"] == {"threshold": 1, "clear": 1}
    assert availability["rule"]["version"] == 1
    assert availability["window_start"] < availability["evaluated_at"]
    (sample_id,) = availability["evidence"]["sample_ids"]
    window = {
        "component_id": collector["id"],
        "metric_name": "up",
        "from": availability["window_start"],
        "to": (
            datetime.fromisoformat(availability["evaluated_at"]) + timedelta(seconds=1)
        ).isoformat(),
    }
    points = get(client, "/metrics", **window)["points"]
    assert {p["sample_id"]: p["value"] for p in points}[sample_id] == 0
    latency = rules["R-LAT-001"]
    assert latency["health"]["state"] in {"healthy", "unknown"}
    assert latency["debounce"] is None or latency["debounce"]["required"] >= 1


def test_health_rules_are_listed_read_only(client: TestClient) -> None:
    active = get(client, "/health-rules")["items"]
    every = get(client, "/health-rules", all_versions="true")["items"]

    assert len(active) == len(every) == 9
    freshness = next(r for r in active if r["key"] == "R-FRESH-001")
    assert freshness["target_types"] == ["analytics", "historian"]
    assert client.post("/api/v1/health-rules", json={}).status_code == 405


def test_rule_evaluations_page_newest_first_with_a_stable_cursor(client: TestClient) -> None:
    collector_id = component(client, "collector-01")["id"]
    window = {"from": "2000-01-01T00:00:00Z", "to": "2000-01-07T00:00:00Z"}
    assert get(client, "/rule-evaluations", **window)["items"] == []

    first = get(client, "/rule-evaluations", component_id=collector_id, limit=5)
    second = get(
        client, "/rule-evaluations", component_id=collector_id, limit=5, cursor=first["next_cursor"]
    )

    times = [e["evaluated_at"] for e in first["items"] + second["items"]]
    assert times == sorted(times, reverse=True)
    assert not {e["id"] for e in first["items"]} & {e["id"] for e in second["items"]}
    only = get(client, "/rule-evaluations", rule_key="R-AVAIL-001", state="critical")["items"]
    assert {(e["component"]["key"], e["rule"]["key"]) for e in only} == {
        ("collector-01", "R-AVAIL-001")
    }


def test_next_pages_keep_the_window_of_the_first_page(seeded_url: str) -> None:
    platform = collector_down(seeded_url, FixedClock(datetime.now(UTC)))
    with client_for(seeded_url, dev_mutations=False) as client:
        first = get(client, "/rule-evaluations", limit=5)
        # Two hours later the default window no longer covers the first page's evaluations.
        platform.simulation.advance_clock(7200, CONTEXT)
        moved = get(client, "/rule-evaluations", limit=5)
        second = get(client, "/rule-evaluations", limit=5, cursor=first["next_cursor"])
    platform.engine.dispose()

    assert moved["items"] == []
    assert len(second["items"]) == 5
    assert second["items"][0]["evaluated_at"] <= first["items"][-1]["evaluated_at"]


@pytest.mark.parametrize(
    ("path", "params", "status", "code"),
    [
        ("/components/00000000-0000-7000-8000-000000000000", {}, 404, "COMPONENT_NOT_FOUND"),
        (
            "/platforms/00000000-0000-7000-8000-000000000000/topology",
            {},
            404,
            "PLATFORM_NOT_FOUND",
        ),
        ("/rule-evaluations", {"cursor": "bm90LWEtY3Vyc29y"}, 422, "INVALID_CURSOR"),
        (
            "/rule-evaluations",
            {"from": "2026-01-01T00:00:00Z", "to": "2026-02-01T00:00:00Z"},
            422,
            "INVALID_TIME_WINDOW",
        ),
        ("/rule-evaluations", {"rule_key": "'; DROP TABLE x"}, 422, "VALIDATION_ERROR"),
    ],
)
def test_invalid_requests_get_problem_details(
    client: TestClient, path: str, params: dict[str, str], status: int, code: str
) -> None:
    response = client.get(f"/api/v1{path}", params=params)

    assert response.status_code == status
    assert response.json()["code"] == code


def test_states_turn_unknown_when_the_worker_stops_evaluating(seeded_url: str) -> None:
    # The worker ran ten minutes ago in realtime; nothing has been evaluated since.
    engine = create_engine(seeded_url)
    platform = manual_platform(
        create_session_factory(engine),
        engine,
        FixedClock(datetime.now(UTC) - timedelta(minutes=10)),
    )
    platform.simulation.set_clock_mode(ClockMode.REALTIME, 1.0, CONTEXT)

    with client_for(seeded_url, dev_mutations=False) as client:
        (stored,) = get(client, "/platforms")["items"]
        collector = component(client, "collector-01")
        rules = get(client, f"/components/{collector['id']}/health")["rules"]
    engine.dispose()

    assert {(r["health"]["state"], r["health"]["stale"]) for r in rules} == {("unknown", True)}
    assert (stored["health"]["state"], stored["health"]["evaluated_state"]) == (
        "unknown",
        "healthy",
    )
    assert stored["health"]["stale"] is True
    assert "worker" in stored["health"]["stale_reason"]
    assert collector["health"]["state"] == "unknown"
