from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import WallClock
from app.core.db import create_session_factory
from app.core.observation import LogSeverity
from tests.api_client import client_for
from tests.fakes import FixedClock, cycling_worker
from tests.observations import component_id, insert_logs, insert_samples

pytestmark = pytest.mark.integration

# Fixed past window: the API's platform clock follows wall time, so a past window is stable.
T0 = datetime(2026, 1, 1, tzinfo=UTC)
WINDOW = {"from": T0.isoformat(), "to": (T0 + timedelta(minutes=10)).isoformat()}
HOLE = range(200, 400)


@pytest.fixture
def factory(seeded_url: str) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(seeded_url)
    yield create_session_factory(engine)
    engine.dispose()


@pytest.fixture
def client(seeded_url: str) -> Iterator[TestClient]:
    with client_for(seeded_url, dev_mutations=False) as test_client:
        yield test_client


@pytest.fixture
def collector(factory: sessionmaker[Session]) -> str:
    """collector-01 `up` every 5 s over ten minutes, with nothing in 200-400 s."""
    component = component_id(factory, "collector-01")
    points = [(T0 + timedelta(seconds=s), 1.0) for s in range(0, 600, 5) if s not in HOLE]
    insert_samples(factory, component, points)
    return str(component)


def series(client: TestClient, component: str, **params: Any) -> Any:
    response = client.get(
        "/api/v1/metrics",
        params={"component_id": component, "metric_name": "up", **WINDOW, **params},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_catalog_lists_metrics_with_units_and_ranges(client: TestClient) -> None:
    items = {m["metric_name"]: m for m in client.get("/api/v1/metrics/catalog").json()["items"]}

    assert set(items) == {
        "up", "probe_latency_ms", "data_age_s", "error_count", "cpu_pct", "mem_pct", "queue_depth"
    }  # fmt: skip
    assert (items["cpu_pct"]["unit"], items["cpu_pct"]["max_value"]) == ("%", 100)


def test_raw_series_is_ordered_utc_and_keeps_its_gap(client: TestClient, collector: str) -> None:
    body = series(client, collector)

    assert (body["mode"], body["unit"], body["environment"]) == ("raw", "bool", "simulation")
    times = [p["observed_at"] for p in body["points"]]
    assert times == sorted(times)
    assert all(t.endswith("Z") for t in times)
    assert len(times) == 120 - len(range(200, 400, 5))
    assert body["gaps"] == [{"start": "2026-01-01T00:03:20Z", "end": "2026-01-01T00:06:40Z"}]
    assert all(p["source"] == "simulation" and p["sample_id"] > 0 for p in body["points"])


def test_series_beyond_max_points_is_aggregated_without_filling_gaps(
    client: TestClient, collector: str
) -> None:
    body = series(client, collector, max_points=10)

    assert (body["mode"], body["bucket_s"]) == ("aggregated", 60)
    assert 0 < len(body["buckets"]) <= 10
    assert body["points"] == []
    starts = [b["bucket_start"] for b in body["buckets"]]
    assert "2026-01-01T00:04:00Z" not in starts
    assert sum(b["count"] for b in body["buckets"]) == 80
    assert all(b["min"] <= b["avg"] <= b["max"] for b in body["buckets"])
    assert body["gaps"] == [{"start": "2026-01-01T00:04:00Z", "end": "2026-01-01T00:06:00Z"}]


@pytest.mark.parametrize(
    ("params", "status", "code"),
    [
        ({"to": (T0 + timedelta(days=7, seconds=1)).isoformat()}, 422, "INVALID_TIME_WINDOW"),
        ({"to": T0.isoformat()}, 422, "INVALID_TIME_WINDOW"),
        ({"from": "2026-01-01T00:00:00"}, 422, "VALIDATION_ERROR"),
        ({"max_points": 2001}, 422, "VALIDATION_ERROR"),
        ({"metric_name": "Robert'); DROP TABLE"}, 422, "VALIDATION_ERROR"),
        ({"unexpected": "1"}, 422, "VALIDATION_ERROR"),
        ({"metric_name": "temperature_c"}, 404, "METRIC_NOT_FOUND"),
        ({"component_id": "00000000-0000-7000-8000-000000000000"}, 404, "COMPONENT_NOT_FOUND"),
    ],
)
def test_series_request_is_bounded_and_validated(
    client: TestClient, collector: str, params: dict[str, str], status: int, code: str
) -> None:
    query = {"component_id": collector, "metric_name": "up", **WINDOW, **params}

    response = client.get("/api/v1/metrics", params=query)

    assert response.status_code == status
    assert response.json()["code"] == code


@pytest.fixture
def logs(factory: sessionmaker[Session]) -> str:
    component = component_id(factory, "historian-01")
    severities = [LogSeverity.INFO, LogSeverity.WARNING, LogSeverity.ERROR, LogSeverity.CRITICAL]
    insert_logs(
        factory,
        component,
        [(T0 + timedelta(seconds=i), severities[i % 4], f"Event {i}") for i in range(10)],
    )
    insert_logs(factory, component_id(factory, "collector-01"), [(T0, LogSeverity.ERROR, "Other")])
    return str(component)


def test_logs_are_paginated_newest_first_without_overlap(client: TestClient, logs: str) -> None:
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, str | int] = {"component_id": logs, "limit": 3, **WINDOW}
        if cursor is not None:
            params["cursor"] = cursor
        page = client.get("/api/v1/logs", params=params).json()
        seen += [item["message"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert seen == [f"Event {i}" for i in range(9, -1, -1)]


def test_logs_filter_by_minimum_severity(client: TestClient, logs: str) -> None:
    params = {"component_id": logs, "min_severity": "error", **WINDOW}

    items = client.get("/api/v1/logs", params=params).json()["items"]

    assert {i["severity"] for i in items} == {"error", "critical"}
    assert {i["component_key"] for i in items} == {"historian-01"}


@pytest.mark.parametrize(
    "cursor",
    [
        "not-base64!",
        "cnVuOjE",  # run:1, another kind
        "bG9nOng6eQ",  # log:x:y
        "bG9nOi0tNTox",  # log:--5:1
        "bG9nOjE6wrI",  # log:1:² (a Unicode digit)
        "bG9nOjE6OTk5OTk5OTk5OTk5OTk5OTk5OTk",  # id beyond BIGINT
        "bG9nOjk5OTk5OTk5OTk5OTk5OTk5OTk5OTk5OjE",  # time beyond datetime
    ],
)
def test_malformed_log_cursor_is_refused(client: TestClient, cursor: str) -> None:
    response = client.get("/api/v1/logs", params={"cursor": cursor, **WINDOW})

    assert (response.status_code, response.json()["code"]) == (422, "INVALID_CURSOR")


def test_system_status_shows_absent_collection(client: TestClient) -> None:
    body = client.get("/api/v1/system/status").json()

    assert body["environment"] == "simulation"
    assert body["collection"]["state"] == "not_started"
    assert body["collection"]["connectors"][0]["connector_key"] == "simulation"
    assert body["worker"]["status"] == "failed"


def test_system_status_reports_the_latest_collection(
    client: TestClient, factory: sessionmaker[Session], seeded_url: str
) -> None:
    # Ten seconds after the seed, so at least one sample slot of the baseline has elapsed.
    wall = FixedClock(WallClock().now() + timedelta(seconds=10))
    cycling_worker(factory, wall).run_cycle(0)

    body = client.get("/api/v1/system/status").json()

    connector = body["collection"]["connectors"][0]
    assert (body["collection"]["state"], connector["state"]) == ("ok", "ok")
    assert connector["last_run"]["sample_count"] > 0
    assert connector["last_success_at"] == connector["last_run"]["started_at"]
    assert body["worker"]["status"] == "ok"
    assert body["collection"]["recent_runs"][0]["id"] == connector["last_run"]["id"]
