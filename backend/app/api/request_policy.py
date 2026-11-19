"""Same-origin JSON mutation boundary shared by login and authenticated actions."""

from http import HTTPStatus

from fastapi import Request

from app.core.exceptions import IphiError


class CrossSiteRequestError(IphiError):
    status = HTTPStatus.FORBIDDEN
    code = "CROSS_SITE_REQUEST"


class JsonRequiredError(IphiError):
    status = HTTPStatus.UNSUPPORTED_MEDIA_TYPE
    code = "JSON_REQUIRED"


def browser_forgery(request: Request) -> IphiError | None:
    """Refuses requests another web page could forge on mutation endpoints.

    A JSON content type is not a CORS "simple" request: browsers preflight it, and the API
    answers no preflight, so a foreign page cannot send it. Sec-Fetch-Site rejects the rest.
    """
    if request.headers.get("sec-fetch-site", "same-origin") not in {"same-origin", "none"}:
        return CrossSiteRequestError("Mutations are accepted from the IPHI interface only.")
    media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media_type != "application/json":
        return JsonRequiredError("Mutations require Content-Type: application/json.")
    return None
