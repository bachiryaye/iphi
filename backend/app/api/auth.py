from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, Security
from fastapi.security import APIKeyCookie
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.api.request_policy import browser_forgery
from app.core.errors import correlation_id_of
from app.core.exceptions import IphiError
from app.identity.auth_domain import CsrfRejectedError, Role, SignedIn
from app.identity.auth_service import SESSION_HOURS, AuthService
from app.identity.domain import AuditAction, AuditContext
from app.identity.passwords import csrf_for, csrf_matches

COOKIE_NAME = "iphi_session"
cookie = APIKeyCookie(name=COOKIE_NAME, auto_error=False)
SessionToken = Annotated[str | None, Security(cookie)]
router = APIRouter(prefix="/api/v1/auth", tags=["identity"])


def auth_service(request: Request) -> AuthService:
    service: AuthService = request.app.state.auth
    return service


def authenticate(request: Request, token: str | None) -> SignedIn:
    existing: SignedIn | None = getattr(request.state, "identity", None)
    if existing is not None:
        return existing
    result = auth_service(request).resolve(token)
    request.state.identity = result
    return result


def require_session(request: Request, token: SessionToken) -> SignedIn:
    return authenticate(request, token)


def require_read(request: Request, token: SessionToken) -> None:
    if request.method in {"GET", "HEAD"}:
        authenticate(request, token)


def context_of(request: Request, identity: SignedIn) -> AuditContext:
    return AuditContext(identity.user.username, correlation_id_of(request.scope), identity.user.id)


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=32, pattern=r"^[a-z0-9][a-z0-9._-]*$")
    password: SecretStr = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    username: str
    display_name: str
    role: Role


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime

    @classmethod
    def of(cls, identity: SignedIn) -> SessionOut:
        return cls(
            user=UserOut(
                username=identity.user.username,
                display_name=identity.user.display_name,
                role=identity.user.role,
            ),
            csrf_token=csrf_for(identity.token),
            expires_at=identity.expires_at,
        )


@router.post("/login", summary="Sign in with a server-side session.")
def login(request: Request, response: Response, body: LoginIn) -> SessionOut:
    refusal = browser_forgery(request)
    if refusal is not None:
        request.app.state.audit.record_denied(
            AuditContext("anonymous", correlation_id_of(request.scope)),
            AuditAction.AUTH_LOGIN,
            refusal.detail,
        )
        raise refusal
    identity = auth_service(request).sign_in(
        body.username, body.password, correlation_id_of(request.scope)
    )
    response.set_cookie(
        COOKIE_NAME,
        identity.token,
        max_age=SESSION_HOURS * 3600,
        httponly=True,
        secure=request.app.state.cookie_secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return SessionOut.of(identity)


@router.get("/me", summary="Current session, role and CSRF proof.")
def me(response: Response, identity: Annotated[SignedIn, Depends(require_session)]) -> SessionOut:
    response.headers["Cache-Control"] = "no-store"
    return SessionOut.of(identity)


@router.post("/logout", status_code=204, summary="Revoke the current server session.")
def logout(request: Request, response: Response, token: SessionToken) -> None:
    context = AuditContext("anonymous", correlation_id_of(request.scope))
    try:
        identity = authenticate(request, token)
        context = context_of(request, identity)
        refusal = browser_forgery(request)
        if refusal is not None:
            raise refusal
        if not csrf_matches(identity.token, request.headers.get("x-csrf-token", "")):
            raise CsrfRejectedError("The session CSRF proof is missing or invalid.")
    except IphiError as exc:
        request.app.state.audit.record_denied(context, AuditAction.AUTH_LOGOUT, exc.detail)
        raise
    auth_service(request).sign_out(identity, context)
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        secure=request.app.state.cookie_secure,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
