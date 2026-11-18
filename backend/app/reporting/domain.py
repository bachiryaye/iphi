from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from http import HTTPStatus
from typing import Protocol

from app.core.exceptions import IphiError
from app.diagnostics.domain.model import StoredDiagnostic
from app.incidents.domain.records import IncidentSnapshot
from app.topology.domain import PlatformTopology


class ReportFormat(StrEnum):
    PDF = "pdf"
    CSV = "csv"


class ReportTooLargeError(IphiError):
    status = HTTPStatus.CONTENT_TOO_LARGE
    code = "REPORT_TOO_LARGE"


class ReportBusyError(IphiError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "REPORT_BUSY"


class ReportRenderError(IphiError):
    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "REPORT_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ReportSnapshot:
    facts: IncidentSnapshot
    diagnostics: tuple[StoredDiagnostic, ...]
    topology: PlatformTopology
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class ReportFile:
    content: bytes
    media_type: str
    filename: str


class ReportRenderer(Protocol):
    def pdf(self, snapshot: ReportSnapshot) -> bytes: ...
