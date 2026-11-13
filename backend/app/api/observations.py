import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_CURSOR_CHARS,
    MAX_PAGE_SIZE,
    cursor_instant,
    cursor_integer,
    decode_cursor,
    encode_cursor,
    encode_instant,
)
from app.api.simulations import simulation_service
from app.api.windows import WindowParams, window_of
from app.core.observation import LogSeverity, ObservationSource, Quality
from app.ingestion.domain.catalog import MetricKind
from app.ingestion.domain.logs import LogPosition, LogQuery, StoredLog
from app.ingestion.domain.series import (
    MAX_POINTS,
    Series,
    SeriesMode,
    SeriesQuery,
)
from app.ingestion.service import MetricCatalogService, ObservationQueryService
from app.simulation.service import SimulationService

router = APIRouter(prefix="/api/v1", tags=["observations"])

DEFAULT_MAX_POINTS = 500
METRIC_NAME_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
Simulation = Literal["simulation"]


class MetricDefinitionOut(BaseModel):
    metric_name: str
    unit: str
    description: str
    min_value: float
    max_value: float
    kind: MetricKind


class MetricCatalogOut(BaseModel):
    items: list[MetricDefinitionOut]


class SamplePointOut(BaseModel):
    sample_id: int = Field(description="Stored sample, citable as evidence.")
    observed_at: datetime
    value: float
    quality: Quality
    source: ObservationSource
    scenario_run_id: uuid.UUID | None


class BucketOut(BaseModel):
    bucket_start: datetime
    min: float
    avg: float
    max: float
    count: int
    worst_quality: Quality
    source: ObservationSource


class GapOut(BaseModel):
    start: datetime
    end: datetime


class MetricSeriesOut(BaseModel):
    environment: Simulation = "simulation"
    component_id: uuid.UUID
    component_key: str
    metric_name: str
    unit: str
    window_start: datetime
    window_end: datetime
    mode: SeriesMode = Field(description="raw samples, or min/avg/max buckets of bucket_s.")
    bucket_s: int | None
    points: list[SamplePointOut] = Field(description="Raw samples, ascending (mode raw).")
    buckets: list[BucketOut] = Field(description="Aggregates, ascending (mode aggregated).")
    gaps: list[GapOut] = Field(
        description="Intervals without data; the series is never interpolated across them."
    )


class LogOut(BaseModel):
    id: int
    component_id: uuid.UUID
    component_key: str
    severity: LogSeverity
    message: str
    fingerprint: str = Field(description="Groups occurrences of the same message template.")
    attributes: dict[str, Any]
    observed_at: datetime
    received_at: datetime
    source: ObservationSource
    scenario_run_id: uuid.UUID | None


class LogPageOut(BaseModel):
    environment: Simulation = "simulation"
    items: list[LogOut]
    next_cursor: str | None


def observation_service(request: Request) -> ObservationQueryService:
    service: ObservationQueryService = request.app.state.observations
    return service


def catalog_service(request: Request) -> MetricCatalogService:
    service: MetricCatalogService = request.app.state.metric_catalog
    return service


def platform_now(
    simulation: Annotated[SimulationService, Depends(simulation_service)],
) -> datetime:
    return simulation.clock().platform_time


Observations = Annotated[ObservationQueryService, Depends(observation_service)]
PlatformNow = Annotated[datetime, Depends(platform_now)]


class SeriesParams(WindowParams):
    component_id: uuid.UUID
    metric_name: str = Field(pattern=METRIC_NAME_PATTERN)
    max_points: int = Field(default=DEFAULT_MAX_POINTS, ge=1, le=MAX_POINTS)


class LogParams(WindowParams):
    component_id: uuid.UUID | None = None
    min_severity: LogSeverity | None = Field(
        default=None, description="Keeps this severity and above."
    )
    cursor: str | None = Field(default=None, max_length=MAX_CURSOR_CHARS)
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


@router.get("/metrics/catalog", summary="Metric catalog: units and accepted ranges.")
def metric_catalog(
    service: Annotated[MetricCatalogService, Depends(catalog_service)],
) -> MetricCatalogOut:
    return MetricCatalogOut(
        items=[
            MetricDefinitionOut(
                metric_name=d.metric_name,
                unit=d.unit,
                description=d.description,
                min_value=d.min_value,
                max_value=d.max_value,
                kind=d.kind,
            )
            for d in service.definitions()
        ]
    )


@router.get(
    "/metrics",
    summary="One metric series of a component; downsampled server-side, gaps kept as gaps.",
)
def metric_series(
    service: Observations, now: PlatformNow, params: Annotated[SeriesParams, Query()]
) -> MetricSeriesOut:
    query = SeriesQuery(
        params.component_id, params.metric_name, window_of(params, now), params.max_points
    )
    return _series_out(service.series(query, now))


@router.get("/logs", summary="Logs, newest first, filtered by component, severity and period.")
def list_logs(
    service: Observations, now: PlatformNow, params: Annotated[LogParams, Query()]
) -> LogPageOut:
    before = None if params.cursor is None else decode_log_cursor(params.cursor)
    query = LogQuery(
        window_of(params, now), params.component_id, params.min_severity, before, params.limit + 1
    )
    logs = service.logs(query)
    page, more = logs[: params.limit], len(logs) > params.limit
    return LogPageOut(
        items=[_log_out(e, service.component_key(e.component_id)) for e in page],
        next_cursor=encode_log_cursor(page[-1].position) if more else None,
    )


def encode_log_cursor(position: LogPosition) -> str:
    return encode_cursor("log", encode_instant(position.observed_at), str(position.id))


def decode_log_cursor(cursor: str) -> LogPosition:
    at, identifier = decode_cursor("log", cursor, 2)
    return LogPosition(cursor_instant(at), cursor_integer(identifier, minimum=1))


def _series_out(series: Series) -> MetricSeriesOut:
    query = series.query
    return MetricSeriesOut(
        component_id=query.component_id,
        component_key=series.component_key,
        metric_name=query.metric_name,
        unit=series.unit,
        window_start=query.window.start,
        window_end=query.window.end,
        mode=series.mode,
        bucket_s=series.bucket_s,
        points=[
            SamplePointOut(
                sample_id=p.sample_id,
                observed_at=p.observed_at,
                value=p.value,
                quality=p.quality,
                source=p.source,
                scenario_run_id=p.scenario_run_id,
            )
            for p in series.raw
        ],
        buckets=[
            BucketOut(
                bucket_start=b.bucket_start,
                min=b.minimum,
                avg=b.average,
                max=b.maximum,
                count=b.count,
                worst_quality=b.worst_quality,
                source=b.source,
            )
            for b in series.buckets
        ],
        gaps=[GapOut(start=g.start, end=g.end) for g in series.gaps],
    )


def _log_out(log: StoredLog, component_key: str) -> LogOut:
    return LogOut(
        id=log.id,
        component_id=log.component_id,
        component_key=component_key,
        severity=log.severity,
        message=log.message,
        fingerprint=log.fingerprint,
        attributes=dict(log.attributes),
        observed_at=log.observed_at,
        received_at=log.received_at,
        source=log.source,
        scenario_run_id=log.scenario_run_id,
    )
