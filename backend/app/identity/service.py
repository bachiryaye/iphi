from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.identity.domain import AuditAction, AuditContext, AuditEntry, AuditOutcome
from app.identity.repository import AuditEventRepository


class AuditLog:
    """Audit rows written in the caller's unit of work: an action and its audit commit together."""

    def __init__(self, session: Session) -> None:
        self._repository = AuditEventRepository(session)

    def record(self, entry: AuditEntry) -> None:
        self._repository.add(entry)


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
