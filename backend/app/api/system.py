from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.monitor.domain import CheckName, CheckStatus, ReadinessReport
from app.monitor.service import ReadinessService

router = APIRouter(tags=["system"])


class LivenessOut(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessCheckOut(BaseModel):
    name: CheckName
    status: CheckStatus
    detail: str
    observed_at: datetime | None = Field(description="Time of the evidence the check relies on.")


class ReadinessOut(BaseModel):
    status: Literal["ready", "not_ready"]
    checked_at: datetime
    cycle_interval_s: float
    checks: list[ReadinessCheckOut]

    @classmethod
    def from_report(cls, report: ReadinessReport) -> ReadinessOut:
        return cls(
            status="ready" if report.ready else "not_ready",
            checked_at=report.checked_at,
            cycle_interval_s=report.cycle_interval_s,
            checks=[
                ReadinessCheckOut(
                    name=c.name, status=c.status, detail=c.detail, observed_at=c.observed_at
                )
                for c in report.checks
            ],
        )


def readiness_service(request: Request) -> ReadinessService:
    service: ReadinessService = request.app.state.readiness
    return service


@router.get("/health", summary="Liveness: the API process answers.")
def health() -> LivenessOut:
    return LivenessOut()


@router.get(
    "/ready",
    summary="Readiness: database, migrations, worker heartbeat and AI provider status.",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessOut}},
)
def ready(
    response: Response, service: Annotated[ReadinessService, Depends(readiness_service)]
) -> ReadinessOut:
    report = service.check()
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessOut.from_report(report)
