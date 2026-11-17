from http import HTTPStatus

from app.core.exceptions import IphiError


class DiagnosisBusyError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "DIAGNOSIS_IN_PROGRESS"


class DiagnosisRateError(IphiError):
    status = HTTPStatus.TOO_MANY_REQUESTS
    code = "DIAGNOSIS_RATE_LIMITED"


class DiagnosisKeyConflictError(IphiError):
    status = HTTPStatus.CONFLICT
    code = "DIAGNOSIS_KEY_CONFLICT"
