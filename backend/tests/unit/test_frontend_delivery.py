from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.frontend import ASSET_CACHE, FRONTEND_CSP
from app.core.settings import Settings
from app.main import create_app

INDEX = '<!doctype html><html><script src="/assets/app-12345678.js"></script></html>'


@pytest.fixture
def frontend_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "dist"
    assets = directory / "assets"
    assets.mkdir(parents=True)
    (directory / "index.html").write_text(INDEX)
    (directory / "theme-init.js").write_text("document.documentElement.dataset.theme = 'dark';")
    (directory / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (assets / "app-12345678.js").write_text("console.log('application');")
    (assets / "app-12345678.css").write_text("body { color: black; }")
    (assets / "plex-12345678.woff2").write_bytes(b"test font")
    (directory / ".env").write_text("PRIVATE_SENTINEL=must-not-be-served")
    (assets / "app-12345678.js.map").write_text("private source map")
    private = tmp_path / "private.js"
    private.write_text("private outside build")
    (assets / "linked-12345678.js").symlink_to(private)
    return directory


def compact_client(directory: Path | None) -> TestClient:
    settings = Settings(
        database_url=SecretStr("postgresql+psycopg://unit@localhost/unused"),
        frontend_dir=directory,
    )
    # Static delivery and missing-session refusal do not need a database or SSE listener.
    return TestClient(create_app(settings), base_url="http://127.0.0.1")


@pytest.mark.parametrize("path", ["/", "/help", "/login", "/components/abc", "/unknown-screen"])
def test_html_navigation_receives_the_build_with_the_existing_ui_policy(
    frontend_dir: Path, path: str
) -> None:
    with compact_client(frontend_dir) as client:
        response = client.get(path, headers={"accept": "text/html"})

    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-security-policy"] == FRONTEND_CSP
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-correlation-id"]


@pytest.mark.parametrize(
    ("path", "mime"),
    [
        ("/assets/app-12345678.js", "javascript"),
        ("/assets/app-12345678.css", "text/css"),
        ("/assets/plex-12345678.woff2", "font/woff2"),
    ],
)
def test_built_assets_keep_mime_types_and_immutable_conditional_caching(
    frontend_dir: Path, path: str, mime: str
) -> None:
    client = compact_client(frontend_dir)
    response = client.get(path)
    unchanged = client.get(path, headers={"if-none-match": response.headers["etag"]})

    assert response.status_code == 200
    assert mime in response.headers["content-type"]
    assert response.headers["cache-control"] == ASSET_CACHE
    assert unchanged.status_code == 304
    assert unchanged.headers["cache-control"] == ASSET_CACHE
    assert unchanged.headers["content-security-policy"] == FRONTEND_CSP
    assert unchanged.content == b""


def test_unhashed_theme_script_revalidates_and_head_has_no_body(frontend_dir: Path) -> None:
    client = compact_client(frontend_dir)

    script = client.get("/theme-init.js")
    navigation = client.head("/help", headers={"accept": "text/html"})

    assert script.headers["cache-control"] == "no-cache"
    assert navigation.status_code == 200
    assert navigation.content == b""
    assert navigation.headers["content-security-policy"] == FRONTEND_CSP


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/not-a-route",
        "/api/not-a-route",
        "/ready/not-a-route",
        "/assets/missing.js",
        "/assets/not-a-file",
        "/.env",
        "/.git/config",
        "/assets/app-12345678.js.map",
        "/assets/linked-12345678.js",
        "/assets/%2e%2e/%2e%2e/private.js",
        "/config.yaml",
    ],
)
def test_missing_api_assets_and_private_paths_never_fall_back_to_html(
    frontend_dir: Path, path: str
) -> None:
    response = compact_client(frontend_dir).get(path, headers={"accept": "text/html"})

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "NOT_FOUND"
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "private" not in response.text.lower()
    assert str(frontend_dir) not in response.text


def test_api_still_refuses_unauthenticated_requests_with_html_accept(frontend_dir: Path) -> None:
    response = compact_client(frontend_dir).get(
        "/api/v1/components", headers={"accept": "text/html"}
    )

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["cache-control"] == "no-store"


def test_static_mount_does_not_add_paths_to_the_api_contract(frontend_dir: Path) -> None:
    ordinary = compact_client(None).get("/api/v1/openapi.json").json()
    compact = compact_client(frontend_dir).get("/api/v1/openapi.json").json()

    assert compact == ordinary
    assert compact_client(None).get("/").status_code == 404


def test_post_to_a_frontend_page_is_not_a_mutation_endpoint(frontend_dir: Path) -> None:
    response = compact_client(frontend_dir).post("/help", content="unexpected")

    assert response.status_code == 405
    assert response.headers["content-type"] == "application/problem+json"


def test_configured_build_without_index_fails_at_startup(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match=r"must contain index\.html"):
        compact_client(tmp_path)


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_managed_postgres_url_preserves_credentials_and_tls_query(scheme: str) -> None:
    suffix = "unit:p%40ss@database:5432/iphi?sslmode=require&connect_timeout=10"

    settings = Settings(database_url=SecretStr(f"{scheme}://{suffix}"))

    assert settings.database_url.get_secret_value() == f"postgresql+psycopg://{suffix}"
    assert "p%40ss" not in repr(settings)


def test_compact_csp_matches_the_existing_frontend_server_policy() -> None:
    repository = Path(__file__).resolve().parents[3]
    nginx = (repository / "frontend/nginx/security-headers.conf").read_text()

    assert f'Content-Security-Policy "{FRONTEND_CSP}"' in nginx
    assert "unsafe-inline" not in FRONTEND_CSP
    assert "unsafe-eval" not in FRONTEND_CSP
