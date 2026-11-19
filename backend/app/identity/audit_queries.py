import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session, sessionmaker

from app.identity.domain import AuditAction, AuditContext, AuditEntry, AuditEvent, AuditOutcome
from app.identity.repository import AuditEventRecord


@dataclass(frozen=True, slots=True)
class AuditFilter:
    start: datetime
    end: datetime
    action: AuditAction | None
    outcome: AuditOutcome | None
    actor: str | None
    before: tuple[datetime, uuid.UUID] | None
    limit: int


class AuditQueries:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def page(self, filters: AuditFilter) -> list[AuditEvent]:
        query = select(AuditEventRecord).where(
            AuditEventRecord.occurred_at >= filters.start,
            AuditEventRecord.occurred_at <= filters.end,
        )
        if filters.action is not None:
            query = query.where(AuditEventRecord.action == filters.action.value)
        if filters.outcome is not None:
            query = query.where(AuditEventRecord.outcome == filters.outcome.value)
        if filters.actor is not None:
            query = query.where(AuditEventRecord.actor_label == filters.actor)
        if filters.before is not None:
            query = query.where(
                tuple_(AuditEventRecord.occurred_at, AuditEventRecord.id) < filters.before
            )
        query = query.order_by(AuditEventRecord.occurred_at.desc(), AuditEventRecord.id.desc())
        with self._factory() as session:
            return [
                AuditEvent(
                    row.id,
                    AuditEntry(
                        AuditContext(row.actor_label, row.correlation_id, row.actor_id),
                        AuditAction(row.action),
                        AuditOutcome(row.outcome),
                        row.occurred_at,
                        row.platform_time,
                        row.target_type,
                        row.target_id,
                        dict(row.details),
                    ),
                )
                for row in session.scalars(query.limit(filters.limit + 1))
            ]
