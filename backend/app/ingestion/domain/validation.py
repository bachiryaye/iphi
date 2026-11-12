"""Validation of connector output before persistence (ADR 0003, architecture §03.1).

Pure: the caller supplies the platform time, the component index and the metric catalog.
Every rejected observation carries a stable code so rejections can be counted and shown.
"""

import hashlib
import json
import math
import re
import uuid
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.connectors.domain import CollectionResult, ObservedLog, ObservedSample
from app.core.observation import LogSeverity, Quality
from app.ingestion.domain.catalog import MetricDefinition

MAX_LOG_MESSAGE_CHARS = 2000
MAX_LOG_ATTRIBUTES_BYTES = 8 * 1024
# Variable parts of a message (numbers, hexadecimal identifiers) do not change its template.
_VARIABLE_TOKEN = re.compile(r"0x[0-9a-fA-F]+|\b[0-9a-fA-F]{8,}\b|\d+(?:\.\d+)?")


class RejectionCode(StrEnum):
    UNKNOWN_COMPONENT = "UNKNOWN_COMPONENT"
    UNKNOWN_METRIC = "UNKNOWN_METRIC"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    VALUE_NOT_FINITE = "VALUE_NOT_FINITE"
    METRIC_OUT_OF_RANGE = "METRIC_OUT_OF_RANGE"
    TIMESTAMP_NOT_AWARE = "TIMESTAMP_NOT_AWARE"
    OBSERVATION_IN_FUTURE = "OBSERVATION_IN_FUTURE"
    OBSERVATION_TOO_LATE = "OBSERVATION_TOO_LATE"
    LOG_MESSAGE_INVALID = "LOG_MESSAGE_INVALID"
    LOG_MESSAGE_TOO_LONG = "LOG_MESSAGE_TOO_LONG"
    LOG_ATTRIBUTES_INVALID = "LOG_ATTRIBUTES_INVALID"
    LOG_ATTRIBUTES_TOO_LARGE = "LOG_ATTRIBUTES_TOO_LARGE"


@dataclass(frozen=True, slots=True)
class IngestionPolicy:
    """Time tolerances relative to platform time (ADR 0003)."""

    future_tolerance: timedelta = timedelta(seconds=30)
    late_tolerance: timedelta = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class AcceptedSample:
    component_id: uuid.UUID
    metric_name: str
    value: float
    unit: str
    quality: Quality
    observed_at: datetime
    scenario_run_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class AcceptedLog:
    component_id: uuid.UUID
    severity: LogSeverity
    message: str
    fingerprint: str
    dedup_key: str
    attributes: Mapping[str, str | int | float | bool]
    observed_at: datetime
    scenario_run_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class Rejection:
    code: RejectionCode
    component_key: str
    subject: str


@dataclass(frozen=True, slots=True)
class ValidatedBatch:
    """`received_at`: platform time of validation, stored as the observations' reception time."""

    received_at: datetime
    samples: tuple[AcceptedSample, ...]
    logs: tuple[AcceptedLog, ...]
    rejections: tuple[Rejection, ...]

    def rejection_counts(self) -> dict[str, int]:
        return dict(sorted(Counter(r.code.value for r in self.rejections).items()))


@dataclass(frozen=True, slots=True)
class ValidationContext:
    now: datetime
    components: Mapping[str, uuid.UUID]
    catalog: Mapping[str, MetricDefinition]
    policy: IngestionPolicy


def validate(result: CollectionResult, context: ValidationContext) -> ValidatedBatch:
    samples: list[AcceptedSample] = []
    logs: list[AcceptedLog] = []
    rejections: list[Rejection] = []
    for sample in result.samples:
        match _validate_sample(sample, context):
            case AcceptedSample() as accepted_sample:
                samples.append(accepted_sample)
            case Rejection() as rejection:
                rejections.append(rejection)
    for log in result.logs:
        match _validate_log(log, context):
            case AcceptedLog() as accepted_log:
                logs.append(accepted_log)
            case Rejection() as rejection:
                rejections.append(rejection)
    return ValidatedBatch(context.now, tuple(samples), tuple(logs), tuple(rejections))


def _validate_sample(
    sample: ObservedSample, context: ValidationContext
) -> AcceptedSample | Rejection:
    issue = _sample_issue(sample, context)
    if issue is not None:
        return Rejection(issue, sample.component_key, sample.metric_name)
    return AcceptedSample(
        context.components[sample.component_key],
        sample.metric_name,
        float(sample.value),
        sample.unit,
        sample.quality,
        sample.observed_at.astimezone(UTC),
        sample.scenario_run_id,
    )


def _sample_issue(sample: ObservedSample, context: ValidationContext) -> RejectionCode | None:
    definition = context.catalog.get(sample.metric_name)
    if sample.component_key not in context.components:
        return RejectionCode.UNKNOWN_COMPONENT
    if definition is None:
        return RejectionCode.UNKNOWN_METRIC
    if sample.unit != definition.unit:
        return RejectionCode.UNIT_MISMATCH
    if not math.isfinite(sample.value):
        return RejectionCode.VALUE_NOT_FINITE
    if not definition.admits(sample.value):
        return RejectionCode.METRIC_OUT_OF_RANGE
    return _timing_issue(sample.observed_at, context)


def _validate_log(log: ObservedLog, context: ValidationContext) -> AcceptedLog | Rejection:
    issue = _log_issue(log, context)
    if issue is not None:
        return Rejection(issue, log.component_key, log.severity.value)
    attributes = canonical_json(log.attributes)
    return AcceptedLog(
        context.components[log.component_key],
        log.severity,
        log.message,
        log_fingerprint(log.severity, log.message),
        _digest(canonical_json([log.severity.value, log.message, attributes]), 16),
        dict(log.attributes),
        log.observed_at.astimezone(UTC),
        log.scenario_run_id,
    )


def _log_issue(log: ObservedLog, context: ValidationContext) -> RejectionCode | None:
    if log.component_key not in context.components:
        return RejectionCode.UNKNOWN_COMPONENT
    # PostgreSQL text and jsonb cannot hold NUL characters.
    if not log.message.strip() or "\x00" in log.message:
        return RejectionCode.LOG_MESSAGE_INVALID
    if len(log.message) > MAX_LOG_MESSAGE_CHARS:
        return RejectionCode.LOG_MESSAGE_TOO_LONG
    return _attributes_issue(log.attributes) or _timing_issue(log.observed_at, context)


def _attributes_issue(attributes: Mapping[str, object]) -> RejectionCode | None:
    try:
        rendered = canonical_json(attributes)
    except ValueError:
        return RejectionCode.LOG_ATTRIBUTES_INVALID
    if "\\u0000" in rendered:
        return RejectionCode.LOG_ATTRIBUTES_INVALID
    if len(rendered.encode()) > MAX_LOG_ATTRIBUTES_BYTES:
        return RejectionCode.LOG_ATTRIBUTES_TOO_LARGE
    return None


def _timing_issue(observed_at: datetime, context: ValidationContext) -> RejectionCode | None:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        return RejectionCode.TIMESTAMP_NOT_AWARE
    if observed_at > context.now + context.policy.future_tolerance:
        return RejectionCode.OBSERVATION_IN_FUTURE
    if observed_at < context.now - context.policy.late_tolerance:
        return RejectionCode.OBSERVATION_TOO_LATE
    return None


def log_fingerprint(severity: LogSeverity, message: str) -> str:
    """Groups occurrences of one message template, whatever their variable parts."""
    return _digest(f"{severity.value}|{_VARIABLE_TOKEN.sub('#', message)}", 8)


def canonical_json(value: object) -> str:
    """Raises ValueError for non-finite numbers or values JSON cannot represent."""
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc


def _digest(material: str, size: int) -> str:
    return hashlib.blake2b(material.encode(), digest_size=size).hexdigest()
