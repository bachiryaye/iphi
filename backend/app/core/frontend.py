"""Optional same-origin delivery of the compiled React application (ADR 0028)."""

from http import HTTPStatus
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

FRONTEND_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)
_PUBLIC_FILES = frozenset({"index.html", "favicon.svg", "theme-init.js"})
_RESERVED_ROOTS = frozenset({"api", "health", "ready", "docs", "redoc"})
_ASSET_SUFFIXES = frozenset(
    {".js", ".css", ".woff2", ".woff", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico"}
)
ASSET_CACHE = "public, max-age=31536000, immutable"


class FrontendFiles(StaticFiles):
    """Serve only build assets and HTML navigations; API misses stay structured errors."""

    def __init__(self, directory: Path) -> None:
        super().__init__(directory=directory, follow_symlink=False)
        if not (directory / "index.html").is_file():
            raise RuntimeError("The configured frontend build must contain index.html.")

    async def get_response(self, path: str, scope: Scope) -> Response:
        path = "" if path == "." else path
        parts = path.split("/")
        if any(part.startswith(".") for part in parts) or parts[0] in _RESERVED_ROOTS:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        if scope["method"] not in {"GET", "HEAD"}:
            raise HTTPException(HTTPStatus.METHOD_NOT_ALLOWED)
        asset = path.startswith("assets/") and Path(path).suffix in _ASSET_SUFFIXES
        if asset or path in _PUBLIC_FILES:
            response = await super().get_response(path, scope)
        elif self._is_navigation(path, scope):
            response = await super().get_response("index.html", scope)
        else:
            raise HTTPException(HTTPStatus.NOT_FOUND)
        response.headers["content-security-policy"] = FRONTEND_CSP
        response.headers["cache-control"] = ASSET_CACHE if asset else "no-cache"
        return response

    @staticmethod
    def _is_navigation(path: str, scope: Scope) -> bool:
        if path.split("/", maxsplit=1)[0] == "assets" or "." in path:
            return False
        accept = next((v for k, v in scope["headers"] if k == b"accept"), b"")
        return path == "" or b"text/html" in accept
