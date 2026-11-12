from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr

from app.core.middleware import MAX_BODY_BYTES
from app.core.settings import Settings
from app.main import create_app
from app.monitor.domain import CheckName, CheckStatus, ReadinessCheck, ReadinessReport

NOW = datetime(2026, 11, 12, 10, 42, 7, tzinfo=UTC)


class Note(BaseModel):
    text: str


class StubReadiness:
    def __init__(self, *statuses: CheckStatus) -> None:
        names = list(CheckName)
        self._checks = tuple(
            ReadinessCheck(names[i], status, "stub") for i, status in enumerate(statuses)
        )

    def check(self) -> ReadinessReport:
        return ReadinessReport(NOW, 5.0, self._checks)


@pytest.fixture
def app() -> FastAPI:
    settings = Settings(database_url=SecretStr("postgresql+psycopg://unit@localhost/unused"))
    application = create_app(settings)
    application.state.readiness = StubReadiness(CheckStatus.OK, CheckStatus.OK)

    @application.get("/_test/items")
    def items(limit: int) -> dict[str, int]:
        return {"limit": limit}

    @application.post("/_test/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @application.post("/_test/notes")
    def notes(note: Note) -> dict[str, int]:
        return {"length": len(note.text)}

    @application.get("/_test/crash")
    def crash() -> None:
        raise RuntimeError("secret internal detail")

    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False) as test_client:
        yield test_client


def test_liveness_answers_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_with_utc_checks_when_all_pass(client: TestClient) -> None:
    response = client.get("/ready")

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["checked_at"] == "2026-11-12T10:42:07Z"
    assert [c["name"] for c in body["checks"]] == ["database", "migrations"]


def test_ready_returns_503_when_a_check_fails(app: FastAPI, client: TestClient) -> None:
    app.state.readiness = StubReadiness(CheckStatus.OK, CheckStatus.FAILED)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_unknown_route_returns_problem_details(client: TestClient) -> None:
    response = client.get("/api/v1/nope")

    body = response.json()
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert body["code"] == "NOT_FOUND"
    assert body["type"] == "urn:iphi:problem:not-found"
    assert body["correlation_id"] == response.headers["x-correlation-id"]


def test_validation_error_lists_field_errors(client: TestClient) -> None:
    response = client.get("/_test/items", params={"limit": "many"})

    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "VALIDATION_ERROR"
    assert body["errors"][0]["loc"] == ["query", "limit"]


def test_unhandled_error_hides_internals(client: TestClient) -> None:
    response = client.get("/_test/crash", headers={"X-Correlation-ID": "trace-crash-0001"})

    body = response.json()
    assert response.status_code == 500
    assert body["code"] == "INTERNAL_ERROR"
    assert body["correlation_id"] == "trace-crash-0001"
    assert "secret" not in response.text
    assert "Traceback" not in response.text


def test_valid_correlation_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "req-2026-11-12.a"})

    assert response.headers["x-correlation-id"] == "req-2026-11-12.a"


@pytest.mark.parametrize("supplied", ["short", "has spaces in it", "x" * 65, "inject\r\nheader"])
def test_invalid_correlation_id_is_replaced(client: TestClient, supplied: str) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": supplied})

    assert response.headers["x-correlation-id"] != supplied
    assert len(response.headers["x-correlation-id"]) == 32


def test_declared_oversized_body_is_rejected(client: TestClient) -> None:
    response = client.post("/_test/echo", content=b"x" * (MAX_BODY_BYTES + 1))

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_streamed_oversized_body_is_rejected(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(5):
            yield b"x" * (MAX_BODY_BYTES // 4)

    response = client.post("/_test/echo", content=chunks())

    assert response.status_code == 413


def test_streamed_oversized_typed_body_is_rejected_as_too_large(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"text": "'
        for _ in range(5):
            yield b"x" * (MAX_BODY_BYTES // 4)
        yield b'"}'

    response = client.post(
        "/_test/notes", content=chunks(), headers={"content-type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_body_within_limit_is_accepted(client: TestClient) -> None:
    response = client.post("/_test/echo", content=b"x" * MAX_BODY_BYTES)

    assert response.json() == {"size": MAX_BODY_BYTES}


def test_api_responses_carry_security_headers(client: TestClient) -> None:
    headers = client.get("/health").headers

    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/_test/echo", b"x" * (MAX_BODY_BYTES + 1)),
        ("GET", "/_test/crash", None),
        ("GET", "/nope", None),
    ],
)
def test_error_responses_carry_security_headers(
    client: TestClient, method: str, path: str, body: bytes | None
) -> None:
    headers = client.request(method, path, content=body).headers

    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert headers["cache-control"] == "no-store"


def test_openapi_is_served_under_api_prefix(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    assert "/ready" in response.json()["paths"]
