"""Opaque keyset cursors (architecture §04.2): `kind:part:part`, URL-safe base64."""

import base64
import binascii
import re
from datetime import datetime, timedelta
from http import HTTPStatus

from app.core.exceptions import IphiError
from app.core.observation import UNIX_EPOCH

MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
MAX_CURSOR_CHARS = 128
# PostgreSQL BIGINT bounds; ASCII digits only (str.isdigit also accepts "²").
_INTEGER = re.compile(r"-?[0-9]{1,19}")
_BIGINT_MAX = 2**63 - 1
_MICROSECOND = timedelta(microseconds=1)


class InvalidCursorError(IphiError):
    status = HTTPStatus.UNPROCESSABLE_CONTENT
    code = "INVALID_CURSOR"


def encode_cursor(kind: str, *parts: str) -> str:
    return base64.urlsafe_b64encode(":".join((kind, *parts)).encode()).decode().rstrip("=")


def decode_cursor(kind: str, cursor: str, size: int) -> list[str]:
    """The `size` parts of a cursor of `kind`; raises InvalidCursorError otherwise."""
    try:
        decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise malformed_cursor() from exc
    prefix, *parts = decoded.split(":", size)
    if prefix != kind or len(parts) != size:
        raise malformed_cursor()
    return parts


def cursor_integer(value: str, minimum: int = -_BIGINT_MAX) -> int:
    """A cursor part as an integer within [minimum, BIGINT max]; InvalidCursorError otherwise."""
    if not _INTEGER.fullmatch(value):
        raise malformed_cursor()
    number = int(value)
    if not minimum <= number <= _BIGINT_MAX:
        raise malformed_cursor()
    return number


def encode_instant(at: datetime) -> str:
    """Integer microseconds since the epoch: exact, and free of the ':' separating parts."""
    return str((at - UNIX_EPOCH) // _MICROSECOND)


def cursor_instant(value: str) -> datetime:
    try:
        return UNIX_EPOCH + cursor_integer(value) * _MICROSECOND
    except OverflowError as exc:
        raise malformed_cursor() from exc


def malformed_cursor() -> InvalidCursorError:
    return InvalidCursorError("The cursor is malformed; restart from the first page.")
