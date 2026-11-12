"""Domain error base, free of web-framework imports so domain modules can raise it (A-03)."""

from http import HTTPStatus


class IphiError(Exception):
    """Subclasses fix `status` and `code`; `app.core.errors` maps them once to RFC 9457."""

    status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail
