from http import HTTPStatus

from app.core.exceptions import IphiError


class MetricNotFoundError(IphiError):
    status = HTTPStatus.NOT_FOUND
    code = "METRIC_NOT_FOUND"


class PlatformNotSeededError(IphiError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "PLATFORM_NOT_SEEDED"
