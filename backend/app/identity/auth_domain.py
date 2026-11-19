import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus

from app.core.exceptions import IphiError


class Role(StrEnum):
    VIEWER = "viewer"
    ENGINEER = "engineer"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class User:
    id: uuid.UUID
    username: str
    display_name: str
    role: Role

    def permits(self, required: Role) -> bool:
        return self.role is Role.ADMIN or self.role is required or required is Role.VIEWER


@dataclass(frozen=True, slots=True)
class SignedIn:
    user: User
    token: str = field(repr=False)
    expires_at: datetime


class AuthenticationRequiredError(IphiError):
    status = HTTPStatus.UNAUTHORIZED
    code = "AUTHENTICATION_REQUIRED"


class InvalidCredentialsError(IphiError):
    status = HTTPStatus.UNAUTHORIZED
    code = "INVALID_CREDENTIALS"


class PermissionDeniedError(IphiError):
    status = HTTPStatus.FORBIDDEN
    code = "PERMISSION_DENIED"


class CsrfRejectedError(IphiError):
    status = HTTPStatus.FORBIDDEN
    code = "CSRF_REJECTED"


class LoginLimitedError(IphiError):
    status = HTTPStatus.TOO_MANY_REQUESTS
    code = "LOGIN_RATE_LIMITED"
