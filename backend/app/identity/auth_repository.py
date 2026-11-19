import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, check_in
from app.identity.auth_domain import Role, User


class UserRecord(Base):
    __tablename__ = "app_user"
    __table_args__ = (CheckConstraint(check_in("role", Role), name="role"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(8))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool]
    created_at: Mapped[datetime]

    def user(self) -> User:
        return User(self.id, self.username, self.display_name, Role(self.role))


class SessionRecord(Base):
    __tablename__ = "user_session"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry"),
        Index("ix_user_session_expires_at", "expires_at"),
        Index("ix_user_session_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid7)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
