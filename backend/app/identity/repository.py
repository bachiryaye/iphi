import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.db import Base, check_in
from app.identity.domain import AuditEntry, AuditOutcome


class AuditEventRecord(Base):
    """Append-only: a database trigger rejects UPDATE and DELETE (migration 0001)."""

    __tablename__ = "audit_event"
    __table_args__ = (
        CheckConstraint(check_in("outcome", AuditOutcome), name="outcome"),
        Index("ix_audit_event_occurred_at", text("occurred_at DESC")),
        Index("ix_audit_event_action", "action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    occurred_at: Mapped[datetime]
    platform_time: Mapped[datetime | None]
    actor_id: Mapped[uuid.UUID | None]
    actor_label: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(8))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class AuditEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: AuditEntry) -> None:
        self._session.add(
            AuditEventRecord(
                occurred_at=entry.occurred_at,
                platform_time=entry.platform_time,
                actor_id=entry.context.actor_id,
                actor_label=entry.context.actor_label,
                action=entry.action,
                target_type=entry.target_type,
                target_id=entry.target_id,
                outcome=entry.outcome.value,
                correlation_id=entry.context.correlation_id,
                details=dict(entry.details),
            )
        )
