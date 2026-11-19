import uuid
from collections.abc import Iterator
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    TypeAdapter,
    field_validator,
)

from app.connectors.domain import CollectionResult, ConnectorIssue, ObservedLog, ObservedSample
from app.core.observation import LogSeverity, Quality, tick_of, tick_time

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_ROWS = 100
MAX_PACKETS = 256
MAX_SAMPLES = 6000
MAX_LOGS = 2000
MAX_REQUEST_QUEUE = 4
KEY = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-z0-9_-]+$")]


class Envelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    version: Literal[1] = 1
    environment: Literal["simulation"] = "simulation"
    source: Literal["mqtt"] = "mqtt"
    request_id: uuid.UUID
    baseline_id: uuid.UUID

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value: object) -> object:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("MQTT version must be an integer")
        return value


class CollectRequest(Envelope):
    now: AwareDatetime
    resume_after: AwareDatetime | None
    not_before: AwareDatetime


class MetricRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    metric_name: KEY
    value: Annotated[FiniteFloat, Field(strict=True)]
    unit: str = Field(max_length=20)
    quality: Quality
    observed_at: AwareDatetime
    scenario_run_id: uuid.UUID


class LogRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    severity: LogSeverity
    message: str = Field(min_length=1, max_length=2000, pattern=r"^[^\x00]*$")
    attributes: dict[str, str | int | float | bool] = Field(max_length=32)
    observed_at: AwareDatetime
    scenario_run_id: uuid.UUID


class DataEnvelope(Envelope):
    sequence: int = Field(ge=0, lt=MAX_PACKETS, strict=True)
    component: KEY


class MetricsPacket(DataEnvelope):
    kind: Literal["metrics"] = "metrics"
    rows: list[MetricRow] = Field(min_length=1, max_length=MAX_ROWS)


class LogsPacket(DataEnvelope):
    kind: Literal["logs"] = "logs"
    rows: list[LogRow] = Field(min_length=1, max_length=MAX_ROWS)


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal["SAMPLE_SLOTS_SKIPPED"]
    message: str = Field(max_length=300)


class Completion(Envelope):
    kind: Literal["complete"] = "complete"
    packets: int = Field(ge=0, le=MAX_PACKETS, strict=True)
    samples: int = Field(ge=0, le=MAX_SAMPLES, strict=True)
    logs: int = Field(ge=0, le=MAX_LOGS, strict=True)
    watermark: AwareDatetime
    issues: list[Issue] = Field(default_factory=list, max_length=2)


Packet = MetricsPacket | LogsPacket | Completion
PACKET_ADAPTER = TypeAdapter(Annotated[Packet, Field(discriminator="kind")])


def require_labels(envelope: Envelope) -> None:
    if not {"version", "environment", "source"}.issubset(envelope.model_fields_set):
        raise ValueError("MQTT messages require explicit version, environment and source")


def encode(packet: BaseModel) -> bytes:
    payload = packet.model_dump_json().encode()
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("MQTT payload exceeds 64 KiB")
    return payload


def packets(result: CollectionResult, request: CollectRequest) -> Iterator[Packet]:
    metadata = {"request_id": request.request_id, "baseline_id": request.baseline_id}
    sequence = 0
    for component in sorted({s.component_key for s in result.samples}):
        samples = [s for s in result.samples if s.component_key == component]
        for start in range(0, len(samples), MAX_ROWS):
            yield MetricsPacket(
                **metadata,
                sequence=sequence,
                component=component,
                rows=[
                    MetricRow(
                        metric_name=s.metric_name,
                        value=s.value,
                        unit=s.unit,
                        quality=s.quality,
                        observed_at=s.observed_at,
                        scenario_run_id=_run_id(s.scenario_run_id),
                    )
                    for s in samples[start : start + MAX_ROWS]
                ],
            )
            sequence += 1
    for component in sorted({s.component_key for s in result.logs}):
        logs = [s for s in result.logs if s.component_key == component]
        for start in range(0, len(logs), MAX_ROWS):
            yield LogsPacket(
                **metadata,
                sequence=sequence,
                component=component,
                rows=[
                    LogRow(
                        severity=s.severity,
                        message=s.message,
                        attributes=dict(s.attributes),
                        observed_at=s.observed_at,
                        scenario_run_id=_run_id(s.scenario_run_id),
                    )
                    for s in logs[start : start + MAX_ROWS]
                ],
            )
            sequence += 1
    yield Completion(
        **metadata,
        packets=sequence,
        samples=len(result.samples),
        logs=len(result.logs),
        watermark=result.watermark or tick_time(tick_of(request.now)),
        issues=[Issue(code=i.code, message=i.message) for i in result.issues],
    )


def observations(packet: MetricsPacket | LogsPacket) -> CollectionResult:
    if isinstance(packet, MetricsPacket):
        return CollectionResult(
            samples=tuple(
                ObservedSample(
                    packet.component,
                    s.metric_name,
                    s.value,
                    s.unit,
                    s.quality,
                    s.observed_at,
                    s.scenario_run_id,
                )
                for s in packet.rows
            )
        )
    return CollectionResult(
        logs=tuple(
            ObservedLog(
                packet.component,
                s.severity,
                s.message,
                s.attributes,
                s.observed_at,
                s.scenario_run_id,
            )
            for s in packet.rows
        )
    )


def issues(completion: Completion) -> tuple[ConnectorIssue, ...]:
    return tuple(ConnectorIssue(i.code, i.message) for i in completion.issues)


def _run_id(value: uuid.UUID | None) -> uuid.UUID:
    if value is None:
        raise ValueError("Simulated MQTT observations require scenario attribution")
    return value
