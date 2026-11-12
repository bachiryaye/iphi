from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.settings import Settings
from app.main import create_app


def client_for(database_url: str, *, dev_mutations: bool) -> TestClient:
    """The API as served locally: loopback host, so TrustedHostMiddleware accepts it."""
    settings = Settings(database_url=SecretStr(database_url), dev_mutations=dev_mutations)
    return TestClient(
        create_app(settings), base_url="http://127.0.0.1", raise_server_exceptions=False
    )
