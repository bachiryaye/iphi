from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.exceptions import IphiError
from app.identity.domain import AuditAction, AuditContext, AuditEntry, AuditOutcome
from app.identity.repository import AuditEventRepository


class AuditLog:
    """Audit rows written in the caller's unit of work: an action and its audit commit together."""

    def __init__(self, session: Session) -> None:
        self._repository = AuditEventRepository(session)

    def record(self, entry: AuditEntry) -> None:
        self._repository.add(entry)


@dataclass(slots=True)
class AuditDraft:
    """What the audit row of a mutation will say, filled in while the mutation runs."""

    platform_time: datetime | None = None
    target_type: str | None = None
    target_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def entry(
        self, context: AuditContext, action: AuditAction, outcome: AuditOutcome, at: datetime
    ) -> AuditEntry:
        return AuditEntry(
            context,
            action,
            outcome,
            at,
            self.platform_time,
            self.target_type,
            self.target_id,
            dict(self.details),
        )


@dataclass(frozen=True, slots=True)
class AuditedWork:
    session: Session
    wall_now: datetime
    audit: AuditDraft


class AuditedMutations:
    """Units of work audited as `allowed` when they commit, and as `failed` in a transaction of
    their own when a domain error refuses them (X-14)."""

    def __init__(self, session_factory: sessionmaker[Session], wall: Clock) -> None:
        self._session_factory = session_factory
        self._wall = wall

    @contextmanager
    def run(self, context: AuditContext, action: AuditAction) -> Iterator[AuditedWork]:
        wall_now = self._wall.now()
        draft = AuditDraft()
        try:
            with self._session_factory.begin() as session:
                yield AuditedWork(session, wall_now, draft)
                AuditLog(session).record(
                    draft.entry(context, action, AuditOutcome.ALLOWED, wall_now)
                )
        except IphiError as exc:
            draft.details["error_code"] = exc.code
            with self._session_factory.begin() as session:
                AuditLog(session).record(
                    draft.entry(context, action, AuditOutcome.FAILED, wall_now)
                )
            raise


class AuditService:
    def __init__(self, session_factory: sessionmaker[Session], wall: Clock) -> None:
        self._session_factory = session_factory
        self._wall = wall

    def record_denied(self, context: AuditContext, action: AuditAction, reason: str) -> None:
        entry = AuditEntry(
            context=context,
            action=action,
            outcome=AuditOutcome.DENIED,
            occurred_at=self._wall.now(),
            platform_time=None,
            target_type=None,
            target_id=None,
            details={"reason": reason},
        )
        with self._session_factory.begin() as session:
            AuditLog(session).record(entry)
