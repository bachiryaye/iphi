import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.core.observation import ObservationSource
from app.ingestion.domain.collection import CollectionRun, CollectionStatus
from app.monitor.domain import (
    CheckName,
    CheckStatus,
    CollectionState,
    ProcessStatus,
    ReadinessReport,
)
from app.monitor.service import ReadinessService, SystemStatus, SystemStatusService
from app.simulation.domain.clock import ClockMode

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


class ClockStatusOut(BaseModel):
    mode: ClockMode
    speed: float
    platform_time: datetime


class HeartbeatOut(BaseModel):
    last_cycle_at: datetime
    last_cycle_duration_ms: int
    cycle_lag_ms: int
    status: ProcessStatus


class WorkerStatusOut(BaseModel):
    status: CheckStatus
    detail: str
    heartbeat: HeartbeatOut | None


class CollectionRunOut(BaseModel):
    id: uuid.UUID
    connector_key: str
    source: ObservationSource
    started_at: datetime
    finished_at: datetime
    status: CollectionStatus
    sample_count: int
    log_count: int
    rejected_count: int
    duplicate_count: int
    rejections: dict[str, int] = Field(description="Rejected observations per rejection code.")
    watermark: datetime | None = Field(
        description="Event time up to which the source has been fully read."
    )
    error_code: str | None
    error_message: str | None

    @classmethod
    def of(cls, run: CollectionRun) -> CollectionRunOut:
        return cls(
            id=run.id,
            connector_key=run.connector_key,
            source=run.source,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status,
            sample_count=run.sample_count,
            log_count=run.log_count,
            rejected_count=run.rejected_count,
            duplicate_count=run.duplicate_count,
            rejections=dict(run.rejections),
            watermark=run.watermark,
            error_code=run.error_code,
            error_message=run.error_message,
        )


class ConnectorStatusOut(BaseModel):
    connector_key: str
    state: CollectionState
    detail: str
    last_run: CollectionRunOut | None
    last_success_at: datetime | None


class CollectionStatusOut(BaseModel):
    state: CollectionState = Field(description="Worst state among enabled connectors.")
    connectors: list[ConnectorStatusOut]
    recent_runs: list[CollectionRunOut] = Field(description="Latest collection runs, newest first.")


class AiProviderStatusOut(BaseModel):
    status: CheckStatus
    detail: str


class SystemStatusOut(BaseModel):
    environment: Literal["simulation"] = "simulation"
    checked_at: datetime
    cycle_interval_s: float
    clock: ClockStatusOut
    worker: WorkerStatusOut
    collection: CollectionStatusOut
    ai_provider: AiProviderStatusOut

    @classmethod
    def of(cls, status: SystemStatus) -> SystemStatusOut:
        heartbeat = status.heartbeat
        return cls(
            checked_at=status.checked_at,
            cycle_interval_s=status.cycle_interval_s,
            clock=ClockStatusOut(
                mode=status.clock.state.mode,
                speed=status.clock.state.speed,
                platform_time=status.clock.platform_time,
            ),
            worker=WorkerStatusOut(
                status=status.worker.status,
                detail=status.worker.detail,
                heartbeat=None
                if heartbeat is None
                else HeartbeatOut(
                    last_cycle_at=heartbeat.last_cycle_at,
                    last_cycle_duration_ms=heartbeat.last_cycle_duration_ms,
                    cycle_lag_ms=heartbeat.cycle_lag_ms,
                    status=heartbeat.status,
                ),
            ),
            collection=CollectionStatusOut(
                state=status.collection,
                connectors=[
                    ConnectorStatusOut(
                        connector_key=c.connector_key,
                        state=c.assessment.state,
                        detail=c.assessment.detail,
                        last_run=None if c.last_run is None else CollectionRunOut.of(c.last_run),
                        last_success_at=c.last_success_at,
                    )
                    for c in status.connectors
                ],
                recent_runs=[CollectionRunOut.of(r) for r in status.recent_runs],
            ),
            ai_provider=AiProviderStatusOut(
                status=status.ai_provider.status, detail=status.ai_provider.detail
            ),
        )


def system_status_service(request: Request) -> SystemStatusService:
    service: SystemStatusService = request.app.state.system_status
    return service


@router.get(
    "/api/v1/system/status",
    summary="Monitor observability: clock, worker cycle, collection runs, AI provider.",
)
def system_status(
    service: Annotated[SystemStatusService, Depends(system_status_service)],
) -> SystemStatusOut:
    return SystemStatusOut.of(service.status())
