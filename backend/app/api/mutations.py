"""Mutation guard while the API is unauthenticated (ADR 0007); US-11 swaps in RBAC."""

from collections.abc import Callable
from http import HTTPStatus

from fastapi import Request

from app.core.errors import correlation_id_of
from app.core.exceptions import IphiError
from app.identity.domain import (
    DEV_ACTOR,
    AuditAction,
    AuditContext,
    MutationPolicy,
    MutationsDisabledError,
)
from app.identity.service import AuditService


def audit_context(request: Request) -> AuditContext:
    return AuditContext(DEV_ACTOR, correlation_id_of(request.scope))


class CrossSiteRequestError(IphiError):
    status = HTTPStatus.FORBIDDEN
    code = "CROSS_SITE_REQUEST"


class JsonRequiredError(IphiError):
    status = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "JSON_REQUIRED"


def browser_forgery(request: Request) -> IphiError | None:
    """Refuses requests another web page could forge while mutations are unauthenticated.

    A JSON content type is not a CORS "simple" request: browsers preflight it, and the API
    answers no preflight, so a foreign page cannot send it. Sec-Fetch-Site rejects the rest.
    """
    if request.headers.get("sec-fetch-site", "same-origin") not in {"same-origin", "none"}:
        return CrossSiteRequestError("Mutations are accepted from the IPHI interface only.")
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type != "application/json":
        return JsonRequiredError("Mutations require Content-Type: application/json.")
    return None


def mutation(action: AuditAction) -> Callable[[Request], AuditContext]:
    """Dependency enforcing ADR 0007; denied attempts are audited (X-14). US-11 swaps in RBAC."""

    def guard(request: Request) -> AuditContext:
        context = audit_context(request)
        policy: MutationPolicy = request.app.state.mutation_policy
        refusal = browser_forgery(request)
        if refusal is None and not policy.enabled:
            refusal = MutationsDisabledError(policy.reason)
        if refusal is not None:
            audit: AuditService = request.app.state.audit
            audit.record_denied(context, action, refusal.detail)
            raise refusal
        return context

    return guard
