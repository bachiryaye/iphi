import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from starlette.requests import Request

from app.api import events
from app.core.db import create_session_factory
from app.core.events import Notice, NoticeType
from app.core.settings import Settings
from app.identity.auth_service import AuthService
from app.identity.users import ensure_users
from app.main import create_app
from tests.api_client import TEST_PASSWORD
from tests.fakes import FixedClock
from tests.health_runs import Platform

pytestmark = pytest.mark.integration


@pytest.fixture
def client(seeded_url: str) -> Iterator[TestClient]:
    settings = Settings(
        database_url=SecretStr(seeded_url),
        demo_admin_password=SecretStr(TEST_PASSWORD),
        demo_engineer_password=SecretStr(TEST_PASSWORD),
        demo_viewer_password=SecretStr(TEST_PASSWORD),
    )
    engine = create_engine(seeded_url)
    wall = FixedClock(datetime.now(UTC))
    ensure_users(create_session_factory(engine), wall, settings)
    app = create_app(settings)
    app.state.auth = AuthService(create_session_factory(engine), wall)
    with TestClient(app, base_url="http://127.0.0.1") as api:
        yield api
    engine.dispose()


def login(client: TestClient, role: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"username": role, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return {"x-csrf-token": response.json()["csrf_token"]}


def test_session_cookie_is_http_only_csrf_is_separate_and_passwords_are_hashed(
    client: TestClient,
    platform: Platform,
) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
    )
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    token = client.cookies["iphi_session"]
    assert token not in response.text
    assert response.json()["csrf_token"] != token
    assert response.headers["cache-control"] == "no-store"
    me = client.get("/api/v1/auth/me")
    assert me.json()["user"]["role"] == "admin"
    assert me.json()["csrf_token"] == response.json()["csrf_token"]
    rows = platform.rows("SELECT password_hash FROM app_user")
    assert len(rows) == 3
    assert all(r[0].startswith("$argon2id$") for r in rows)
    assert all(TEST_PASSWORD not in r[0] for r in rows)
    (stored,) = platform.rows("SELECT token_hash FROM user_session")
    assert stored[0] != token
    assert len(stored[0]) == 64


@pytest.mark.parametrize("role", ["viewer", "engineer", "admin"])
def test_role_by_mutation_matrix_is_enforced_and_denials_are_audited(
    client: TestClient,
    platform: Platform,
    role: str,
) -> None:
    headers = login(client, role)
    incident = client.get("/api/v1/incidents").json()["items"][0]["id"]
    unknown = str(uuid.uuid7())
    cases = [
        ("/simulations/scenarios", {"scenario_key": "latency_rise"}, "scenario.start"),
        (f"/simulations/runs/{unknown}/stop", {}, "scenario.stop"),
        ("/simulations/clock", {"action": "set_mode", "mode": "manual"}, "clock.update"),
        (f"/incidents/{incident}/ack", {}, "incident.ack"),
        (f"/incidents/{incident}/resolve", {"comment": "Investigated."}, "incident.resolve"),
        (f"/incidents/{incident}/comments", {"comment": "Inspection note."}, "incident.comment"),
        (f"/incidents/{incident}/diagnose?mode=deterministic", {}, "incident.diagnose"),
        (f"/incidents/{incident}/diagnose?mode=llm", {}, "incident.diagnose"),
        ("/simulations/reset", {}, "simulation.reset"),
    ]
    denied = []
    for path, body, action in cases:
        response = client.post("/api/v1" + path, json=body, headers=headers)
        if role == "viewer" or (role == "engineer" and action == "simulation.reset"):
            assert response.status_code == 403, (path, response.text)
            assert response.json()["code"] == "PERMISSION_DENIED"
            denied.append(action)
        else:
            assert response.status_code not in {401, 403, 422, 500}, (path, response.text)
    audit = platform.rows(
        "SELECT action, actor_label, actor_id FROM audit_event WHERE outcome='denied'"
    )
    assert sorted(r[0] for r in audit) == sorted(denied)
    assert all(r[1] == role and r[2] is not None for r in audit)
    if role == "viewer":
        assert client.get(f"/api/v1/incidents/{incident}").json()["status"] == "open"
        assert client.get(f"/api/v1/incidents/{incident}/diagnostics").json()["items"] == []


def test_missing_wrong_and_cross_session_csrf_do_not_mutate(
    client: TestClient, platform: Platform
) -> None:
    first = login(client, "engineer")
    second = login(client, "engineer")
    assert first != second
    path = "/api/v1/simulations/clock"
    for headers in ({}, {"x-csrf-token": "x" * 64}, first):
        response = client.post(path, json={"action": "advance", "seconds": 30}, headers=headers)
        assert response.status_code == 403
        assert response.json()["code"] == "CSRF_REJECTED"
    rows = platform.rows(
        "SELECT outcome FROM audit_event WHERE action='clock.update' AND outcome='denied'"
    )
    assert len(rows) == 3
    assert all(r[0] == "denied" for r in rows)


def test_logout_revokes_stolen_cookie_and_expiry_uses_wall_clock(client: TestClient) -> None:
    headers = login(client, "viewer")
    token = client.cookies["iphi_session"]
    assert client.post("/api/v1/auth/logout", json={}, headers=headers).status_code == 204
    client.cookies.set("iphi_session", token)
    assert client.get("/api/v1/platforms").status_code == 401
    client.cookies.clear()
    login(client, "viewer")
    assert isinstance(client.app, FastAPI)
    client.app.state.auth._wall.current += timedelta(hours=9)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503  # The test has no live worker.


def test_disabled_users_and_role_changes_take_effect_on_existing_session(
    client: TestClient,
    platform: Platform,
) -> None:
    headers = login(client, "admin")
    with platform.engine.begin() as db:
        db.execute(text("UPDATE app_user SET role='viewer' WHERE username='admin'"))
    response = client.post("/api/v1/simulations/reset", json={}, headers=headers)
    assert response.status_code == 403
    with platform.engine.begin() as db:
        db.execute(text("UPDATE app_user SET is_active=false WHERE username='admin'"))
    assert client.get("/api/v1/platforms").status_code == 401


def test_invalid_credentials_are_uniform_and_persistently_throttled(client: TestClient) -> None:
    for _ in range(6):
        response = client.post(
            "/api/v1/auth/login", json={"username": "missing", "password": "invalid"}
        )
        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"
        assert "invalid" not in response.json()["detail"]
    response = client.post(
        "/api/v1/auth/login", json={"username": "missing", "password": "invalid"}
    )
    assert response.status_code == 429
    assert response.json()["code"] == "LOGIN_RATE_LIMITED"


def test_login_forgery_and_oversized_password_are_rejected_without_echo(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": TEST_PASSWORD},
        headers={"sec-fetch-site": "cross-site"},
    )
    assert response.status_code == 403
    secret = "unique-private-value-" * 10
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": secret})
    assert response.status_code == 422
    assert secret not in response.text


def test_reads_require_session_and_admin_audit_is_bounded_and_paginated(client: TestClient) -> None:
    for path in (
        "platforms",
        "components",
        "metrics/catalog",
        "incidents",
        "system/status",
        "events/stream",
    ):
        assert client.get("/api/v1/" + path).status_code == 401
    login(client, "viewer")
    assert client.get("/api/v1/audit-events").status_code == 403
    login(client, "admin")
    first = client.get("/api/v1/audit-events?limit=2").json()
    assert len(first["items"]) == 2
    assert first["next_cursor"]
    second = client.get(
        "/api/v1/audit-events", params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert not ({r["id"] for r in first["items"]} & {r["id"] for r in second["items"]})
    assert TEST_PASSWORD not in str(first)
    assert client.get("/api/v1/audit-events?limit=201").status_code == 422
    assert client.get("/api/v1/audit-events?cursor=invalid").status_code == 422
    assert (
        client.get(
            "/api/v1/audit-events?from=2026-01-01T00:00:00Z&to=2026-02-01T00:00:00Z"
        ).status_code
        == 422
    )


def test_anonymous_mutation_is_refused_and_audited(client: TestClient, platform: Platform) -> None:
    response = client.post("/api/v1/simulations/scenarios", json={"scenario_key": "collector_down"})
    assert response.status_code == 401
    (row,) = platform.rows(
        "SELECT actor_label, actor_id, outcome FROM audit_event "
        "WHERE action='scenario.start' AND outcome='denied'"
    )
    assert tuple(row) == ("anonymous", None, "denied")
    assert client.post("/api/v1/auth/logout", json={}).status_code == 401
    assert (
        len(
            platform.rows(
                "SELECT id FROM audit_event WHERE action='auth.logout' AND outcome='denied'"
            )
        )
        == 1
    )


def test_production_cookie_requires_https(client: TestClient, seeded_url: str) -> None:
    app = create_app(Settings(database_url=SecretStr(seeded_url), deployment_mode="production"))
    with TestClient(app, base_url="https://127.0.0.1") as secure:
        response = secure.post(
            "/api/v1/auth/login", json={"username": "viewer", "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        assert "; Secure" in response.headers["set-cookie"]
        assert secure.get("/api/v1/auth/me").status_code == 200


def test_environment_password_rotation_revokes_sessions_and_is_audited(
    client: TestClient,
    seeded_url: str,
    platform: Platform,
) -> None:
    login(client, "admin")
    token = client.cookies["iphi_session"]
    new_password = "replacement-test-password"
    settings = Settings(
        database_url=SecretStr(seeded_url), demo_admin_password=SecretStr(new_password)
    )
    ensure_users(create_session_factory(platform.engine), FixedClock(datetime.now(UTC)), settings)
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": new_password}
        ).status_code
        == 200
    )
    (event,) = platform.rows(
        "SELECT details FROM audit_event WHERE action='identity.password.rotate'"
    )
    assert new_password not in str(event[0])
    assert token not in str(event[0])


def test_new_logins_bound_active_sessions_and_invalidate_the_oldest(client: TestClient) -> None:
    tokens = []
    assert isinstance(client.app, FastAPI)
    for _ in range(9):
        login(client, "viewer")
        tokens.append(client.cookies["iphi_session"])
        client.app.state.auth._wall.current += timedelta(seconds=61)
    client.cookies.clear()
    client.cookies.set("iphi_session", tokens[0])
    assert client.get("/api/v1/auth/me").status_code == 401
    client.cookies.clear()
    client.cookies.set("iphi_session", tokens[1])
    assert client.get("/api/v1/auth/me").status_code == 200


def test_every_authenticated_mutation_requires_csrf(client: TestClient, platform: Platform) -> None:
    login(client, "admin")
    incident = client.get("/api/v1/incidents").json()["items"][0]["id"]
    unknown = str(uuid.uuid7())
    cases = [
        ("/simulations/scenarios", {"scenario_key": "latency_rise"}),
        (f"/simulations/runs/{unknown}/stop", {}),
        ("/simulations/clock", {"action": "advance", "seconds": 30}),
        ("/simulations/reset", {}),
        (f"/incidents/{incident}/ack", {}),
        (f"/incidents/{incident}/resolve", {"comment": "Inspection complete."}),
        (f"/incidents/{incident}/comments", {"comment": "Inspection note."}),
        (f"/incidents/{incident}/diagnose?mode=deterministic", {}),
        (f"/incidents/{incident}/diagnose?mode=llm", {}),
        ("/auth/logout", {}),
    ]
    for path, body in cases:
        response = client.post("/api/v1" + path, json=body)
        assert response.status_code == 403, (path, response.text)
        assert response.json()["code"] == "CSRF_REJECTED"
    assert client.get("/api/v1/auth/me").status_code == 200
    assert len(platform.rows("SELECT id FROM audit_event WHERE outcome='denied'")) == len(cases)


@pytest.mark.parametrize("invalidation", ["logout", "expiry"])
def test_existing_sse_closes_before_sending_more_data_after_session_invalidation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, invalidation: str
) -> None:
    headers = login(client, "viewer")
    token = client.cookies["iphi_session"]
    elapsed = iter([0.0, 16.0])
    monkeypatch.setattr(events, "time", SimpleNamespace(monotonic=lambda: next(elapsed)))
    app = client.app
    assert isinstance(app, FastAPI)
    request = Request(
        {
            "type": "http",
            "app": app,
            "headers": [(b"cookie", f"iphi_session={token}".encode())],
        }
    )

    async def exercise() -> None:
        queue: asyncio.Queue[Notice | None] = asyncio.Queue()
        sync = Notice(NoticeType.SYNC, "sync", datetime(2026, 11, 19, tzinfo=UTC))
        stream = events.events_stream(request, (queue, sync))
        await anext(stream)
        if invalidation == "logout":
            assert client.post("/api/v1/auth/logout", json={}, headers=headers).status_code == 204
        else:
            app.state.auth._wall.current += timedelta(hours=9)
        queue.put_nowait(Notice(NoticeType.COMPONENT, "after-invalidation", sync.platform_time))
        with pytest.raises(StopAsyncIteration):
            await anext(stream)

    asyncio.run(exercise())
