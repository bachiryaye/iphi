import uuid
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import AwareDatetime, BaseModel, Field, model_validator

from app.api.auth import context_of, require_session
from app.api.pagination import (
    cursor_instant,
    decode_cursor,
    encode_cursor,
    encode_instant,
    malformed_cursor,
)
from app.identity.audit_queries import AuditFilter, AuditQueries
from app.identity.auth_domain import PermissionDeniedError, Role, SignedIn
from app.identity.domain import AuditAction, AuditOutcome

router = APIRouter(prefix="/api/v1/audit-events", tags=["identity"])


class AuditQuery(BaseModel):
    start: AwareDatetime | None = Field(default=None, alias="from")
    end: AwareDatetime | None = Field(default=None, alias="to")
    action: AuditAction | None = None
    outcome: AuditOutcome | None = None
    actor: str | None = Field(default=None, min_length=1, max_length=64)
    cursor: str | None = Field(default=None, max_length=128)
    limit: int = Field(default=50, ge=1, le=200)

    @model_validator(mode="after")
    def window(self) -> AuditQuery:
        if (self.start is None) != (self.end is None):
            raise ValueError("Specify both audit time bounds, or neither.")
        if (
            self.start is not None
            and self.end is not None
            and (self.end < self.start or self.end - self.start > timedelta(days=7))
        ):
            raise ValueError("The audit window must be ordered and at most seven days.")
        return self


class AuditEventOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    platform_time: datetime | None
    actor_label: str
    actor_id: uuid.UUID | None
    action: str
    outcome: AuditOutcome
    target_type: str | None
    target_id: str | None
    correlation_id: str | None
    details: dict[str, Any]


class AuditListOut(BaseModel):
    environment: str = "simulation"
    items: list[AuditEventOut]
    next_cursor: str | None


@router.get("", summary="Admin-only bounded audit journal with stable cursor pagination.")
def audit_events(
    request: Request,
    query: Annotated[AuditQuery, Query()],
    identity: Annotated[SignedIn, Depends(require_session)],
) -> AuditListOut:
    if not identity.user.permits(Role.ADMIN):
        refusal = PermissionDeniedError("The audit journal requires admin. The refusal is audited.")
        request.app.state.audit.record_denied(
            context_of(request, identity), AuditAction.AUDIT_READ, refusal.detail
        )
        raise refusal
    before = None
    if query.cursor is not None:
        instant, identifier = decode_cursor("audit", query.cursor, 2)
        try:
            before = (cursor_instant(instant), uuid.UUID(identifier))
        except ValueError as exc:
            raise malformed_cursor() from exc
    end = query.end or request.app.state.wall.now()
    start = query.start or end - timedelta(days=1)
    service: AuditQueries = request.app.state.audit_queries
    rows = service.page(
        AuditFilter(start, end, query.action, query.outcome, query.actor, before, query.limit)
    )
    more = len(rows) > query.limit
    rows = rows[: query.limit]
    return AuditListOut(
        items=[
            AuditEventOut(
                id=r.id,
                occurred_at=r.entry.occurred_at,
                platform_time=r.entry.platform_time,
                actor_label=r.entry.context.actor_label,
                actor_id=r.entry.context.actor_id,
                action=r.entry.action,
                outcome=r.entry.outcome,
                target_type=r.entry.target_type,
                target_id=r.entry.target_id,
                correlation_id=r.entry.context.correlation_id,
                details=dict(r.entry.details),
            )
            for r in rows
        ],
        next_cursor=encode_cursor(
            "audit", encode_instant(rows[-1].entry.occurred_at), str(rows[-1].id)
        )
        if more
        else None,
    )
