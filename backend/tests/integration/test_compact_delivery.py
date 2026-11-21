from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from app.core.settings import Settings
from app.main import create_app
from tests.api_client import sign_in

pytestmark = pytest.mark.integration


@pytest.fixture
def compact_api(seeded_url: str, tmp_path: Path) -> Iterator[TestClient]:
    (tmp_path / "index.html").write_text("<!doctype html><html>Compiled dashboard</html>")
    settings = Settings(
        database_url=SecretStr(seeded_url.replace("postgresql+psycopg://", "postgresql://")),
        deployment_mode="production",
        allowed_hosts="frontend.test,127.0.0.1",
        frontend_dir=tmp_path,
    )
    with TestClient(create_app(settings), base_url="https://frontend.test") as client:
        yield client


def test_compact_https_session_keeps_viewer_permissions_and_audited_denials(
    compact_api: TestClient, seeded_url: str
) -> None:
    public = compact_api.get("/help", headers={"accept": "text/html"})
    assert public.status_code == 200
    assert public.headers["cache-control"] == "no-cache"
    assert compact_api.get("/api/v1/components").status_code == 401
    sign_in(compact_api, seeded_url, "viewer")

    cookie = next(c for c in compact_api.cookies.jar if c.name == "iphi_session")
    assert cookie.secure
    assert cookie.has_nonstandard_attr("HttpOnly")
    assert cookie.get_nonstandard_attr("SameSite") == "strict"
    assert compact_api.get("/api/v1/components").status_code == 200
    denied = compact_api.post(
        "/api/v1/simulations/scenarios", json={"scenario_key": "collector_down"}
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "PERMISSION_DENIED"
    engine = create_engine(seeded_url)
    try:
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM audit_event "
                        "WHERE action='scenario.start' AND outcome='denied' "
                        "AND actor_label='viewer'"
                    )
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()


def test_compact_html_does_not_weaken_csrf_or_cache_authenticated_responses(
    compact_api: TestClient, seeded_url: str
) -> None:
    sign_in(compact_api, seeded_url, "admin")

    denied = compact_api.post(
        "/api/v1/simulations/scenarios",
        json={"scenario_key": "collector_down"},
        headers={"x-csrf-token": "incorrect", "accept": "text/html"},
    )
    me = compact_api.get("/api/v1/auth/me")

    assert denied.status_code == 403
    assert denied.headers["content-type"] == "application/problem+json"
    assert denied.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in denied.headers["content-security-policy"]
    assert me.status_code == 200
    assert me.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in me.headers["content-security-policy"]
