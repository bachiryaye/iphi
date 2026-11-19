"""Session, role and CSRF authorization; every denied mutation is audited (US-11)."""

from collections.abc import Callable

from fastapi import Request

from app.api.auth import SessionToken, authenticate, context_of
from app.api.request_policy import browser_forgery
from app.core.errors import correlation_id_of
from app.core.exceptions import IphiError
from app.identity.auth_domain import CsrfRejectedError, PermissionDeniedError, Role
from app.identity.domain import AuditAction, AuditContext
from app.identity.passwords import csrf_matches
from app.identity.service import AuditService


def mutation(action: AuditAction) -> Callable[..., AuditContext]:
    def guard(request: Request, token: SessionToken) -> AuditContext:
        context = AuditContext("anonymous", correlation_id_of(request.scope))
        try:
            identity = authenticate(request, token)
            context = context_of(request, identity)
            required = Role.ADMIN if action is AuditAction.SIMULATION_RESET else Role.ENGINEER
            if not identity.user.permits(required):
                raise PermissionDeniedError(
                    f"This action requires the {required.value} role. The refusal is audited."
                )
            refusal = browser_forgery(request)
            if refusal is not None:
                raise refusal
            if not csrf_matches(identity.token, request.headers.get("x-csrf-token", "")):
                raise CsrfRejectedError(
                    "The session CSRF proof is missing or invalid. The refusal is audited."
                )
        except IphiError as exc:
            audit: AuditService = request.app.state.audit
            audit.record_denied(context, action, exc.detail)
            raise
        return context

    return guard
