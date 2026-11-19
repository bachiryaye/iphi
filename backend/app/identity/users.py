import uuid

from pydantic import SecretStr
from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.core.settings import Settings
from app.identity.auth_domain import Role
from app.identity.auth_repository import SessionRecord, UserRecord
from app.identity.domain import AuditAction, AuditContext, AuditEntry, AuditOutcome
from app.identity.passwords import HASHER, password_matches
from app.identity.service import AuditLog


def ensure_users(factory: sessionmaker[Session], wall: Clock, settings: Settings) -> None:
    """Explicit operator environment seeds demo credentials; changing one revokes its sessions."""
    credentials: tuple[tuple[Role, SecretStr], ...] = (
        (Role.VIEWER, settings.demo_viewer_password),
        (Role.ENGINEER, settings.demo_engineer_password),
        (Role.ADMIN, settings.demo_admin_password),
    )
    for role, secret in credentials:
        password = secret.get_secret_value()
        if password and not 12 <= len(password) <= 128:
            raise ValueError(f"The configured {role.value} demo password needs 12-128 characters.")
    with factory.begin() as session:
        for role, secret in credentials:
            if not secret.get_secret_value():
                continue
            now = wall.now()
            user = session.scalar(select(UserRecord).where(UserRecord.username == role.value))
            action = None
            if user is None:
                user = UserRecord(
                    id=uuid.uuid7(),
                    username=role.value,
                    display_name=f"Demo {role.value}",
                    role=role.value,
                    password_hash=HASHER.hash(secret.get_secret_value()),
                    is_active=True,
                    created_at=now,
                )
                session.add(user)
                action = AuditAction.USER_SEED
            elif not password_matches(user.password_hash, secret):
                user.password_hash = HASHER.hash(secret.get_secret_value())
                session.execute(
                    update(SessionRecord)
                    .where(SessionRecord.user_id == user.id)
                    .values(revoked_at=now)
                )
                action = AuditAction.PASSWORD_ROTATE
            if action is not None:
                AuditLog(session).record(
                    AuditEntry(
                        AuditContext("bootstrap", None),
                        action,
                        AuditOutcome.ALLOWED,
                        now,
                        None,
                        "user",
                        str(user.id),
                        {"source": "operator_environment"},
                    )
                )
