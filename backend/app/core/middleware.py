"""Pure ASGI middleware: correlation IDs, request bounds and security headers."""

import re
import time
import uuid
from http import HTTPStatus

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import problem_response

CORRELATION_HEADER = "x-correlation-id"
_CORRELATION_HEADER_RAW = CORRELATION_HEADER.encode()
# Client-supplied IDs are echoed into logs and audit rows, so they are constrained (X-03).
_CORRELATION_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")

MAX_BODY_BYTES = 64 * 1024

API_SECURITY_HEADERS = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
    "x-frame-options": "DENY",
    "cache-control": "no-store",
}
# Swagger UI and ReDoc load their bundles from a CDN; only those pages get a wider policy.
DOCS_PATHS = frozenset({"/docs", "/redoc"})
DOCS_CSP = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: "
    "https://fastapi.tiangolo.com; connect-src 'self'; frame-ancestors 'none'"
)

log = structlog.get_logger(__name__)


def _incoming_correlation_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers", []):
        if name == _CORRELATION_HEADER_RAW:
            candidate = value.decode("latin-1")
            return candidate if _CORRELATION_ID.fullmatch(candidate) else None
    return None


class CorrelationIdMiddleware:
    """Outermost middleware: binds the correlation ID, logs each request, contains crashes.

    It is the process boundary for HTTP (C-14): an unhandled error is logged with context and
    answered as a 500 problem without internal details (X-06).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = _incoming_correlation_id(scope) or uuid.uuid7().hex
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        started = time.perf_counter()
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR.value
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message)[CORRELATION_HEADER] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            log.exception("http.unhandled_error", method=scope["method"], path=scope["path"])
            if not response_started:
                response = problem_response(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "INTERNAL_ERROR",
                    "An internal error occurred; quote the correlation ID when reporting it.",
                    correlation_id,
                )
                await response(scope, receive, send_with_id)
        finally:
            log.info(
                "http.request",
                method=scope["method"],
                path=scope["path"],
                status=status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.unbind_contextvars("correlation_id")


class BodySizeLimitMiddleware:
    """Rejects request bodies above MAX_BODY_BYTES (X-03), declared or streamed."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self._declared_length(scope) > self.max_bytes:
            await self._reject(scope, receive, send)
            return

        received = 0
        rejected = False

        # Raising from receive() would reach FastAPI's body parser, which turns any error into
        # a 400. The 413 is sent here instead and the app sees a client disconnect.
        async def bounded_receive() -> Message:
            nonlocal received, rejected
            if rejected:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    rejected = True
                    await self._reject(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not rejected:
                await send(message)

        await self.app(scope, bounded_receive, guarded_send)

    @staticmethod
    def _declared_length(scope: Scope) -> int:
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                return int(value) if value.isdigit() else 0
        return 0

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        state = scope.get("state", {})
        response = problem_response(
            HTTPStatus.CONTENT_TOO_LARGE,
            "PAYLOAD_TOO_LARGE",
            f"Request bodies are limited to {self.max_bytes} bytes.",
            state.get("correlation_id"),
        )
        await response(scope, receive, send)


class SecurityHeadersMiddleware:
    """Baseline response headers for the API (X-11); the frontend server sets its own CSP."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_docs = scope["path"] in DOCS_PATHS

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in API_SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
                if is_docs:
                    headers["content-security-policy"] = DOCS_CSP
            await send(message)

        await self.app(scope, receive, send_with_headers)
