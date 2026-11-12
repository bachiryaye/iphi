"""RFC 9457 problem details (rules.md S-07, C-06, X-06)."""

from http import HTTPStatus
from typing import cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import Scope

PROBLEM_MEDIA_TYPE = "application/problem+json"

log = structlog.get_logger(__name__)


class FieldError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class Problem(BaseModel):
    type: str = Field(description="URN identifying the problem type.")
    title: str
    status: int
    detail: str
    code: str = Field(description="Stable machine-readable error code.")
    correlation_id: str | None
    errors: list[FieldError] = Field(default_factory=list)


class IphiError(Exception):
    """Base for domain errors; subclasses fix `status` and `code`, mapped once here."""

    status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def problem_type(code: str) -> str:
    return f"urn:iphi:problem:{code.lower().replace('_', '-')}"


def correlation_id_of(scope: Scope) -> str | None:
    value = scope.get("state", {}).get("correlation_id")
    return value if isinstance(value, str) else None


def problem_response(
    status: HTTPStatus,
    code: str,
    detail: str,
    correlation_id: str | None,
    errors: list[FieldError] | None = None,
) -> JSONResponse:
    body = Problem(
        type=problem_type(code),
        title=status.phrase,
        status=status.value,
        detail=detail,
        code=code,
        correlation_id=correlation_id,
        errors=errors or [],
    )
    return JSONResponse(
        body.model_dump(mode="json"), status_code=status.value, media_type=PROBLEM_MEDIA_TYPE
    )


async def _handle_iphi_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(IphiError, exc)
    log.info("http.domain_error", code=exc.code, status=exc.status.value)
    return problem_response(exc.status, exc.code, exc.detail, correlation_id_of(request.scope))


async def _handle_http_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    status = HTTPStatus(exc.status_code)
    return problem_response(
        status, status.name, status.description, correlation_id_of(request.scope)
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    errors = [
        FieldError(loc=list(err["loc"]), msg=err["msg"], type=err["type"]) for err in exc.errors()
    ]
    return problem_response(
        HTTPStatus.UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "The request is invalid; see errors.",
        correlation_id_of(request.scope),
        errors,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IphiError, _handle_iphi_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
