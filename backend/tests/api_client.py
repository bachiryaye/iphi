from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.clock import WallClock
from app.core.db import create_db_engine, create_session_factory
from app.core.settings import Settings
from app.identity.users import ensure_users
from app.main import create_app

TEST_PASSWORD = "test-only-session-password"


def sign_in(client: TestClient, database_url: str, role: str = "admin") -> None:
    settings = Settings(
        database_url=SecretStr(database_url),
        demo_viewer_password=SecretStr(TEST_PASSWORD),
        demo_engineer_password=SecretStr(TEST_PASSWORD),
        demo_admin_password=SecretStr(TEST_PASSWORD),
    )
    engine = create_db_engine(settings)
    try:
        ensure_users(create_session_factory(engine), WallClock(), settings)
    finally:
        engine.dispose()
    response = client.post("/api/v1/auth/login", json={"username": role, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["x-csrf-token"] = response.json()["csrf_token"]


def client_for(database_url: str, *, role: str) -> TestClient:
    """The real session-authenticated API; callers explicitly choose the exercised role."""
    settings = Settings(database_url=SecretStr(database_url))
    client = TestClient(
        create_app(settings), base_url="http://127.0.0.1", raise_server_exceptions=False
    )
    sign_in(client, database_url, role)
    return client
