from datetime import timedelta

from pydantic import SecretStr
from sqlalchemy import delete, or_, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import Clock
from app.identity.auth_domain import (
    AuthenticationRequiredError,
    InvalidCredentialsError,
    LoginLimitedError,
    SignedIn,
)
from app.identity.auth_repository import SessionRecord, UserRecord
from app.identity.domain import AuditAction, AuditContext, AuditEntry, AuditOutcome
from app.identity.passwords import HASHER, TOKEN_PATTERN, new_token, password_matches, token_hash
from app.identity.repository import AuditEventRecord
from app.identity.service import AuditLog

LOGIN_LOCK = 0x1F4E_0011
SESSION_HOURS = 8


class AuthService:
    def __init__(self, factory: sessionmaker[Session], wall: Clock) -> None:
        self._factory = factory
        self._wall = wall
        self._dummy_hash = HASHER.hash(new_token())

    def sign_in(self, username: str, password: SecretStr, correlation_id: str | None) -> SignedIn:
        now = self._wall.now()
        refusal: InvalidCredentialsError | LoginLimitedError | None = None
        signed_in: SignedIn | None = None
        context = AuditContext("anonymous", correlation_id)
        with self._factory.begin() as session:
            # Serialize and bound expensive password checks across API processes.
            admitted = session.scalar(
                text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOGIN_LOCK}
            )
            if not admitted:
                refusal = LoginLimitedError("Sign-in is busy; try again shortly.")
            else:
                recent = select(AuditEventRecord).where(
                    AuditEventRecord.action == AuditAction.AUTH_LOGIN.value,
                    AuditEventRecord.occurred_at > now - timedelta(seconds=60),
                )
                attempts = session.scalars(recent.limit(21)).all()
                if len(attempts) >= 20 or sum(a.target_id == username for a in attempts) >= 6:
                    refusal = LoginLimitedError(
                        "Too many sign-in attempts; try again after a minute."
                    )
                else:
                    record = session.scalar(
                        select(UserRecord).where(UserRecord.username == username)
                    )
                    valid = password_matches(
                        record.password_hash if record else self._dummy_hash, password
                    )
                    if record is None or not valid or not record.is_active:
                        refusal = InvalidCredentialsError("The username or password is incorrect.")
                    else:
                        if HASHER.check_needs_rehash(record.password_hash):
                            record.password_hash = HASHER.hash(password.get_secret_value())
                        context = AuditContext(record.username, correlation_id, record.id)
                        token = new_token()
                        expires = now + timedelta(hours=SESSION_HOURS)
                        old = (
                            select(SessionRecord.id)
                            .where(
                                or_(
                                    SessionRecord.expires_at <= now,
                                    SessionRecord.revoked_at.is_not(None),
                                )
                            )
                            .limit(100)
                        )
                        session.execute(delete(SessionRecord).where(SessionRecord.id.in_(old)))
                        sessions = session.scalars(
                            select(SessionRecord)
                            .where(SessionRecord.user_id == record.id)
                            .order_by(SessionRecord.created_at.desc(), SessionRecord.id.desc())
                        ).all()
                        for previous in sessions[7:]:
                            session.delete(previous)
                        session.add(
                            SessionRecord(
                                token_hash=token_hash(token),
                                user_id=record.id,
                                created_at=now,
                                expires_at=expires,
                                revoked_at=None,
                            )
                        )
                        signed_in = SignedIn(record.user(), token, expires)
            AuditLog(session).record(
                AuditEntry(
                    context,
                    AuditAction.AUTH_LOGIN,
                    AuditOutcome.DENIED if refusal else AuditOutcome.ALLOWED,
                    now,
                    None,
                    "username",
                    username,
                    {"error_code": refusal.code} if refusal else {},
                )
            )
        if refusal is not None:
            raise refusal
        if signed_in is None:
            raise RuntimeError("A successful sign-in must produce a session.")
        return signed_in

    def resolve(self, token: str | None) -> SignedIn:
        if token is None or TOKEN_PATTERN.fullmatch(token) is None:
            raise AuthenticationRequiredError("Sign in to access the simulated platform.")
        with self._factory() as session:
            row = session.execute(
                select(UserRecord, SessionRecord)
                .join(SessionRecord, SessionRecord.user_id == UserRecord.id)
                .where(
                    SessionRecord.token_hash == token_hash(token),
                    SessionRecord.revoked_at.is_(None),
                    SessionRecord.expires_at > self._wall.now(),
                    UserRecord.is_active.is_(True),
                )
            ).one_or_none()
            if row is None:
                raise AuthenticationRequiredError("The session has expired. Sign in again.")
            user, record = row
            return SignedIn(user.user(), token, record.expires_at)

    def sign_out(self, signed_in: SignedIn, context: AuditContext) -> None:
        now = self._wall.now()
        with self._factory.begin() as session:
            record = session.scalar(
                select(SessionRecord)
                .where(SessionRecord.token_hash == token_hash(signed_in.token))
                .with_for_update()
            )
            if record is not None:
                record.revoked_at = now
            AuditLog(session).record(
                AuditEntry(
                    context,
                    AuditAction.AUTH_LOGOUT,
                    AuditOutcome.ALLOWED,
                    now,
                    None,
                    "user",
                    str(signed_in.user.id),
                    {},
                )
            )
